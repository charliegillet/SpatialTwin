import pytest
from backend.app.contracts import AlternativeId, ComputationStatus, RunContext
from backend.app.planner.flow_solver import FlowPlanner


@pytest.fixture
def context():
    return RunContext(
        geometry_revision="geom-shack15-v1",
        scenario_revision=1,
        physical_revision=1,
    )


@pytest.fixture
def planner():
    return FlowPlanner()


def test_baseline_solve_conservation(planner, context):
    envelope = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.KEEP_CURRENT,
        blocked_portals=set(),
        blocked_boundaries=set(),
    )
    assert envelope.validator_report.is_valid
    assert envelope.initial_population == 120
    assert envelope.completed_crossings == 120
    assert envelope.remaining_population == 0
    assert envelope.status == ComputationStatus.COMPLETE_WITHIN_MODEL


def test_p2_blocked_yields_intervention_benefit(planner, context):
    # Keep current (P3 closed)
    env_keep = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.KEEP_CURRENT,
        blocked_portals={"P2"},
        blocked_boundaries=set(),
    )
    assert env_keep.validator_report.is_valid
    assert env_keep.completed_crossings == 60
    assert env_keep.remaining_population == 60

    # Open P3 (Reserve opened)
    env_open = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.OPEN_P3,
        blocked_portals={"P2"},
        blocked_boundaries=set(),
    )
    assert env_open.validator_report.is_valid
    assert env_open.completed_crossings > env_keep.completed_crossings
    assert env_open.completed_crossings == 117
    assert env_open.remaining_population == 3


def test_b2_blocked_truthfully_shows_no_benefit(planner, context):
    """
    Critical adversarial invariant: Opening P3 feeds East corridor which leads to B2.
    If B2 is blocked, opening P3 provides ZERO additional throughput.
    """
    env_keep = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.KEEP_CURRENT,
        blocked_portals=set(),
        blocked_boundaries={"B2"},
    )
    assert env_keep.validator_report.is_valid
    assert env_keep.completed_crossings == 60
    assert env_keep.boundary_breakdown.get("B2", 0) == 0

    env_open = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.OPEN_P3,
        blocked_portals=set(),
        blocked_boundaries={"B2"},
    )
    assert env_open.validator_report.is_valid
    assert env_open.completed_crossings == env_keep.completed_crossings
    assert env_open.boundary_breakdown.get("B2", 0) == 0


def test_all_boundaries_blocked_preserves_all_occupants(planner, context):
    """
    If all exits are blocked, occupants must not disappear; 100% must be accounted in holding.
    """
    env = planner.solve(
        base_context=context,
        alternative_id=AlternativeId.KEEP_CURRENT,
        blocked_portals=set(),
        blocked_boundaries={"B1", "B2"},
    )
    assert env.validator_report.is_valid
    assert env.completed_crossings == 0
    assert env.remaining_population == 120
    assert env.status == ComputationStatus.NO_FEASIBLE_EXIT
