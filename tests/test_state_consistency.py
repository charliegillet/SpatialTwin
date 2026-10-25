"""State, store, service and intake fixes: commit order, blockability, durability, honest recommendations."""
import sqlite3
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app import main
from backend.app.ai.requests import GroundingRequest
from backend.app.contracts import AlternativeId, ApplyBlockageCommand, EntityType, GateObservedState, RunContext, TargetId
from backend.app.hardware.display import DisplayProjector
from backend.app.state import store as store_module
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import ProposalAlreadyReviewed


def block(manager, target="P2", key="k1", kind=EntityType.PORTAL):
    return ApplyBlockageCommand(
        scenario_id="facility-demo", expected_scenario_revision=manager.context.scenario_revision,
        idempotency_key=key, target_type=kind, target_id=TargetId(target), source="manual_override",
        expected_context=manager.context)


def test_failed_solve_leaves_state_and_idempotency_key_untouched(monkeypatch):
    manager = StateManager()
    before, plan = manager.context, manager.current_plan
    real = manager.planner.solve

    def boom(*args, **kwargs):
        raise RuntimeError("solver crashed")

    monkeypatch.setattr(manager.planner, "solve", boom)
    with pytest.raises(RuntimeError):
        manager.apply_blockage(block(manager))
    assert manager.context == before and manager.current_plan is plan and not manager.blocked_portals
    assert not manager.store.has_event_key("k1")
    monkeypatch.setattr(manager.planner, "solve", real)
    ok, err, _ = manager.apply_blockage(block(manager))
    assert ok, err
    assert manager.blocked_portals == {"P2"} and manager.store.has_event_key("k1")


def test_failed_event_write_leaves_memory_untouched(monkeypatch):
    manager = StateManager()
    before = manager.context

    def refuse(*args, **kwargs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(manager.store, "save_event", refuse)
    with pytest.raises(sqlite3.OperationalError):
        manager.apply_blockage(block(manager))
    assert manager.context == before and not manager.blocked_portals


def test_duplicate_key_changes_nothing():
    manager = StateManager()
    assert manager.apply_blockage(block(manager))[0]
    context = manager.context
    ok, err, _ = manager.apply_blockage(block(manager, target="P1"))
    assert not ok and "Duplicate" in err
    assert manager.context == context and manager.blocked_portals == {"P2"}


def test_non_blockable_element_is_rejected_with_a_clear_error():
    manager = StateManager()
    manager.venue_graph.portals["P2"].can_be_blocked = False
    ok, err, _ = manager.apply_blockage(block(manager))
    assert not ok and "cannot be blocked" in err
    assert not manager.blocked_portals and not manager.store.has_event_key("k1")


def test_reviewed_proposal_conflict_rolls_back_and_maps_to_409(monkeypatch):
    manager = StateManager()
    cmd = block(manager)
    cmd = cmd.model_copy(update={"proposal_id": "proposal-missing"})
    with pytest.raises(ProposalAlreadyReviewed):
        manager.store.save_event("facility-demo", 1, "APPLY_BLOCKAGE", cmd.model_dump(), "k9", "now")
    assert not manager.store.has_event_key("k9")

    def conflict(command):
        raise ProposalAlreadyReviewed("x")

    monkeypatch.setattr(main.state_manager, "apply_blockage", conflict)
    context = main.state_manager.get_current_context()
    response = TestClient(main.app, client=("127.0.0.1", 1)).post(
        "/api/scenarios/facility-demo/commands",
        json={"type": "APPLY_BLOCKAGE", "expected_context": context.model_dump(),
              "expected_scenario_revision": context.scenario_revision, "idempotency_key": "k-409",
              "target_type": "portal", "target_id": "P2"})
    assert response.status_code == 409


def test_store_uses_full_sync_closes_connections_and_anchors_to_repo(tmp_path):
    store = store_module.SQLiteStore(str(tmp_path / "s.sqlite3"))
    with store._get_connection() as conn:
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")  # closed after the context manager
    assert (store_module.REPO_ROOT / "backend" / "app").is_dir()


def test_comparison_recommends_open_p3_only_with_valid_reports(monkeypatch):
    manager = StateManager()
    service = ScenarioService(manager)
    context = manager.context
    real = service.evaluate_alternative

    def evaluate(ctx, alternative, request_id):
        env = real(ctx, alternative, request_id)
        if alternative == AlternativeId.OPEN_P3:
            env = env.model_copy(update={
                "completed_crossings": env.completed_crossings + 10,
                "validator_report": env.validator_report.model_copy(update={"is_valid": False})})
        return env

    monkeypatch.setattr(service, "evaluate_alternative", evaluate)
    result = service.get_checked_comparison(context, "r1")
    assert result["net_gain_completed"] > 0 and result["has_benefit"] is False
    assert result["recommendation"] == AlternativeId.KEEP_CURRENT.value
    assert "validation" in result["explanation"]


def test_no_benefit_explanation_reflects_the_actual_blocked_set():
    manager = StateManager()
    service = ScenarioService(manager)
    clear = service.get_checked_comparison(manager.context, "r-clear")
    assert "B2" not in clear["explanation"] and "No targets are blocked" in clear["explanation"]
    assert manager.apply_blockage(block(manager, target="P1", kind=EntityType.PORTAL))[0]
    blocked = service.get_checked_comparison(manager.context, "r-blocked")
    assert "Blocked targets: P1" in blocked["explanation"]


def test_display_distinguishes_unknown_from_closed_and_needs_valid_plan():
    manager = StateManager()
    projector = DisplayProjector()
    closed = projector.project(manager.current_plan, set(), GateObservedState.CLOSED)
    unknown = projector.project(manager.current_plan, set(), GateObservedState.UNKNOWN)
    assert closed[16] != unknown[16]
    green = DisplayProjector.rgb_to_int(0, 160, 0)
    assert green in closed[:16]
    invalid = manager.current_plan.model_copy(update={
        "validator_report": manager.current_plan.validator_report.model_copy(update={"is_valid": False})})
    assert green not in projector.project(invalid, set(), GateObservedState.CLOSED)[:16]


def grounding(**changes):
    context = RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1)
    return GroundingRequest(capture_id="cap-1", timestamp_iso="2026-10-24T10:00:00Z", source_context=context, **changes)


@pytest.mark.parametrize("dimensions", [(0, 10), (-1, 5), (8193, 10), (10, 10**9)])
def test_grounding_dimensions_are_bounded(dimensions):
    with pytest.raises(ValidationError):
        grounding(dimensions=dimensions)
    assert grounding(dimensions=(8192, 1)).dimensions == (8192, 1)


@pytest.mark.parametrize("stamp", ["not a time", "2026-10-24T10:00:00", ""])
def test_grounding_timestamp_is_parsed_at_intake(stamp):
    context = RunContext(geometry_revision="geom-shack15-v1", scenario_revision=1, physical_revision=1)
    with pytest.raises(ValidationError):
        GroundingRequest(capture_id="c", timestamp_iso=stamp, source_context=context)


def test_hazard_baseline_failure_is_a_500_code_not_silent(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("secret internals")

    monkeypatch.setattr(main.scenario_service, "evaluate_alternative", broken)
    response = TestClient(main.app, client=("127.0.0.1", 1)).post(
        "/api/hazard/simulate",
        json={"alternative_id": "KEEP_CURRENT", "events": [{"element_id": "P1", "close_at_s": 0}]})
    assert response.status_code == 500
    assert response.json() == {"detail": {"code": "baseline_evaluation_failed"}}


def test_hazard_route_passes_live_blockage_state(monkeypatch):
    seen = {}
    real = main.execute_hazard_tool

    def spy(name, arguments, ctx):
        seen["ctx"] = ctx
        return real(name, arguments, ctx)

    monkeypatch.setattr(main, "execute_hazard_tool", spy)
    monkeypatch.setattr(main.state_manager, "blocked_portals", {"P2"})
    monkeypatch.setattr(main.state_manager, "blocked_boundaries", {"B2"})
    monkeypatch.setattr(main.state_manager, "physical_gate_state", GateObservedState.OPEN)
    TestClient(main.app, client=("127.0.0.1", 1)).post(
        "/api/hazard/simulate",
        json={"alternative_id": "KEEP_CURRENT", "events": [{"element_id": "P1", "close_at_s": 0}]})
    ctx = seen["ctx"]
    assert ctx.blocked_portals == frozenset({"P2"}) and ctx.blocked_boundaries == frozenset({"B2"})
    assert ctx.p3_physical_open is True
