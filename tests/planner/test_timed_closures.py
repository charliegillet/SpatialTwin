import copy
import json
import pytest
from backend.app.contracts import AlternativeId, RunContext
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.planner.schedule_checker import validate_schedule

BASELINE_CASES = [
    (alt, bp, bb)
    for alt in AlternativeId
    for bp in (set(), {"P1"}, {"P2"}, {"P3"})
    for bb in (set(), {"B1"})
]


@pytest.fixture
def context():
    return RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1)


@pytest.fixture
def planner():
    return FlowPlanner()


def _stable(envelope):
    data = envelope.model_dump(mode="json")
    data.pop("run_id")
    data.pop("timings_ms")
    return json.dumps(data, sort_keys=True, default=str)


@pytest.mark.parametrize("alt,bp,bb", BASELINE_CASES)
def test_empty_or_none_closures_match_baseline(planner, context, alt, bp, bb):
    base = planner.solve(context, alt, set(bp), set(bb))
    for kwargs in ({"portal_close_at": None, "boundary_close_at": None},
                   {"portal_close_at": {}, "boundary_close_at": {}}):
        assert _stable(planner.solve(context, alt, set(bp), set(bb), **kwargs)) == _stable(base)
    assert "schedule_timed_closures" not in base.validator_report.checks_run


def test_closure_at_horizon_never_exceeds_no_closure_flow(planner, context):
    base = planner.solve(context, AlternativeId.OPEN_P3, {"P2"}, set())
    H = base.horizon_seconds
    late = planner.solve(context, AlternativeId.OPEN_P3, {"P2"}, set(),
                         portal_close_at={"P1": H}, boundary_close_at={"B1": H + 0})
    # close_step == T drops the final-step edges (t < close_step), so never more than baseline
    assert late.completed_crossings <= base.completed_crossings
    assert late.candidate_hash != base.candidate_hash
    assert late.validator_report.is_valid


def test_closure_changes_candidate_hash(planner, context):
    a = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(), boundary_close_at={"B1": 10})
    b = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(), boundary_close_at={"B1": 20})
    assert a.candidate_hash != b.candidate_hash


@pytest.mark.parametrize("alt", list(AlternativeId))
def test_monotonic_and_conserving(planner, context, alt):
    base = planner.solve(context, alt, set(), set())
    H, dt = base.horizon_seconds, base.time_step_seconds
    for kind in ("portal_close_at", "boundary_close_at"):
        ids = ("P1", "P2", "P3") if kind == "portal_close_at" else ("B1", "B2")
        for eid in ids:
            previous = None
            for when in range(0, H + 1, dt * 3):
                env = planner.solve(context, alt, set(), set(), **{kind: {eid: when}})
                assert env.initial_population == env.completed_crossings + env.remaining_population
                assert env.validator_report.is_valid, env.validator_report.reasons
                assert env.completed_crossings <= base.completed_crossings
                if previous is not None:
                    assert env.completed_crossings >= previous
                previous = env.completed_crossings


def test_closing_both_boundaries_early_blocks_exit(planner, context):
    env = planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(),
                        boundary_close_at={"B1": 0, "B2": 0})
    assert env.completed_crossings == 0
    assert env.initial_population == env.remaining_population
    assert env.validator_report.is_valid


def _witness_inputs(planner, context):
    """Re-run the solver internals' witness by capturing the checker call."""
    captured = {}
    original = planner.checker.validate

    def spy(**kw):
        captured.update(kw)
        return original(**kw)

    planner.checker.validate = spy
    env = planner.solve(context, AlternativeId.OPEN_P3, set(), set(),
                        boundary_close_at={"B1": 20})
    planner.checker.validate = original
    return env, captured


def test_checker_rejects_tampered_witness_after_close(planner, context):
    env, kw = _witness_inputs(planner, context)
    assert env.validator_report.is_valid
    assert "schedule_timed_closures" in env.validator_report.checks_run
    dt = env.time_step_seconds
    late_t = 20 // dt + 1
    flow = copy.deepcopy(kw["flow_witness"])
    flow.setdefault(("WEST", late_t), {})[f"B_B1_{late_t}"] = 1
    report = planner.checker.validate(**{**kw, "flow_witness": flow})
    assert not report.is_valid
    assert any("at or after its close time" in r for r in report.reasons)


def test_checker_rejects_tampered_portal_witness_after_close(planner, context):
    captured = {}
    original = planner.checker.validate

    def spy(**kw):
        captured.update(kw)
        return original(**kw)

    planner.checker.validate = spy
    planner.solve(context, AlternativeId.OPEN_P3, set(), set(), portal_close_at={"P1": 10})
    planner.checker.validate = original
    portal = planner.venue.portals["P1"]
    dt = captured["time_step_seconds"]
    steps = max(1, portal.travel_time_seconds // dt)
    t = 10 // dt + 1
    flow = copy.deepcopy(captured["flow_witness"])
    flow.setdefault((portal.from_zone, t), {})[(portal.to_zone, t + steps)] = 1
    report = planner.checker.validate(**{**captured, "flow_witness": flow})
    assert not report.is_valid
    assert any("portal P1" in r and "close time" in r for r in report.reasons)


def test_validate_schedule_defaults_unchanged(planner, context):
    env, kw = _witness_inputs(planner, context)
    checks, _ = validate_schedule(planner.venue, kw["timeline"], kw["initial_population"],
                                  kw["completed_crossings"], kw["zone_occupancy"],
                                  kw["boundary_breakdown"], kw["horizon_seconds"],
                                  kw["time_step_seconds"], set(), set(), kw["flow_witness"])
    assert "schedule_timed_closures" not in checks


@pytest.mark.parametrize("kwargs", [
    {"portal_close_at": {"P9": 30}},
    {"boundary_close_at": {"B9": 30}},
    {"portal_close_at": {"B1": 30}},
    {"portal_close_at": {"P1": -30}},
    {"boundary_close_at": {"B1": -1}},
    {"boundary_close_at": {"B1": 7}},
    {"portal_close_at": {"P1": 10**6}},
    {"portal_close_at": {"P1": 30.0}},
    {"portal_close_at": {"P1": True}},
])
def test_invalid_closures_rejected(planner, context, kwargs):
    with pytest.raises(ValueError):
        planner.solve(context, AlternativeId.KEEP_CURRENT, set(), set(), **kwargs)
