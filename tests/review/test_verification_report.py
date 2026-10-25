"""The verification report re-measures checked results and never guesses outside the model."""
from dataclasses import replace

import pytest

from backend.app.contracts import GateObservedState, InvestigationStatus
from backend.app.review.basis import ReviewUnavailable, checked_frames, snapshot_basis
from backend.app.review.verification import build_verification
from tests.review.review_helpers import block, local_investigation

OUTSIDE = ["outside:survival", "outside:venue_survey", "outside:declared_parameters",
           "outside:camera_accuracy", "outside:gate_reliability", "outside:movement_during_actuation"]


def by_id(report):
    return {item.requirement_id: item for item in report.requirements}


def assert_summary_matches(report):
    statuses = [item.status for item in report.requirements]
    assert report.summary.model_dump() == {
        "passed": statuses.count("pass"), "failed": statuses.count("fail"),
        "checker_attested": statuses.count("checker_attested"),
        "cannot_measure": statuses.count("cannot_measure"), "not_run": statuses.count("not_run")}
    assert report.verdict == ("not_verified" if report.summary.failed else "verified_within_model")  # no investigation


def test_p2_closure_report_carries_measured_values_checker_items_and_scope_limits(manager):
    block(manager, "portal", "P2", "verify-p2")
    report = build_verification(snapshot_basis(manager, "simulator"))
    items = by_id(report)
    assert report.verdict == "verified_within_model"
    assert items["population_conserved"].measured == "120 = 60 completed + 60 remaining"
    assert (items["frames_conserve_population"].value, items["frames_conserve_population"].limit) == (21, 21)
    assert (items["boundary_quota:B1"].value, items["boundary_quota:B1"].limit, items["boundary_quota:B1"].status) == (60, 60, "pass")
    assert (items["boundary_step_rate:B1"].value, items["boundary_step_rate:B1"].limit) == (3, 3)
    # With P2 unavailable and P3 observed closed, the east side has no route: it must stay empty.
    assert items["unreachable_zone_empty:EAST"].status == "pass"
    assert items["unreachable_zone_empty:RESERVE"].status == "pass"
    assert "unreachable_zone_empty:WEST" not in items
    assert items["flow_witness_edges"].status == "checker_attested"
    assert items["comparison_equal_conditions"].status == "not_run"
    assert [item.requirement_id for item in report.requirements if item.status == "cannot_measure"] == OUTSIDE
    assert all(item.method == "outside_model" for item in report.requirements if item.status == "cannot_measure")
    assert "Simulator endpoint" in items["outside:gate_reliability"].measured
    assert "not survival" in report.scope_note
    plan_refs = {pointer.ref for item in report.requirements for pointer in item.evidence if pointer.source == "checked_plan"}
    assert plan_refs == {manager.current_plan.run_id}
    assert_summary_matches(report)


def test_report_remeasures_against_the_venue_spec_instead_of_trusting_the_checker_flag(manager):
    basis = snapshot_basis(manager, "simulator")
    venue = basis.venue.model_copy(deep=True)
    venue.boundaries["B1"].service_rate_per_sec = 1.0
    venue.zones["WEST"].max_capacity = 20
    report = build_verification(replace(basis, venue=venue))
    items = by_id(report)
    assert (items["boundary_quota:B1"].status, items["boundary_quota:B1"].limit) == ("fail", 40)
    assert (items["boundary_step_rate:B1"].status, items["boundary_step_rate:B1"].limit) == ("fail", 2)
    assert (items["zone_capacity:WEST"].status, items["zone_capacity:WEST"].value) == ("fail", 30)
    assert report.verdict == "not_verified"
    assert_summary_matches(report)


def test_flow_into_a_zone_without_an_available_route_fails(manager):
    # The run was solved with P1 available; reviewing it against a P1 closure must not pass.
    basis = snapshot_basis(manager, "simulator")
    report = build_verification(replace(basis, blocked_portals=frozenset({"P1"})))
    west = by_id(report)["unreachable_zone_empty:WEST"]
    assert west.status == "fail" and west.value > 0
    assert report.verdict == "not_verified"


def test_blocked_downstream_boundary_has_zero_flow_and_an_honest_zero_comparison(manager):
    block(manager, "boundary", "B2", "verify-b2")
    investigation = local_investigation(manager)
    report = build_verification(snapshot_basis(manager, "simulator"), investigation)
    items = by_id(report)
    assert items["blocked_boundary_zero_flow:B2"].status == "pass"
    assert "boundary_quota:B2" not in items
    comparison = items["comparison_equal_conditions"]
    assert (comparison.status, comparison.value) == ("pass", 0)
    assert "local solver comparison, no Gemini call" in comparison.measured


def test_saved_comparison_is_checked_for_currentness_and_equal_conditions(manager):
    block(manager, "portal", "P2", "verify-compare")
    investigation = local_investigation(manager)
    basis = snapshot_basis(manager, "simulator")
    comparison = by_id(build_verification(basis, investigation))["comparison_equal_conditions"]
    assert (comparison.status, comparison.value) == ("pass", 57)
    assert comparison.measured.startswith("KEEP_CURRENT 60 vs OPEN_P3 117 (+57)")

    unequal = investigation.model_copy(deep=True)
    unequal.candidate_envelopes[1].horizon_seconds = 60
    assert by_id(build_verification(basis, unequal))["comparison_equal_conditions"].status == "fail"
    unverified_live = investigation.model_copy(update={"provenance": "live", "provider_interaction_id": None})
    assert by_id(build_verification(basis, unverified_live))["comparison_equal_conditions"].status == "fail"
    incomplete = investigation.model_copy(update={"status": InvestigationStatus.INCOMPLETE})
    assert by_id(build_verification(basis, incomplete))["comparison_equal_conditions"].status == "not_run"

    block(manager, "portal", "P1", "verify-later")
    later = by_id(build_verification(snapshot_basis(manager, "simulator"), investigation))
    assert later["comparison_equal_conditions"].status == "not_run"
    assert "earlier context" in later["comparison_equal_conditions"].measured


@pytest.mark.parametrize("state", [GateObservedState.UNKNOWN, GateObservedState.TRANSIT, GateObservedState.FAULT])
def test_unconfirmed_reserve_state_is_a_failed_physical_requirement(manager, state):
    manager.update_physical_observation(state, "boot-review", 2, 2)
    report = build_verification(snapshot_basis(manager, "physical_serial"))
    assert by_id(report)["reserve_state_observed"].status == "fail"
    assert report.verdict == "not_verified"
    assert "repeated-cycle" in by_id(report)["outside:gate_reliability"].measured


def test_missing_flow_witness_checks_cannot_be_attested(manager):
    basis = snapshot_basis(manager, "simulator")
    checks = [check for check in basis.plan.validator_report.checks_run if check != "schedule_allowed_edges"]
    plan = basis.plan.model_copy(update={"validator_report": basis.plan.validator_report.model_copy(update={"checks_run": checks})})
    report = build_verification(replace(basis, plan=plan))
    assert by_id(report)["flow_witness_edges"].status == "fail"


def test_report_is_unavailable_without_a_current_checked_run(manager):
    basis = snapshot_basis(manager, "simulator")
    with pytest.raises(ReviewUnavailable, match="^no_checked_plan$"):
        build_verification(replace(basis, plan=None))
    with pytest.raises(ReviewUnavailable, match="^stale_plan$"):
        build_verification(replace(basis, context=block(manager, "portal", "P2", "verify-stale")))


def test_unrun_measured_item_makes_the_verdict_incomplete_not_verified(manager):
    block(manager, "portal", "P2", "verify-incomplete")
    basis = snapshot_basis(manager, "simulator")
    investigation = local_investigation(manager)
    assert build_verification(basis, investigation).verdict == "verified_within_model"
    # A supplied but unusable comparison did not run: not a verified result.
    incomplete = investigation.model_copy(update={"status": InvestigationStatus.INCOMPLETE})
    report = build_verification(basis, incomplete)
    assert by_id(report)["comparison_equal_conditions"].status == "not_run"
    assert report.summary.failed == 0 and report.verdict == "incomplete"
    # No investigation supplied: the optional comparison does not block the verdict.
    assert build_verification(basis).verdict == "verified_within_model"
    # A failure still dominates.
    unequal = investigation.model_copy(deep=True)
    unequal.candidate_envelopes[1].horizon_seconds = 60
    assert build_verification(basis, unequal).verdict == "not_verified"


@pytest.mark.parametrize("field,bad", [("step", 1.0), ("step", True), ("time_seconds", 2.0)])
def test_timeline_indices_must_be_exact_ints(manager, field, bad):
    basis = snapshot_basis(manager, "simulator")
    timeline = [dict(frame) for frame in basis.plan.timeline]
    index = 1
    timeline[index][field] = bad if field == "step" else float(timeline[index]["time_seconds"])
    plan = basis.plan.model_copy(update={"timeline": timeline})
    with pytest.raises(ReviewUnavailable, match="invalid_timeline"):
        checked_frames(replace(basis, plan=plan))


def test_step_limit_follows_the_planner_minimum_of_one(manager):
    from types import SimpleNamespace
    from backend.app.review.basis import boundary_quota, boundary_step_limit
    venue = SimpleNamespace(boundaries={"B": SimpleNamespace(service_rate_per_sec=0.4)})
    basis = SimpleNamespace(venue=venue, plan=SimpleNamespace(time_step_seconds=2, horizon_seconds=40))
    assert boundary_step_limit(basis, "B") == 1  # int(0.8) == 0 would wrongly fail a legal step
    assert boundary_quota(basis, "B") == 16
