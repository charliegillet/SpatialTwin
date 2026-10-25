"""Managed-agent team routes for any accepted venue (exact JSON in docs/plans/contracts/agent-team.md).

POST /api/venues/{venue_id}/investigate                     -> {investigation_id, deadline_at, lanes, trace_url}
GET  /api/venues/{venue_id}/investigations/{id}             -> progress + (team) result
POST /api/venues/{venue_id}/investigations/{id}/cancel
GET  /api/venues/{venue_id}/investigations/{id}/trace       -> SSE, Last-Event-ID replay, ": ping" every 10 s
POST /api/venues/{venue_id}/investigations/{id}/followup    -> {investigation_id, parent_investigation_id, ...}

Without ``lanes`` an investigation runs the Strategist lane only, exactly as the existing panel expects; the agent
team asks for ``["strategist", "robustness"]``. The top-level ``status``/``investigation`` follow the first lane, so
the existing panel finishes when the Strategist does; ``team_status`` and ``lanes`` describe the whole team.
Investigations are scoped to their venue: another venue's path answers 404. The tools the agents can call are
read-only views of the local door planner; no hardware is involved.
"""
from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.managed.door_agent import (
    FOLLOWUP_DEADLINE_SECONDS, FOLLOWUP_MAX_DEADLINE_SECONDS, LANES, ROBUSTNESS_DEADLINE_SECONDS,
    ROBUSTNESS_MAX_DEADLINE_SECONDS, STRATEGIST_DEADLINE_SECONDS, STRATEGIST_MAX_DEADLINE_SECONDS, DoorAgentResult,
    DoorAgentRunner, compose_team, deadline_stamp, lane_deadline, lane_id,
)
from backend.app.ai.managed.ledger import TRACE_PHASE
from backend.app.ai.managed.scenarios import ScenarioError, parse_scenario
from backend.app.ai.managed.trace import PING_SECONDS, TraceHub
from backend.app.hazard.door_planner import DoorPlanError, resolve_request
from backend.app.venues.camera import CAMERA_STORE
from backend.app.venues.model import get_venue
from backend.app.venues.schemas import DoorPlanRequest

MAX_DEADLINE_SECONDS = STRATEGIST_MAX_DEADLINE_SECONDS  # legacy import name
TEAM_STARTED = "team_started"
SUPERSEDE_WAIT_SECONDS = 5.0
MAX_METAS = 256


class DoorInvestigationRequest(DoorPlanRequest):
    mode: Literal["live", "local"] = "local"
    deadline_seconds: float = Field(default=STRATEGIST_DEADLINE_SECONDS, gt=0, le=STRATEGIST_MAX_DEADLINE_SECONDS)
    lanes: Optional[List[Literal["strategist", "robustness"]]] = Field(default=None, min_length=1, max_length=2)
    robustness_deadline_seconds: float = Field(default=ROBUSTNESS_DEADLINE_SECONDS, gt=0,
                                               le=ROBUSTNESS_MAX_DEADLINE_SECONDS)
    supersede: bool = True


class FollowupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str = Field(min_length=1, max_length=120)
    mode: Literal["live", "local"] = "local"
    deadline_seconds: float = Field(default=FOLLOWUP_DEADLINE_SECONDS, gt=0, le=FOLLOWUP_MAX_DEADLINE_SECONDS)


def build_door_agent_router(adapter: ManagedAgentAdapter, slots: asyncio.Semaphore,
                            fixtures_enabled: Callable[[], bool], *, runner: Optional[DoorAgentRunner] = None,
                            trace_hub: Optional[TraceHub] = None, team_slots: Optional[asyncio.Semaphore] = None,
                            ping_seconds: float = PING_SECONDS) -> APIRouter:
    router = APIRouter(prefix="/api/venues")
    ledger = adapter.ledger
    hub = trace_hub or TraceHub(
        durable=lambda investigation_id, elapsed, record: ledger.event(investigation_id, elapsed, TRACE_PHASE, record),
        loader=ledger.trace_events)
    runner = runner or DoorAgentRunner(adapter, trace=hub)
    if runner.trace is None:
        runner.trace = hub
    # One live two-lane team at a time (each team also holds one shared provider slot).
    team_slots = team_slots or asyncio.Semaphore(1)
    active: Dict[str, asyncio.Task] = {}
    team_task: Dict[str, Optional[str]] = {"id": None}
    unsaved: Dict[str, Any] = {}  # terminal results the ledger could not persist (bounded, in memory)
    metas: "OrderedDict[str, dict]" = OrderedDict()

    def venue_or_404(venue_id: str):
        venue = get_venue(venue_id)
        if venue is None:
            raise HTTPException(404, detail={"code": "unknown_venue"})
        return venue

    async def team_meta(investigation_id: str) -> Optional[dict]:
        if investigation_id in metas:
            return metas[investigation_id]
        try:
            rows = await asyncio.to_thread(ledger.events, investigation_id, 1, phases=(TEAM_STARTED,),
                                           exclude_phases=())
        except Exception:
            return None
        if not rows:
            return None
        meta = {k: v for k, v in rows[-1].items() if k not in ("phase", "elapsed_ms")}
        remember(investigation_id, meta)
        return meta

    def remember(investigation_id: str, meta: dict) -> None:
        metas[investigation_id] = meta
        while len(metas) > MAX_METAS:
            metas.popitem(last=False)

    async def scoped(venue_id: str, investigation_id: str) -> tuple:
        """(meta, saved result) for a run of this venue; 404 when unknown or owned by another venue."""
        meta = await team_meta(investigation_id)
        saved = await runner.get_saved_result(investigation_id) or unsaved.get(investigation_id)
        owner = (meta or {}).get("venue_id") or (saved.venue_id if saved is not None else None)
        if owner is None and investigation_id not in active:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        if owner is not None and owner != venue_id:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        return meta, saved

    def validate_hazards(venue, venue_id: str, request: DoorPlanRequest) -> DoorPlanRequest:
        for hazard in request.hazards:
            if hazard.source == "camera":
                code = CAMERA_STORE.verify_camera_hazard(venue_id, hazard)
                if code is not None:
                    raise HTTPException(422, detail={"code": code})
        plan_request = DoorPlanRequest(hazards=request.hazards, horizon_seconds=request.horizon_seconds)
        try:
            resolve_request(venue, plan_request)
        except DoorPlanError as error:
            raise HTTPException(422, detail={"code": error.code}) from None
        return plan_request

    async def start(venue, plan_request: DoorPlanRequest, mode: str, lanes: List[str],
                    seconds: Dict[str, float], *, team: bool, extra: Dict[str, Any],
                    meta_extra: Dict[str, Any]) -> Dict[str, Any]:
        """Claim the slots, record the team, launch the owner task. Slots are released when the team ends."""
        holds_team = False
        if team:
            if team_slots.locked():
                previous = active.get(team_task["id"] or "")
                if not (meta_extra.get("supersede") and previous is not None):
                    raise HTTPException(429, "Too many investigations are running; try again shortly")
                if not previous.done() and not previous.cancelling():
                    previous.cancel()  # a newer hazard set supersedes the running team
                try:
                    await asyncio.wait_for(team_slots.acquire(), SUPERSEDE_WAIT_SECONDS)
                except (asyncio.TimeoutError, TimeoutError):
                    raise HTTPException(429, "Too many investigations are running; try again shortly") from None
            else:
                await team_slots.acquire()
            holds_team = True
        if slots.locked():
            if holds_team:
                team_slots.release()
            raise HTTPException(429, "Too many investigations are running; try again shortly")
        await slots.acquire()  # not locked, so this does not suspend: the check and the claim are atomic
        investigation_id = f"dinv-{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        deadlines = {lane: (seconds[lane], deadline_stamp(seconds[lane], now)) for lane in lanes}
        lane_meta = {lane: {"investigation_id": lane_id(investigation_id, lane), "deadline_seconds": value,
                            "deadline_at": stamp[0], "deadline_at_ms": stamp[1]}
                     for lane, (value, stamp) in deadlines.items()}
        team_deadline_ms = max(v["deadline_at_ms"] for v in lane_meta.values())
        meta = {"venue_id": venue.venue_id, "mode": mode, "lanes": list(lanes), "lane_deadlines": lane_meta,
                "deadline_at_ms": team_deadline_ms, "deadline_at": max(v["deadline_at"] for v in lane_meta.values()),
                "request": plan_request.model_dump(mode="json"),
                **{k: v for k, v in meta_extra.items() if k != "supersede"}}
        try:
            remember(investigation_id, meta)
            await asyncio.to_thread(ledger.event, investigation_id, 0.0, TEAM_STARTED, meta)
            hub.open(investigation_id)
            await hub.publish(investigation_id, "deadline", {"deadline_at": meta["deadline_at"],
                                                             "deadline_at_ms": team_deadline_ms, "lanes": lane_meta})
        except BaseException:
            slots.release()
            if holds_team:
                team_slots.release()
            raise

        async def owner() -> None:
            try:
                result = await runner.run_team(venue, plan_request, investigation_id, mode, list(lanes),
                                               {lane: (value, stamp[1]) for lane, (value, stamp) in deadlines.items()},
                                               **extra)
                if result is not None and await runner.get_saved_result(investigation_id) is None:
                    while len(unsaved) >= 32:
                        unsaved.pop(next(iter(unsaved)))
                    unsaved[investigation_id] = result
            finally:
                slots.release()
                if holds_team:
                    team_slots.release()
                    if team_task["id"] == investigation_id:
                        team_task["id"] = None
                active.pop(investigation_id, None)
                if not hub.closed(investigation_id):
                    await hub.publish(investigation_id, "done", {"team_status": "cancelled"})
                    await hub.close(investigation_id)

        try:
            active[investigation_id] = asyncio.create_task(owner())
            if holds_team:
                team_task["id"] = investigation_id
        except BaseException:
            slots.release()
            if holds_team:
                team_slots.release()
            raise
        return {"investigation_id": investigation_id, "deadline_at": meta["deadline_at"],
                "deadline_at_ms": team_deadline_ms, "lanes": lane_meta,
                "trace_url": f"/api/venues/{venue.venue_id}/investigations/{investigation_id}/trace"}

    @router.post("/{venue_id}/investigate")
    async def investigate(venue_id: str, request: DoorInvestigationRequest) -> Dict[str, Any]:
        venue = venue_or_404(venue_id)
        if request.mode == "local" and not fixtures_enabled():
            raise HTTPException(403, "Local demo investigations are disabled in production mode")
        # Same validation as door-plan, before any slot or provider is used.
        plan_request = validate_hazards(venue, venue_id, request)
        lanes = [lane for lane in LANES if lane in (request.lanes or ["strategist"])]
        if len(set(request.lanes or [])) != len(request.lanes or []):
            raise HTTPException(422, detail={"code": "duplicate_lane"})
        seconds = {"strategist": lane_deadline("strategist", request.deadline_seconds),
                   "robustness": lane_deadline("robustness", request.robustness_deadline_seconds)}
        team = "robustness" in lanes and request.mode == "live"
        return await start(venue, plan_request, request.mode, lanes, seconds, team=team, extra={},
                           meta_extra={"supersede": request.supersede})

    async def compose(investigation_id: str, meta: dict, saved: Optional[DoorAgentResult]) -> Optional[DoorAgentResult]:
        if saved is not None and saved.lanes:
            return saved
        lanes = meta["lanes"]
        outcomes = {}
        for lane in lanes:
            live = await runner.get_saved_result(lane_id(investigation_id, lane))
            fallback = await runner.get_saved_result(lane_id(investigation_id, lane, fallback=True))
            if live is not None:
                outcomes[lane] = (live, fallback)
        team_status = "running" if investigation_id in active else "finished"
        return compose_team(investigation_id, lanes, outcomes, team_status, running=meta.get("lane_deadlines"))

    def lanes_snapshot(meta: dict, investigation: Optional[DoorAgentResult]) -> Dict[str, Any]:
        if investigation is not None and investigation.lanes:
            return investigation.lanes
        return {lane: {"lane": lane, "status": "running", **(meta.get("lane_deadlines") or {}).get(lane, {})}
                for lane in meta.get("lanes", [])}

    @router.get("/{venue_id}/investigations/{investigation_id}")
    async def progress(venue_id: str, investigation_id: str) -> Dict[str, Any]:
        venue_or_404(venue_id)
        meta, saved = await scoped(venue_id, investigation_id)
        if meta is None:  # a run recorded before the agent team existed
            events = await runner.get_progress(investigation_id)
            return {"investigation_id": investigation_id, "status": saved.status.value if saved else "running",
                    "provider_progress": events, "investigation": saved.model_dump(mode="json") if saved else None}
        investigation = await compose(investigation_id, meta, saved)
        events = await runner.get_progress(lane_id(investigation_id, meta["lanes"][0]))
        if investigation is not None and investigation.team_status == "running" and investigation_id not in active:
            investigation = investigation.model_copy(update={"team_status": "finished"})
        return {"investigation_id": investigation_id,
                "status": investigation.status.value if investigation else "running",
                "team_status": (investigation.team_status if investigation and investigation.team_status
                                else "running" if investigation_id in active else "finished"),
                "deadline_at": meta.get("deadline_at"), "deadline_at_ms": meta.get("deadline_at_ms"),
                "lanes": lanes_snapshot(meta, investigation),
                "parent_investigation_id": meta.get("parent_investigation_id"),
                "trace_url": f"/api/venues/{venue_id}/investigations/{investigation_id}/trace",
                "provider_progress": events,
                "investigation": investigation.model_dump(mode="json") if investigation else None}

    @router.post("/{venue_id}/investigations/{investigation_id}/cancel")
    async def cancel(venue_id: str, investigation_id: str) -> Dict[str, Any]:
        venue_or_404(venue_id)
        meta, saved = await scoped(venue_id, investigation_id)
        task: Optional[asyncio.Task] = active.get(investigation_id)
        if task is not None:
            # Let a newly scheduled owner take its first turn so it can persist the cancellation.
            await asyncio.sleep(0)
            if not task.done():
                if not task.cancelling():
                    task.cancel()
                return {"status": "cancellation_requested"}
        result = saved if saved is not None or meta is None else await compose(investigation_id, meta, saved)
        if result is None:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        return {"status": "already_finished", "investigation": result.model_dump(mode="json")}

    @router.get("/{venue_id}/investigations/{investigation_id}/trace")
    async def trace(venue_id: str, investigation_id: str,
                    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
                    after: Optional[int] = Query(default=None, ge=0)) -> StreamingResponse:
        venue_or_404(venue_id)
        meta, _ = await scoped(venue_id, investigation_id)
        if meta is None:
            raise HTTPException(404, detail={"code": "no_trace"})
        cursor = last_event_id if last_event_id is not None else (str(after) if after is not None else None)
        return StreamingResponse(hub.events(investigation_id, cursor, ping_seconds=ping_seconds),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.post("/{venue_id}/investigations/{investigation_id}/followup")
    async def followup(venue_id: str, investigation_id: str, body: FollowupRequest) -> Dict[str, Any]:
        """'What if D3 jams?': continue the parent's robustness lane in the same sandbox (environment_id +
        previous_interaction_id), or evaluate locally. A live follow-up that cannot reuse the environment fails and
        falls back to the labelled local lane."""
        venue = venue_or_404(venue_id)
        meta, _ = await scoped(venue_id, investigation_id)
        if meta is None:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        if body.mode == "local" and not fixtures_enabled():
            raise HTTPException(403, "Local demo investigations are disabled in production mode")
        if investigation_id in active:
            raise HTTPException(409, detail={"code": "parent_running"})
        try:
            scenario = parse_scenario(body.scenario)
        except ScenarioError as error:
            raise HTTPException(422, detail={"code": str(error)}) from None
        plan_request = DoorPlanRequest.model_validate(meta["request"])
        parent: Dict[str, Any] = {}
        robustness = await runner.get_saved_result(lane_id(investigation_id, "robustness"))
        if robustness is not None and robustness.provenance == "live":
            acks = await asyncio.to_thread(ledger.events, lane_id(investigation_id, "robustness"), 8,
                                           phases=("ack_sent",), exclude_phases=())
            parent = {"environment_id": robustness.provider_environment_id,
                      "interaction_id": acks[-1].get("interaction_id") if acks else None}
        seconds = {"followup": lane_deadline("followup", body.deadline_seconds)}
        return {**await start(venue, plan_request, body.mode, ["followup"], seconds, team=False,
                              extra={"scenario": scenario.label, "parent": parent,
                                     "parent_investigation_id": investigation_id},
                              meta_extra={"parent_investigation_id": investigation_id, "scenario": scenario.label}),
                "parent_investigation_id": investigation_id, "scenario": scenario.label}

    return router
