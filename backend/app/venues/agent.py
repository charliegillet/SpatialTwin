"""Managed-agent door investigation routes for building-v2.

POST /api/venues/{venue_id}/investigate            -> {investigation_id}; the run continues in the background
GET  /api/venues/{venue_id}/investigations/{id}    -> progress + result
POST /api/venues/{venue_id}/investigations/{id}/cancel

The tools the agent can call are read-only views of the local door planner; no hardware is involved.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import Field

from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.managed.door_agent import MAX_DEADLINE_SECONDS, DoorAgentRunner
from backend.app.hazard.door_planner import DoorPlanError, resolve_request
from backend.app.venues.camera import CAMERA_STORE
from backend.app.venues.model import get_venue
from backend.app.venues.schemas import DoorPlanRequest


class DoorInvestigationRequest(DoorPlanRequest):
    mode: Literal["live", "local"] = "local"
    deadline_seconds: float = Field(default=MAX_DEADLINE_SECONDS, gt=0, le=MAX_DEADLINE_SECONDS)


def build_door_agent_router(adapter: ManagedAgentAdapter, slots: asyncio.Semaphore,
                            fixtures_enabled: Callable[[], bool]) -> APIRouter:
    router = APIRouter(prefix="/api/venues")
    runner = DoorAgentRunner(adapter)
    active: Dict[str, asyncio.Task] = {}
    unsaved: Dict[str, Any] = {}  # terminal results the ledger could not persist (bounded, in memory)

    def venue_or_404(venue_id: str):
        venue = get_venue(venue_id)
        if venue is None:
            raise HTTPException(404, detail={"code": "unknown_venue"})
        return venue

    @router.post("/{venue_id}/investigate")
    async def investigate(venue_id: str, request: DoorInvestigationRequest) -> Dict[str, Any]:
        venue = venue_or_404(venue_id)
        if request.mode == "local" and not fixtures_enabled():
            raise HTTPException(403, "Local demo investigations are disabled in production mode")
        # Same validation as door-plan, before any slot or provider is used.
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
        if slots.locked():
            raise HTTPException(429, "Too many investigations are running; try again shortly")
        await slots.acquire()  # not locked, so this does not suspend: the check and the claim are atomic
        investigation_id = f"dinv-{uuid.uuid4()}"

        async def owner() -> None:
            try:
                result = await runner.run(venue, plan_request, investigation_id, request.mode,
                                          request.deadline_seconds)
                if await runner.get_saved_result(investigation_id) is None:
                    while len(unsaved) >= 32:
                        unsaved.pop(next(iter(unsaved)))
                    unsaved[investigation_id] = result
            finally:
                slots.release()
                active.pop(investigation_id, None)

        try:
            active[investigation_id] = asyncio.create_task(owner())
        except BaseException:
            slots.release()
            raise
        return {"investigation_id": investigation_id}

    @router.get("/{venue_id}/investigations/{investigation_id}")
    async def progress(venue_id: str, investigation_id: str) -> Dict[str, Any]:
        venue_or_404(venue_id)
        result = await runner.get_saved_result(investigation_id) or unsaved.get(investigation_id)
        if investigation_id not in active and result is None:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        events = await runner.get_progress(investigation_id)
        return {"investigation_id": investigation_id,
                "status": result.status.value if result else "running",
                "provider_progress": events,
                "investigation": result.model_dump(mode="json") if result else None}

    @router.post("/{venue_id}/investigations/{investigation_id}/cancel")
    async def cancel(venue_id: str, investigation_id: str) -> Dict[str, Any]:
        venue_or_404(venue_id)
        task: Optional[asyncio.Task] = active.get(investigation_id)
        if task is not None:
            # Let a newly scheduled owner take its first turn so it can persist the cancellation.
            await asyncio.sleep(0)
            if not task.done():
                if not task.cancelling():
                    task.cancel()
                return {"status": "cancellation_requested"}
        result = await runner.get_saved_result(investigation_id) or unsaved.get(investigation_id)
        if result is None:
            raise HTTPException(404, detail={"code": "unknown_investigation"})
        return {"status": "already_finished", "investigation": result.model_dump(mode="json")}

    return router
