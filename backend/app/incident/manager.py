"""IncidentManager: the server-side mirror of one incident (hazards, checked plan, door actuators, approvals).

Why it exists: hazards used to live only in the browser and POST /api/venues/{id}/door-plan is stateless, so phones,
agents and approvals had nothing to share. This holds one incident for one venue, keyed by `plan_revision` (bumped on
every change) and the checker's `candidate_hash`. An approval must quote both, so a click on a stale card cannot
move a door.

The control loop mirrors the tabletop: AI proposes, the local checker decides, a human approves, the device moves, and
only an observed endpoint counts. A gate that is never observed at its target becomes "stuck": the planner re-runs
with that door closed and the new plan is published as a fallback. The planner itself is untouched; "stuck" is modeled
by planning on a copy of the venue where the door is closed and not openable.
"""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Dict, List, Optional, Set
from uuid import uuid4

from backend.app.hazard.door_planner import DoorPlanError, plan_doors
from backend.app.incident.events import EventHub, now_iso
from backend.app.incident.gates import ControllerConfig, GateState, VirtualDoorController
from backend.app.incident.models import (
    ApprovalRecord, ApproveRequest, IncidentPlan, IncidentState, PlanDoorView, PlanExitView,
)
from backend.app.venues import model as venue_model
from backend.app.venues.model import VenueV2
from backend.app.venues.schemas import DoorPlanRequest, DoorPlanResponse, HazardInput

CONTROLLABLE = ("motorized", "simulated_servo")
MAX_APPROVALS_KEPT = 20


class IncidentError(Exception):
    """An error the router turns into HTTP status + {"code": ...}."""

    def __init__(self, code: str, status: int = 422):
        super().__init__(code)
        self.code = code
        self.status = status


def with_stuck_closed(venue: VenueV2, stuck: Set[str]) -> VenueV2:
    """A copy of the venue where each stuck door is closed and the planner may not open it.

    The geometry revision is suffixed so the planner's per-revision no-hazard cache and the candidate hash never mix
    a stuck-door run with the intact venue.
    """
    if not stuck:
        return venue
    doors = [d.model_copy(update={"default_state": "closed", "planner_can_open": False}) if d.id in stuck else d
             for d in venue.doors]
    return venue.model_copy(update={"doors": doors,
                                    "geometry_revision": f"{venue.geometry_revision}+stuck:{','.join(sorted(stuck))}"})


class IncidentManager:
    def __init__(self, config: Optional[ControllerConfig] = None, hub: Optional[EventHub] = None):
        self.config = config or ControllerConfig()
        self.hub = hub or EventHub()
        self.venue: Optional[VenueV2] = None
        self.controller: Optional[VirtualDoorController] = None
        self.hazards: List[HazardInput] = []
        self.plan: Optional[IncidentPlan] = None
        self.plan_error: Optional[str] = None
        self.plan_revision = 0
        self.stuck: Set[str] = set()
        self.approvals: List[ApprovalRecord] = []
        self._lock = asyncio.Lock()
        self._tasks: Set["asyncio.Task[Any]"] = set()
        self._epoch = 0  # bumps on reset / venue change so a late background task drops its result

    # -- binding -------------------------------------------------------------------------------------------------

    def _bind(self, venue: VenueV2) -> None:
        """Starts a fresh incident for this venue. plan_revision keeps growing so old approvals stay stale."""
        if self.controller is not None:
            self.controller._emit_cb = None
            self.controller.reset(quiet=True)
        self._epoch += 1
        self.venue = venue
        gates = {d.id: d.default_state for d in venue.doors if d.actuation in CONTROLLABLE}
        self.controller = VirtualDoorController(gates, self.config, emit=self._on_device, on_stale=self._on_stale)
        self.hazards, self.plan, self.plan_error = [], None, None
        self.stuck.clear()
        self.approvals.clear()
        self.plan_revision += 1

    def _ensure_bound(self) -> VenueV2:
        untouched = self.plan is None and not self.hazards and not self.approvals
        if self.venue is None or untouched:
            from backend.app.venues.registry import venue_registry
            active = venue_model.get_venue(venue_registry().active()["venue_id"]) or venue_model.load_building_v2()
            if self.venue is None or (active.venue_id, active.geometry_revision) != (self.venue.venue_id, self.venue.geometry_revision):
                self._bind(active)
        assert self.venue is not None
        return self.venue

    # -- events --------------------------------------------------------------------------------------------------

    def _on_device(self, kind: str, payload: Dict[str, Any]) -> None:
        self.hub.publish(kind, {"plan_revision": self.plan_revision, **payload})

    def _on_stale(self) -> None:
        if any(a.status == "actuating" for a in self.approvals):
            return  # the in-flight approval sees the unknown gates and replans itself
        self._spawn(self._stale_fallback())

    def _spawn(self, coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    # -- view ----------------------------------------------------------------------------------------------------

    def _render_plan(self) -> Optional[IncidentPlan]:
        if self.plan is None or self.controller is None:
            return self.plan
        gates = {g["gate_id"]: g for g in self.controller.view()["gates"]}
        doors = [d.model_copy(update={"applied": gates[d.id]["applied"] if d.id in gates else "sign"}) for d in self.plan.doors]
        return self.plan.model_copy(update={"doors": doors})

    def state(self) -> IncidentState:
        venue = self._ensure_bound()
        assert self.controller is not None
        return IncidentState(
            venue_id=venue.venue_id, geometry_revision=venue.geometry_revision, plan_revision=self.plan_revision,
            hazards=[h.model_dump(mode="json") for h in self.hazards], plan=self._render_plan(), plan_error=self.plan_error,
            controller=self.controller.view(), stuck_doors=sorted(self.stuck), approvals=list(self.approvals),
            approval_in_progress=any(a.status == "actuating" for a in self.approvals), last_event_id=self.hub.last_id)

    def snapshot(self) -> Dict[str, Any]:
        return {"state": self.state().model_dump(mode="json")}

    # -- planning ------------------------------------------------------------------------------------------------

    async def _plan(self, hazards: List[HazardInput], stuck: Set[str], reason: str) -> IncidentPlan:
        venue = self.venue
        assert venue is not None  # bound by the caller; re-binding here could swap the venue mid-request
        planning = with_stuck_closed(venue, stuck)
        try:
            response: DoorPlanResponse = await asyncio.to_thread(plan_doors, planning, DoorPlanRequest(hazards=hazards))
        except DoorPlanError as error:
            raise IncidentError(error.code, 422) from None
        return self._summarize(venue, response, stuck, reason)

    def _summarize(self, venue: VenueV2, resp: DoorPlanResponse, stuck: Set[str], reason: str) -> IncidentPlan:
        assert self.controller is not None
        original = {d.id: d for d in venue.doors}
        doors: List[PlanDoorView] = []
        for d in resp.doors:
            controllable = self.controller.has_gate(d.id)
            is_stuck = d.id in stuck
            doors.append(PlanDoorView(
                id=d.id, state=d.state, lamp="red" if is_stuck else d.lamp, actuation=d.actuation, controllable=controllable,
                changed=d.state != original[d.id].default_state, stuck=is_stuck, decided_by=d.decided_by,
                reason=f"{d.id} stuck closed: never observed at its endpoint; not commanded" if is_stuck else d.reason,
                applied="unknown"))
        note = ("with " + ", ".join(sorted(stuck)) + " stuck closed") if stuck else None
        return IncidentPlan(
            plan_id=resp.plan_id, plan_revision=0, candidate_hash=resp.chosen.candidate_hash,
            label="fallback" if stuck else "primary", note=note, reason=reason,
            valid=resp.chosen.validator_report.is_valid, status=resp.chosen.status,
            initial_population=resp.chosen.initial_population, completed_crossings=resp.chosen.completed_crossings,
            baseline_completed=resp.baseline.completed_crossings, no_hazard_completed=resp.no_hazard_completed,
            door_states={d.id: d.state for d in doors}, doors=doors,
            exits=[PlanExitView(id=x.id, zone=x.zone, safe=x.safe, lamp=x.lamp, modeled_crossings=x.modeled_crossings,
                                reason=x.reason) for x in resp.exits],
            lights_px=resp.lights.px, stuck_doors=sorted(stuck), advisories=list(resp.advisories),
            announcement=resp.announcement, created_at=now_iso())

    def _commit_plan(self, plan: IncidentPlan, hazards: List[HazardInput]) -> IncidentPlan:
        self.plan_revision += 1
        self.hazards = hazards
        self.plan = plan.model_copy(update={"plan_revision": self.plan_revision})
        self.plan_error = None
        self.hub.publish("plan", {"plan_revision": self.plan_revision, "plan": self._render_plan().model_dump(mode="json"),
                                  "hazards": [h.model_dump(mode="json") for h in hazards], "stuck_doors": sorted(self.stuck)})
        return self.plan

    async def _replan_locked(self, reason: str) -> Optional[IncidentPlan]:
        """Re-plans the current hazards with the current stuck set. On a planner error the plan is withdrawn, not kept."""
        try:
            plan = await self._plan(self.hazards, set(self.stuck), reason)
        except IncidentError as error:
            self.plan_revision += 1
            self.plan, self.plan_error = None, error.code
            self.hub.publish("plan", {"plan_revision": self.plan_revision, "plan": None, "plan_error": error.code,
                                      "stuck_doors": sorted(self.stuck)})
            return None
        return self._commit_plan(plan, self.hazards)

    # -- hazards -------------------------------------------------------------------------------------------------

    async def set_hazards(self, venue_id: str, expected_plan_revision: int, hazards: List[HazardInput]) -> IncidentState:
        venue = venue_model.get_venue(venue_id)
        if venue is None:
            raise IncidentError("unknown_venue", 404)
        async with self._lock:
            self._ensure_bound()
            if any(a.status == "actuating" for a in self.approvals):
                raise IncidentError("approval_in_progress", 409)
            if self.venue is not None and (venue.venue_id, venue.geometry_revision) != (self.venue.venue_id, self.venue.geometry_revision):
                # A different venue is a different incident; the client's revision belongs to the old one.
                self._bind(venue)
            elif expected_plan_revision != self.plan_revision:
                raise IncidentError("stale_plan", 409)
            for hazard in hazards:
                if hazard.source == "camera":
                    from backend.app.venues.camera import CAMERA_STORE
                    code = CAMERA_STORE.verify_camera_hazard(venue_id, hazard)
                    if code is not None:
                        raise IncidentError(code, 422)
            plan = await self._plan(list(hazards), set(self.stuck), "hazards updated")
            self._commit_plan(plan, list(hazards))
        return self.state()

    # -- approval ------------------------------------------------------------------------------------------------

    def _observed(self, door_id: str) -> Optional[str]:
        assert self.controller is not None
        return self.controller.gates[door_id].snapshot()["observed"]

    async def approve(self, request: ApproveRequest) -> ApprovalRecord:
        async with self._lock:
            self._ensure_bound()
            assert self.controller is not None
            if any(a.status == "actuating" for a in self.approvals):
                raise IncidentError("approval_in_progress", 409)
            plan = self.plan
            if plan is None:
                raise IncidentError("no_plan", 409)
            if (request.plan_revision != self.plan_revision or request.candidate_hash != plan.candidate_hash
                    or request.door_states != plan.door_states):
                raise IncidentError("stale_plan", 409)
            if not plan.valid:
                raise IncidentError("plan_not_valid", 422)
            commands: Dict[str, str] = {}
            for door_id, state in plan.door_states.items():
                if self.controller.has_gate(door_id) and door_id not in self.stuck and self._observed(door_id) != state:
                    commands[door_id] = "OPEN" if state == "open" else "CLOSED"
            approval = ApprovalRecord(
                approval_id=f"apv-{uuid4().hex[:12]}", plan_revision=plan.plan_revision, candidate_hash=plan.candidate_hash,
                door_states=dict(plan.door_states), status="actuating" if commands else "applied", commands=commands,
                results={}, started_at=now_iso(), finished_at=None if commands else now_iso(),
                reason=None if commands else "no gate needed to move; sign doors follow the plan")
            self.approvals.append(approval)
            del self.approvals[:-MAX_APPROVALS_KEPT]
            self.hub.publish("approval", {"plan_revision": self.plan_revision, "approval": approval.model_dump(mode="json")})
            if commands:
                self._spawn(self._actuate(approval, commands, self._epoch))
        return approval

    async def _actuate(self, approval: ApprovalRecord, commands: Dict[str, str], epoch: int) -> None:
        assert self.controller is not None
        controller = self.controller
        outcomes = await controller.command_many(commands)  # type: ignore[arg-type]
        if epoch != self._epoch:
            return  # a reset or venue change superseded this approval
        results = {o.gate_id: f"{o.result}:{o.detail}" for o in outcomes}
        failed = {o.gate_id: o for o in outcomes if o.result != "arrived"}
        async with self._lock:
            if epoch != self._epoch:
                return
            approval.results = results
            approval.finished_at = now_iso()
            if not failed:
                approval.status = "applied"
                self.hub.publish("approval", {"plan_revision": self.plan_revision, "approval": approval.model_dump(mode="json")})
                return
            newly = set(failed)
            if controller.stale:
                newly |= set(controller.gates)
            self.stuck |= newly
            approval.status = "failed"
            parts = [f"{gid} {'open' if commands.get(gid) == 'OPEN' else 'close'} never observed ({o.detail})"
                     for gid, o in sorted(failed.items())]
            approval.reason = "; ".join(parts) + "; re-planned with " + ", ".join(sorted(newly)) + " stuck closed"
            fallback = await self._replan_locked("fallback: " + approval.reason)
            approval.fallback_plan_revision = fallback.plan_revision if fallback else self.plan_revision
            self.hub.publish("approval", {"plan_revision": self.plan_revision, "approval": approval.model_dump(mode="json")})

    async def _stale_fallback(self) -> None:
        assert self.controller is not None
        epoch = self._epoch
        async with self._lock:
            if epoch != self._epoch or self.plan is None:
                return
            self.stuck |= set(self.controller.gates)
            await self._replan_locked("fallback: controller heartbeat lost; every gate UNKNOWN, none counted open")

    # -- faults and reset ------------------------------------------------------------------------------------------

    def inject_fault(self, gate_id: Optional[str], fault: str) -> Dict[str, Any]:
        self._ensure_bound()
        assert self.controller is not None
        if fault != "heartbeat_timeout":
            if not gate_id:
                raise IncidentError("gate_required", 422)
            if not self.controller.has_gate(gate_id):
                raise IncidentError("unknown_gate", 404)
        self.controller.inject_fault(fault, gate_id)
        return self.controller.view()

    def clear_faults(self, gate_id: Optional[str]) -> Dict[str, Any]:
        self._ensure_bound()
        assert self.controller is not None
        if gate_id is not None and not self.controller.has_gate(gate_id):
            raise IncidentError("unknown_gate", 404)
        self.controller.clear_fault(gate_id)
        return self.controller.view()

    async def reset(self) -> IncidentState:
        async with self._lock:
            venue = self._ensure_bound()
            assert self.controller is not None
            self._epoch += 1
            self.controller.reset(quiet=True)
            self.hazards, self.plan, self.plan_error = [], None, None
            self.stuck.clear()
            self.approvals.clear()
            self.plan_revision += 1
            self.hub.publish("reset", {"plan_revision": self.plan_revision, "venue_id": venue.venue_id,
                                       "line": "RESET incident cleared; faults cleared; gates returned to default endpoints",
                                       "state": self.state().model_dump(mode="json")})
        return self.state()
