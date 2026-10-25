"""
Hardware Bridge: Integrates Physical Serial or In-Memory Simulator with StateManager
Manages heartbeat, telemetry observation stream, operator-approved gate movements,
and LED display refresh.
"""

from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional
import serial

from backend.app.contracts import (
    GateObservedState,
    GateTarget,
    HostCommandEnvelope,
    SerialCommandType,
    SerialResponseType,
)
from backend.app.hardware.display import DisplayProjector
from backend.app.hardware.protocol import (
    make_arm_command,
    make_display_command,
    make_gate_target_command,
    make_heartbeat_command,
    make_hello_command,
    parse_device_line,
)
from backend.app.hardware.simulator import HardwareSimulator
from backend.app.state.manager import StateManager

logger = logging.getLogger("spatialtwin.hardware")


class HardwareBridge:
    def __init__(self, state_manager: StateManager, port: Optional[str] = None, baud: int = 115200):
        self.state_manager = state_manager
        self.port = port or os.environ.get("SERIAL_PORT", "").strip()
        self.baud = baud
        self.session_id = f"host-sess-{int(time.time())}"
        self.cmd_counter = 0

        self.projector = DisplayProjector()
        self.serial_conn: Optional[serial.Serial] = None
        self.simulator: Optional[HardwareSimulator] = None
        self.is_simulator = False

        self.boot_id: Optional[str] = None
        self.gate_epoch: int = 1
        self.armed = False
        self.is_running = False

        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None

    def _next_cmd_id(self) -> str:
        self.cmd_counter += 1
        return f"cmd-{self.cmd_counter}"

    async def start(self) -> None:
        self.is_running = True
        if self.port:
            try:
                logger.info(f"Connecting to hardware serial port: {self.port} at {self.baud}...")
                self.serial_conn = serial.Serial(self.port, self.baud, timeout=0.1)
                self.is_simulator = False
                logger.info("Physical serial connection established.")
            except Exception as e:
                logger.warning(f"Could not open serial port {self.port}: {e}. Falling back to simulator.")
                self._init_simulator()
        else:
            logger.info("No SERIAL_PORT configured; starting high-fidelity HardwareSimulator.")
            self._init_simulator()

        # Start background heartbeat and reader
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self.serial_conn and not self.is_simulator:
            self._reader_task = asyncio.create_task(self._physical_reader_loop())

        # Send initial HELLO handshake
        await self.send_hello()

    def _init_simulator(self) -> None:
        self.is_simulator = True
        self.simulator = HardwareSimulator(on_message=self._on_simulator_message)
        self.boot_id = self.simulator.boot_id

    def _on_simulator_message(self, line: str) -> None:
        self._handle_incoming_line(line)

    def _send_raw(self, line: str) -> None:
        if self.is_simulator and self.simulator:
            self.simulator.handle_line(line)
        elif self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(line.encode("utf-8"))

    async def send_hello(self) -> None:
        cmd_id = self._next_cmd_id()
        line = make_hello_command(self.session_id, cmd_id)
        self._send_raw(line)

    async def send_arm(self) -> None:
        if not self.boot_id:
            return
        cmd_id = self._next_cmd_id()
        line = make_arm_command(self.session_id, cmd_id, self.boot_id)
        self._send_raw(line)
        self.armed = True

    async def request_gate_target(self, target: GateTarget) -> Tuple[bool, str]:
        """
        Sends move command. Requires that the device has been armed.
        """
        if not self.boot_id:
            return False, "Hardware handshake not completed yet"
        if not self.armed:
            await self.send_arm()

        cmd_id = self._next_cmd_id()
        line = make_gate_target_command(
            session_id=self.session_id,
            command_id=cmd_id,
            target=target,
            boot_id=self.boot_id,
            gate_epoch=self.gate_epoch,
            scenario_revision=self.state_manager.context.scenario_revision,
        )
        self._send_raw(line)
        return True, cmd_id

    async def update_display(self) -> None:
        pixels = self.projector.project(
            current_plan=self.state_manager.current_plan,
            blocked_portals=self.state_manager.blocked_portals,
            gate_state=self.state_manager.physical_gate_state,
        )
        cmd_id = self._next_cmd_id()
        line = make_display_command(self.session_id, cmd_id, pixels)
        self._send_raw(line)

    def _handle_incoming_line(self, line: str) -> None:
        data = parse_device_line(line)
        if not data:
            return

        msg_type = data.get("type")
        if msg_type == SerialResponseType.HELLO_ACK.value:
            self.boot_id = data.get("boot_id")
            logger.info(f"Received HELLO_ACK from boot_id: {self.boot_id}")
            asyncio.create_task(self.send_arm())

        elif msg_type == SerialResponseType.OBSERVATION.value:
            boot_id = data.get("boot_id", "")
            seq = data.get("seq", 0)
            epoch = data.get("gate_epoch", self.gate_epoch)
            self.gate_epoch = epoch
            raw_state = data.get("state", "UNKNOWN")

            try:
                state_enum = GateObservedState(raw_state)
            except ValueError:
                state_enum = GateObservedState.UNKNOWN

            changed, new_plan = self.state_manager.update_physical_observation(
                new_state=state_enum,
                boot_id=boot_id,
                seq=seq,
                gate_epoch=epoch,
            )
            # When state changes, refresh display
            asyncio.create_task(self.update_display())

    async def _physical_reader_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while self.is_running and self.serial_conn and self.serial_conn.is_open:
            try:
                line_bytes = await loop.run_in_executor(None, self.serial_conn.readline)
                line = line_bytes.decode("utf-8", errors="replace")
                if line:
                    self._handle_incoming_line(line)
            except Exception as e:
                logger.error(f"Error reading physical serial: {e}")
                await asyncio.sleep(0.5)

    async def _heartbeat_loop(self) -> None:
        while self.is_running:
            try:
                cmd_id = self._next_cmd_id()
                line = make_heartbeat_command(self.session_id, cmd_id)
                self._send_raw(line)
                await asyncio.sleep(0.25)  # 250 ms heartbeat
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(1.0)

    async def stop(self) -> None:
        self.is_running = False
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
        if self._reader_task:
            self._reader_task.cancel()
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
