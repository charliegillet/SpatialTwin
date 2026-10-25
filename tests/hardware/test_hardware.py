import asyncio
import json
import pytest
from backend.app.contracts import GateObservedState, GateTarget, SerialResponseType
from backend.app.hardware.protocol import (
    make_arm_command,
    make_gate_target_command,
    make_hello_command,
    parse_device_line,
)
from backend.app.hardware.simulator import HardwareSimulator


def test_protocol_serialization_and_parsing():
    parsed = parse_device_line('{"v":1,"type":"HELLO_ACK","boot_id":"b1"}\n')
    assert parsed is not None
    assert parsed["v"] == 1
    assert parsed["type"] == "HELLO_ACK"
    # Host-to-device command types are not valid device responses.
    assert parse_device_line(make_hello_command("sess-1", "cmd-1")) is None
    assert parse_device_line('{"v":1,"type":"EXPLODE"}') is None
    assert parse_device_line('{"v":1,"type":"ACK","pad":"' + "x" * 3000 + '"}') is None


@pytest.mark.asyncio
async def test_hardware_simulator_movement_and_switches():
    emitted = []

    def on_msg(line: str):
        parsed = json.loads(line)
        emitted.append(parsed)

    sim = HardwareSimulator(on_message=on_msg)

    # 1. Hello
    sim.handle_line(make_hello_command("sess-1", "cmd-hello"))
    assert any(m.get("type") == "HELLO_ACK" for m in emitted)

    # 2. Arm
    sim.handle_line(make_arm_command("sess-1", "cmd-arm", sim.boot_id))
    assert sim.armed is True

    # 3. Command Move to OPEN
    emitted.clear()
    sim.handle_line(
        make_gate_target_command("sess-1", "cmd-move-1", GateTarget.OPEN, sim.boot_id, 1, 1)
    )

    # Immediate response is ACK (ACCEPTED) and TRANSIT observation
    assert any(m.get("type") == "ACK" and m.get("status") == "ACCEPTED" for m in emitted)
    assert any(m.get("type") == "OBSERVATION" and m.get("state") == "TRANSIT" for m in emitted)

    # Wait for mechanical transit to complete
    await asyncio.sleep(0.6)

    # Endpoint confirmed
    assert sim.gate_state == GateObservedState.OPEN
    assert sim.open_switch is True
    assert sim.closed_switch is False
    assert any(
        m.get("type") == "OBSERVATION"
        and m.get("state") == "OPEN"
        and m.get("open_switch") is True
        for m in emitted
    )
