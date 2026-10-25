"""Independent timeline checks: a plausible aggregate must not hide lost people."""

from copy import deepcopy

import pytest

from backend.app.contracts import AlternativeId, ComputationStatus, RunContext
from backend.app.planner.checker import PlanChecker
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.planner.model import get_default_venue_graph


ZONE_FIELDS = {
    "EVENT": "event_occupancy",
    "WEST": "west_occupancy",
    "EAST": "east_occupancy",
    "RESERVE": "reserve_occupancy",
}
TIMELINE_CHECKS = {
    "timeline_population_conservation",
    "timeline_boundary_rates",
    "timeline_terminal_consistency",
}


@pytest.fixture
def context():
    return RunContext(
        geometry_revision="geom-shack15-v1",
        scenario_revision=1,
        physical_revision=1,
    )


@pytest.fixture
def checked_trace(context):
    # Authored independently of FlowPlanner: two people use P1/B1 every slot.
    # At each sample, arrivals and boundary service happened, departures did not.
    frames = [
        {
            "step": step,
            "time_seconds": step * 2,
            "event_occupancy": 6 - step * 2,
            "west_occupancy": 0,
            "east_occupancy": 0,
            "reserve_occupancy": 0,
            "in_transit_occupancy": 0,
            "b1_cumulative": step * 2,
            "b2_cumulative": 0,
            "total_completed": step * 2,
        }
        for step in range(4)
    ]
    return {
        "base_context": context,
        "blocked_portals": {"P3"},
        "blocked_boundaries": set(),
        "p3_is_open": False,
        "initial_population": 6,
        "completed_crossings": 6,
        "remaining_population": 0,
        "boundary_breakdown": {"B1": 6, "B2": 0},
        "zone_occupancy": {"EVENT": 0, "WEST": 0, "EAST": 0, "RESERVE": 0},
        "status": ComputationStatus.COMPLETE_WITHIN_MODEL,
        "horizon_seconds": 6,
        "time_step_seconds": 2,
        "timeline": frames,
    }


@pytest.fixture
def witnessed_trace(checked_trace):
    # Two occupants depart EVENT on P1 in each of three slots. All six use
    # B1 immediately on arrival; the other four/two wait in EVENT meanwhile.
    checked_trace["flow_witness"] = {
        "SOURCE": {("EVENT", 0): 6},
        ("EVENT", 0): {("EVENT", 1): 4, ("WEST", 1): 2},
        ("EVENT", 1): {("EVENT", 2): 2, ("WEST", 2): 2},
        ("EVENT", 2): {("WEST", 3): 2},
        ("WEST", 1): {"B_B1_1": 2},
        "B_B1_1": {"EXIT_COLLECTOR": 2},
        ("WEST", 2): {"B_B1_2": 2},
        "B_B1_2": {"EXIT_COLLECTOR": 2},
        ("WEST", 3): {"B_B1_3": 2},
        "B_B1_3": {"EXIT_COLLECTOR": 2},
    }
    return checked_trace


def validate(trace):
    return PlanChecker(get_default_venue_graph()).validate(**trace)


def test_independently_authored_trace_is_valid(checked_trace):
    report = validate(checked_trace)
    assert report.is_valid, report.reasons
    assert TIMELINE_CHECKS <= set(report.checks_run)


def test_aggregate_only_call_remains_supported(checked_trace):
    checked_trace.pop("timeline")
    report = validate(checked_trace)
    assert report.is_valid, report.reasons
    assert not TIMELINE_CHECKS.intersection(report.checks_run)


def test_independently_authored_flow_witness_matches_trace(witnessed_trace):
    report = validate(witnessed_trace)
    assert report.is_valid, report.reasons
    assert {"schedule_allowed_edges", "schedule_flow_conservation", "timeline_matches_flow"} <= set(report.checks_run)


def test_flow_witness_cannot_use_a_blocked_portal(witnessed_trace):
    witnessed_trace["blocked_portals"].add("P1")
    assert not validate(witnessed_trace).is_valid


def test_flow_witness_cannot_exceed_portal_throughput(witnessed_trace):
    venue = get_default_venue_graph().model_copy(deep=True)
    venue.portals["P1"].throughput_per_sec = 0.5
    # The witness sends two through a portal limited to one per 2s slot.
    report = PlanChecker(venue).validate(**witnessed_trace)
    assert not report.is_valid


def test_balanced_but_invented_zone_frame_is_rejected_against_flow(witnessed_trace):
    witnessed_trace["timeline"][1].update(event_occupancy=3, west_occupancy=1)
    without_witness = {key: value for key, value in witnessed_trace.items() if key != "flow_witness"}
    # All sampled totals, rates, capacities and terminal values still look valid.
    assert validate(without_witness).is_valid
    report = validate(witnessed_trace)
    assert not report.is_valid
    assert "timeline_matches_flow" in report.checks_run


def test_flow_witness_internal_node_cannot_create_an_occupant(witnessed_trace):
    witnessed_trace["flow_witness"][("EVENT", 0)][("WEST", 1)] = 3
    assert not validate(witnessed_trace).is_valid


def test_intermediate_population_loss_fails_despite_valid_final_totals(checked_trace):
    checked_trace["timeline"][1]["event_occupancy"] -= 1
    report = validate(checked_trace)
    assert not report.is_valid
    assert report.reasons


@pytest.mark.parametrize("field", [*ZONE_FIELDS.values(), "in_transit_occupancy"])
def test_negative_intermediate_count_cannot_hide_in_balanced_sum(checked_trace, field):
    frame = checked_trace["timeline"][1]
    original = frame[field]
    frame[field] = -1
    compensation = "west_occupancy" if field == "event_occupancy" else "event_occupancy"
    frame[compensation] += original + 1
    assert sum(frame[key] for key in ZONE_FIELDS.values()) + frame["in_transit_occupancy"] + frame["total_completed"] == 6
    assert not validate(checked_trace).is_valid


def test_nonmonotonic_boundary_count_fails_even_when_every_frame_balances(checked_trace):
    for frame, completed in zip(checked_trace["timeline"], (0, 3, 2, 5)):
        frame.update(event_occupancy=6 - completed, b1_cumulative=completed, total_completed=completed)
    checked_trace.update(
        completed_crossings=5,
        remaining_population=1,
        boundary_breakdown={"B1": 5, "B2": 0},
        zone_occupancy={"EVENT": 1, "WEST": 0, "EAST": 0, "RESERVE": 0},
        status=ComputationStatus.PARTIAL_WITHIN_HORIZON,
    )
    assert not validate(checked_trace).is_valid


def test_per_slot_boundary_rate_is_checked_not_only_horizon_quota(checked_trace):
    # Four in one 2s slot exceeds B1's 1.5/s rate, but six overall is below 9.
    checked_trace["timeline"][1].update(event_occupancy=2, b1_cumulative=4, total_completed=4)
    assert checked_trace["boundary_breakdown"]["B1"] <= 1.5 * checked_trace["horizon_seconds"]
    assert not validate(checked_trace).is_valid


def test_cumulative_boundary_sum_must_equal_frame_completed(checked_trace):
    checked_trace["timeline"][1]["b2_cumulative"] = 1
    assert not validate(checked_trace).is_valid


@pytest.mark.parametrize(
    "corruption",
    ["empty_trace", "missing_frame", "duplicate_step", "wrong_timestamp", "reversed_frames", "truncated_end", "missing_count"],
)
def test_invalid_time_grid_or_incomplete_frame_fails_closed(checked_trace, corruption):
    frames = checked_trace["timeline"]
    if corruption == "empty_trace":
        frames.clear()
    elif corruption == "missing_frame":
        del frames[1]
    elif corruption == "duplicate_step":
        frames[1]["step"] = 0
    elif corruption == "wrong_timestamp":
        frames[1]["time_seconds"] = 3
    elif corruption == "reversed_frames":
        frames.reverse()
    elif corruption == "truncated_end":
        frames.pop()
    else:
        del frames[1]["in_transit_occupancy"]
    report = validate(checked_trace)
    assert not report.is_valid
    assert report.reasons


def test_initial_population_must_start_in_event_zone(checked_trace):
    checked_trace["timeline"][0].update(event_occupancy=5, west_occupancy=1)
    assert not validate(checked_trace).is_valid


def test_terminal_crossings_must_match_envelope(checked_trace):
    checked_trace["timeline"][-1].update(event_occupancy=1, b1_cumulative=5, total_completed=5)
    assert not validate(checked_trace).is_valid


@pytest.mark.parametrize("terminal_field", ["west_occupancy", "in_transit_occupancy"])
def test_terminal_zone_distribution_and_zero_transit_are_required(checked_trace, terminal_field):
    checked_trace.update(
        completed_crossings=4,
        remaining_population=2,
        boundary_breakdown={"B1": 4, "B2": 0},
        zone_occupancy={"EVENT": 2, "WEST": 0, "EAST": 0, "RESERVE": 0},
        status=ComputationStatus.PARTIAL_WITHIN_HORIZON,
    )
    final = checked_trace["timeline"][-1]
    final.update(event_occupancy=2, b1_cumulative=4, total_completed=4)
    assert validate(checked_trace).is_valid
    final.update(event_occupancy=0, **{terminal_field: 2})
    assert not validate(checked_trace).is_valid


def assert_all_frames_conserve(envelope, venue):
    assert envelope.validator_report.is_valid, envelope.validator_report.reasons
    assert TIMELINE_CHECKS <= set(envelope.validator_report.checks_run)
    frames = envelope.timeline
    assert len(frames) == envelope.horizon_seconds // envelope.time_step_seconds + 1
    last_boundary = {"B1": 0, "B2": 0}
    count_fields = [*ZONE_FIELDS.values(), "in_transit_occupancy", "total_completed", "b1_cumulative", "b2_cumulative"]
    for step, frame in enumerate(frames):
        assert frame["step"] == step
        assert frame["time_seconds"] == step * envelope.time_step_seconds
        assert all(type(frame[key]) is int and frame[key] >= 0 for key in count_fields)
        assert sum(frame[key] for key in ZONE_FIELDS.values()) + frame["in_transit_occupancy"] + frame["total_completed"] == envelope.initial_population
        assert frame["b1_cumulative"] + frame["b2_cumulative"] == frame["total_completed"]
        for boundary, key in (("B1", "b1_cumulative"), ("B2", "b2_cumulative")):
            delta = frame[key] - last_boundary[boundary]
            assert 0 <= delta <= int(venue.boundaries[boundary].service_rate_per_sec * envelope.time_step_seconds)
            last_boundary[boundary] = frame[key]
    assert frames[0]["event_occupancy"] == envelope.initial_population
    assert all(frames[0][key] == 0 for key in ("west_occupancy", "east_occupancy", "reserve_occupancy", "in_transit_occupancy", "total_completed"))
    assert frames[-1]["in_transit_occupancy"] == 0
    assert frames[-1]["total_completed"] == envelope.completed_crossings
    for zone, key in ZONE_FIELDS.items():
        assert frames[-1][key] == envelope.zone_occupancy[zone]
    for boundary, key in (("B1", "b1_cumulative"), ("B2", "b2_cumulative")):
        assert frames[-1][key] == envelope.boundary_breakdown[boundary]


@pytest.mark.parametrize(
    "portals,boundaries,alternative",
    [
        (set(), set(), AlternativeId.KEEP_CURRENT),
        ({"P1"}, set(), AlternativeId.KEEP_CURRENT),
        ({"P1"}, set(), AlternativeId.OPEN_P3),
        ({"P2"}, set(), AlternativeId.KEEP_CURRENT),
        ({"P2"}, set(), AlternativeId.OPEN_P3),
        (set(), {"B2"}, AlternativeId.KEEP_CURRENT),
        (set(), {"B2"}, AlternativeId.OPEN_P3),
        (set(), {"B1", "B2"}, AlternativeId.KEEP_CURRENT),
    ],
)
def test_solver_preserves_every_occupant_in_every_frame(context, portals, boundaries, alternative):
    planner = FlowPlanner()
    envelope = planner.solve(context, alternative, portals, boundaries)
    assert_all_frames_conserve(envelope, planner.venue)
    if "B2" in boundaries:
        assert all(frame["b2_cumulative"] == 0 for frame in envelope.timeline)


def test_long_portal_transit_is_counted_between_departure_and_arrival(context):
    venue = get_default_venue_graph().model_copy(deep=True)
    venue.portals["P1"].travel_time_seconds = 6
    planner = FlowPlanner(venue)
    envelope = planner.solve(context, AlternativeId.KEEP_CURRENT, {"P2"}, set())
    assert_all_frames_conserve(envelope, venue)
    assert any(frame["in_transit_occupancy"] > 0 for frame in envelope.timeline)
    assert all(frame["b1_cumulative"] == 0 for frame in envelope.timeline if frame["time_seconds"] < 6)


def test_timeline_validation_does_not_mutate_supplied_evidence(checked_trace):
    before = deepcopy(checked_trace)
    assert validate(checked_trace).is_valid
    assert checked_trace == before


def test_repeated_solves_have_stable_candidate_hash_and_distinct_run_ids(context, monkeypatch):
    monkeypatch.setattr("backend.app.planner.flow_solver.time.time", lambda: 1234567890.0)
    planner = FlowPlanner()
    first = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set())
    second = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set())
    assert first.candidate_hash == second.candidate_hash
    assert first.run_id != second.run_id


def test_candidate_hash_includes_timestep_even_when_other_inputs_match(context):
    planner = FlowPlanner()
    first = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(), time_step_seconds=2)
    second = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(), time_step_seconds=4)
    assert first.base_context == second.base_context
    assert first.horizon_seconds == second.horizon_seconds
    assert first.initial_population == second.initial_population
    assert first.candidate_hash != second.candidate_hash


def test_displayed_assumption_rates_follow_the_actual_boundary_specs(context):
    venue = get_default_venue_graph().model_copy(deep=True)
    venue.boundaries["B1"].service_rate_per_sec = 1.25
    venue.boundaries["B2"].service_rate_per_sec = 0.75
    envelope = FlowPlanner(venue).solve(context, AlternativeId.KEEP_CURRENT, set(), set())
    assert envelope.validator_report.is_valid, envelope.validator_report.reasons
    for boundary, spec in venue.boundaries.items():
        assert any(boundary in line and f"{spec.service_rate_per_sec:g}" in line for line in envelope.assumptions)
