"""IncidentManager: the server-side mirror of one incident (hazards, checked plan, door actuators, approvals).

Why it exists: hazards used to live only in the browser and POST /api/venues/{id}/door-plan is stateless, so phones,
agents and approvals had nothing to share. This holds one incident for one venue, keyed by `plan_revision` (bumped on
every change) and the checker's `candidate_hash`. An approval must quote both, so a click on a stale card cannot
move a door.

The control loop mirrors the tabletop: AI proposes, the local checker decides, a human approves, the device moves, and
only an observed endpoint counts. A gate that is never observed at its target becomes "stuck": the planner re-runs
with that door closed and the new plan is published as a fallback. The planner itself is untouched; "stuck" is modeled
by planning on a copy of the venue where the door is closed and not openable.

The unattended fail-safe (backend/app/incident/failsafe.py, off by default) is the one exception to "a human approves":
armed, it approves a checked plan nobody approved within its window, after holding closed every gate into a hazard room
("held", modeled like "stuck").
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Dict, List, Literal, Optional, Set, Tuple
from uuid import uuid4

from backend.app.hazard.door_planner import DoorPlanError, plan_doors
from backend.app.incident.events import EventHub, now_iso
from backend.app.incident.failsafe import (
    DEFAULT_WINDOW_SECONDS, deadline_iso, gates_into_hazard, held_reason, join_ids, left_open,
)
from backend.app.incident.gates import ControllerConfig, GateState, VirtualDoorController
from backend.app.incident.models import (
    ApprovalRecord, ApproveRequest, FailSafeAction, FailSafeView, IncidentPlan, IncidentState, PlanDoorView, PlanExitView,
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


def with_closed(venue: VenueV2, doors: Set[str], tag: str) -> VenueV2:
    """A copy of the venue where each listed door is closed and the planner may not open it.

    The geometry revision is suffixed so the planner's per-revision no-hazard cache and the candidate hash never mix
    such a run with the intact venue.
    """
    if not doors:
        return venue
    copied = [d.model_copy(update={"default_state": "closed", "planner_can_open": False}) if d.id in doors else d
              for d in venue.doors]
    return venue.model_copy(update={"doors": copied,
                                    "geometry_revision": f"{venue.geometry_revision}+{tag}:{','.join(sorted(doors))}"})


def with_stuck_closed(venue: VenueV2, stuck: Set[str]) -> VenueV2:
    return with_closed(venue, stuck, "stuck")


def _current_task() -> Optional["asyncio.Task[Any]"]:
    try:
        return asyncio.current_task()
    except RuntimeError:  # no running loop: a sync caller such as a rebind from state()
        return None


class IncidentManager:
    def __init__(self, config: Optional[ControllerConfig] = None, hub: Optional[EventHub] = None):
        self.config = config or ControllerConfig()
        self.hub = hub or EventHub()
        self.venue: Optional[VenueV2] = None
        self.controller: Optional[VirtualDoorController] = None
        self.hazards: List[HazardInput] = []
        self.plan: Optional[IncidentPlan] = None
        # The full checked door plan behind ``plan`` (routes, lamps, timeline), for the twin to draw what is executed.
        self.door_plan: Optional[DoorPlanResponse] = None
        self.plan_error: Optional[str] = None
        self.plan_revision = 0
        self.stuck: Set[str] = set()
        # Stuck gates whose CLOSE was never observed: their position is unknown and they may still be open.
        self.close_unseen: Set[str] = set()
        self.approvals: List[ApprovalRecord] = []
        self._lock = asyncio.Lock()
        self._tasks: Set["asyncio.Task[Any]"] = set()
        self._epoch = 0  # bumps on reset / venue change so a late background task drops its result
        # Unattended fail-safe, off by default. Its timer is not one of _tasks: wait_idle must not sleep through a window.
        self.failsafe_armed = False
        self.failsafe_window = DEFAULT_WINDOW_SECONDS
        self.held: Dict[str, List[str]] = {}  # gates the fail-safe holds closed -> hazard rooms (zone ids) they open into
        self.failsafe_last: Optional[FailSafeAction] = None
        self._failsafe_timer: Optional["asyncio.Task[Any]"] = None
        self._failsafe_revision: Optional[int] = None
        self._failsafe_deadline: Optional[float] = None  # time.monotonic()
        self._failsafe_deadline_at: Optional[str] = None

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
        self.hazards, self.plan, self.plan_error, self.door_plan = [], None, None, None
        self.stuck.clear()
        self.close_unseen.clear()
        self.approvals.clear()
        self._disarm_failsafe()  # a new incident starts with a person in the loop
        self.plan_revision += 1
        # Every other client still shows the old venue's gates and approvals: a rebind is a reset with the new state.
        self.hub.publish("reset", {"plan_revision": self.plan_revision, "venue_id": venue.venue_id,
                                   "line": f"BIND incident moved to {venue.venue_id}; gates at default endpoints",
                                   "state": self._state_unbound_safe().model_dump(mode="json")})

    def _state_unbound_safe(self) -> IncidentState:
        assert self.venue is not None and self.controller is not None
        return IncidentState(
            venue_id=self.venue.venue_id, geometry_revision=self.venue.geometry_revision, plan_revision=self.plan_revision,
            hazards=[h.model_dump(mode="json") for h in self.hazards], plan=self._render_plan(), plan_error=self.plan_error,
            controller=self.controller.view(), stuck_doors=sorted(self.stuck), approvals=list(self.approvals),
            approval_in_progress=any(a.status == "actuating" for a in self.approvals), failsafe=self.failsafe_view(),
            last_event_id=self.hub.last_id)

    def _ensure_bound(self, allow_rebind: bool = True) -> VenueV2:
        untouched = self.plan is None and not self.hazards and not self.approvals
        if self.venue is None or (untouched and allow_rebind):
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
        # A read never rebinds while a mutation holds the lock: set_hazards binds a venue, then awaits the planner
        # with the incident still "untouched", and a poll in that window must not swap the venue and controller.
        self._ensure_bound(allow_rebind=not self._lock.locked())
        return self._state_unbound_safe()

    def door_plan_view(self) -> Dict[str, Any]:
        """The full checked plan for the current revision, or null when there is none (no hazards, withdrawn)."""
        self._ensure_bound(allow_rebind=not self._lock.locked())
        door_plan = self.door_plan if self.plan is not None else None
        return {"plan_revision": self.plan_revision, "door_plan": door_plan.model_dump(mode="json") if door_plan else None}

    def snapshot(self) -> Dict[str, Any]:
        return {"state": self.state().model_dump(mode="json")}

    # -- planning ------------------------------------------------------------------------------------------------

    def _held_reasons(self, venue: VenueV2, held: Set[str]) -> Dict[str, str]:
        names = {z.id: z.name for z in venue.zones}
        return {d: held_reason(d, [names.get(z, z) for z in self.held.get(d, [])]) for d in held}

    async def _plan(self, hazards: List[HazardInput], stuck: Set[str], reason: str) -> Tuple[IncidentPlan, DoorPlanResponse]:
        venue = self.venue
        assert venue is not None  # bound by the caller; re-binding here could swap the venue mid-request
        held = set(self.held) - stuck
        planning = with_closed(with_stuck_closed(venue, stuck), held, "held")
        try:
            response: DoorPlanResponse = await asyncio.to_thread(plan_doors, planning, DoorPlanRequest(hazards=hazards))
        except DoorPlanError as error:
            raise IncidentError(error.code, 422) from None
        # The planner saw a copy with the stuck (and held) doors closed; the twin draws the real venue, so the plan names it.
        reasons = {d: (f"{d} close never observed: its position is unknown and it may still be open; planned as closed, "
                       "not commanded") if d in self.close_unseen else f"{d} stuck closed: never observed at its endpoint; not commanded"
                   for d in stuck}
        reasons.update(self._held_reasons(venue, held))
        doors = [d.model_copy(update={"reason": reasons[d.id]}) if d.id in reasons else d for d in response.doors]
        full = response.model_copy(update={"geometry_revision": venue.geometry_revision, "doors": doors})
        return self._summarize(venue, response, stuck, reason, held, reasons), full

    def _summarize(self, venue: VenueV2, resp: DoorPlanResponse, stuck: Set[str], reason: str,
                   held: Optional[Set[str]] = None, reasons: Optional[Dict[str, str]] = None) -> IncidentPlan:
        assert self.controller is not None
        held, reasons = held or set(), reasons or {}
        original = {d.id: d for d in venue.doors}
        doors: List[PlanDoorView] = []
        for d in resp.doors:
            controllable = self.controller.has_gate(d.id)
            is_stuck = d.id in stuck
            doors.append(PlanDoorView(
                id=d.id, state=d.state, lamp="red" if is_stuck or d.id in held else d.lamp, actuation=d.actuation,
                controllable=controllable, changed=d.state != original[d.id].default_state, stuck=is_stuck,
                decided_by=d.decided_by, reason=reasons.get(d.id, d.reason), applied="unknown"))
        parts = ([", ".join(sorted(stuck)) + " stuck closed"] if stuck else []) + (
            [", ".join(sorted(held)) + " held closed by the fail-safe"] if held else [])
        note = ("with " + "; ".join(parts)) if parts else None
        return IncidentPlan(
            plan_id=resp.plan_id, plan_revision=0, candidate_hash=resp.chosen.candidate_hash,
            label="fallback" if stuck else "primary", note=note, reason=reason,
            valid=resp.chosen.validator_report.is_valid, status=resp.chosen.status,
            initial_population=resp.chosen.initial_population, completed_crossings=resp.chosen.completed_crossings,
            baseline_completed=resp.baseline.completed_crossings, no_hazard_completed=resp.no_hazard_completed,
            door_states={d.id: d.state for d in doors}, doors=doors,
            exits=[PlanExitView(id=x.id, zone=x.zone, safe=x.safe, lamp=x.lamp, modeled_crossings=x.modeled_crossings,
                                reason=x.reason) for x in resp.exits],
            lights_px=resp.lights.px, stuck_doors=sorted(stuck), held_doors=sorted(held), advisories=list(resp.advisories),
            announcement=resp.announcement, created_at=now_iso())

    def _commit_plan(self, plan: IncidentPlan, hazards: List[HazardInput], door_plan: DoorPlanResponse,
                     schedule: bool = True) -> IncidentPlan:
        self.plan_revision += 1
        self.hazards = hazards
        self.door_plan = door_plan
        self.plan = plan.model_copy(update={"plan_revision": self.plan_revision})
        self.plan_error = None
        self.hub.publish("plan", {"plan_revision": self.plan_revision, "plan": self._render_plan().model_dump(mode="json"),
                                  "hazards": [h.model_dump(mode="json") for h in hazards], "stuck_doors": sorted(self.stuck)})
        if schedule:
            self._schedule_failsafe()
        return self.plan

    async def _replan_locked(self, reason: str, schedule: bool = True) -> Optional[IncidentPlan]:
        """Re-plans the current hazards with the current stuck set. On a planner error the plan is withdrawn, not kept."""
        try:
            plan, door_plan = await self._plan(self.hazards, set(self.stuck), reason)
        except IncidentError as error:
            self.plan_revision += 1
            self.plan, self.plan_error, self.door_plan = None, error.code, None
            self._cancel_failsafe_timer()
            self.hub.publish("plan", {"plan_revision": self.plan_revision, "plan": None, "plan_error": error.code,
                                      "stuck_doors": sorted(self.stuck)})
            return None
        return self._commit_plan(plan, self.hazards, door_plan, schedule=schedule)

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
            # New hazards are a new situation: the fail-safe re-decides what to hold once its window runs out.
            held, self.held = self.held, {}
            try:
                plan, door_plan = await self._plan(list(hazards), set(self.stuck), "hazards updated")
            except IncidentError:
                self.held = held
                raise
            self._commit_plan(plan, list(hazards), door_plan)
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
            approval = self._approve_locked(plan)
            if self._failsafe_timer is not None:
                self._cancel_failsafe_timer()
                self._publish_failsafe(f"FAILSAFE r{plan.plan_revision}: a person approved; the fail-safe stands by")
        return approval

    def _approve_locked(self, plan: IncidentPlan, actor: Literal["operator", "fail_safe"] = "operator") -> ApprovalRecord:
        """Commands every gate whose observed state differs from the plan. Callers hold the lock and checked the plan."""
        assert self.controller is not None
        commands: Dict[str, str] = {}
        for door_id, state in plan.door_states.items():
            if self.controller.has_gate(door_id) and door_id not in self.stuck and self._observed(door_id) != state:
                commands[door_id] = "OPEN" if state == "open" else "CLOSED"
        approval = ApprovalRecord(
            approval_id=f"apv-{uuid4().hex[:12]}", plan_revision=plan.plan_revision, candidate_hash=plan.candidate_hash,
            door_states=dict(plan.door_states), status="actuating" if commands else "applied", commands=commands,
            results={}, started_at=now_iso(), finished_at=None if commands else now_iso(),
            reason=None if commands else "no gate needed to move; sign doors follow the plan", actor=actor)
        self.approvals.append(approval)
        del self.approvals[:-MAX_APPROVALS_KEPT]
        self.hub.publish("approval", {"plan_revision": self.plan_revision, "approval": approval.model_dump(mode="json")})
        if commands:
            self._spawn(self._actuate(approval, commands, self._epoch))
        return approval

    async def _actuate(self, approval: ApprovalRecord, commands: Dict[str, str], epoch: int) -> None:
        # A reset or venue change between the approval and this task's first turn must stop the movement before it
        # starts: checking only afterwards would drop the result but leave a gate moving after Reset.
        if epoch != self._epoch or self.controller is None:
            return
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
                if self.plan is not None and set(self.plan.held_doors) - set(self.held):
                    # A person took over ("I'm here") while these doors moved: hand the held gates back now.
                    await self._replan_locked("a person took over: the gates the fail-safe held closed are open to the planner again")
                return
            newly = set(failed)
            if controller.stale:
                newly |= set(controller.gates)
            self.stuck |= newly
            self.close_unseen |= {gid for gid in failed if commands.get(gid) == "CLOSED"}
            approval.status = "failed"
            parts = [f"{gid} {'open' if commands.get(gid) == 'OPEN' else 'close'} never observed ({o.detail})"
                     for gid, o in sorted(failed.items())]
            unseen = sorted(newly & self.close_unseen)
            approval.reason = "; ".join(parts) + "; re-planned with " + ", ".join(sorted(newly)) + " stuck closed" + (
                f" ({join_ids(unseen)}: position unknown, may still be open)" if unseen else "")
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
            self.hazards, self.plan, self.plan_error, self.door_plan = [], None, None, None
            self.stuck.clear()
            self.close_unseen.clear()
            self.approvals.clear()
            self._disarm_failsafe()
            self.plan_revision += 1
            self.hub.publish("reset", {"plan_revision": self.plan_revision, "venue_id": venue.venue_id,
                                       "line": "RESET incident cleared; faults cleared; fail-safe off; gates returned to default endpoints",
                                       "state": self.state().model_dump(mode="json")})
        return self.state()

    # -- unattended fail-safe ------------------------------------------------------------------------------------

    def _approved(self, revision: int) -> Optional[ApprovalRecord]:
        return next((a for a in reversed(self.approvals) if a.plan_revision == revision and a.status != "failed"), None)

    def _cancel_failsafe_timer(self) -> None:
        timer, self._failsafe_timer = self._failsafe_timer, None
        if timer is not None and not timer.done() and timer is not _current_task():
            timer.cancel()
        self._failsafe_revision = self._failsafe_deadline = self._failsafe_deadline_at = None

    def _disarm_failsafe(self) -> None:
        self.failsafe_armed = False
        self.held = {}
        self.failsafe_last = None
        self._cancel_failsafe_timer()

    def _publish_failsafe(self, line: str) -> None:
        self.hub.publish("failsafe", {"plan_revision": self.plan_revision, "line": line,
                                      "failsafe": self.failsafe_view().model_dump(mode="json")})

    def _schedule_failsafe(self) -> None:
        """Every new checked plan gives a person the window; the fail-safe acts only if nobody approved it by then."""
        self._cancel_failsafe_timer()
        plan = self.plan
        if not self.failsafe_armed or plan is None or not plan.valid or self._approved(plan.plan_revision):
            return
        window = self.failsafe_window
        self._failsafe_revision = plan.plan_revision
        self._failsafe_deadline = time.monotonic() + window
        self._failsafe_deadline_at = deadline_iso(window)
        self._failsafe_timer = asyncio.ensure_future(self._failsafe_after(plan.plan_revision, self._epoch, window))
        self._publish_failsafe(f"FAILSAFE r{plan.plan_revision}: waiting {window:g} s for a person to approve")

    async def _failsafe_after(self, revision: int, epoch: int, delay: float) -> None:
        await asyncio.sleep(delay)
        async with self._lock:
            if self._failsafe_timer is asyncio.current_task():
                self._failsafe_timer = None
                self._failsafe_revision = self._failsafe_deadline = self._failsafe_deadline_at = None
            if epoch != self._epoch or revision != self.plan_revision or not self.failsafe_armed:
                return
            try:
                await self._failsafe_act_locked()
            except Exception as error:  # noqa: BLE001 - the view must never say "acting" forever
                self._publish_failsafe(f"FAILSAFE: could not act ({type(error).__name__}); nothing moved; a person must approve")

    async def _failsafe_act_locked(self) -> None:
        """Nobody approved in time: hold every gate into a hazard room closed, re-check, then approve as the fail-safe."""
        assert self.controller is not None and self.venue is not None
        plan, window = self.plan, self.failsafe_window
        if plan is None or not plan.valid:
            self._publish_failsafe("FAILSAFE: no checked plan; nothing moved")
            return
        if any(a.status == "actuating" for a in self.approvals) or self._approved(plan.plan_revision):
            return
        primary = plan
        # A gate whose position is unknown is never trusted: it counts as stuck closed.
        doubtful = {gid for gid, g in self.controller.gates.items()
                    if g.state in (GateState.FAULT, GateState.UNKNOWN)} - self.stuck
        risky = gates_into_hazard(self.door_plan, self.controller.gates, self.stuck | doubtful) if self.door_plan else {}
        opening = left_open(plan.door_states, risky)
        names = {z.id: z.name for z in self.venue.zones}
        parts: List[str] = []
        if opening:
            rooms = sorted({names.get(z, z) for gid in opening for z in risky[gid]})
            parts.append(f"held {join_ids(opening)} closed ({'it opens' if len(opening) == 1 else 'they open'} into "
                         f"{join_ids(rooms)}, a room with a hazard)")
        if doubtful:
            parts.append(f"treated {join_ids(sorted(doubtful))} as stuck closed (position unknown)")
        if opening or doubtful:
            saved = (set(self.stuck), dict(self.held))
            self.stuck |= doubtful
            self.held.update(risky)  # every gate into a hazard room, so the re-check cannot open another one
            reason = f"fail-safe: nobody approved within {window:g} s; " + "; ".join(parts)
            try:
                checked, door_plan = await self._plan(self.hazards, set(self.stuck), reason)
            except Exception as error:
                self.stuck, self.held = saved
                if not isinstance(error, IncidentError):
                    raise
                checked = None
            if checked is None or not checked.valid:
                # The person's plan stays as it was, approvable; the fail-safe moves nothing it could not check.
                self.stuck, self.held = saved
                self._publish_failsafe(f"FAILSAFE r{plan.plan_revision}: no checked plan with "
                                       f"{join_ids(sorted(set(opening) | doubtful))} closed; nothing moved; a person must approve")
                return
            plan = self._commit_plan(checked, self.hazards, door_plan, schedule=False)
        if self.door_plan is not None:
            open_into = sorted(d.id for d in self.door_plan.doors if d.id in self.close_unseen and d.entry_denied_into)
            if open_into:
                parts.append(f"{join_ids(open_into)} may still be open into a room with a hazard (its close was never observed)")
        approval = self._approve_locked(plan, actor="fail_safe")
        moves = ", ".join(f"{'opening' if target == 'OPEN' else 'closing'} {gid}" for gid, target in sorted(approval.commands.items()))
        parts.append(moves or "no gate needed to move")
        parts.append(f"{plan.completed_crossings} of {plan.initial_population} modeled crossings")
        if opening and primary.completed_crossings > plan.completed_crossings:
            parts.append(f"a person could approve {primary.completed_crossings} by opening {join_ids(opening)}")
        summary = "; ".join(parts)
        self.failsafe_last = FailSafeAction(at=now_iso(), plan_revision=plan.plan_revision,
                                            approval_id=approval.approval_id, summary=summary)
        self._publish_failsafe(f"FAILSAFE r{plan.plan_revision}: nobody approved within {window:g} s; {summary}")

    def failsafe_view(self) -> FailSafeView:
        plan = self.plan
        held = {gid: list(self.held.get(gid, [])) for gid in (plan.held_doors if plan else [])}
        base: Dict[str, Any] = {"armed": self.failsafe_armed, "window_seconds": self.failsafe_window,
                                "held_doors": held, "last_action": self.failsafe_last}
        if not self.failsafe_armed:
            return FailSafeView(**base, status="off", note="Off: a person approves every door move.")
        if plan is None or not plan.valid:
            return FailSafeView(**base, status="standing_by", note="Armed: waiting for a checked plan.")
        approval = self._approved(plan.plan_revision)
        if approval is not None:
            acted = approval.actor == "fail_safe"
            return FailSafeView(**base, status="acted" if acted else "approved", plan_revision=plan.plan_revision,
                                note=(f"Nobody approved within {self.failsafe_window:g} s: the fail-safe approved r{plan.plan_revision}."
                                      if acted else f"A person approved r{plan.plan_revision}; the fail-safe stands by."))
        if self._failsafe_revision == plan.plan_revision and self._failsafe_deadline is not None:
            gates = self.controller.gates if self.controller else {}
            doubtful = {gid for gid, g in gates.items() if g.state in (GateState.FAULT, GateState.UNKNOWN)} - self.stuck
            risky = gates_into_hazard(self.door_plan, gates, self.stuck | doubtful) if self.door_plan else {}
            return FailSafeView(**base, status="counting_down", plan_revision=plan.plan_revision,
                                deadline_at=self._failsafe_deadline_at,
                                seconds_left=round(max(0.0, self._failsafe_deadline - time.monotonic()), 1),
                                would_hold=left_open(plan.door_states, risky), in_doubt=sorted(doubtful),
                                note=f"If nobody approves r{plan.plan_revision}, the fail-safe approves it when the window ends.")
        return FailSafeView(**base, status="standing_by", plan_revision=plan.plan_revision,
                            note="Armed: standing by for the next checked plan.")

    async def set_failsafe(self, armed: bool, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> FailSafeView:
        """Arm (starts the window for the current plan) or disarm. Disarming is a person taking over: any gate the
        fail-safe held closed is handed back to the planner, so the plan a person sees is the full one again."""
        async with self._lock:
            self._ensure_bound()
            if armed:
                self.failsafe_armed, self.failsafe_window = True, float(window_seconds)
                self._publish_failsafe(f"FAILSAFE armed: if nobody approves a checked plan within {self.failsafe_window:g} s it "
                                       "approves it, never opening a motorized door into a room with fire, smoke, gas or a chemical")
                self._schedule_failsafe()
            else:
                was_held = bool(self.plan and self.plan.held_doors)
                self.failsafe_armed = False
                self._cancel_failsafe_timer()
                self.held = {}
                self._publish_failsafe("FAILSAFE off: a person approves every door move")
                if was_held and not any(a.status == "actuating" for a in self.approvals):
                    await self._replan_locked("a person took over: the gates the fail-safe held closed are open to the planner again")
            return self.failsafe_view()

    async def wait_failsafe(self) -> None:
        """Test hook: wait for a pending fail-safe window (and anything it started) to finish."""
        timer = self._failsafe_timer
        if timer is not None:
            await asyncio.gather(timer, return_exceptions=True)
        await self.wait_idle()
