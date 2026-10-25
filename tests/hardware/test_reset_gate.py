"""Reset for next judge: close P3 through the acknowledged command path; observation confirms arrival."""
import asyncio
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.contracts import ApplyBlockageCommand, EntityType, GateObservedState, GateTarget, TargetId
from backend.app.hardware.bridge import HardwareBridge
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService

RESET = "/api/hardware/reset-gate"


def _wire(monkeypatch, main, manager, bridge=None):
    service = ScenarioService(manager)
    monkeypatch.setattr(main, "state_manager", manager)
    monkeypatch.setattr(main, "scenario_service", service)
    monkeypatch.setattr(main, "grounding_adapter", GroundingAdapter(api_key=""))
    monkeypatch.setattr(main, "managed_agent_adapter", ManagedAgentAdapter(service, api_key=""))
    monkeypatch.setattr(main, "active_investigations", {})
    if bridge is not None:
        monkeypatch.setattr(main, "hardware_bridge", bridge)


@pytest.fixture
def stub(monkeypatch):
    from backend.app import main
    manager = StateManager()
    _wire(monkeypatch, main, manager)
    calls = []

    async def device(target):
        calls.append(target)
        return True, "cmd-1"

    async def no_display():
        return None

    monkeypatch.setattr(main.hardware_bridge, "request_gate_target", device)
    monkeypatch.setattr(main.hardware_bridge, "update_display", no_display)
    monkeypatch.setattr(main.hardware_bridge, "is_simulator", True)
    return TestClient(main.app), manager, main, calls


def test_already_closed_sends_no_command(stub):
    client, manager, _, calls = stub
    assert manager.physical_gate_state != GateObservedState.OPEN
    manager.physical_gate_state = GateObservedState.CLOSED
    response = client.post(RESET)
    assert response.status_code == 200 and response.json() == {"status": "ALREADY_CLOSED"}
    assert calls == []


def test_open_gate_sends_closed_and_records_event(stub):
    client, manager, _, calls = stub
    manager.physical_gate_state = GateObservedState.OPEN
    response = client.post(RESET)
    assert response.status_code == 200
    assert response.json() == {"status": "CLOSE_ACKNOWLEDGED", "command_id": "cmd-1"}
    assert calls == [GateTarget.CLOSED]
    # Repeat calls get a fresh idempotency key, so a second reset is not rejected as a duplicate.
    assert client.post(RESET).status_code == 200


def test_refused_while_investigation_running(stub):
    client, manager, main, calls = stub
    manager.physical_gate_state = GateObservedState.OPEN

    async def pending():
        await asyncio.sleep(30)

    loop = asyncio.new_event_loop()
    task = loop.create_task(pending())
    main.active_investigations["inv"] = (task, manager.context)
    try:
        response = client.post(RESET)
        assert response.status_code == 409 and response.json()["detail"] == "investigation_running"
        assert calls == []
        assert client.get("/health").json()["investigation_running"] is True
    finally:
        task.cancel()
        loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
        loop.close()


def test_no_ack_is_502(stub, monkeypatch):
    client, manager, main, _ = stub
    manager.physical_gate_state = GateObservedState.OPEN

    async def refuse(target):
        return False, "ack_timeout"

    monkeypatch.setattr(main.hardware_bridge, "request_gate_target", refuse)
    response = client.post(RESET)
    assert response.status_code == 502 and response.json()["detail"] == "device_not_acknowledged:ack_timeout"


def test_physical_requires_operator_token_first(stub, monkeypatch):
    client, manager, main, calls = stub
    manager.physical_gate_state = GateObservedState.OPEN
    monkeypatch.setattr(main.hardware_bridge, "is_simulator", False)
    monkeypatch.setenv("SPATIALTWIN_OPERATOR_TOKEN", "right-token")
    monkeypatch.delenv("SPATIALTWIN_OPERATORS", raising=False)
    assert client.post(RESET).status_code == 403
    assert client.post(RESET, headers={"X-Operator-Token": "wrong"}).status_code == 403
    assert calls == []
    ok = client.post(RESET, headers={"X-Operator-Token": "right-token"})
    assert ok.status_code == 200 and calls == [GateTarget.CLOSED]


def test_health_reports_no_investigation_by_default(stub):
    client, *_ = stub
    assert client.get("/health").json()["investigation_running"] is False


def _wait_for(manager, state, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if manager.physical_gate_state == state:
            return True
        time.sleep(0.05)
    return False


def test_full_cycle_on_simulator(monkeypatch):
    """approve -> OPEN observed -> reset-gate -> CLOSED observed, against the real simulator."""
    from backend.app import main
    monkeypatch.delenv("SERIAL_PORT", raising=False)
    manager = StateManager()
    bridge = HardwareBridge(manager, port="")
    _wire(monkeypatch, main, manager, bridge)
    with TestClient(main.app) as client:
        client.post("/api/scenarios/facility-demo/commands", json={
            "type": "APPLY_BLOCKAGE", "expected_context": manager.context.model_dump(),
            "expected_scenario_revision": manager.context.scenario_revision, "idempotency_key": uuid4().hex,
            "target_type": "portal", "target_id": "P2"}).raise_for_status()
        ctx = manager.context
        inv = client.post("/api/scenarios/facility-demo/investigate", json={
            "expected_context": ctx.model_dump(), "investigation_id": uuid4().hex, "mode": "local"}).json()["investigation"]
        run_id = next(c["run_id"] for c in inv["candidate_envelopes"] if c["alternative_id"] == "OPEN_P3")
        approve = client.post("/api/hardware/operator-approve", json={
            "expected_context": ctx.model_dump(), "candidate_alternative": "OPEN_P3",
            "investigation_id": inv["investigation_id"], "candidate_run_id": run_id, "idempotency_key": uuid4().hex})
        assert approve.status_code == 200, approve.text
        assert _wait_for(manager, GateObservedState.OPEN)
        reset = client.post(RESET)
        assert reset.status_code == 200 and reset.json()["status"] == "CLOSE_ACKNOWLEDGED"
        assert _wait_for(manager, GateObservedState.CLOSED)
        assert client.post(RESET).json() == {"status": "ALREADY_CLOSED"}


def test_old_investigation_cannot_be_approved_after_reset_scenario(stub):
    client, manager, main, calls = stub
    client.post("/api/scenarios/facility-demo/commands", json={
        "type": "APPLY_BLOCKAGE", "expected_context": manager.context.model_dump(),
        "expected_scenario_revision": manager.context.scenario_revision, "idempotency_key": uuid4().hex,
        "target_type": "portal", "target_id": "P2"}).raise_for_status()
    old = manager.context
    inv = client.post("/api/scenarios/facility-demo/investigate", json={
        "expected_context": old.model_dump(), "investigation_id": uuid4().hex, "mode": "local"}).json()["investigation"]
    run_id = next(c["run_id"] for c in inv["candidate_envelopes"] if c["alternative_id"] == "OPEN_P3")
    reset = client.post("/api/scenarios/facility-demo/commands", json={
        "type": "RESET_SCENARIO", "expected_context": old.model_dump(),
        "expected_scenario_revision": old.scenario_revision, "idempotency_key": uuid4().hex})
    assert reset.status_code == 200, reset.text
    body = {"expected_context": old.model_dump(), "candidate_alternative": "OPEN_P3",
            "investigation_id": inv["investigation_id"], "candidate_run_id": run_id, "idempotency_key": uuid4().hex}
    assert client.post("/api/hardware/operator-approve", json=body).status_code == 409
    body["expected_context"] = manager.context.model_dump()
    assert client.post("/api/hardware/operator-approve", json=body).status_code == 409
    assert calls == []
