from copy import deepcopy

import pytest

from backend.app.planner.checker_v2 import ClaimedResult, SolveInputs, check, validate_inputs
from backend.app.planner.flow_solver_v2 import FlowSolverV2

DEFAULT_CLOSED = frozenset({"D4", "D9"})


@pytest.fixture(scope="module")
def solver(venue):
    return FlowSolverV2(venue)


def claim(outcome):
    return ClaimedResult(outcome.initial_population, outcome.completed_crossings, outcome.remaining_population,
                         dict(outcome.exit_breakdown), dict(outcome.zone_remaining), outcome.status,
                         deepcopy(outcome.timeline), deepcopy(outcome.witness))


def arcs_between(witness, zone_a, zone_b):
    return sum(a for u, d in witness.items() for v, a in d.items()
               if isinstance(u, tuple) and isinstance(v, tuple) and u[0] != v[0] and {u[0], v[0]} == {zone_a, zone_b})


def test_baseline_multi_origin_conserves_everyone(solver):
    out = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED))
    assert out.initial_population == 125
    assert out.completed_crossings + out.remaining_population == 125
    assert out.validator_report["is_valid"], out.validator_report["reasons"]
    for frame in out.timeline:
        assert sum(frame["occupancy"].values()) + frame["in_transit"] + frame["total_completed"] == 125
    first = out.timeline[0]
    assert first["occupancy"]["HALL"] == 80 and first["occupancy"]["WEST_CORR"] == 0
    assert out.timeline[-1]["total_completed"] == out.completed_crossings


def test_deterministic_hash_and_flow(solver):
    inputs = SolveInputs(closed_doors=DEFAULT_CLOSED, no_entry_from={"LOBBY": 0}, untenable_at={"LOBBY": 6})
    a, b = solver.solve(inputs), solver.solve(inputs)
    assert a.candidate_hash == b.candidate_hash and a.run_id != b.run_id
    assert a.witness == b.witness and a.timeline == b.timeline
    assert solver.solve(SolveInputs(closed_doors=frozenset({"D4"}))).candidate_hash != a.candidate_hash


def test_no_entry_keeps_egress_open(solver):
    out = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, no_entry_from={"LOBBY": 0}, untenable_at={"LOBBY": 6},
                                   exit_closed_from={"E1": 0}))
    assert out.validator_report["is_valid"], out.validator_report["reasons"]
    into_lobby = sum(a for u, d in out.witness.items() for v, a in d.items()
                     if isinstance(u, tuple) and isinstance(v, tuple) and v[0] == "LOBBY" and u[0] != "LOBBY")
    out_of_lobby = sum(a for u, d in out.witness.items() for v, a in d.items()
                       if isinstance(u, tuple) and isinstance(v, tuple) and u[0] == "LOBBY" and v[0] != "LOBBY")
    assert into_lobby == 0 and out_of_lobby == 20  # all 20 occupants leave through doors before 6 s


def test_untenable_zone_strands_people_as_remaining(solver):
    out = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, no_entry_from={"HALL": 0}, untenable_at={"HALL": 0}))
    assert out.zone_remaining["HALL"] == 80
    assert out.remaining_population == 80 and out.validator_report["is_valid"]


def test_exit_closed_from_zero_blocks_exit(solver):
    out = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, exit_closed_from={"E1": 0}))
    assert out.exit_breakdown["E1"] == 0 and out.validator_report["is_valid"]


def test_multipliers_reduce_capacity(solver):
    closed_exits = {"E1": 0, "E4": 0}
    base = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, exit_closed_from=closed_exits), horizon_seconds=20)
    slow = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, exit_closed_from=closed_exits,
                                    multipliers={"E2": (0.5, 1.0), "D10": (0.5, 2.0), "D2": (0.5, 2.0)}),
                        horizon_seconds=20)
    assert slow.completed_crossings < base.completed_crossings
    assert slow.validator_report["is_valid"]


def test_closed_doors_carry_no_flow(solver):
    out = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED))
    assert arcs_between(out.witness, "HALL", "STAIR_N") == 0
    assert arcs_between(out.witness, "EAST_CORR", "DOCK") == 0


def test_status_values(solver):
    assert solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED)).status == "COMPLETE_WITHIN_MODEL"
    assert solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED, exit_closed_from={"E1": 0}),
                        horizon_seconds=10).status == "PARTIAL_WITHIN_HORIZON"
    none = solver.solve(SolveInputs(closed_doors=DEFAULT_CLOSED,
                                    exit_closed_from={"E1": 0, "E2": 0, "E3": 0, "E4": 0}))
    assert none.status == "NO_FEASIBLE_EXIT" and none.validator_report["is_valid"]


@pytest.mark.parametrize("inputs", [
    SolveInputs(closed_doors=frozenset({"D99"})),
    SolveInputs(no_entry_from={"HALL": 3}),        # not a multiple of dt
    SolveInputs(untenable_at={"HALL": 40}),        # at the horizon
    SolveInputs(untenable_at={"HALL": -2}),
    SolveInputs(exit_closed_from={"E9": 0}),
    SolveInputs(multipliers={"D1": (0.0, 1.0)}),
    SolveInputs(no_entry_from={"NOWHERE": 0}),
])
def test_invalid_inputs_rejected(solver, venue, inputs):
    with pytest.raises(ValueError):
        validate_inputs(venue, inputs, 40, 2)
    with pytest.raises(ValueError):
        solver.solve(inputs)


INPUTS = SolveInputs(closed_doors=DEFAULT_CLOSED, no_entry_from={"LOBBY": 0}, untenable_at={"LOBBY": 6})


def tampered(solver, venue, mutate):
    c = claim(solver.solve(INPUTS))
    mutate(c)
    return check(venue, INPUTS, 40, 2, c)


def test_checker_accepts_untampered(solver, venue):
    report = tampered(solver, venue, lambda c: None)
    assert report["is_valid"], report["reasons"]
    assert "flow_conservation" in report["checks_run"] and "no_flow_on_disallowed_arcs" in report["checks_run"]


def test_checker_rejects_flow_on_closed_door(solver, venue):
    def mutate(c):  # one person through closed D4 (HALL -> STAIR_N)
        c.witness.setdefault(("HALL", 0), {})[("STAIR_N", 2)] = 1
    report = tampered(solver, venue, mutate)
    assert not report["is_valid"] and any("disallowed arc" in r for r in report["reasons"])


def test_checker_rejects_entry_into_denied_zone(solver, venue):
    def mutate(c):
        c.witness.setdefault(("HALL", 2), {})[("LOBBY", 3)] = 1
    report = tampered(solver, venue, mutate)
    assert any("disallowed arc" in r for r in report["reasons"])


def test_checker_rejects_over_capacity(solver, venue):
    def mutate(c):
        for u, d in c.witness.items():
            for v, a in d.items():
                if isinstance(u, tuple) and isinstance(v, tuple) and u[0] == "HALL" and v[0] == "WEST_CORR" and a:
                    d[v] = a + 50
                    return
    report = tampered(solver, venue, mutate)
    assert any("exceeds capacity" in r for r in report["reasons"])


def test_checker_rejects_lost_people(solver, venue):
    def mutate(c):
        c.timeline[5]["occupancy"]["HALL"] -= 3
    assert not tampered(solver, venue, mutate)["is_valid"]


def test_checker_rejects_wrong_totals_and_status(solver, venue):
    def mutate(c):
        c.completed_crossings += 1
        c.remaining_population -= 1
    assert not tampered(solver, venue, mutate)["is_valid"]
    assert not tampered(solver, venue, lambda c: setattr(c, "status", "NO_FEASIBLE_EXIT"))["is_valid"]


def test_checker_rejects_wrong_source_injection(solver, venue):
    def mutate(c):
        c.witness["SOURCE"][("HALL", 0)] = 79
    assert not tampered(solver, venue, mutate)["is_valid"]
