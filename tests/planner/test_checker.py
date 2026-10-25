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
