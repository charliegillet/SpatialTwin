"""Local robustness lane and claim re-verification. The local checker (``door_planner``) is the only authority.

``ScenarioEvaluator`` evaluates a door-state candidate under a scenario from the shared grammar (``scenarios.py``):
faults go through ``door_planner.evaluate_candidate``; hazard changes (untenable sensitivity, a second hazard)
re-resolve the hazard effects first. Every number it returns is a checked, modeled crossing count, never survival.

``robustness_sweep`` is the offline robustness lane (and the reference an agent's sandbox sweep is compared with):
N-1 single failures (each open door stuck closed, each usable exit blocked, partial jams), untenable-time
sensitivity and the worst second hazard per zone. ``verify_claims`` re-runs every number an agent submitted.
"""
from __future__ import annotations

import time
from typing import Any, Dict, FrozenSet, List, Mapping, Optional

from backend.app.hazard.door_planner import (
    MAX_HAZARDS, DoorPlanError, Faults, PlanContext, evaluate_candidate, evaluate_states, opened_from_states,
    plan_context, plan_context_resolved, validate_faults,
)
from backend.app.venues.model import VenueV2
from backend.app.venues.schemas import DoorPlanRequest

from .scenarios import HAZARD_TYPES, Scenario, ScenarioError, parse_scenario, scenario_hazards

MAX_SWEEP_SOLVES = 600
SWEEP_JAM_FACTOR = 0.5
SENSITIVITY_RANGE = (2, 38)  # seconds, inclusive, stepped by the venue time step
SECOND_HAZARD_TYPES = HAZARD_TYPES
SWEEP_PROVENANCE = "local_checker"
SWEEP_NOTE = ("Local checker sweep: modeled crossings of a synthetic population under declared faults; "
              "not a survival prediction. Doors in the twin are simulated.")


class ScenarioEvaluator:
    """Evaluates door-state candidates under scenarios for one hazard request, caching every resolved scenario."""

    def __init__(self, venue: VenueV2, request: DoorPlanRequest, *, context: Optional[PlanContext] = None):
        self.venue = venue
        self.base = context if context is not None else plan_context(venue, request)
        self._contexts: Dict[Any, PlanContext] = {(): self.base}
        self._defaults = {kind: d.untenable_s for kind, d in venue.hazard_defaults.items()}
        self._zones = frozenset(z.id for z in venue.zones)

    @property
    def free(self) -> List[str]:
        return list(self.base.free)

    def solves(self) -> int:
        return sum(len(ctx._cache) for ctx in self._contexts.values())

    def context_for(self, scenario: Scenario) -> PlanContext:
        if not scenario.changes_hazards:
            return self.base
        key = (scenario.untenable, scenario.second_hazard)
        ctx = self._contexts.get(key)
        if ctx is None:
            hazards = scenario_hazards(self.base.hazards, scenario, horizon=self.base.horizon,
                                       dt=self.venue.time_step_seconds, defaults=self._defaults, zones=self._zones,
                                       max_hazards=MAX_HAZARDS)
            ctx = plan_context_resolved(self.venue, self.base.horizon, hazards)
            self._contexts[key] = ctx
        return ctx

    @staticmethod
    def faults_for(scenario: Scenario) -> Faults:
        return Faults(stuck_closed=scenario.stuck_closed, blocked_exits=scenario.blocked_exits, jams=scenario.jams)

    def evaluate(self, door_states: Mapping[str, Any], scenario: Scenario | str) -> Dict[str, Any]:
        """Candidate outcome and the best state under the same scenario. Raises ScenarioError / DoorPlanError."""
        if isinstance(scenario, str):
            scenario = parse_scenario(scenario)
        opened = opened_from_states(self.base, door_states)
        ctx = self.context_for(scenario)
        faults = self.faults_for(scenario)
        validate_faults(self.venue, faults)
        # A second (gas) hazard can lock a free door; a locked door stays in its default state.
        projected = opened & frozenset(ctx.free)
        candidate = evaluate_candidate(ctx, projected, faults)
        best = evaluate_states(ctx, faults)[0]
        checked = bool(best["valid"])
        holds = checked and candidate["valid"] and (
            candidate["outcome"].completed_crossings >= best["outcome"].completed_crossings)
        return {
            "scenario": scenario.label,
            "door_states": {d: ("open" if d in projected else "closed") for d in ctx.free},
            "completed_crossings": candidate["outcome"].completed_crossings,
            "initial_population": candidate["outcome"].initial_population,
            "modeled_exposure_people_seconds": candidate["exposure"],
            "is_valid": candidate["valid"],
            "candidate_hash": candidate["outcome"].candidate_hash,
            "best_door_states": {d: ("open" if d in best["opened"] else "closed") for d in ctx.free},
            "best_completed_crossings": best["outcome"].completed_crossings,
            "best_is_valid": checked,
            "holds": holds,
        }


def expand_states(states: Mapping[str, str], free: List[str]) -> Dict[str, str]:
    """A scenario's door states keyed back to the request's controllable doors. A door a scenario hazard locked
    (gas) is absent from the scenario's free set and stays closed."""
    return {door: states.get(door, "closed") for door in free}


def _states(free: List[str], opened: FrozenSet[str]) -> Dict[str, str]:
    return {d: ("open" if d in opened else "closed") for d in free}


def single_failure_scenarios(evaluator: ScenarioEvaluator, door_states: Mapping[str, str]) -> List[str]:
    """N-1 list for a candidate: each door it leaves open stuck closed, each usable exit blocked, and a x0.5 jam
    on each controllable door it opens and on each usable exit. The sandbox kit's sweep builds the same list."""
    ctx = evaluator.base
    opened = opened_from_states(ctx, door_states)
    open_doors = sorted(d.id for d in evaluator.venue.doors if d.id not in (ctx.default_closed - opened))
    closed_exits = {x for x, t in ctx.fx.inputs_base.exit_closed_from.items() if t == 0}
    usable_exits = sorted(x.id for x in evaluator.venue.exits if x.id not in closed_exits)
    scenarios = [f"stuck_closed:{d}" for d in open_doors]
    scenarios += [f"exit_blocked:{x}" for x in usable_exits]
    scenarios += [f"jam:{d}@{SWEEP_JAM_FACTOR:.2f}" for d in sorted(opened)]
    scenarios += [f"jam:{x}@{SWEEP_JAM_FACTOR:.2f}" for x in usable_exits]
    return scenarios


def robustness_sweep(venue: VenueV2, request: DoorPlanRequest, door_states: Optional[Mapping[str, str]] = None, *,
                     evaluator: Optional[ScenarioEvaluator] = None, max_solves: int = MAX_SWEEP_SOLVES,
                     deadline: Optional[float] = None, include_sensitivity: bool = True,
                     include_second_hazards: bool = True) -> Dict[str, Any]:
    """The local robustness lane. ``door_states`` defaults to the checker's best state.

    Stops early (``truncated``) when ``max_solves`` solves or the monotonic ``deadline`` is reached; everything
    reported up to then is checked. JSON-serialisable.
    """
    started = time.perf_counter()
    evaluator = evaluator or ScenarioEvaluator(venue, request)
    ctx = evaluator.base
    ranked = evaluate_states(ctx)
    best = ranked[0]
    candidate = dict(door_states) if door_states is not None else _states(ctx.free, best["opened"])
    opened = opened_from_states(ctx, candidate)
    truncated = False

    def budget_left() -> bool:
        nonlocal truncated
        if evaluator.solves() >= max_solves or (deadline is not None and time.monotonic() >= deadline):
            truncated = True
            return False
        return True

    baseline = evaluator.evaluate(candidate, "baseline")
    single: List[Dict[str, Any]] = []
    for label in single_failure_scenarios(evaluator, candidate):
        if not budget_left():
            break
        result = evaluator.evaluate(candidate, label)
        result["delta_vs_baseline"] = result["completed_crossings"] - baseline["completed_crossings"]
        single.append(result)
    breaks = [s for s in single if not s["holds"]]

    # Other checker-valid states that tie the best at baseline: how many of their own single failures they hold.
    tied: List[Dict[str, Any]] = []
    for option in ranked:
        if not budget_left():
            break
        if not option["valid"] or option["outcome"].completed_crossings != best["outcome"].completed_crossings:
            continue
        states = _states(ctx.free, option["opened"])
        results = []
        for label in single_failure_scenarios(evaluator, states):
            if not budget_left():
                break
            results.append(evaluator.evaluate(states, label))
        tied.append({"door_states": states, "completed_crossings": option["outcome"].completed_crossings,
                     "single_failures_total": len(results),
                     "single_failures_held": sum(1 for r in results if r["holds"]),
                     "is_candidate": option["opened"] == opened})
    tied.sort(key=lambda t: (-(t["single_failures_held"] / t["single_failures_total"] if t["single_failures_total"] else 1),
                             sorted(d for d, s in t["door_states"].items() if s == "open")))

    # Fallback if a door the candidate opens jams shut: the checker's best with that door stuck closed.
    fallback: Optional[Dict[str, Any]] = None
    for door in sorted(opened):
        if not budget_left():
            break
        result = evaluator.evaluate(candidate, f"stuck_closed:{door}")
        option = {"if_jammed": door, "door_states": result["best_door_states"],
                  "completed_crossings": result["best_completed_crossings"], "is_valid": result["best_is_valid"],
                  "candidate_completed_crossings": result["completed_crossings"]}
        if fallback is None or option["candidate_completed_crossings"] < fallback["candidate_completed_crossings"]:
            fallback = option

    sensitivity: List[Dict[str, Any]] = []
    if include_sensitivity:
        dt = venue.time_step_seconds
        low, high = SENSITIVITY_RANGE
        for hazard in ctx.hazards:
            if hazard["type"] == "WATER" or hazard.get("untenable_s") is None:
                continue
            curve = []
            for seconds in range(max(low, dt), min(high, ctx.horizon - dt) + 1, dt):
                if seconds % dt or not budget_left():
                    continue
                result = evaluator.evaluate(candidate, f"untenable:{hazard['id']}={seconds}")
                curve.append({"untenable_s": seconds, "completed_crossings": result["completed_crossings"],
                              "best_completed_crossings": result["best_completed_crossings"],
                              "holds": result["holds"]})
            sensitivity.append({"hazard_id": hazard["id"], "type": hazard["type"], "zone_id": hazard["zone_id"],
                                "declared_untenable_s": hazard["untenable_s"], "curve": curve})

    second: List[Dict[str, Any]] = []
    if include_second_hazards:
        hazard_zones = {h["zone_id"] for h in ctx.hazards}
        if len(ctx.hazards) < MAX_HAZARDS:
            for zone in venue.zones:
                if zone.id in hazard_zones:
                    continue
                worst: Optional[Dict[str, Any]] = None
                for kind in SECOND_HAZARD_TYPES:
                    if not budget_left():
                        break
                    try:
                        result = evaluator.evaluate(candidate, f"second_hazard:{kind}@{zone.id}")
                    except (ScenarioError, DoorPlanError):
                        continue
                    if worst is None or result["completed_crossings"] < worst["completed_crossings"]:
                        worst = {"zone_id": zone.id, "type": kind, **{k: result[k] for k in (
                            "completed_crossings", "best_completed_crossings", "best_door_states", "holds",
                            "is_valid")}}
                if worst is not None:
                    second.append(worst)
                if truncated:
                    break

    return {
        "provenance": SWEEP_PROVENANCE,
        "candidate": candidate,
        "candidate_is_checked_best": opened == best["opened"],
        "baseline": baseline,
        "single_failures": single,
        "single_failures_total": len(single),
        "single_failures_held": len(single) - len(breaks),
        "breaks": [{"scenario": s["scenario"], "completed_crossings": s["completed_crossings"],
                    "best_door_states": s["best_door_states"], "best_completed_crossings": s["best_completed_crossings"]}
                   for s in breaks],
        "fallback_if_jammed": fallback,
        "tied_best_states": tied,
        "most_robust_tied_state": tied[0]["door_states"] if tied else None,
        "untenable_sensitivity": sensitivity,
        "worst_second_hazard": second,
        "solves": evaluator.solves(),
        "truncated": truncated,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "note": SWEEP_NOTE,
    }


def robustness_headline(sweep: Mapping[str, Any]) -> str:
    """'D9 open holds 13 of 15 single failures; breaks if D3 stuck closed; fallback if D9 jams: D4 open.'"""
    def named(states: Mapping[str, str]) -> str:
        return " + ".join(f"{d} open" for d in sorted(d for d, s in states.items() if s == "open")) \
            or "all controllable doors closed"

    text = (f"{named(sweep.get('candidate') or {})} holds {sweep.get('single_failures_held', 0)} of "
            f"{sweep.get('single_failures_total', 0)} single failures")
    breaks = [b["scenario"] for b in (sweep.get("breaks") or [])][:2]
    if breaks:
        text += "; breaks under " + ", ".join(breaks)
    tied = sweep.get("tied_best_states") or []
    if tied and not tied[0].get("is_candidate"):
        top = tied[0]
        text += (f"; {named(top['door_states'])} ties at baseline and holds {top['single_failures_held']} of "
                 f"{top['single_failures_total']}")
    fallback = sweep.get("fallback_if_jammed")
    if fallback and fallback.get("is_valid"):
        text += f"; if {fallback['if_jammed']} jams: {named(fallback.get('door_states') or {})}"
    return text + " (modeled crossings, local checker)."


def verify_claims(evaluator: ScenarioEvaluator, door_states: Mapping[str, str],
                  fallback_if_jammed: Optional[Mapping[str, str]], claims: List[Mapping[str, Any]]) -> Dict[str, Any]:
    """Re-run every claimed number with the local checker. A claim is reproduced only when the crossings match
    exactly and, when the agent gave one, the candidate hash matches too."""
    checks: List[Dict[str, Any]] = []
    for index, claim in enumerate(claims):
        applies_to = claim.get("applies_to") or "recommended"
        target = door_states if applies_to == "recommended" else fallback_if_jammed
        entry: Dict[str, Any] = {"index": index, "scenario": str(claim.get("scenario", ""))[:120],
                                 "applies_to": applies_to, "claimed_completed_crossings": claim.get("completed_crossings"),
                                 "claimed_candidate_hash": claim.get("candidate_hash"), "local_completed_crossings": None,
                                 "local_candidate_hash": None, "local_is_valid": None, "reproduced": False, "reason": None}
        try:
            if target is None:
                raise ScenarioError("claim_target_missing")
            local = evaluator.evaluate(target, str(claim.get("scenario", "")))
        except (ScenarioError, DoorPlanError) as error:
            entry["reason"] = str(error) if isinstance(error, ScenarioError) else error.code
            checks.append(entry)
            continue
        entry.update(scenario=local["scenario"], local_completed_crossings=local["completed_crossings"],
                     local_candidate_hash=local["candidate_hash"], local_is_valid=local["is_valid"])
        if local["completed_crossings"] != claim.get("completed_crossings"):
            entry["reason"] = "crossings_mismatch"
        elif claim.get("candidate_hash") not in (None, local["candidate_hash"]):
            entry["reason"] = "candidate_hash_mismatch"
        else:
            entry["reproduced"] = True
        checks.append(entry)
    reproduced = sum(1 for c in checks if c["reproduced"])
    return {"verified": reproduced, "total": len(checks), "checks": checks,
            "mismatches": [c for c in checks if not c["reproduced"]]}
