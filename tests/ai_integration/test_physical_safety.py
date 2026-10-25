"""Physical approval and emergency stop: operator authorization, acknowledgement before recording."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.contracts import ApplyBlockageCommand, EntityType, TargetId
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService


@pytest.fixture
def api(monkeypatch):
    from backend.app import main
    from backend.app.ai.grounding.adapter import GroundingAdapter
    from backend.app.ai.managed.adapter import ManagedAgentAdapter
    manager = StateManager()
    monkeypatch.setattr(main, "state_manager", manager)
    service = ScenarioService(manager)
    monkeypatch.setattr(main, "scenario_service", service)
    monkeypatch.setattr(main, "grounding_adapter", GroundingAdapter(api_key=""))
    monkeypatch.setattr(main, "managed_agent_adapter", ManagedAgentAdapter(service, api_key=""))
    monkeypatch.setattr(main, "active_investigations", {})

    async def no_display():
        return None

    monkeypatch.setattr(main.hardware_bridge, "update_display", no_display)
    return TestClient(main.app), manager, main


def physical(monkeypatch, main):
    monkeypatch.setattr(main.hardware_bridge, "is_simulator", False)


def base_body(ctx, key):
    # Complete request shape, so the authorization check is what decides the response.
    return {"expected_context": ctx.model_dump(), "candidate_alternative": "OPEN_P3",
            "investigation_id": "inv-unsaved", "candidate_run_id": "run-unsaved", "idempotency_key": key}


def test_physical_approval_without_configured_token_is_refused(api, monkeypatch):
    client, manager, main = api
    physical(monkeypatch, main)
    monkeypatch.delenv("SPATIALTWIN_OPERATOR_TOKEN", raising=False)
    response = client.post("/api/hardware/operator-approve", json=base_body(manager.context, "k1"))
    assert response.status_code == 403 and response.json()["detail"] == "operator_token_not_configured"


def test_physical_approval_with_wrong_token_is_refused(api, monkeypatch):
    client, manager, main = api
    physical(monkeypatch, main)
    monkeypatch.setenv("SPATIALTWIN_OPERATOR_TOKEN", "correct-token")
    response = client.post("/api/hardware/operator-approve", json=base_body(manager.context, "k2"),
                           headers={"X-Operator-Token": "wrong-token"})
    assert response.status_code == 403 and response.json()["detail"] == "operator_token_rejected"


def test_emergency_stop_on_physical_hardware_needs_the_token(api, monkeypatch):
    client, _, main = api
    physical(monkeypatch, main)
    monkeypatch.setenv("SPATIALTWIN_OPERATOR_TOKEN", "correct-token")
    assert client.post("/api/hardware/stop").status_code == 403
    assert client.post("/api/hardware/stop", headers={"X-Operator-Token": "correct-token"}).status_code in (200, 502)


def test_unacknowledged_command_is_refused_and_key_stays_reusable(api, monkeypatch):
    client, manager, main = api
    manager.apply_blockage(ApplyBlockageCommand(expected_scenario_revision=1, idempotency_key="block",
                                                target_type=EntityType.PORTAL, target_id=TargetId.P2))
    ctx = manager.context
    outcomes = [(False, "ack_timeout"), (True, "cmd-2")]
    calls = []

    async def device(target):
        calls.append(target)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(main.hardware_bridge, "request_gate_target", device)
    monkeypatch.setattr(main.hardware_bridge, "is_simulator", True)
    result = client.post("/api/scenarios/facility-demo/investigate", json={
        "expected_context": ctx.model_dump(), "investigation_id": uuid4().hex, "mode": "local"}).json()["investigation"]
    body = base_body(ctx, "retry-key")
    body.update(investigation_id=result["investigation_id"],
                candidate_run_id=next(c["run_id"] for c in result["candidate_envelopes"] if c["alternative_id"] == "OPEN_P3"))

    refused = client.post("/api/hardware/operator-approve", json=body)
    assert refused.status_code == 502 and "device_not_acknowledged" in refused.json()["detail"]
    assert manager.store.has_event_key("retry-key") is False

    accepted = client.post("/api/hardware/operator-approve", json=body)
    assert accepted.status_code == 200 and accepted.json()["acknowledged"] is True
    assert manager.store.has_event_key("retry-key") is True
    assert len(calls) == 2


def test_investigation_concurrency_is_capped(api, monkeypatch):
    client, manager, main = api
    import asyncio
    monkeypatch.setattr(main, "_investigation_slots", asyncio.Semaphore(0))  # all slots busy
    response = client.post("/api/scenarios/facility-demo/investigate", json={
        "expected_context": manager.context.model_dump(), "investigation_id": uuid4().hex, "mode": "local"})
    assert response.status_code == 429
