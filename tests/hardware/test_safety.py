"""Hardware safety: a movement is acknowledged only by a matching device ACK; failures never look like success."""
import json

import pytest

from backend.app.contracts import GateTarget
from backend.app.hardware.bridge import HardwareBridge, HardwareUnavailable
from backend.app.state.manager import StateManager


@pytest.fixture
def state():
    return StateManager()


async def started_simulator(state):
    bridge = HardwareBridge(state, port="")
    await bridge.start()
    return bridge


@pytest.mark.asyncio
async def test_simulator_move_is_acknowledged_by_matching_command(state, monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_MODE", "demo")
    bridge = await started_simulator(state)
    ok, command_id = await bridge.request_gate_target(GateTarget.OPEN)
    assert ok and command_id.startswith("cmd-")


@pytest.mark.asyncio
async def test_unplugged_serial_port_is_a_failure_not_a_success(state):
    bridge = HardwareBridge(state, port="")
    bridge.is_simulator = False
    bridge.serial_conn = None
    bridge.boot_id, bridge.armed = "boot-a", True
    ok, reason = await bridge.request_gate_target(GateTarget.OPEN)
    assert ok is False and reason == "serial_disconnected"


@pytest.mark.asyncio
async def test_missing_ack_times_out_as_failure(state):
    bridge = await started_simulator(state)
    bridge._send_raw = lambda line: None  # the device never answers
    ok, reason = await bridge._send_and_await_ack("{}", "cmd-silent", timeout=0.05)
    assert ok is False and reason == "ack_timeout"
    assert "cmd-silent" not in bridge._pending


@pytest.mark.asyncio
async def test_device_fault_for_the_command_is_a_failure(state):
    bridge = await started_simulator(state)
    fault = json.dumps({"v": 1, "type": "FAULT", "command_id": "cmd-fault", "fault": "DEVICE_NOT_ARMED"})
    bridge._send_raw = lambda line: bridge._handle_incoming_line(fault)
    ok, reason = await bridge._send_and_await_ack("{}", "cmd-fault")
    assert ok is False and reason == "DEVICE_NOT_ARMED"


@pytest.mark.asyncio
async def test_ack_for_another_command_does_not_acknowledge_this_one(state):
    bridge = await started_simulator(state)
    other = json.dumps({"v": 1, "type": "ACK", "command_id": "cmd-other", "status": "OK"})
    bridge._send_raw = lambda line: bridge._handle_incoming_line(other)
    ok, reason = await bridge._send_and_await_ack("{}", "cmd-mine", timeout=0.05)
    assert ok is False and reason == "ack_timeout"


@pytest.mark.asyncio
async def test_production_never_falls_back_to_simulator(state, monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_MODE", "production")
    bridge = HardwareBridge(state, port="/dev/spatialtwin-does-not-exist")
    await bridge.start()
    assert bridge.is_simulator is False
    assert bridge.transport_available() is False
    assert bridge.unavailable_reason == "serial_unavailable"


@pytest.mark.asyncio
async def test_production_without_serial_port_is_unavailable(state, monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_MODE", "production")
    bridge = HardwareBridge(state, port="")
    await bridge.start()
    assert bridge.is_simulator is False and bridge.transport_available() is False


@pytest.mark.asyncio
async def test_demo_still_falls_back_to_simulator(state, monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_MODE", "demo")
    bridge = HardwareBridge(state, port="/dev/spatialtwin-does-not-exist")
    await bridge.start()
    assert bridge.is_simulator is True


@pytest.mark.asyncio
async def test_observation_from_another_boot_is_ignored(state):
    bridge = await started_simulator(state)
    seen = []
    state.update_physical_observation = lambda **kwargs: seen.append(kwargs) or (False, None)
    bridge.boot_id = "boot-a"
    stale = json.dumps({"v": 1, "type": "OBSERVATION", "boot_id": "boot-b", "seq": 9, "gate_epoch": 1, "state": "OPEN"})
    bridge._handle_incoming_line(stale)
    assert seen == []


@pytest.mark.asyncio
async def test_emergency_stop_is_acknowledged_and_disarms(state):
    bridge = await started_simulator(state)
    bridge.armed = True
    ok, command_id = await bridge.request_stop()
    assert ok and command_id.startswith("cmd-") and bridge.armed is False


@pytest.mark.asyncio
async def test_display_refresh_without_transport_does_not_raise(state):
    bridge = HardwareBridge(state, port="")
    bridge.is_simulator = False
    bridge.serial_conn = None
    await bridge.update_display()  # informational only: must not fail a route


@pytest.mark.asyncio
async def test_firmware_arm_ack_without_command_id_arms_the_bridge(state):
    # The firmware's ARMED acknowledgement has no command_id; it answers the one ARM in flight.
    bridge = await started_simulator(state)
    bridge.armed = False
    armed_ack = json.dumps({"v": 1, "type": "ACK", "status": "ARMED"})
    bridge._send_raw = lambda line: bridge._handle_incoming_line(armed_ack)
    assert await bridge.send_arm() is True and bridge.armed is True


@pytest.mark.asyncio
async def test_unmatched_ack_without_command_id_does_not_arm(state):
    bridge = await started_simulator(state)
    bridge.armed = False
    stray = json.dumps({"v": 1, "type": "ACK", "status": "ACCEPTED"})
    bridge._send_raw = lambda line: bridge._handle_incoming_line(stray)
    assert await bridge.send_arm() is False and bridge.armed is False
