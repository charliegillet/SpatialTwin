"""Regression tests for the independent review of the building-v2 planner."""
from backend.app.hazard import door_planner
from backend.app.hazard.door_planner import plan_doors
from backend.app.planner.checker_v2 import EXIT_COLLECTOR, ClaimedResult, SolveInputs, check, expected_arcs
from backend.app.planner.flow_solver_v2 import FlowSolverV2
from tests.venues.conftest import make_request


def test_smoke_exit_carries_no_flow_once_its_sign_says_unsafe(venue):
    plan = plan_doors(venue, make_request([("SMOKE", 20, 4)]))  # smoke in the Lobby, whose exit is E1
    e1 = next(e for e in plan.exits if e.id == "E1")
    assert e1.safe is False and e1.modeled_crossings == 0
    assert all(route.exit_id != "E1" for route in plan.routes)
    assert "Do not use the south exit." in plan.announcement


def test_every_unsafe_exit_has_zero_crossings_across_hazard_types(venue):
    for kind in ("FIRE", "SMOKE", "GAS", "CHEMICAL"):
        for zone in venue.zones:
            cx = sum(p[0] for p in zone.polygon) / len(zone.polygon)
            cy = sum(p[1] for p in zone.polygon) / len(zone.polygon)
            plan = plan_doors(venue, make_request([(kind, cx, cy)]))
            for exit_ in plan.exits:
                if not exit_.safe:
                    assert exit_.modeled_crossings == 0, (kind, zone.id, exit_.id)


def test_checker_rejects_unknown_exit_nodes_instead_of_crashing(venue):
    outcome = FlowSolverV2(venue).solve(SolveInputs(), venue.default_horizon_seconds)
    witness = {k: dict(v) for k, v in outcome.witness.items()}
    witness.setdefault("X_ZZ_0", {})[EXIT_COLLECTOR] = 1
    claim = ClaimedResult(
        initial_population=outcome.initial_population, completed_crossings=outcome.completed_crossings,
        remaining_population=outcome.remaining_population, exit_breakdown=outcome.exit_breakdown,
        zone_remaining=outcome.zone_remaining, status=outcome.status, timeline=outcome.timeline, witness=witness)
    report = check(venue, SolveInputs(), venue.default_horizon_seconds, venue.time_step_seconds, claim)
    assert report["is_valid"] is False
    assert any("X_ZZ_0" in reason for reason in report["reasons"])


def test_exit_ids_with_underscores_are_counted(venue):
    renamed = venue.model_copy(deep=True)
    renamed.exits[0].id = "E_1"
    renamed.led_map = {("E_1" if k == "E1" else k): v for k, v in renamed.led_map.items()}
    arcs = expected_arcs(renamed, SolveInputs(), renamed.default_horizon_seconds, renamed.time_step_seconds)
    assert any(isinstance(u, str) and u.startswith("X_E_1_") for (u, v) in arcs if v == EXIT_COLLECTOR)
    outcome = FlowSolverV2(renamed).solve(SolveInputs(), renamed.default_horizon_seconds)
    assert outcome.validator_report["is_valid"], outcome.validator_report["reasons"]
    assert outcome.exit_breakdown["E_1"] > 0


def test_no_checked_plan_withholds_door_changes_and_announcement(venue, monkeypatch):
    real_solve = FlowSolverV2.solve

    def failing(self, inputs, horizon):
        out = real_solve(self, inputs, horizon)
        out.validator_report = {**out.validator_report, "is_valid": False, "reasons": ["forced for test"]}
        return out

    monkeypatch.setattr(FlowSolverV2, "solve", failing)
    monkeypatch.setattr(door_planner, "_NO_HAZARD_CACHE", {})
    plan = plan_doors(venue, make_request([("FIRE", 20, 4)]))
    assert plan.chosen.validator_report.is_valid is False
    assert plan.announcement == ""
    assert not any(d.decided_by == "door_planner" for d in plan.doors)
    assert plan.advisories[0].startswith("No checked plan")
