"""Adversarial lab previews must stay hypothetical, equal-context, and read-only."""

from copy import deepcopy
from inspect import signature

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts import AlternativeId, GateObservedState, RunContext
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore


@pytest.fixture
def lab(tmp_path):
    manager = StateManager(SQLiteStore(str(tmp_path / "lab.sqlite3")))
    manager.physical_gate_state = GateObservedState.CLOSED
    return manager, ScenarioService(manager)


@pytest.fixture
def lab_api(lab, monkeypatch):
    from backend.app import main

    manager, service = lab
    monkeypatch.setattr(main, "state_manager", manager)
    monkeypatch.setattr(main, "scenario_service", service)

    async def forbidden_external_action(*args, **kwargs):
        pytest.fail("A read-only scenario lab must not use AI providers or hardware")

    monkeypatch.setattr(main.grounding_adapter, "interpret_capture", forbidden_external_action)
    monkeypatch.setattr(main.managed_agent_adapter, "investigate_scenario", forbidden_external_action)
    monkeypatch.setattr(main.hardware_bridge, "update_display", forbidden_external_action)
    monkeypatch.setattr(main.hardware_bridge, "request_gate_target", forbidden_external_action)
    # Deliberately do not enter TestClient's context: no hardware lifespan starts.
    return TestClient(main.app), manager


def database_contents(manager):
    with manager.store._get_connection() as connection:
        return tuple(connection.iterdump())


def authoritative_state(manager):
    snapshot = manager.get_current_snapshot()
    snapshot.pop("timestamp_iso")
    return deepcopy(snapshot)


def by_case(result):
    assert len(result["cases"]) == 4
    cases = {case["id"]: case for case in result["cases"]}
    assert set(cases) == {"baseline", "p1_blocked", "p2_blocked", "b2_blocked"}
    return cases


def solve_arguments(solve, args, kwargs):
    bound = signature(solve).bind(*args, **kwargs)
    bound.apply_defaults()
    return bound.arguments


def test_canonical_cases_use_checked_equal_conditions_and_truthful_gains(lab, monkeypatch):
    manager, service = lab
    context = manager.get_current_context()
    solve = service.planner.solve
    calls = []

    def counted(*args, **kwargs):
        calls.append(deepcopy(solve_arguments(solve, args, kwargs)))
        return solve(*args, **kwargs)

    monkeypatch.setattr(service.planner, "solve", counted)
    result = service.get_scenario_lab(context)
    assert result["base_context"] == context.model_dump()
    assert result["generated_at_iso"]
    assert result["hypothetical"] is True
    assert result["provenance"] == "local_scenario_lab"
    assert result["reserve_basis"] == "reported"
    assert result["p3_physical_open"] is False
    assert result["comparable"] is True
    assert result["errors"] == []
    cases = by_case(result)
    expected = {
        "baseline": ([], [], 120, 120, 0),
        "p1_blocked": (["P1"], [], 60, 60, 0),
        "p2_blocked": (["P2"], [], 60, 117, 57),
        "b2_blocked": ([], ["B2"], 60, 60, 0),
    }
    assert len(calls) == 8
    for case_id, (portals, boundaries, keep_count, open_count, gain) in expected.items():
        case = cases[case_id]
        assert case["blocked_portals"] == portals
        assert case["blocked_boundaries"] == boundaries
        assert case["comparable"] is True
        assert case["reasons"] == []
        assert case["net_gain"] == gain
        pair = (case["keep_current"], case["open_p3"])
        assert [candidate["alternative_id"] for candidate in pair] == ["KEEP_CURRENT", "OPEN_P3"]
        assert [candidate["completed_crossings"] for candidate in pair] == [keep_count, open_count]
        for candidate in pair:
            assert candidate["base_context"] == context.model_dump()
            assert candidate["initial_population"] == 120
            assert candidate["horizon_seconds"] == 40
            assert candidate["time_step_seconds"] == 2
            assert candidate["validator_report"]["is_valid"] is True
            assert candidate["completed_crossings"] + candidate["remaining_population"] == 120
            if boundaries:
                assert candidate["boundary_breakdown"]["B2"] == 0
        case_calls = [call for call in calls if call["blocked_portals"] == set(portals) and call["blocked_boundaries"] == set(boundaries)]
        assert len(case_calls) == 2
        assert {call["alternative_id"] for call in case_calls} == {AlternativeId.KEEP_CURRENT, AlternativeId.OPEN_P3}
    assert all(call["base_context"] == context for call in calls)
    assert all(call["p3_physical_open"] is False for call in calls)


def test_preview_replaces_accepted_blockages_without_changing_or_persisting_state(lab):
    manager, service = lab
    # Accepted state is deliberately different from every single-blockage case.
    manager.blocked_portals.update({"P1", "P2"})
    manager.blocked_boundaries.add("B2")
    before_state = authoritative_state(manager)
    before_database = database_contents(manager)
    result = service.get_scenario_lab(manager.context)
    cases = by_case(result)
    assert cases["baseline"]["keep_current"]["completed_crossings"] == 120
    assert cases["p2_blocked"]["net_gain"] == 57
    assert authoritative_state(manager) == before_state
    assert database_contents(manager) == before_database


def test_reported_open_reserve_does_not_claim_a_new_opening_benefit(lab):
    manager, service = lab
    manager.physical_gate_state = GateObservedState.OPEN
    result = service.get_scenario_lab(manager.context, reserve_basis="reported")
    assert result["p3_physical_open"] is True
    p2 = by_case(result)["p2_blocked"]
    assert p2["keep_current"]["completed_crossings"] == 117
    assert p2["open_p3"]["completed_crossings"] == 117
    assert p2["net_gain"] == 0


@pytest.mark.parametrize("gate_state", [GateObservedState.UNKNOWN, GateObservedState.TRANSIT, GateObservedState.FAULT])
def test_uncertain_reported_reserve_fails_before_solving(lab, monkeypatch, gate_state):
    manager, service = lab
    manager.physical_gate_state = gate_state
    before = database_contents(manager)

    def unexpected_solve(*args, **kwargs):
        pytest.fail("Reported reserve uncertainty must be rejected before solving")

    monkeypatch.setattr(service.planner, "solve", unexpected_solve)
    with pytest.raises(ValueError):
        service.get_scenario_lab(manager.context, reserve_basis="reported")
    assert database_contents(manager) == before


@pytest.mark.parametrize("gate_state", list(GateObservedState))
def test_closed_benchmark_is_explicit_even_when_reported_reserve_differs(lab, gate_state):
    manager, service = lab
    manager.physical_gate_state = gate_state
    before = authoritative_state(manager)
    result = service.get_scenario_lab(manager.context, reserve_basis="closed_benchmark")
    assert result["hypothetical"] is True
    assert result["reserve_basis"] == "closed_benchmark"
    assert result["p3_physical_open"] is False
    assert by_case(result)["p2_blocked"]["net_gain"] == 57
    assert authoritative_state(manager) == before


def test_unknown_reserve_basis_is_rejected_without_guessing(lab, monkeypatch):
    manager, service = lab
    monkeypatch.setattr(service.planner, "solve", lambda *args, **kwargs: pytest.fail("Unknown basis reached planner"))
    with pytest.raises(ValueError):
        service.get_scenario_lab(manager.context, reserve_basis="optimistic")


@pytest.mark.parametrize(
    "field,value",
    [
        ("geometry_revision", "another-geometry"),
        ("scenario_revision", 2),
        ("physical_revision", 2),
        ("parameters_revision", "another-parameter-set"),
        ("solver_version", "another-solver"),
        ("state_epoch", "another-process"),
    ],
)
def test_full_stale_context_is_rejected_before_any_preview(lab, monkeypatch, field, value):
    manager, service = lab
    stale = RunContext(**{**manager.context.model_dump(exclude={"context_hash"}), field: value})
    monkeypatch.setattr(service.planner, "solve", lambda *args, **kwargs: pytest.fail("Stale context reached planner"))
    with pytest.raises(ValueError):
        service.get_scenario_lab(stale)


@pytest.mark.parametrize("change_after", [1, 8])
def test_context_drift_during_solving_cannot_return_a_comparable_lab(lab, monkeypatch, change_after):
    manager, service = lab
    old_context = manager.context
    before_database = database_contents(manager)
    solve = service.planner.solve
    calls = []

    def change_context(*args, **kwargs):
        candidate = solve(*args, **kwargs)
        calls.append(candidate.run_id)
        if len(calls) == change_after:
            with manager._state_lock:
                manager.context = RunContext(**{
                    **old_context.model_dump(exclude={"context_hash"}),
                    "physical_revision": old_context.physical_revision + 1,
                })
        return candidate

    monkeypatch.setattr(service.planner, "solve", change_context)
    with pytest.raises(ValueError):
        service.get_scenario_lab(old_context)
    assert calls
    assert database_contents(manager) == before_database


@pytest.mark.parametrize("corruption", [
    "invalid_report", "unequal_population", "unequal_horizon", "unequal_step",
    "stale_candidate_context", "wrong_alternative", "population_loss", "wrong_boundary_sum",
])
def test_bad_or_unequal_candidates_never_publish_a_gain(lab, monkeypatch, corruption):
    manager, service = lab
    solve = service.planner.solve
    altered = []

    def invalid_candidate(*args, **kwargs):
        arguments = solve_arguments(solve, args, kwargs)
        candidate = solve(*args, **kwargs)
        if arguments["blocked_portals"] == {"P2"} and arguments["alternative_id"] == AlternativeId.OPEN_P3:
            candidate = candidate.model_copy(deep=True)
            if corruption == "invalid_report":
                candidate.validator_report.is_valid = False
                candidate.validator_report.reasons = ["Independent adversarial rejection"]
            elif corruption == "unequal_population":
                candidate.initial_population += 1
            elif corruption == "unequal_horizon":
                candidate.horizon_seconds += 2
            elif corruption == "unequal_step":
                candidate.time_step_seconds += 1
            elif corruption == "stale_candidate_context":
                candidate.base_context = RunContext(**{
                    **candidate.base_context.model_dump(exclude={"context_hash"}),
                    "physical_revision": candidate.base_context.physical_revision + 1,
                })
            elif corruption == "wrong_alternative":
                candidate.alternative_id = AlternativeId.KEEP_CURRENT
            elif corruption == "population_loss":
                candidate.remaining_population -= 1
            else:
                candidate.boundary_breakdown["B2"] -= 1
            altered.append(candidate.run_id)
        return candidate

    monkeypatch.setattr(service.planner, "solve", invalid_candidate)
    before_database = database_contents(manager)
    result = service.get_scenario_lab(manager.context)
    assert len(altered) == 1
    p2 = by_case(result)["p2_blocked"]
    assert p2["comparable"] is False
    assert p2["net_gain"] is None
    assert p2["reasons"]
    assert result["comparable"] is False
    assert database_contents(manager) == before_database


def test_http_lab_is_explicit_read_only_and_has_no_provider_or_hardware_path(lab_api):
    client, manager = lab_api
    before_state = authoritative_state(manager)
    before_database = database_contents(manager)
    response = client.post("/api/scenarios/facility-demo/lab", json={
        "expected_context": manager.context.model_dump(),
        "reserve_basis": "closed_benchmark",
    })
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["hypothetical"] is True
    assert result["provenance"] == "local_scenario_lab"
    assert by_case(result)["p2_blocked"]["net_gain"] == 57
    assert authoritative_state(manager) == before_state
    assert database_contents(manager) == before_database


@pytest.mark.parametrize("corruption", ["missing_context", "extra_field", "invalid_basis", "forged_hash"])
def test_http_lab_rejects_invalid_request_contract(lab_api, corruption):
    client, manager = lab_api
    body = {"expected_context": manager.context.model_dump(), "reserve_basis": "reported"}
    if corruption == "missing_context":
        del body["expected_context"]
    elif corruption == "extra_field":
        body["actuate"] = True
    elif corruption == "invalid_basis":
        body["reserve_basis"] = "optimistic"
    else:
        body["expected_context"]["context_hash"] = "forged"
    before = database_contents(manager)
    response = client.post("/api/scenarios/facility-demo/lab", json=body)
    assert response.status_code == 422
    assert database_contents(manager) == before


def test_http_lab_rejects_stale_context(lab_api):
    client, manager = lab_api
    stale = RunContext(**{**manager.context.model_dump(exclude={"context_hash"}), "state_epoch": "old-process"})
    response = client.post("/api/scenarios/facility-demo/lab", json={"expected_context": stale.model_dump()})
    assert response.status_code == 409


@pytest.mark.parametrize("state", [GateObservedState.UNKNOWN, GateObservedState.TRANSIT, GateObservedState.FAULT])
def test_http_reported_reserve_conflict_is_distinct_from_invalid_input(lab_api, state):
    client, manager = lab_api
    manager.physical_gate_state = state
    response = client.post("/api/scenarios/facility-demo/lab", json={
        "expected_context": manager.context.model_dump(), "reserve_basis": "reported",
    })
    assert response.status_code == 409


def test_http_lab_rejects_unknown_facility(lab_api):
    client, manager = lab_api
    response = client.post("/api/scenarios/not-the-demo/lab", json={
        "expected_context": manager.context.model_dump(), "reserve_basis": "closed_benchmark",
    })
    assert response.status_code == 404
