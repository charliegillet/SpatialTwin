"""Local door planner for any accepted venue (building-v2 or a compiled one).

Free set F = doors the planner may open (planner_can_open, default closed, not gas-locked). All 2^|F| states are
solved with the forked v2 solver and checked independently; the best checker-valid state wins. AI is not involved:
the plan is hypothetical and local (provenance local_door_planner_v1).
"""
from __future__ import annotations

import itertools
import time
from collections import OrderedDict
from dataclasses import replace
from typing import Any, Dict, List, Optional, Tuple
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
_NO_HAZARD_CACHE: "OrderedDict[Tuple[str, int], int]" = OrderedDict()
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
    key = (venue.geometry_revision, horizon)
    if key in _NO_HAZARD_CACHE:
        _NO_HAZARD_CACHE.move_to_end(key)
        return _NO_HAZARD_CACHE[key]
    closed = frozenset(d.id for d in venue.doors if d.default_state == "closed")
    completed = solver.solve(SolveInputs(closed_doors=closed), horizon).completed_crossings
    _NO_HAZARD_CACHE[key] = completed
    while len(_NO_HAZARD_CACHE) > _NO_HAZARD_CACHE_SIZE:
        _NO_HAZARD_CACHE.popitem(last=False)
    return completed


def plan_doors(venue: VenueV2, request: DoorPlanRequest) -> DoorPlanResponse:
    started = time.perf_counter()
    horizon, hazards = resolve_request(venue, request)
    dt = venue.time_step_seconds
    fx: HazardEffects = compute_effects(venue, hazards, horizon)
    solver = FlowSolverV2(venue)

    default_closed = frozenset(d.id for d in venue.doors if d.default_state == "closed")
    free = sorted(d.id for d in venue.doors
                  if d.planner_can_open and d.default_state == "closed" and d.id not in fx.gas_locked_doors)

    # Enumerate every open/closed state of the free set.
    candidates: List[dict] = []
    for bits in itertools.product((False, True), repeat=len(free)):
        opened = frozenset(d for d, on in zip(free, bits) if on)
        inputs = replace(fx.inputs_base, closed_doors=default_closed - opened)
        outcome = solver.solve(inputs, horizon)
        candidates.append({"opened": opened, "outcome": outcome,
                           "valid": outcome.validator_report["is_valid"],
                           "exposure": _exposure(outcome, fx.hazard_zone_types)})
    candidates.sort(key=lambda c: (not c["valid"], -c["outcome"].completed_crossings, c["exposure"],
                                   len(c["opened"]), tuple(sorted(c["opened"]))))
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
        advisories.append(", ".join(simulated) + " is a simulated servo door; the physical gate is on the tabletop board.")
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
