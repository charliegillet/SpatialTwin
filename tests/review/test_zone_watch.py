"""Zone watchers report measured conditions of the checked run; the orchestrator never predicts benefit."""
from dataclasses import replace

import pytest

from backend.app.contracts import GateObservedState
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.review.basis import ReviewUnavailable, snapshot_basis
from backend.app.review.watch import run_zone_watch
from tests.review.review_helpers import authoritative, block

WATCHERS = ["zone:EVENT", "zone:WEST", "zone:EAST", "zone:RESERVE", "passage:P1", "passage:P2",
            "boundary:B1", "boundary:B2", "reserve:P3"]


def by_id(report):
    return {record.record_id: record for record in report.records}


def test_p2_closure_escalates_with_measured_records_and_routes_to_the_checked_comparison(manager):
    block(manager, "portal", "P2", "watch-p2")
    before = authoritative(manager)
    report = run_zone_watch(snapshot_basis(manager, "simulator"))
    records = by_id(report)

    assert [watcher.watcher_id for watcher in report.watchers] == WATCHERS
    assert report.escalation == "escalated"
    assert report.escalation_reasons == ["zone:EVENT:RESIDUAL_HOLDING", "passage:P2:PASSAGE_UNAVAILABLE"]
    assert report.next_step == "compare_alternatives"
    held = records["zone:EVENT:RESIDUAL_HOLDING"]
    assert (held.value, held.at_seconds, held.severity) == (60, 40, "alert")
    assert {pointer.ref for pointer in held.evidence} == {manager.current_plan.run_id}
    assert (records["boundary:B1:BOUNDARY_AT_QUOTA"].value, records["boundary:B1:BOUNDARY_AT_QUOTA"].limit) == (60, 60)
    assert records["boundary:B1:BOUNDARY_AT_QUOTA"].severity == "advisory"
    assert records["boundary:B2:BOUNDARY_IDLE"].value == 0
    assert report.delivery == "local_record_only" and "No message" in report.notice
    # A watch suggests the comparison step; it never claims the comparison's outcome.
    assert not any(word in record.summary.lower() for record in report.records for word in ("gain", "benefit", "improve"))
    for watcher in report.watchers:
        assert watcher.record_ids and all(records[record_id].watcher_id == watcher.watcher_id for record_id in watcher.record_ids)
    assert authoritative(manager) == before


def test_completed_baseline_is_nominal_and_quota_saturation_is_informational(manager):
    report = run_zone_watch(snapshot_basis(manager, "physical_serial"))
    assert (report.escalation, report.next_step, report.escalation_reasons) == ("nominal", "none", [])
    records = by_id(report)
    assert records["boundary:B1:BOUNDARY_AT_QUOTA"].severity == "info"
    assert "reserve:P3:SIMULATED_ENDPOINT" not in records
    assert records["reserve:P3:RESERVE_OBSERVED"].severity == "info"


@pytest.mark.parametrize("state", [GateObservedState.UNKNOWN, GateObservedState.TRANSIT, GateObservedState.FAULT])
def test_unconfirmed_reserve_escalates_and_waits_for_an_endpoint(manager, state):
    manager.update_physical_observation(state, "boot-review", 2, 2)
    report = run_zone_watch(snapshot_basis(manager, "simulator"))
    assert report.escalation == "escalated"
    assert "reserve:P3:RESERVE_UNCONFIRMED" in report.escalation_reasons
    assert report.next_step == "await_endpoint"


def test_reported_state_without_telemetry_is_advisory_not_observed(manager):
    manager.last_hardware_boot_id = None
    records = by_id(run_zone_watch(snapshot_basis(manager, "simulator")))
    assert records["reserve:P3:TELEMETRY_MISSING"].severity == "advisory"
    assert "reserve:P3:RESERVE_OBSERVED" not in records


def test_confirmed_open_reserve_keeps_remaining_occupants_visible_without_another_alternative(manager):
    block(manager, "portal", "P2", "watch-open")
    manager.update_physical_observation(GateObservedState.OPEN, "boot-review", 2, 2)
    report = run_zone_watch(snapshot_basis(manager, "simulator"))
    records = by_id(report)
    assert records["zone:EVENT:RESIDUAL_HOLDING"].value == 3
    assert records["boundary:B2:NOMINAL"].value == 57
    assert report.next_step == "no_allowed_alternative"


def test_closed_downstream_boundary_is_reported_without_predicting_a_reserve_benefit(manager):
    block(manager, "boundary", "B2", "watch-b2")
    report = run_zone_watch(snapshot_basis(manager, "simulator"))
    records = by_id(report)
    assert records["boundary:B2:BOUNDARY_UNAVAILABLE"].value == 0
    assert records["zone:EVENT:RESIDUAL_HOLDING"].value == 60
    assert report.next_step == "compare_alternatives"


def test_capacity_pressure_uses_the_declared_venue_capacity(manager):
    basis = snapshot_basis(manager, "simulator")
    venue = basis.venue.model_copy(deep=True)
    venue.zones["WEST"].max_capacity = 32
    records = by_id(run_zone_watch(replace(basis, venue=venue)))
    pressure = records["zone:WEST:CAPACITY_PRESSURE"]
    assert (pressure.value, pressure.limit, pressure.severity) == (30, 32, "advisory")


def test_watch_never_solves_again(manager, monkeypatch):
    basis = snapshot_basis(manager, "simulator")

    def forbidden(*args, **kwargs):
        pytest.fail("The watch must read the accepted run, not compute a new one")

    monkeypatch.setattr(FlowPlanner, "solve", forbidden)
    assert run_zone_watch(basis).run_id == manager.current_plan.run_id


def tampered(basis, **plan_updates):
    return replace(basis, plan=basis.plan.model_copy(update=plan_updates, deep=True))


def test_fail_closed_on_stale_rejected_incomplete_or_inconsistent_runs(manager):
    basis = snapshot_basis(manager, "simulator")
    plan = basis.plan
    stale = block(manager, "portal", "P1", "watch-stale")
    cases = {
        "no_checked_plan": replace(basis, plan=None),
        "stale_plan": replace(basis, context=stale),
        "plan_rejected_by_checker": tampered(basis, validator_report=plan.validator_report.model_copy(
            update={"is_valid": False, "reasons": ["injected"]})),
        "checker_evidence_incomplete": tampered(basis, validator_report=plan.validator_report.model_copy(
            update={"checks_run": [check for check in plan.validator_report.checks_run if check != "timeline_matches_flow"]})),
        "plan_not_accepted_layout": tampered(basis, alternative_id="OPEN_P3"),
    }
    lost = [dict(frame) for frame in plan.timeline]
    lost[5]["west_occupancy"] -= 1
    cases["invalid_timeline"] = tampered(basis, timeline=lost)
    for code, candidate in cases.items():
        with pytest.raises(ReviewUnavailable, match=f"^{code}$"):
            run_zone_watch(candidate)
