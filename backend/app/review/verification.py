"""Requirement-level verification report for one accepted checked run.

Measured items are re-derived here from the published envelope and the reviewed
venue spec. Checker items name the server checks they rely on. Claims outside
the model are always listed as cannot_measure; they are never guessed.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from backend.app.contracts import AlternativeId, InvestigationResult, InvestigationStatus, RunContext
from .basis import (
    BOUNDARY_FIELDS, OBSERVED_GATE_STATES, ZONE_FIELDS, EvidencePointer, ReviewBasis,
    boundary_quota, boundary_step_limit, checked_frames, reachable_zones,
)

Status = Literal["pass", "fail", "checker_attested", "cannot_measure", "not_run"]
FLOW_WITNESS_CHECKS = ("schedule_allowed_edges", "schedule_flow_conservation", "timeline_matches_flow")
SCOPE_NOTE = ("Counts describe modeled floor-transfer boundary crossings of synthetic occupants on an "
              "illustrative tabletop over a finite horizon. They are not survival, street evacuation "
              "or measurements of people.")


class Requirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requirement_id: str
    category: Literal["conservation", "capacity", "topology", "status", "context", "physical", "comparison", "scope"]
    scope: str
    statement: str
    method: Literal["measured", "checker", "outside_model"]
    status: Status
    measured: Optional[str] = None
    expected: Optional[str] = None
    value: Optional[int] = None
    limit: Optional[int] = None
    evidence: List[EvidencePointer]


class VerificationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: int
    failed: int
    checker_attested: int
    cannot_measure: int
    not_run: int


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["verification-v1"] = "verification-v1"
    base_context: RunContext
    run_id: str
    candidate_hash: str
    verdict: Literal["verified_within_model", "not_verified", "incomplete"]
    summary: VerificationSummary
    requirements: List[Requirement]
    scope_note: str = SCOPE_NOTE


def _measured(requirement_id: str, category: str, scope: str, statement: str, ok: bool,
              measured: str, expected: str, evidence: List[EvidencePointer], **values) -> Requirement:
    return Requirement(requirement_id=requirement_id, category=category, scope=scope, statement=statement,
                       method="measured", status="pass" if ok else "fail", measured=measured,
                       expected=expected, evidence=evidence, **values)


def _outside(requirement_id: str, scope: str, statement: str, measured: str,
             evidence: List[EvidencePointer]) -> Requirement:
    return Requirement(requirement_id=requirement_id, category="scope", scope=scope, statement=statement,
                       method="outside_model", status="cannot_measure", measured=measured, evidence=evidence)


def _comparison(basis: ReviewBasis, investigation: Optional[InvestigationResult]) -> Requirement:
    base = dict(requirement_id="comparison_equal_conditions", category="comparison", scope="investigation",
                statement="A saved alternative comparison uses equal population, horizon and timestep, and its gain comes from checked counts.")
    if investigation is None:
        return Requirement(**base, method="measured", status="not_run",
                           measured="No saved investigation was supplied or found for this review.", evidence=[])
    pointer = lambda field: EvidencePointer(source="investigation", ref=investigation.investigation_id, field=field)
    if not investigation.base_context.is_current(basis.context):
        return Requirement(**base, method="measured", status="not_run",
                           measured="The saved investigation belongs to an earlier context.", evidence=[pointer("base_context")])
    if investigation.status != InvestigationStatus.COMPLETED or investigation.errors:
        return Requirement(**base, method="measured", status="not_run",
                           measured=f"The saved investigation is {investigation.status.value}; no comparison is claimed.",
                           evidence=[pointer("status")])
    found = {candidate.alternative_id: candidate for candidate in investigation.candidate_envelopes}
    keep, opened = found.get(AlternativeId.KEEP_CURRENT), found.get(AlternativeId.OPEN_P3)
    ok = bool(keep and opened and investigation.provenance in ("live", "local")
              and (investigation.provenance != "live" or investigation.provider_interaction_id)
              and all(item.is_publishable and item.base_context.is_current(basis.context)
                      and item.completed_crossings + item.remaining_population == item.initial_population
                      for item in (keep, opened))
              and (keep.initial_population, keep.horizon_seconds, keep.time_step_seconds)
              == (opened.initial_population, opened.horizon_seconds, opened.time_step_seconds))
    if not ok:
        return Requirement(**base, method="measured", status="fail",
                           measured="The saved comparison lacks two current checked candidates under equal conditions.",
                           evidence=[pointer("candidate_envelopes")])
    gain = opened.completed_crossings - keep.completed_crossings
    source = "live managed investigation receipt" if investigation.provenance == "live" else "local solver comparison, no Gemini call"
    return Requirement(**base, method="measured", status="pass", value=gain,
                       measured=(f"KEEP_CURRENT {keep.completed_crossings} vs OPEN_P3 {opened.completed_crossings} "
                                 f"({gain:+d}) at {keep.initial_population} occupants / {keep.horizon_seconds}s; {source}."),
                       expected="Equal conditions; gain equals the difference of checked crossings.",
                       evidence=[pointer("candidate_envelopes.KEEP_CURRENT.completed_crossings"),
                                 pointer("candidate_envelopes.OPEN_P3.completed_crossings")])


def build_verification(basis: ReviewBasis, investigation: Optional[InvestigationResult] = None) -> VerificationReport:
    frames = checked_frames(basis)
    plan, venue = basis.plan, basis.venue
    population, last = plan.initial_population, len(frames) - 1
    items: List[Requirement] = []

    items.append(_measured("population_conserved", "conservation", "plan",
        "Every synthetic occupant is either a completed crossing or still remaining.",
        population == plan.completed_crossings + plan.remaining_population,
        f"{population} = {plan.completed_crossings} completed + {plan.remaining_population} remaining",
        "initial = completed + remaining",
        [basis.plan_pointer("initial_population"), basis.plan_pointer("completed_crossings"),
         basis.plan_pointer("remaining_population")], value=population))
    conserving = sum(sum(frame[key] for key in ZONE_FIELDS.values()) + frame["in_transit_occupancy"]
                     + frame["total_completed"] == population for frame in frames)
    items.append(_measured("frames_conserve_population", "conservation", "timeline",
        "At every stored frame, holding + in transfer + completed equals the initial population.",
        conserving == len(frames), f"{conserving} of {len(frames)} frames conserve {population}",
        f"{len(frames)} of {len(frames)}", [basis.plan_pointer("timeline[*]")],
        value=conserving, limit=len(frames)))
    located = sum(plan.zone_occupancy.get(zone, 0) for zone in ZONE_FIELDS)
    items.append(_measured("residual_located_in_zones", "conservation", "plan",
        "Every remaining occupant is held in a named zone at the horizon.",
        located == plan.remaining_population,
        f"{located} held in zones; {plan.remaining_population} remaining", "held = remaining",
        [basis.plan_pointer("zone_occupancy"), basis.plan_pointer("remaining_population")], value=located))

    for zone_id, spec in venue.zones.items():
        key = ZONE_FIELDS[zone_id]
        peak = max(frame[key] for frame in frames)
        items.append(_measured(f"zone_capacity:{zone_id}", "capacity", f"zone:{zone_id}",
            f"{spec.name} never holds more than its declared capacity.", peak <= spec.max_capacity,
            f"peak {peak}", f"≤ {spec.max_capacity}",
            [basis.plan_pointer(f"timeline[*].{key}"), basis.venue_pointer(f"zones.{zone_id}.max_capacity")],
            value=peak, limit=spec.max_capacity))

    for boundary_id in venue.boundaries:
        key = BOUNDARY_FIELDS[boundary_id]
        crossings = plan.boundary_breakdown.get(boundary_id, 0)
        evidence = [basis.plan_pointer(f"boundary_breakdown.{boundary_id}"),
                    basis.venue_pointer(f"boundaries.{boundary_id}.service_rate_per_sec")]
        if boundary_id in basis.blocked_boundaries:
            peak = max(frame[key] for frame in frames)
            items.append(_measured(f"blocked_boundary_zero_flow:{boundary_id}", "topology", f"boundary:{boundary_id}",
                f"Unavailable boundary {boundary_id} services no crossing at any frame.", peak == 0,
                f"{peak} crossings", "0", [basis.plan_pointer(f"timeline[*].{key}"), basis.state_pointer("blocked_boundaries")],
                value=peak, limit=0))
            continue
        quota = boundary_quota(basis, boundary_id)
        items.append(_measured(f"boundary_quota:{boundary_id}", "capacity", f"boundary:{boundary_id}",
            f"{boundary_id} crossings stay within its finite-horizon quota.", crossings <= quota,
            f"{crossings} crossings", f"≤ {quota}", evidence, value=crossings, limit=quota))
        step_limit = boundary_step_limit(basis, boundary_id)
        deltas = [frame[key] - (frames[index - 1][key] if index else 0) for index, frame in enumerate(frames)]
        steepest = max(deltas)
        items.append(_measured(f"boundary_step_rate:{boundary_id}", "capacity", f"boundary:{boundary_id}",
            f"{boundary_id} never services more than its per-step rate, and its cumulative count never decreases.",
            min(deltas) >= 0 and steepest <= step_limit,
            f"max {steepest} per {plan.time_step_seconds}s step", f"0 to {step_limit}",
            [basis.plan_pointer(f"timeline[*].{key}"), basis.venue_pointer(f"boundaries.{boundary_id}.service_rate_per_sec")],
            value=steepest, limit=step_limit))

    reachable = reachable_zones(basis)
    for zone_id in venue.zones:
        if zone_id in reachable:
            continue
        key = ZONE_FIELDS[zone_id]
        exits = [boundary_id for boundary_id, spec in venue.boundaries.items() if spec.from_zone == zone_id]
        peak = max(frame[key] for frame in frames)
        crossed = max((frame[BOUNDARY_FIELDS[boundary_id]] for frame in frames for boundary_id in exits), default=0)
        items.append(_measured(f"unreachable_zone_empty:{zone_id}", "topology", f"zone:{zone_id}",
            f"{venue.zones[zone_id].name} has no available route from the populated zone, so it holds no one and its boundaries service no one.",
            peak == 0 and crossed == 0, f"peak {peak} held; {crossed} crossings via {', '.join(exits) or 'no boundary'}", "0 held; 0 crossings",
            [basis.plan_pointer(f"timeline[*].{key}"), basis.state_pointer("blocked_portals"),
             basis.state_pointer("physical_gate_state")], value=peak + crossed, limit=0))

    completed = plan.completed_crossings
    expected_status = ("COMPLETE_WITHIN_MODEL" if completed == population
                       else "NO_FEASIBLE_EXIT" if completed == 0 else "PARTIAL_WITHIN_HORIZON")
    items.append(_measured("status_consistent", "status", "plan",
        "The computation status agrees with the completed count.", plan.status.value == expected_status,
        plan.status.value, expected_status, [basis.plan_pointer("status"), basis.plan_pointer("completed_crossings")]))
    terminal = frames[last]
    items.append(_measured("terminal_matches_published", "status", "plan",
        "The final stored frame equals the published totals.",
        terminal["total_completed"] == completed and terminal["in_transit_occupancy"] == 0,
        f"final frame {terminal['total_completed']} completed, {terminal['in_transit_occupancy']} in transfer",
        f"{completed} completed, 0 in transfer", [basis.plan_pointer(f"timeline[{last}]")]))
    items.append(_measured("context_current", "context", "plan",
        "The run belongs to the current full context.", plan.base_context.is_current(basis.context),
        f"scenario {plan.base_context.scenario_revision} · physical {plan.base_context.physical_revision}",
        f"scenario {basis.context.scenario_revision} · physical {basis.context.physical_revision}",
        [basis.plan_pointer("base_context.context_hash"), basis.state_pointer("context.context_hash")]))
    items.append(_measured("reserve_state_observed", "physical", "reserve:P3",
        "The reserve state used by this run is an observed endpoint state.",
        basis.gate_state in OBSERVED_GATE_STATES, f"reported {basis.gate_state.value}", "OPEN or CLOSED",
        [basis.state_pointer("physical_gate_state")]))

    report = plan.validator_report
    attested = all(check in report.checks_run for check in FLOW_WITNESS_CHECKS) and report.is_valid and not report.reasons
    items.append(Requirement(requirement_id="flow_witness_edges", category="topology", scope="plan",
        statement="Every unit of modeled flow uses an available edge within its capacity, and the schedule matches that flow.",
        method="checker", status="checker_attested" if attested else "fail",
        measured="Server checker re-enumerated allowed edges against the solver flow witness." if attested
        else "Flow-witness checks are missing or reported findings.",
        evidence=[basis.plan_pointer(f"validator_report.checks_run.{check}") for check in FLOW_WITNESS_CHECKS]))
    items.append(_comparison(basis, investigation))

    items.append(_outside("outside:survival", "real_world",
        "Survival, injury or street evacuation of real people.",
        "Not modeled. Counts are synthetic floor-transfer crossings.", [basis.plan_pointer("assumptions")]))
    items.append(_outside("outside:venue_survey", "geometry",
        "Agreement with a surveyed venue plan.",
        f"{venue.geometry_revision} is an illustrative tabletop fixture.", [basis.venue_pointer("geometry_revision")]))
    items.append(_outside("outside:declared_parameters", "parameters",
        "Measured venue capacities and boundary rates.",
        f"Capacities and rates are declared in {basis.context.parameters_revision}, not measured.",
        [basis.venue_pointer("boundaries"), basis.venue_pointer("zones")]))
    items.append(_outside("outside:camera_accuracy", "perception",
        "Real-board camera grounding accuracy.",
        "No recorded real-board capture trial set is part of this report.", []))
    items.append(_outside("outside:gate_reliability", "reserve:P3",
        "Physical gate motion and repeated-cycle reliability.",
        "Simulator endpoint; no physical motion was observed." if basis.hardware_mode == "simulator"
        else "One endpoint observation does not measure repeated-cycle reliability.",
        [basis.state_pointer("hardware_mode")]))
    items.append(_outside("outside:movement_during_actuation", "timeline",
        "Occupant movement while the gate is moving.",
        "Each run restarts from equal initial conditions.", [basis.plan_pointer("timeline[0]")]))

    counts = {status: sum(item.status == status for item in items)
              for status in ("pass", "fail", "checker_attested", "cannot_measure", "not_run")}
    summary = VerificationSummary(passed=counts["pass"], failed=counts["fail"],
                                  checker_attested=counts["checker_attested"],
                                  cannot_measure=counts["cannot_measure"], not_run=counts["not_run"])
    # A measured item that did not run is a gap, not a pass. The comparison is optional by design:
    # with no investigation supplied it is reported as not_run but does not block the verdict.
    unrun = [item for item in items if item.method == "measured" and item.status == "not_run"
             and not (item.requirement_id == "comparison_equal_conditions" and investigation is None)]
    verdict = "not_verified" if summary.failed else "incomplete" if unrun else "verified_within_model"
    return VerificationReport(base_context=basis.context, run_id=plan.run_id, candidate_hash=plan.candidate_hash,
                              verdict=verdict,
                              summary=summary, requirements=items)
