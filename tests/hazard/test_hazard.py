import copy

import pytest
from pydantic import ValidationError

from backend.app.ai.managed.adapter import TOOL_DEFINITIONS
from backend.app.contracts import AlternativeId, RunContext
from backend.app.hazard.exposure import EXPOSURE_LABEL, modeled_exposure_people_seconds
from backend.app.hazard.model import HazardEvent, HazardSchedule, HazardToolError, ToolContext
from backend.app.hazard.tools import HAZARD_TOOL_DEFINITIONS, execute_hazard_tool
from backend.app.planner.model import get_default_venue_graph


@pytest.fixture
def ctx():
    base = RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1)
    return ToolContext(venue=get_default_venue_graph(), base_context=base)


def ev(element_id="P1", close_at_s=20, zones=("EVENT",)):
    return {"element_id": element_id, "close_at_s": close_at_s, "hazard_zone_ids": list(zones)}


def args(events, alt="OPEN_P3"):
    return {"alternative_id": alt, "events": events}


def validate(events, ctx):
    return HazardSchedule.model_validate({"events": events}, context={"ctx": ctx})


def test_valid_schedule_accepted(ctx):
    s = validate([ev("P1", 10), ev("B2", 30), ev("P2", 0)], ctx)
    assert len(s.events) == 3


def test_duplicate_element_rejected(ctx):
    with pytest.raises(ValidationError):
        validate([ev("P1", 10), ev("P1", 20)], ctx)


@pytest.mark.parametrize("t", [40, 60, -2, 3])
def test_bad_close_time_rejected(ctx, t):
    with pytest.raises(ValidationError):
        validate([ev("P1", t)], ctx)


def test_unknown_ids_rejected(ctx):
    with pytest.raises(ValidationError):
        validate([ev("P9", 10)], ctx)
    with pytest.raises(ValidationError):
        validate([ev("P1", 10, ("NOWHERE",))], ctx)


def test_extra_fields_rejected(ctx):
    with pytest.raises(ValidationError):
        HazardEvent(element_id="P1", close_at_s=2, hazard_zone_ids=(), note="x")
    with pytest.raises(ValidationError):
        HazardSchedule.model_validate({"events": [ev()], "extra": 1})


def test_event_count_bounds():
    with pytest.raises(ValidationError):
        HazardSchedule.model_validate({"events": []})
    with pytest.raises(ValidationError):
        HazardSchedule.model_validate({"events": [ev(f"P{i}", 2) for i in range(7)]})


def test_determinism_and_duplicate_call(ctx):
    a = args([ev("P1", 10), ev("B2", 24)])
    snapshot = copy.deepcopy(a)
    r1 = execute_hazard_tool("score_exposure", a, ctx)
    r2 = execute_hazard_tool("score_exposure", a, ctx)
    assert r1 == r2 and a == snapshot


def test_conservation_in_timeline(ctx):
    from backend.app.hazard.schedule import solve_schedule
    for alt in AlternativeId:
        env = solve_schedule(validate([ev("P1", 10), ev("B1", 20)], ctx), ctx, alt)
        for f in env.timeline:
            tot = f["event_occupancy"] + f["west_occupancy"] + f["east_occupancy"] + f["reserve_occupancy"]
            assert tot + f["in_transit_occupancy"] + f["total_completed"] == env.initial_population
        modeled_exposure_people_seconds(env.timeline, ["EVENT"], env.time_step_seconds, env.initial_population)


def test_exposure_raises_on_broken_conservation():
    frame = {"event_occupancy": 5, "west_occupancy": 0, "east_occupancy": 0, "reserve_occupancy": 0,
             "in_transit_occupancy": 0, "total_completed": 0}
    with pytest.raises(ValueError):
        modeled_exposure_people_seconds([frame], ["EVENT"], 2, 10)
    assert modeled_exposure_people_seconds([frame], ["EVENT"], 2, 5) == (10, EXPOSURE_LABEL)
    assert "not a casualty or survival prediction" in EXPOSURE_LABEL


def test_closures_lower_or_equal_completed_and_expose(ctx):
    base = execute_hazard_tool("score_exposure", args([ev("P3", 2, ("EVENT",))], "KEEP_CURRENT"), ctx)
    assert base["modeled_exposure_people_seconds"] > 0
    assert base["is_valid"] is True and base["reasons"] == []
    assert base["completed_crossings"] + base["remaining_population"] <= 120


def test_infeasible_closure_reports_zero_exit(ctx):
    r = execute_hazard_tool("simulate_hazard_schedule",
                            args([ev("B1", 0), ev("B2", 0), ev("P1", 0), ev("P2", 0), ev("P3", 0)], "OPEN_P3"), ctx)
    assert r["completed_crossings"] == 0 and r["remaining_population"] == 120


def test_invalid_checker_report_is_surfaced(ctx, monkeypatch):
    from backend.app.hazard import tools
    from backend.app.hazard.schedule import solve_schedule
    real = solve_schedule(validate([ev()], ctx), ctx, AlternativeId.OPEN_P3)
    bad = real.model_copy(update={"validator_report": real.validator_report.model_copy(
        update={"is_valid": False, "reasons": ["checker_reason"]})})
    monkeypatch.setattr(tools, "solve_schedule", lambda *a, **k: bad)
    r = execute_hazard_tool("simulate_hazard_schedule", args([ev()]), ctx)
    assert r["is_valid"] is False and r["reasons"] == ["checker_reason"]


def test_fixed_keys(ctx):
    r1 = execute_hazard_tool("simulate_hazard_schedule", args([ev()]), ctx)
    r2 = execute_hazard_tool("score_exposure", args([ev()]), ctx)
    assert set(r1) == set(r2)
    assert r1["modeled_exposure_people_seconds"] is None and r2["modeled_exposure_people_seconds"] is not None


def test_tool_definitions_shape():
    assert [d["name"] for d in HAZARD_TOOL_DEFINITIONS] == ["simulate_hazard_schedule", "score_exposure"]
    for d in HAZARD_TOOL_DEFINITIONS:
        assert set(d) == set(TOOL_DEFINITIONS[0])
        assert d["type"] == "function" and d["parameters"]["additionalProperties"] is False
        assert d["parameters"]["type"] == "object"
        assert d["parameters"]["required"] == ["alternative_id", "events"]
        assert d["parameters"]["properties"]["events"]["items"]["additionalProperties"] is False


def test_unknown_tool_rejected(ctx):
    with pytest.raises(HazardToolError) as e:
        execute_hazard_tool("set_gate", args([ev()]), ctx)
    assert str(e.value) == "unknown_tool"


@pytest.mark.parametrize("bad", [
    {}, {"alternative_id": "OPEN_P3"}, {"events": [ev()]},
    {"alternative_id": "NOPE", "events": [ev()]},
    {"alternative_id": "OPEN_P3", "events": [ev()], "extra": 1},
    {"alternative_id": "OPEN_P3", "events": [dict(ev(), note="hi")]},
    {"alternative_id": "OPEN_P3", "events": [dict(ev(), close_at_s="10")]},
    {"alternative_id": "OPEN_P3", "events": [dict(ev(), close_at_s=True)]},
    {"alternative_id": "OPEN_P3", "events": [dict(ev(), close_at_s=40)]},
    {"alternative_id": "OPEN_P3", "events": [ev("P1", 4), ev("P1", 6)]},
    {"alternative_id": "OPEN_P3", "events": "x"},
    None,
])
def test_bad_args_rejected(ctx, bad):
    with pytest.raises(HazardToolError) as e:
        execute_hazard_tool("score_exposure", bad, ctx)
    assert str(e.value) == "invalid_arguments"


def test_schedule_uses_live_state_from_context(ctx, monkeypatch):
    from backend.app.hazard import schedule as sched
    seen = {}
    real = sched.FlowPlanner.solve

    def spy(self, base_context, alt, bp, bb, **kw):
        seen.update(bp=set(bp), bb=set(bb), kw=kw)
        return real(self, base_context, alt, bp, bb, **kw)

    monkeypatch.setattr(sched.FlowPlanner, "solve", spy)
    live = ToolContext(venue=ctx.venue, base_context=ctx.base_context, blocked_portals=frozenset({"P2"}),
                       blocked_boundaries=frozenset({"B1"}), p3_physical_open=True)
    sched.solve_schedule(validate([ev("P1", 10)], live), live, AlternativeId.KEEP_CURRENT)
    assert seen["bp"] == {"P2"} and seen["bb"] == {"B1"} and seen["kw"]["p3_physical_open"] is True
    assert ToolContext(venue=ctx.venue, base_context=ctx.base_context).blocked_portals == frozenset()


def test_live_blockage_changes_result(ctx):
    live = ToolContext(venue=ctx.venue, base_context=ctx.base_context, blocked_portals=frozenset({"P1", "P2"}))
    a = args([ev("B2", 30)], "KEEP_CURRENT")
    open_r = execute_hazard_tool("simulate_hazard_schedule", a, ctx)
    blocked_r = execute_hazard_tool("simulate_hazard_schedule", a, live)
    assert blocked_r["completed_crossings"] < open_r["completed_crossings"]


def test_exposure_without_zones_is_none_not_zero(ctx):
    from backend.app.hazard.exposure import NO_ZONES_LABEL
    frame = {"event_occupancy": 5, "west_occupancy": 0, "east_occupancy": 0, "reserve_occupancy": 0,
             "in_transit_occupancy": 0, "total_completed": 0}
    assert modeled_exposure_people_seconds([frame], [], 2, 5) == (None, NO_ZONES_LABEL)
    r = execute_hazard_tool("score_exposure", args([ev("P1", 10, ())]), ctx)
    assert r["modeled_exposure_people_seconds"] is None and r["exposure_label"] == NO_ZONES_LABEL
    assert "modeled" not in r["exposure_label"].replace("not modeled", "")


def test_zero_time_step_is_rejected_not_crash(ctx):
    bad = ToolContext(venue=ctx.venue, base_context=ctx.base_context)
    object.__setattr__(bad, "time_step_seconds", 0)
    with pytest.raises(ValueError, match="invalid_time_step"):
        validate([ev("P1", 10)], bad)
    with pytest.raises(HazardToolError) as e:
        execute_hazard_tool("score_exposure", args([ev("P1", 10)]), bad)
    assert str(e.value) == "invalid_arguments"


def test_programming_errors_are_not_masked(ctx, monkeypatch):
    from backend.app.hazard import tools

    def boom(*a, **k):
        raise RuntimeError("bug")
    monkeypatch.setattr(tools, "solve_schedule", boom)
    with pytest.raises(RuntimeError):
        execute_hazard_tool("score_exposure", args([ev()]), ctx)
    monkeypatch.setattr(tools, "solve_schedule", lambda *a, **k: (_ for _ in ()).throw(ValueError("x")))
    with pytest.raises(HazardToolError) as e:
        execute_hazard_tool("score_exposure", args([ev()]), ctx)
    assert str(e.value) == "evaluation_failed"
