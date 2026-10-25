"""SET_DISPLAY compact px line: alphabet, size budget, per-state encoding, simulator decode, bridge outcomes."""
import asyncio
import json

import pytest

from backend.app.contracts import GateObservedState
from backend.app.hardware.bridge import DISPLAY_UPDATED, HardwareBridge
from backend.app.hardware.display import (
    DisplayProjector, PX_ALPHABET, PX_CODE_RGB, decode_px, encode_px,
)
from backend.app.hardware.protocol import MAX_DISPLAY_LINE_BYTES, make_display_command
from backend.app.hardware.simulator import HardwareSimulator
from backend.app.state.manager import StateManager


def project(plan, blocked, gate):
    projector = DisplayProjector()
    projector.project(plan, set(blocked), gate)
    return projector.current_px


def invalid_copy(plan):
    return plan.model_copy(update={
        "validator_report": plan.validator_report.model_copy(update={"is_valid": False})})


def test_code_table_is_one_character_per_pixel_and_unique_steady_colours():
    assert all(len(code) == 1 for code in PX_CODE_RGB)
    assert set(PX_ALPHABET) == set("0GRABUgrau")
    steady = [rgb for code, rgb in PX_CODE_RGB.items() if code.isupper() or code == "0"]
    assert len(steady) == len(set(steady))


def test_px_encoding_for_each_display_state():
    plan = StateManager().current_plan
    # Clear board, valid plan, gate closed: B1/B2 carry flow (green), P3 dim blue.
    clear = project(plan, [], GateObservedState.CLOSED)
    assert len(clear) == 24 and set(clear) <= set(PX_ALPHABET)
    assert clear[16:] == "B" * 8 and clear[:8] == "G" * 8
    # P2 blocked: red on LEDs 8..15 only.
    assert project(plan, ["P2"], GateObservedState.CLOSED)[8:16] == "R" * 8
    assert project(plan, ["P2"], GateObservedState.CLOSED)[:8] == clear[:8]
    # P3 states.
    assert project(plan, [], GateObservedState.OPEN)[16:] == "G" * 8
    assert project(plan, [], GateObservedState.TRANSIT)[16:] == "A" * 8
    assert project(plan, [], GateObservedState.FAULT)[16:] == "R" * 8
    assert project(plan, [], GateObservedState.UNKNOWN)[16:] == "U" * 8
    # Never claim flow from a plan the checker rejected.
    assert "G" not in project(invalid_copy(plan), [], GateObservedState.CLOSED)[:16]
    assert project(invalid_copy(plan), [], GateObservedState.CLOSED)[:16] == "B" * 16


def test_encode_decode_round_trip_and_rejects_bad_input():
    plan = StateManager().current_plan
    projector = DisplayProjector()
    pixels = projector.project(plan, {"P2"}, GateObservedState.OPEN)
    assert decode_px(encode_px(pixels)) == pixels
    with pytest.raises(ValueError):
        encode_px(pixels[:23])
    with pytest.raises(ValueError):
        encode_px([0x123456] * 24)
    with pytest.raises(ValueError):
        decode_px("G" * 23)
    with pytest.raises(ValueError):
        decode_px("G" * 23 + "X")
    assert decode_px("g" * 24) == decode_px("G" * 24)  # flashing decodes to its steady colour


def test_display_line_is_compact_even_with_long_ids():
    px = "R" * 8 + "G" * 8 + "U" * 8
    line = make_display_command("host-sess-1761400000", "cmd-999999", px)
    assert line.endswith("\n") and len(line.encode()) <= MAX_DISPLAY_LINE_BYTES
    data = json.loads(line)
    assert data == {"v": 1, "type": "SET_DISPLAY", "session_id": "host-sess-1761400000",
                    "command_id": "cmd-999999", "px": px}
    assert "display_pixels" not in data
    for bad in ("G" * 23, "G" * 25, "G" * 23 + "x", "G" * 23 + '"'):
        with pytest.raises(ValueError):
            make_display_command("s", "c", bad)


def test_simulator_decodes_px_and_stop_keeps_leds_dark_until_arm():
    replies = []
    sim = HardwareSimulator(on_message=lambda line: replies.append(json.loads(line)))
    px = "R" * 8 + "G" * 8 + "U" * 8
    sim.handle_line(make_display_command("s", "cmd-1", px))
    assert sim.display_pixels == decode_px(px)
    assert replies[-1]["type"] == "ACK" and replies[-1]["status"] == DISPLAY_UPDATED
    assert replies[-1]["command_id"] == "cmd-1"

    sim.handle_line(json.dumps({"v": 1, "type": "STOP_OUTPUTS", "command_id": "cmd-2"}))
    assert sim.display_pixels == [0] * 24
    sim.handle_line(make_display_command("s", "cmd-3", px))
    assert replies[-1]["type"] == "FAULT" and replies[-1]["command_id"] == "cmd-3"
    assert sim.display_pixels == [0] * 24
    sim.handle_line(json.dumps({"v": 1, "type": "ARM", "command_id": "cmd-4"}))
    sim.handle_line(make_display_command("s", "cmd-5", px))
    assert replies[-1]["status"] == DISPLAY_UPDATED and sim.display_pixels == decode_px(px)

    sim.handle_line(json.dumps({"v": 1, "type": "SET_DISPLAY", "command_id": "cmd-6", "px": "bad"}))
    assert replies[-1]["type"] == "FAULT" and replies[-1]["fault"] == "BAD_PX"
    assert sim.display_pixels == decode_px(px)


@pytest.mark.asyncio
async def test_bridge_display_reaches_simulator_and_reports_updated():
    bridge = HardwareBridge(StateManager(), port="")
    await bridge.start()
    await bridge.update_display()
    await asyncio.sleep(0.05)
    assert bridge.last_display_status == DISPLAY_UPDATED
    assert bridge.simulator.display_pixels == decode_px(bridge.projector.current_px)
    await bridge.stop()


@pytest.mark.asyncio
async def test_bridge_display_fault_is_visible_and_never_disarms_or_blocks(caplog):
    bridge = HardwareBridge(StateManager(), port="")
    bridge.is_simulator = False
    bridge.boot_id, bridge.armed = "boot-a", True

    def fault(line):
        command_id = json.loads(line)["command_id"]
        bridge._handle_incoming_line(json.dumps(
            {"v": 1, "type": "FAULT", "command_id": command_id, "fault": "BAD_PX"}))
    bridge.serial_conn = type("C", (), {"is_open": True, "write": lambda self, b: fault(b.decode())})()
    with caplog.at_level("WARNING", logger="spatialtwin.hardware"):
        await asyncio.wait_for(bridge.update_display(), 0.5)  # returns at once
        await asyncio.sleep(0.05)
    assert bridge.last_display_status == "failed:BAD_PX"
    assert "Display update not confirmed" in caplog.text
    assert bridge.armed is True


@pytest.mark.asyncio
async def test_bridge_late_display_ack_does_not_block_and_times_out_visibly(monkeypatch):
    from backend.app.hardware import bridge as bridge_module
    monkeypatch.setattr(bridge_module, "ACK_TIMEOUT_S", 0.05)
    bridge = HardwareBridge(StateManager(), port="")
    bridge.is_simulator = False
    bridge.serial_conn = type("C", (), {"is_open": True, "write": lambda self, b: None})()
    await asyncio.wait_for(bridge.update_display(), 0.5)
    await asyncio.sleep(0.15)
    assert bridge.last_display_status == "failed:ack_timeout"
    assert bridge._pending == {}
