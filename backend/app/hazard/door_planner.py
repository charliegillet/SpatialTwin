"""Local door planner for any accepted venue (building-v2 or a compiled one).

Free set F = doors the planner may open (planner_can_open, default closed, not gas-locked). All 2^|F| states are
solved with the forked v2 solver and checked independently; the best checker-valid state wins. AI is not involved:
the plan is hypothetical and local (provenance local_door_planner_v1).

``evaluate_with_faults`` evaluates one door-state candidate under declared faults (a door stuck closed, an exit
blocked from t=0, a partial jam as a throughput multiplier). It is the same enumeration ``plan_doors`` uses, so a
fault-free evaluation is the planner's own number; the agent team uses it to re-verify every number an agent
claims and as the offline robustness lane. Faults only remove or slow capacity; they never add any.
"""
from __future__ import annotations

import itertools
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field, replace
from typing import Any, Dict, FrozenSet, Iterator, List, Mapping, Optional, Tuple
from uuid import uuid4

from backend.app.hazard.announce import build_announcement
from backend.app.hazard.effects_v2 import HAZARDOUS, HazardEffects, compute_effects
from backend.app.planner.checker_v2 import EXIT_COLLECTOR, SOURCE, UNASSIGNED, SolveInputs
from backend.app.planner.flow_solver_v2 import FlowSolverV2, SolveOutcome
from backend.app.venues.model import VenueV2
from backend.app.venues.schemas import (
    Baseline, DoorPlanRequest, DoorPlanResponse, HazardEcho, LightSegment, PlanAlternative, PlanDoor,
    PlanExit, PlanLights, PlanOutcome, PlanRoute, PlanZone, Position, TimelineFrameV2, ValidatorReportV2,
)

EXPOSURE_LABEL = "Modeled people-seconds in hazard zones; not a casualty or survival prediction"
MAX_HAZARDS = 6
MIN_HORIZON, MAX_HORIZON = 10, 120
EXIT_CODE = {"green_flash": "F", "green": "g", "red_x": "X", "red_static": "S"}

MIN_PIXELS = 24
# Bounded: compiled venues each add a geometry revision.
# Keyed by venue id too: two venues may share a geometry revision string.
_NO_HAZARD_CACHE: "OrderedDict[Tuple[str, str, int], int]" = OrderedDict()
_NO_HAZARD_CACHE_SIZE = 64


def pixel_count_for(venue: VenueV2) -> int:
    return max([MIN_PIXELS] + [end + 1 for _, end in venue.led_map.values()])


class DoorPlanError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _is_even_step(value: float, dt: int) -> bool:
    return float(value).is_integer() and int(value) % dt == 0


def resolve_request(venue: VenueV2, request: DoorPlanRequest) -> Tuple[int, List[dict]]:
    dt = venue.time_step_seconds
    if len(request.hazards) > MAX_HAZARDS:
        raise DoorPlanError("too_many_hazards")
    ids = [h.id for h in request.hazards]
    if len(set(ids)) != len(ids):
        raise DoorPlanError("duplicate_hazard_id")
    horizon = venue.default_horizon_seconds if request.horizon_seconds is None else request.horizon_seconds
    if not _is_even_step(horizon, dt) or not MIN_HORIZON <= horizon <= MAX_HORIZON:
        raise DoorPlanError("invalid_horizon")
    horizon = int(horizon)
    resolved: List[dict] = []
    for h in request.hazards:
        zone_id = venue.locate_zone(h.position.x, h.position.y)
        if zone_id is None:
            raise DoorPlanError("outside_building")
        if h.zone_id is not None and h.zone_id != zone_id:
            raise DoorPlanError("zone_mismatch")
        if h.type == "WATER":
            tenable = None
        elif h.untenable_s is not None:
            if not _is_even_step(h.untenable_s, dt) or not 0 <= h.untenable_s < horizon:
                raise DoorPlanError("invalid_untenable_time")
            tenable = int(h.untenable_s)
        else:
            default = venue.hazard_defaults[h.type].untenable_s
            # a venue default longer than a short horizon is capped to the last step rather than refused
            tenable = None if default is None else min(default, horizon - dt)
        resolved.append({"id": h.id, "type": h.type, "zone_id": zone_id, "untenable_s": tenable,
                         "source": h.source, "position": h.position, "proposal_id": h.proposal_id})
    return horizon, resolved


def _exposure(outcome: SolveOutcome, hazard_zones: Dict[str, str]) -> int:
    if not hazard_zones:
        return 0
    dt = outcome.time_step_seconds
    return sum(sum(frame["occupancy"].get(z, 0) for z in hazard_zones) * dt for frame in outcome.timeline[:-1])


def _decompose_routes(venue: VenueV2, outcome: SolveOutcome, multipliers: Dict[str, Tuple[float, float]]) -> List[PlanRoute]:
    """Deterministic unit-path decomposition of the witness, grouped by (origin, zone path, exit)."""
    flow: Dict[Any, Dict[Any, int]] = {u: {v: a for v, a in d.items() if a > 0} for u, d in outcome.witness.items()}
    groups: Dict[Tuple[str, Tuple[str, ...], str], int] = {}
    for zone in sorted(venue.zones, key=lambda z: z.id):
        for _ in range(flow.get(SOURCE, {}).get((zone.id, 0), 0)):
            node: Any = (zone.id, 0)
            flow[SOURCE][node] -= 1
            path = [zone.id]
            exit_id = None
            while True:
                options = sorted((v for v, a in flow.get(node, {}).items() if a > 0), key=str)
                if not options:
                    break
                nxt = options[0]
                flow[node][nxt] -= 1
                if isinstance(nxt, tuple):
                    if nxt[0] != path[-1]:
                        path.append(nxt[0])
                    node = nxt
                elif nxt == UNASSIGNED:
                    break
                elif isinstance(nxt, str) and nxt.startswith("X_"):
                    exit_id = nxt[2:].rsplit("_", 1)[0]  # X_<exit id>_<step>; exit ids may contain "_"
                    break
                else:
                    break
            if exit_id is not None:
                key = (zone.id, tuple(path), exit_id)
                groups[key] = groups.get(key, 0) + 1
    routes: List[PlanRoute] = []
    for (origin, path, exit_id), people in groups.items():
        via = []
        for a, b in zip(path, path[1:]):
            door = venue.door_between(a, b)
            via.append(door.id if door else "?")
        slowed = any(multipliers.get(e, (1.0, 1.0))[0] < 1.0 or multipliers.get(e, (1.0, 1.0))[1] > 1.0
                     for e in via + [exit_id])
        routes.append(PlanRoute(origin=origin, path=list(path), via_doors=via, exit_id=exit_id, people=people, slowed=slowed))
    routes.sort(key=lambda r: (-r.people, r.origin, r.exit_id, r.path))
    return routes


def _no_hazard_completed(venue: VenueV2, solver: FlowSolverV2, horizon: int) -> int:
    key = (venue.venue_id, venue.geometry_revision, horizon)
    if key in _NO_HAZARD_CACHE:
        _NO_HAZARD_CACHE.move_to_end(key)
        return _NO_HAZARD_CACHE[key]
    closed = frozenset(d.id for d in venue.doors if d.default_state == "closed")
    completed = solver.solve(SolveInputs(closed_doors=closed), horizon).completed_crossings
    _NO_HAZARD_CACHE[key] = completed
    while len(_NO_HAZARD_CACHE) > _NO_HAZARD_CACHE_SIZE:
        _NO_HAZARD_CACHE.popitem(last=False)
    return completed


# --- Candidate evaluation (shared by plan_doors, evaluate_with_faults and the robustness sweep) ---------------

MAX_FAULT_TERMS = 8  # elements named in one Faults value; the agent's scenario grammar allows at most 3


@dataclass(frozen=True)
class Faults:
    """Declared faults layered on a hazard scenario; every one only removes or slows capacity.

    * ``stuck_closed``: doors that cannot open for the whole horizon (whatever the candidate says);
    * ``blocked_exits``: exits blocked from t=0;
    * ``jams``: (door or exit id, throughput factor in (0, 1)) pairs; the factor multiplies any hazard slowdown
      already on that element (a half-jammed door in smoke passes x0.25), travel time is unchanged.
    """

    stuck_closed: FrozenSet[str] = frozenset()
    blocked_exits: FrozenSet[str] = frozenset()
    jams: Tuple[Tuple[str, float], ...] = ()

    @property
    def empty(self) -> bool:
        return not (self.stuck_closed or self.blocked_exits or self.jams)

    def canonical(self) -> dict:
        return {"stuck_closed": sorted(self.stuck_closed), "blocked_exits": sorted(self.blocked_exits),
                "jams": sorted([element, factor] for element, factor in self.jams)}


NO_FAULTS = Faults()


@dataclass
class PlanContext:
    """One resolved hazard scenario: effects, solver and the free set, reused across candidates and faults."""

    venue: VenueV2
    horizon: int
    hazards: List[dict]
    fx: HazardEffects
    solver: FlowSolverV2
    default_closed: FrozenSet[str]
    free: List[str]
    _cache: Dict[Any, dict] = field(default_factory=dict, repr=False)


def plan_context_resolved(venue: VenueV2, horizon: int, hazards: List[dict]) -> PlanContext:
    """Context from already-resolved hazards (id, type, zone_id, untenable_s, ...), as ``resolve_request`` returns."""
    fx: HazardEffects = compute_effects(venue, hazards, horizon)
    default_closed = frozenset(d.id for d in venue.doors if d.default_state == "closed")
    free = sorted(d.id for d in venue.doors
                  if d.planner_can_open and d.default_state == "closed" and d.id not in fx.gas_locked_doors)
    return PlanContext(venue=venue, horizon=horizon, hazards=hazards, fx=fx, solver=FlowSolverV2(venue),
                       default_closed=default_closed, free=free)


def plan_context(venue: VenueV2, request: DoorPlanRequest) -> PlanContext:
    horizon, hazards = resolve_request(venue, request)
    return plan_context_resolved(venue, horizon, hazards)


def free_states(free: List[str]) -> Iterator[FrozenSet[str]]:
    """Every open/closed state of the free set, as the set of opened doors, in the planner's fixed order."""
    for bits in itertools.product((False, True), repeat=len(free)):
        yield frozenset(d for d, on in zip(free, bits) if on)


def validate_faults(venue: VenueV2, faults: Faults) -> None:
    doors = {d.id for d in venue.doors}
    exits = {e.id for e in venue.exits}
    if len(faults.stuck_closed) + len(faults.blocked_exits) + len(faults.jams) > MAX_FAULT_TERMS:
        raise DoorPlanError("too_many_faults")
    if any(door not in doors for door in faults.stuck_closed):
        raise DoorPlanError("unknown_fault_door")
    if any(exit_id not in exits for exit_id in faults.blocked_exits):
        raise DoorPlanError("unknown_fault_exit")
    seen = set()
    for element, factor in faults.jams:
        if element not in doors and element not in exits:
            raise DoorPlanError("unknown_fault_element")
        if element in seen:
            raise DoorPlanError("duplicate_fault_element")
        seen.add(element)
        if type(factor) not in (int, float) or not math.isfinite(factor) or not 0 < factor < 1:
            raise DoorPlanError("invalid_jam_factor")


def apply_faults(ctx: PlanContext, opened: FrozenSet[str], faults: Faults = NO_FAULTS) -> SolveInputs:
    """Solver inputs for one candidate. Without faults this is exactly the planner's own input."""
    inputs = replace(ctx.fx.inputs_base, closed_doors=ctx.default_closed - opened)
    if faults.empty:
        return inputs
    exit_closed = dict(inputs.exit_closed_from)
    for exit_id in faults.blocked_exits:
        exit_closed[exit_id] = 0
    multipliers = dict(inputs.multipliers)
    for element, factor in faults.jams:
        thr, trv = multipliers.get(element, (1.0, 1.0))
        multipliers[element] = (thr * float(factor), trv)
    return replace(inputs, closed_doors=inputs.closed_doors | faults.stuck_closed,
                   exit_closed_from=exit_closed, multipliers=multipliers)


def _rank_key(candidate: dict) -> tuple:
    return (not candidate["valid"], -candidate["outcome"].completed_crossings, candidate["exposure"],
            len(candidate["opened"]), tuple(sorted(candidate["opened"])))


def evaluate_candidate(ctx: PlanContext, opened: FrozenSet[str], faults: Faults = NO_FAULTS) -> dict:
    """Solve and independently check one candidate; cached per context (the solver is deterministic)."""
    key = (opened, faults.stuck_closed, faults.blocked_exits, tuple(sorted(faults.jams)))
    cached = ctx._cache.get(key)
    if cached is not None:
        return cached
    outcome = ctx.solver.solve(apply_faults(ctx, opened, faults), ctx.horizon)
    candidate = {"opened": opened, "outcome": outcome, "valid": outcome.validator_report["is_valid"],
                 "exposure": _exposure(outcome, ctx.fx.hazard_zone_types)}
    ctx._cache[key] = candidate
    return candidate


def evaluate_states(ctx: PlanContext, faults: Faults = NO_FAULTS) -> List[dict]:
    """Every free-set state under ``faults``, ranked like the planner (valid, crossings, exposure, fewest opened)."""
    candidates = [evaluate_candidate(ctx, opened, faults) for opened in free_states(ctx.free)]
    candidates.sort(key=_rank_key)
    return candidates


@dataclass(frozen=True)
class FaultOutcome:
    """Checked outcome of one door-state candidate under declared faults. Modeled crossings, never survival."""

    door_states: Dict[str, str]
    faults: Dict[str, Any]
    completed_crossings: int
    initial_population: int
    remaining_population: int
    modeled_exposure_people_seconds: int
    is_valid: bool
    candidate_hash: str
    status: str
    exit_breakdown: Dict[str, int]

    def as_dict(self) -> Dict[str, Any]:
        return {"door_states": dict(self.door_states), "faults": self.faults,
                "completed_crossings": self.completed_crossings, "initial_population": self.initial_population,
                "remaining_population": self.remaining_population,
                "modeled_exposure_people_seconds": self.modeled_exposure_people_seconds,
                "is_valid": self.is_valid, "candidate_hash": self.candidate_hash, "status": self.status,
                "exit_breakdown": dict(self.exit_breakdown)}


def opened_from_states(ctx: PlanContext, door_states: Mapping[str, Any]) -> FrozenSet[str]:
    """Strict: exactly the free doors, each 'open' or 'closed'."""
    if not isinstance(door_states, Mapping) or set(door_states) != set(ctx.free):
        raise DoorPlanError("invalid_door_states")
    if any(type(state) is not str or state not in ("open", "closed") for state in door_states.values()):
        raise DoorPlanError("invalid_door_states")
    return frozenset(door for door, state in door_states.items() if state == "open")


def fault_outcome(ctx: PlanContext, candidate: dict, faults: Faults = NO_FAULTS) -> FaultOutcome:
    outcome: SolveOutcome = candidate["outcome"]
    return FaultOutcome(
        door_states={d: ("open" if d in candidate["opened"] else "closed") for d in ctx.free},
        faults=faults.canonical(), completed_crossings=outcome.completed_crossings,
        initial_population=outcome.initial_population, remaining_population=outcome.remaining_population,
        modeled_exposure_people_seconds=candidate["exposure"], is_valid=candidate["valid"],
        candidate_hash=outcome.candidate_hash, status=outcome.status, exit_breakdown=dict(outcome.exit_breakdown))


def evaluate_with_faults(venue: VenueV2, request: Optional[DoorPlanRequest], door_states: Mapping[str, Any],
                         faults: Optional[Faults] = None, *, context: Optional[PlanContext] = None) -> FaultOutcome:
    """Evaluate one door-state candidate (exactly the free doors) under ``faults``.

    With no faults the number equals the planner's own alternative for that state. Pass ``context`` to reuse one
    resolved scenario across many calls (the robustness sweep and claim verification do).
    """
    ctx = context if context is not None else plan_context(venue, request)
    faults = faults or NO_FAULTS
    validate_faults(ctx.venue, faults)
    opened = opened_from_states(ctx, door_states)
    return fault_outcome(ctx, evaluate_candidate(ctx, opened, faults), faults)


def zone_point(venue: VenueV2, zone_id: str) -> Optional[Tuple[float, float]]:
    """A point that ``locate_zone`` maps to ``zone_id`` (vertex mean first, then a coarse grid), or None."""
    zone = next((z for z in venue.zones if z.id == zone_id), None)
    if zone is None:
        return None
    xs = [p[0] for p in zone.polygon]
    ys = [p[1] for p in zone.polygon]
    tries = [(sum(xs) / len(xs), sum(ys) / len(ys))]
    for i in range(1, 8):
        for j in range(1, 8):
            tries.append((min(xs) + (max(xs) - min(xs)) * i / 8, min(ys) + (max(ys) - min(ys)) * j / 8))
    for x, y in tries:
        if venue.locate_zone(x, y) == zone_id:
            return (round(x, 3), round(y, 3))
    return None


def plan_doors(venue: VenueV2, request: DoorPlanRequest) -> DoorPlanResponse:
    started = time.perf_counter()
    ctx = plan_context(venue, request)
    horizon, hazards, fx, solver = ctx.horizon, ctx.hazards, ctx.fx, ctx.solver
    dt = venue.time_step_seconds
    free = ctx.free

    # Enumerate every open/closed state of the free set.
    candidates = evaluate_states(ctx)
    best = candidates[0]
    chosen: SolveOutcome = best["outcome"]
    # With no checker-valid state the doors stay at their defaults on screen and no announcement is made;
    # the UI withholds the numbers (validator_report.is_valid is false).
    checked = best["valid"]
    shown_opened = best["opened"] if checked else frozenset()
    baseline = next(c for c in candidates if not c["opened"])
    by_opened = {c["opened"]: c for c in candidates}
    no_hazard = _no_hazard_completed(venue, solver, horizon)
    mult = fx.inputs_base.multipliers

    # Doors
    doors: List[PlanDoor] = []
    for d in venue.doors:
        e = fx.door_effects[d.id]
        opened_by_planner = d.id in shown_opened
        denied = sorted(e.entry_denied_into)
        released = e.released and not e.gas_held
        state = d.default_state
        decided = "default"
        lamp = "green"
        locked = e.gas_locked
        reasons: List[str] = list(e.reasons) if not released else [r for r in e.reasons]
        if locked:
            decided, lamp = "gas_lock", "red_static"
        elif e.gas_held:
            decided, lamp = "hazard_rule", "red_static"
        elif opened_by_planner:
            state, decided = "open", "door_planner"
            without = by_opened.get(best["opened"] - {d.id})
            delta = chosen.completed_crossings - without["outcome"].completed_crossings if without else 0
            if delta > 0:
                text = f"opened: +{delta} modeled crossings"
            elif without and best["exposure"] < without["exposure"]:
                text = "opened: lowers modeled exposure"
            else:
                text = "opened"
            if denied:
                text += "; egress only; entry into " + ", ".join(denied) + " denied"
            reasons = [text]
            lamp = "red" if denied else "green"
        elif released:
            state, decided, lamp = "closed", "hazard_rule", "red"
        elif denied:
            decided, lamp = "hazard_rule", "red"
            reasons = reasons or ["Entry into " + ", ".join(denied) + " denied"]
        elif d.default_state == "closed":
            lamp = "off"
        if not reasons:
            reasons = ["Default state" + (" (closed, kept closed)" if d.default_state == "closed" else "")]
        if (state == "closed") != (d.default_state == "closed"):
            pass
        doors.append(PlanDoor(id=d.id, state=state, lamp=lamp, entry_denied_into=denied, reason="; ".join(reasons),
                              actuation=d.actuation, changed=state != d.default_state, locked=locked, decided_by=decided))

    # Exits
    exits: List[PlanExit] = []
    for x in venue.exits:
        e = fx.exit_effects[x.id]
        crossed = chosen.exit_breakdown[x.id]
        if e.gas:
            lamp = "red_static"
        elif e.unsafe:
            lamp = "red_x"
        else:
            lamp = "green_flash" if crossed > 0 else "green"
        if e.unsafe:
            reason = "; ".join(e.reasons)
        else:
            slow = mult.get(x.id, (1.0, 1.0))[0] < 1.0
            reason = (f"Safe: {crossed} modeled crossings" if crossed else "Safe; no modeled flow") + ("; slowed" if slow else "")
        exits.append(PlanExit(id=x.id, zone=x.zone, safe=not e.unsafe, lamp=lamp, reason=reason, modeled_crossings=crossed))

    # Zones
    zones = [PlanZone(id=z.id, status=fx.zone_effects[z.id].status, hazard_type=fx.zone_effects[z.id].hazard_type,
                      untenable_at_s=fx.zone_effects[z.id].untenable_at_s,
                      throughput_multiplier=fx.zone_effects[z.id].throughput_multiplier,
                      initial_occupants=z.initial_occupants, remaining_at_horizon=chosen.zone_remaining[z.id])
             for z in venue.zones]

    routes = _decompose_routes(venue, chosen, mult)

    # Lights (screen only): at least the 24 pixels of building-v2, more if the venue's led_map needs them
    door_by_id = {d.id: d for d in doors}
    exit_by_id = {x.id: x for x in exits}
    pixel_count = pixel_count_for(venue)
    px = ["0"] * pixel_count
    segments: List[LightSegment] = []
    for element, (start, end) in venue.led_map.items():
        if element in exit_by_id:
            code = EXIT_CODE[exit_by_id[element].lamp]
        else:
            pd = door_by_id[element]
            code = "L" if pd.locked else ("O" if pd.state == "open" else "B")
        for i in range(start, min(end, pixel_count - 1) + 1):
            px[i] = code
        segments.append(LightSegment(element_id=element, range=[start, end], code=code))

    # Advisories
    advisories = list(fx.advisories)
    if not checked:
        advisories.insert(0, "No checked plan: every door state failed the independent checker, so no numbers are shown.")
    simulated = [d.id for d in venue.doors if d.actuation == "simulated_servo" and d.id in shown_opened]
    if simulated:
        advisories.append(", ".join(simulated) + " is a simulated servo door, driven by the virtual door controller.")
    if chosen.remaining_population:
        for z in venue.zones:
            left = chosen.zone_remaining[z.id]
            if not left:
                continue
            ze = fx.zone_effects[z.id]
            if ze.untenable_at_s is not None:
                cause = f"{ze.hazard_type.lower() if ze.hazard_type else 'hazard'} made the zone untenable at {ze.untenable_at_s} s " \
                        f"and the doors and exits out of it could not take everyone in that window"
            else:
                cause = "the modeled doors and exits could not carry everyone out within the horizon"
            advisories.append(f"{left} modeled occupants remain in {z.name} at {horizon} s: {cause}. "
                              "This is a modeled outcome of the declared assumptions, not an intended one.")

    alternatives = [PlanAlternative(
        door_states={d: ("open" if d in c["opened"] else "closed") for d in free},
        completed_crossings=c["outcome"].completed_crossings, modeled_exposure_people_seconds=c["exposure"],
        is_valid=c["valid"], rank=i + 1, run_id=c["outcome"].run_id) for i, c in enumerate(candidates)]

    echo = [HazardEcho(id=h["id"], type=h["type"], position=Position(x=h["position"].x, y=h["position"].y),
                       zone_id=h["zone_id"], source=h["source"], untenable_s=h["untenable_s"],
                       proposal_id=h["proposal_id"], effective=fx.effective[h["id"]], effects=fx.hazard_notes[h["id"]])
            for h in hazards]

    outcome_model = PlanOutcome(
        run_id=chosen.run_id, candidate_hash=chosen.candidate_hash, status=chosen.status,
        initial_population=chosen.initial_population, completed_crossings=chosen.completed_crossings,
        remaining_population=chosen.remaining_population, horizon_seconds=chosen.horizon_seconds,
        time_step_seconds=chosen.time_step_seconds, exit_breakdown=chosen.exit_breakdown,
        timeline=[TimelineFrameV2(**f) for f in chosen.timeline],
        validator_report=ValidatorReportV2(**chosen.validator_report),
        modeled_exposure_people_seconds=best["exposure"], exposure_label=EXPOSURE_LABEL)

    return DoorPlanResponse(
        plan_id=f"dp-{uuid4().hex}", venue_id=venue.venue_id, geometry_revision=venue.geometry_revision,
        hazards=echo, doors=doors, exits=exits, zones=zones, routes=routes, chosen=outcome_model,
        baseline=Baseline(completed_crossings=baseline["outcome"].completed_crossings, run_id=baseline["outcome"].run_id),
        no_hazard_completed=no_hazard, alternatives=alternatives,
        lights=PlanLights(px="".join(px), segments=segments, held=list(fx.held)),
        advisories=advisories,
        announcement="" if not checked else build_announcement(
            {z.id: z.name for z in venue.zones}, {x.id: x.name for x in venue.exits},
            [{"type": h.type, "zone_id": h.zone_id, "effective": h.effective} for h in echo],
            [{"id": x.id, "safe": x.safe, "modeled_crossings": x.modeled_crossings} for x in exits],
            [{"id": d.id, "zones": next(v.zones for v in venue.doors if v.id == d.id), "decided_by": d.decided_by,
              "state": d.state} for d in doors]),
        model_assumptions=fx.assumptions + [
            f"Horizon {horizon} s, step {dt} s, synthetic population {chosen.initial_population}.",
            "Modeled exposure sums occupancy x step over the first T steps of the timeline, in zones with FIRE, SMOKE, GAS or CHEMICAL."],
        timings_ms=round((time.perf_counter() - started) * 1000.0, 2))
