import pytest
from backend.app.contracts import ComputationStatus, RunContext
from backend.app.planner.checker import PlanChecker
from backend.app.planner.model import get_default_venue_graph


@pytest.fixture
def checker():
    return PlanChecker(get_default_venue_graph())


@pytest.fixture
def context():
    return RunContext(
        geometry_revision="geom-shack15-v1",
        scenario_revision=1,
        physical_revision=1,
    )


def test_checker_catches_conservation_discrepancy(checker, context):
    report = checker.validate(
        base_context=context,
        blocked_portals=set(),
        blocked_boundaries=set(),
        p3_is_open=False,
        initial_population=120,
        completed_crossings=100,
        remaining_population=10,  # 100 + 10 = 110 != 120!
        boundary_breakdown={"B1": 50, "B2": 50},
        zone_occupancy={"EVENT": 10},
        status=ComputationStatus.PARTIAL_WITHIN_HORIZON,
        horizon_seconds=40,
        time_step_seconds=2,
    )
    assert not report.is_valid
    assert not report.conservation_verified
    assert any("Conservation violated" in r for r in report.reasons)


def test_checker_catches_flow_through_blocked_boundary(checker, context):
    report = checker.validate(
        base_context=context,
        blocked_portals=set(),
        blocked_boundaries={"B2"},
        p3_is_open=False,
        initial_population=120,
        completed_crossings=120,
        remaining_population=0,
        boundary_breakdown={"B1": 60, "B2": 60},  # B2 is blocked but has flow!
        zone_occupancy={},
        status=ComputationStatus.COMPLETE_WITHIN_MODEL,
        horizon_seconds=40,
        time_step_seconds=2,
    )
    assert not report.is_valid
    assert any("Blocked boundary B2 serviced 60" in r for r in report.reasons)


def test_checker_catches_quota_exceeded(checker, context):
    # Over 40s @ 1.5 pers/s, max B1 quota is 60
    report = checker.validate(
        base_context=context,
        blocked_portals=set(),
        blocked_boundaries=set(),
        p3_is_open=False,
        initial_population=120,
        completed_crossings=100,
        remaining_population=20,
        boundary_breakdown={"B1": 80, "B2": 20},  # 80 > 60!
        zone_occupancy={"EVENT": 20},
        status=ComputationStatus.PARTIAL_WITHIN_HORIZON,
        horizon_seconds=40,
        time_step_seconds=2,
    )
    assert not report.is_valid
    assert not report.quota_respected
    assert any("exceeding max horizon quota" in r for r in report.reasons)


def test_infeasible_phase_one_is_not_publishable(monkeypatch, context):
    import networkx as nx
    from backend.app.contracts import AlternativeId
    from backend.app.planner import flow_solver

    def infeasible(*args, **kwargs):
        raise nx.NetworkXUnfeasible("forced")

    monkeypatch.setattr(flow_solver.nx, "min_cost_flow", infeasible)
    env = flow_solver.FlowPlanner().solve(context, AlternativeId.KEEP_CURRENT, set(), set())
    assert env.status == ComputationStatus.SOLVER_INFEASIBLE
    assert not env.validator_report.is_valid
    assert not env.is_publishable


def _solved(context, alternative):
    from backend.app.planner.flow_solver import FlowPlanner
    captured = {}
    planner = FlowPlanner()
    original = planner.checker.validate

    def spy(**kwargs):
        captured.update(kwargs)
        return original(**kwargs)

    planner.checker.validate = spy
    planner.solve(context, alternative, set(), set())
    return planner, captured


def test_checker_rejects_p3_flow_when_p3_closed(context):
    from backend.app.contracts import AlternativeId
    planner, kw = _solved(context, AlternativeId.KEEP_CURRENT)
    assert "P3" in kw["blocked_portals"] and not kw["p3_is_open"]
    flow = {k: dict(v) for k, v in kw["flow_witness"].items()}
    flow.setdefault(("EVENT", 0), {})[("RESERVE", 2)] = 1
    report = planner.checker.validate(**{**kw, "flow_witness": flow})
    assert not report.is_valid
    assert any("P3 is closed" in r for r in report.reasons)


def test_checker_accepts_p3_flow_when_p3_open(context):
    from backend.app.contracts import AlternativeId
    planner, kw = _solved(context, AlternativeId.OPEN_P3)
    assert kw["p3_is_open"]
    assert planner.checker.validate(**kw).is_valid


def test_slow_boundary_uses_same_minimum_slot_as_solver(context):
    from backend.app.contracts import AlternativeId
    from backend.app.planner.flow_solver import FlowPlanner
    venue = get_default_venue_graph()
    venue.boundaries["B1"].service_rate_per_sec = 0.4  # int(0.4 * dt=2) == 0, solver slot is max(1, 0)
    env = FlowPlanner(venue).solve(context, AlternativeId.KEEP_CURRENT, set(), set())
    assert env.boundary_breakdown["B1"] > 0
    assert not any("service rate" in r for r in env.validator_report.reasons)
