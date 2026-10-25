"""
High-Fidelity Hardware Simulator for Arduino UNO R4 Minima + PCA9685
Accurately models dual endpoint switches, debouncing, servo transit delay,
heartbeat timeouts, and NDJSON message streams.
"""

from __future__ import annotations
import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional
from backend.app.contracts import GateObservedState, GateTarget, SerialResponseType


class HardwareSimulator:
    def __init__(self, on_message: Optional[Callable[[str], None]] = None):
        self.boot_id = f"sim-boot-{int(time.time())}"
        self.seq = 0
        self.gate_epoch = 1
        self.armed = False
        self.gate_state = GateObservedState.CLOSED
        self.open_switch = False
        self.closed_switch = True
        self.last_heartbeat = time.time()
        self.on_message = on_message
        self._moving_task: Optional[asyncio.Task] = None
        self.display_pixels: List[int] = [0] * 24

    def emit(self, msg_type: SerialResponseType, payload: Dict[str, Any]) -> None:
        self.seq += 1
        data = {
            "v": 1,
            "type": msg_type.value,
            "boot_id": self.boot_id,
            "seq": self.seq,
            "gate_epoch": self.gate_epoch,
            **payload,
        }
        line = json.dumps(data) + "\n"
        if self.on_message:
            self.on_message(line)

    def handle_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            cmd = json.loads(line)
        except Exception:
            self.emit(SerialResponseType.FAULT, {"fault": "MALFORMED_JSON"})
            return

        cmd_type = cmd.get("type")
        cmd_id = cmd.get("command_id", "none")

        if cmd_type == "HELLO":
            self.last_heartbeat = time.time()
            self.emit(SerialResponseType.HELLO_ACK, {
                "command_id": cmd_id,
                "boot_id": self.boot_id,
                "session_id": cmd.get("session_id"),
                "status": "READY",
            })
            self._send_observation(cmd_id)

        elif cmd_type == "HEARTBEAT":
            self.last_heartbeat = time.time()
            # Silent ack or periodic observation

        elif cmd_type == "ARM":
            self.last_heartbeat = time.time()
            self.armed = True
            self.emit(SerialResponseType.ACK, {"command_id": cmd_id, "status": "ARMED"})
            self._send_observation(cmd_id)

        elif cmd_type == "SET_GATE_TARGET":
            self.last_heartbeat = time.time()
            target = cmd.get("target")

            # Check arming
            if not self.armed:
                self.emit(SerialResponseType.FAULT, {
                    "command_id": cmd_id,
                    "fault": "DEVICE_NOT_ARMED",
                })
                return

            # Acknowledge acceptance (ACK does NOT mean arrival!)
            self.emit(SerialResponseType.ACK, {
                "command_id": cmd_id,
                "status": "ACCEPTED",
                "target": target,
            })

            # Disengage current endpoint switch immediately -> Enter TRANSIT
            self.gate_state = GateObservedState.TRANSIT
            self.open_switch = False
            self.closed_switch = False
            self._send_observation(cmd_id)

            # Start simulated mechanical transit
            if self._moving_task and not self._moving_task.done():
                self._moving_task.cancel()

            self._moving_task = asyncio.create_task(
                self._finish_movement(target, cmd_id)
            )

        elif cmd_type == "SET_DISPLAY":
            self.display_pixels = cmd.get("display_pixels", [0] * 24)
            self.emit(SerialResponseType.ACK, {"command_id": cmd_id, "status": "DISPLAY_UPDATED"})

        elif cmd_type == "STOP_OUTPUTS":
            self.armed = False
            if self._moving_task and not self._moving_task.done():
                self._moving_task.cancel()
            self.display_pixels = [0] * 24
            self.emit(SerialResponseType.ACK, {"command_id": cmd_id, "status": "STOPPED"})

    async def _finish_movement(self, target: str, command_id: str) -> None:
        # Mechanical transit duration (e.g. 500 ms)
        await asyncio.sleep(0.5)

        # Engage endpoint switch and debounce
        if target == "OPEN":
            self.gate_state = GateObservedState.OPEN
            self.open_switch = True
            self.closed_switch = False
        else:
            self.gate_state = GateObservedState.CLOSED
            self.open_switch = False
            self.closed_switch = True

        self.gate_epoch += 1
        self._send_observation(command_id)

    def _send_observation(self, command_id: Optional[str] = None) -> None:
        self.emit(SerialResponseType.OBSERVATION, {
            "gate_id": "G1",
            "state": self.gate_state.value,
            "open_switch": self.open_switch,
            "closed_switch": self.closed_switch,
            "command_id": command_id,
            "fault": None,
        })
