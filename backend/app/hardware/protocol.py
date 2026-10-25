"""
Hardware Serial Bridge NDJSON Protocol Envelopes
Contract v: 1
"""

import json
from typing import Any, Dict, List, Optional
from backend.app.contracts import (
    DeviceObservation,
    GateObservedState,
    GateTarget,
    HostCommandEnvelope,
    SerialCommandType,
    SerialResponseType,
)


def make_hello_command(session_id: str, command_id: str) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.HELLO,
        session_id=session_id,
        command_id=command_id,
    )
    return cmd.model_dump_json() + "\n"


def make_heartbeat_command(session_id: str, command_id: str) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.HEARTBEAT,
        session_id=session_id,
        command_id=command_id,
    )
    return cmd.model_dump_json() + "\n"


def make_arm_command(session_id: str, command_id: str, boot_id: str) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.ARM,
        session_id=session_id,
        command_id=command_id,
        expected_boot_id=boot_id,
    )
    return cmd.model_dump_json() + "\n"


def make_gate_target_command(
    session_id: str,
    command_id: str,
    target: GateTarget,
    boot_id: str,
    gate_epoch: int,
    scenario_revision: int,
) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.SET_GATE_TARGET,
        session_id=session_id,
        command_id=command_id,
        expected_boot_id=boot_id,
        expected_gate_epoch=gate_epoch,
        scenario_revision=scenario_revision,
        gate_id="G1",
        target=target,
    )
    return cmd.model_dump_json() + "\n"


def make_display_command(session_id: str, command_id: str, pixels: List[int]) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.SET_DISPLAY,
        session_id=session_id,
        command_id=command_id,
        display_pixels=pixels,
    )
    return cmd.model_dump_json() + "\n"


# A device envelope is a few hundred bytes; anything near this size is noise or an attack.
MAX_LINE_BYTES = 2048
ALLOWED_RESPONSE_TYPES = frozenset(item.value for item in SerialResponseType)


def parse_device_line(line: str) -> Optional[Dict[str, Any]]:
    """Parses one device line. Oversized lines and unknown response types are dropped."""
    if len(line) > MAX_LINE_BYTES:
        return None
    line = line.strip()
    if not line:
        return None
    try:
        data = json.loads(line)
    except (json.JSONDecodeError, RecursionError):
        return None
    if isinstance(data, dict) and data.get("v") == 1 and data.get("type") in ALLOWED_RESPONSE_TYPES:
        return data
    return None


def make_stop_command(session_id: str, command_id: str) -> str:
    cmd = HostCommandEnvelope(
        v=1,
        type=SerialCommandType.STOP_OUTPUTS,
        session_id=session_id,
        command_id=command_id,
    )
    return cmd.model_dump_json() + "\n"
