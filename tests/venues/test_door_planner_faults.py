"""evaluate_with_faults, the shared scenario grammar and the local robustness sweep (N-1) on two venues."""
import itertools
import json
import time
from pathlib import Path

import pytest

from backend.app.ai.managed import scenarios as grammar
from backend.app.ai.managed.robustness import (
    ScenarioEvaluator, robustness_headline, robustness_sweep, single_failure_scenarios, verify_claims,
)
from backend.app.hazard import door_planner
from backend.app.hazard.door_planner import (
    DoorPlanError, Faults, apply_faults, evaluate_with_faults, plan_context, plan_doors, resolve_request, zone_point,
)
from backend.app.venues.model import VenueV2
from tests.venues.conftest import make_request

GOLDEN = json.loads((Path(__file__).parents[1] / "agents" / "fixtures" / "planner_golden.json").read_text())
LOBBY = ("FIRE", 20, 4)
BEST = {"D4": "closed", "D9": "open"}


@pytest.fixture(scope="module")
def home():
    return VenueV2.model_validate(json.loads((Path(__file__).parent / "fixtures" / "home_flat.json").read_text()))


def golden_request(case):
    return make_request([tuple(h[:3]) + ((h[3],) if len(h) > 3 else ()) for h in case["hazards"]])


@pytest.mark.parametrize("index", range(len(GOLDEN["cases"])))
def test_goldens_are_reproduced_by_plan_doors_and_by_fault_free_evaluation(venue, home, index):
    case = GOLDEN["cases"][index]
    target = venue if case["venue"] == "building-v2" else home
    request = golden_request(case)
    plan = plan_doors(target, request)
    assert [a.model_dump(exclude={"run_id"}) for a in plan.alternatives] == case["alternatives"]
    assert plan.chosen.candidate_hash == case["chosen_candidate_hash"]
    assert (plan.chosen.completed_crossings, plan.baseline.completed_crossings) == (
        case["chosen_completed"], case["baseline_completed"])
    assert plan.lights.px == case["lights_px"]
    ctx = plan_context(target, request)
    for alternative in case["alternatives"]:
        outcome = evaluate_with_faults(target, request, alternative["door_states"], context=ctx)
        assert (outcome.completed_crossings, outcome.modeled_exposure_people_seconds, outcome.is_valid) == (
            alternative["completed_crossings"], alternative["modeled_exposure_people_seconds"], alternative["is_valid"])
    best = evaluate_with_faults(target, request, case["alternatives"][0]["door_states"])
    assert best.candidate_hash == case["chosen_candidate_hash"] and best.faults == Faults().canonical()


def test_faults_only_remove_or_slow_capacity(venue):
    request = make_request([LOBBY])
    ctx = plan_context(venue, request)
    base = evaluate_with_faults(venue, request, BEST, context=ctx)
    assert base.completed_crossings == 125
    stuck = evaluate_with_faults(venue, request, BEST, Faults(stuck_closed=frozenset({"D9"})), context=ctx)
    blocked = evaluate_with_faults(venue, request, BEST, Faults(blocked_exits=frozenset({"E3"})), context=ctx)
    jammed = evaluate_with_faults(venue, request, BEST, Faults(jams=(("E2", 0.5),)), context=ctx)
    assert (stuck.completed_crossings, blocked.completed_crossings, jammed.completed_crossings) == (96, 96, 114)
    assert stuck.candidate_hash != base.candidate_hash and stuck.is_valid and jammed.is_valid
    assert stuck.faults == {"stuck_closed": ["D9"], "blocked_exits": [], "jams": []}
    # A stuck door the candidate keeps closed changes nothing; faults never add capacity.
    for door in ("D4",):
        same = evaluate_with_faults(venue, request, BEST, Faults(stuck_closed=frozenset({door})), context=ctx)
        assert same.completed_crossings == 125
    for doors, exits in itertools.product([(), ("D2",), ("D2", "D10")], [(), ("E4",)]):
        faulted = evaluate_with_faults(venue, request, BEST, Faults(frozenset(doors), frozenset(exits)), context=ctx)
        assert faulted.completed_crossings <= base.completed_crossings


def test_jams_multiply_the_hazard_slowdown(venue):
    ctx = plan_context(venue, make_request([("SMOKE", 20, 14)]))
    assert ctx.fx.inputs_base.multipliers["D4"] == (0.5, 1.0)
    inputs = apply_faults(ctx, frozenset({"D4"}), Faults(jams=(("D4", 0.5), ("E1", 0.25))))
    assert inputs.multipliers["D4"] == (0.25, 1.0) and inputs.multipliers["E1"] == (0.25, 1.0)
    assert apply_faults(ctx, frozenset({"D4"})) == apply_faults(ctx, frozenset({"D4"}), Faults())


@pytest.mark.parametrize("faults, code", [
    (Faults(stuck_closed=frozenset({"D99"})), "unknown_fault_door"),
    (Faults(blocked_exits=frozenset({"D9"})), "unknown_fault_exit"),
    (Faults(jams=(("Z1", 0.5),)), "unknown_fault_element"),
    (Faults(jams=(("D9", 1.0),)), "invalid_jam_factor"),
    (Faults(jams=(("D9", 0.0),)), "invalid_jam_factor"),
    (Faults(jams=(("D9", float("nan")),)), "invalid_jam_factor"),
    (Faults(jams=(("D9", 0.5), ("D9", 0.4))), "duplicate_fault_element"),
    (Faults(stuck_closed=frozenset({f"D{i}" for i in range(1, 10)})), "too_many_faults"),
])
def test_invalid_faults_are_refused_with_a_code(venue, faults, code):
    with pytest.raises(DoorPlanError) as error:
        evaluate_with_faults(venue, make_request([LOBBY]), BEST, faults)
    assert error.value.code == code


@pytest.mark.parametrize("states", [{"D4": "closed"}, {"D4": "closed", "D9": "open", "D1": "open"},
                                    {"D4": "ajar", "D9": "open"}, {"D4": "closed", "D9": True}])
def test_door_states_must_be_exactly_the_free_set(venue, states):
    with pytest.raises(DoorPlanError) as error:
        evaluate_with_faults(venue, make_request([LOBBY]), states)
    assert error.value.code == "invalid_door_states"


def test_scenario_grammar_is_strict_and_canonical():
    parsed = grammar.parse_scenario("jam:D9@0.5 + stuck_closed:D3")
    assert parsed.label == "jam:D9@0.50+stuck_closed:D3" and parsed.jams == (("D9", 0.5),)
    assert parsed.stuck_closed == frozenset({"D3"}) and not parsed.changes_hazards
    assert grammar.parse_scenario("baseline").is_baseline
    mixed = grammar.parse_scenario("untenable:h0=10+second_hazard:SMOKE@HALL")
    assert mixed.untenable == (("h0", 10),) and mixed.second_hazard == ("SMOKE", "HALL") and mixed.changes_hazards
    for text, code in [("", "scenario_missing"), (None, "scenario_missing"), ("x" * 121, "scenario_too_long"),
                       ("baseline+stuck_closed:D3", "scenario_baseline_not_alone"),
                       ("stuck_closed:d3", "scenario_unrecognized"), ("jam:D9@1.5", "scenario_unrecognized"),
                       ("jam:D9@0.0", "scenario_bad_factor"), ("stuck_closed:D3+jam:D3@0.50", "scenario_duplicate_element"),
                       ("a+b+c+d", "scenario_term_count"), ("open D9 please", "scenario_unrecognized"),
                       ("second_hazard:FIRE@HALL+second_hazard:GAS@LOBBY", "scenario_duplicate_hazard")]:
        with pytest.raises(grammar.ScenarioError) as error:
            grammar.parse_scenario(text)
        assert str(error.value) == code, text


def test_sandbox_fault_arithmetic_matches_the_planner(venue):
    """scenarios.fault_fields (copied into the sandbox) and door_planner.apply_faults must agree exactly."""
    for hazards in ([LOBBY], [("SMOKE", 20, 14)], [("WATER", 20, 14)]):
        ctx = plan_context(venue, make_request(hazards))
        for label in ["stuck_closed:D3", "exit_blocked:E2", "jam:D4@0.50+jam:E1@0.25", "stuck_closed:D9+exit_blocked:E3",
                      "jam:D2@0.75+stuck_closed:D10+exit_blocked:E4", "baseline"]:
            scenario = grammar.parse_scenario(label)
            for opened in (frozenset(), frozenset({"D9"}), frozenset({"D4", "D9"})):
                mine = apply_faults(ctx, opened, Faults(scenario.stuck_closed, scenario.blocked_exits, scenario.jams))
                base = apply_faults(ctx, opened)
                closed, exits, mult = grammar.fault_fields(base.closed_doors, base.exit_closed_from,
                                                           base.multipliers, scenario)
                assert (mine.closed_doors, mine.exit_closed_from, mine.multipliers) == (closed, exits, mult), label


def test_sandbox_untenable_resolution_matches_resolve_request(venue):
    dt = venue.time_step_seconds
    for kind, explicit, horizon in itertools.product(["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"],
                                                     [None, 0, 6, 20], [20, 40]):
        if explicit is not None and explicit >= horizon:
            continue
        request = make_request([(kind, 20, 4, {} if explicit is None else {"untenable_s": explicit})],
                               horizon_seconds=horizon)
        _, resolved = resolve_request(venue, request)
        default = venue.hazard_defaults[kind].untenable_s
        assert grammar.resolve_untenable(kind, explicit, default, horizon, dt) == resolved[0]["untenable_s"]
    with pytest.raises(grammar.ScenarioError):
        grammar.resolve_untenable("FIRE", 7, None, 40, dt)


def test_hazard_scenarios_re_resolve_the_effects(venue):
    evaluator = ScenarioEvaluator(venue, make_request([("FIRE", 20, 14)]))
    fast = evaluator.evaluate({"D4": "open", "D9": "closed"}, "untenable:h0=2")
    slow = evaluator.evaluate({"D4": "open", "D9": "closed"}, "untenable:h0=30")
    assert fast["completed_crossings"] < slow["completed_crossings"]
    gas = evaluator.evaluate({"D4": "open", "D9": "closed"}, "second_hazard:GAS@HALL")
    assert gas["door_states"] == {"D9": "closed"}  # gas locks D4: it leaves the controllable set
    for label, code in [("untenable:nope=10", "scenario_unknown_hazard"), ("untenable:h0=7", "scenario_bad_untenable"),
                        ("second_hazard:FIRE@NOWHERE", "scenario_unknown_zone")]:
        with pytest.raises(grammar.ScenarioError) as error:
            evaluator.evaluate(BEST, label)
        assert str(error.value) == code
    assert zone_point(venue, "HALL") is not None and venue.locate_zone(*zone_point(venue, "HALL")) == "HALL"
    assert zone_point(venue, "NOWHERE") is None


def test_n1_sweep_on_building_v2(venue):
    sweep = robustness_sweep(venue, make_request([LOBBY]))
    assert sweep["candidate"] == BEST and sweep["candidate_is_checked_best"] and not sweep["truncated"]
    assert (sweep["single_failures_held"], sweep["single_failures_total"]) == (8, 16)
    assert {b["scenario"] for b in sweep["breaks"]} >= {"stuck_closed:D9", "stuck_closed:D2", "exit_blocked:E3"}
    assert sweep["fallback_if_jammed"] == {"if_jammed": "D9", "door_states": {"D4": "open", "D9": "closed"},
                                           "completed_crossings": 102, "is_valid": True,
                                           "candidate_completed_crossings": 96}
    assert sweep["most_robust_tied_state"] == {"D4": "open", "D9": "open"}
    assert sweep["tied_best_states"][0]["single_failures_held"] == sweep["tied_best_states"][0]["single_failures_total"]
    curve = sweep["untenable_sensitivity"][0]["curve"]
    assert [c["untenable_s"] for c in curve] == list(range(2, 39, 2))
    assert curve[0]["completed_crossings"] == 119 and curve[-1]["completed_crossings"] == 125
    worst = {w["zone_id"]: w for w in sweep["worst_second_hazard"]}
    assert set(worst) == {"HALL", "ROOM_A", "KITCHEN", "WEST_CORR", "EAST_CORR", "STAIR_N", "DOCK"}
    assert worst["HALL"]["type"] == "SMOKE" and worst["HALL"]["completed_crossings"] == 69
    assert robustness_headline(sweep) == (
        "D9 open holds 8 of 16 single failures; breaks under stuck_closed:D10, stuck_closed:D2; D4 open + D9 open "
        "ties at baseline and holds 18 of 18; if D9 jams: D4 open (modeled crossings, local checker).")
    json.dumps(sweep)  # serialisable as it is published


def test_n1_sweep_on_the_hand_written_home(home):
    request = make_request([("FIRE", 1, 1)])
    sweep = robustness_sweep(home, request)
    assert sweep["candidate"] == {"D5": "open"}
    assert sweep["single_failures_total"] == len(single_failure_scenarios(ScenarioEvaluator(home, request), {"D5": "open"}))
    assert sweep["single_failures_held"] == sweep["single_failures_total"] == 10
    assert all(s["is_valid"] for s in sweep["single_failures"])
    assert robustness_headline(sweep).startswith("D5 open holds 10 of 10 single failures")


def test_sweep_stops_at_its_solve_budget_and_deadline(venue):
    capped = robustness_sweep(venue, make_request([LOBBY]), max_solves=12)
    assert capped["truncated"] and capped["solves"] <= 20
    late = robustness_sweep(venue, make_request([LOBBY]), deadline=time.monotonic() - 1)
    assert late["truncated"] and late["single_failures"] == [] and late["baseline"]["completed_crossings"] == 125


def test_verify_claims_reproduces_exact_numbers_only(venue):
    evaluator = ScenarioEvaluator(venue, make_request([LOBBY]))
    good = evaluator.evaluate(BEST, "stuck_closed:D9")
    result = verify_claims(evaluator, BEST, {"D4": "open", "D9": "closed"}, [
        {"scenario": "stuck_closed:D9", "completed_crossings": good["completed_crossings"],
         "candidate_hash": good["candidate_hash"]},
        {"scenario": "stuck_closed:D9", "completed_crossings": 97},
        {"scenario": "baseline", "completed_crossings": 102, "applies_to": "fallback"},
        {"scenario": "baseline", "completed_crossings": 125, "candidate_hash": "f" * 16},
        {"scenario": "drop the doors", "completed_crossings": 1}])
    assert (result["verified"], result["total"]) == (2, 5)
    assert [c["reason"] for c in result["checks"]] == [None, "crossings_mismatch", None, "candidate_hash_mismatch",
                                                       "scenario_unrecognized"]
    assert result["checks"][2]["applies_to"] == "fallback"


def test_no_hazard_cache_is_keyed_by_venue_too(venue, home):
    door_planner._NO_HAZARD_CACHE.clear()
    twin = home.model_copy(update={"geometry_revision": venue.geometry_revision})
    assert plan_doors(venue, make_request([])).no_hazard_completed == 125
    assert plan_doors(twin, make_request([])).no_hazard_completed == 7
    assert len(door_planner._NO_HAZARD_CACHE) == 2
