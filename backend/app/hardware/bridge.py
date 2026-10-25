"""
Hardware Bridge: Integrates Physical Serial or In-Memory Simulator with StateManager
Manages heartbeat, telemetry observation stream, operator-approved gate movements,
and LED display refresh.

Safety rules enforced here:
- A movement is reported as acknowledged only after the device replies with an ACK
  carrying the same command_id. A closed port, a write error, a FAULT or a missing
  ACK within ACK_TIMEOUT_S is a failure, never a silent success.
- The serial-to-simulator fallback is refused in production mode.
- Observations from a different boot are ignored.
- request_stop() sends STOP_OUTPUTS and disarms the host view, whatever the device answers.
"""

from __future__ import annotations
import asyncio
import logging
import os
import time
from typing import Any, Coroutine, Dict, Optional, Set, Tuple
import serial

from backend.app.contracts import (
    GateObservedState,
    GateTarget,
    SerialResponseType,
)
from backend.app.hardware.display import DisplayProjector
from backend.app.hardware.protocol import (
    make_arm_command,
    make_display_command,
    make_gate_target_command,
    make_heartbeat_command,
    make_hello_command,
    make_stop_command,
    MAX_LINE_BYTES,
    parse_device_line,
)
from backend.app.hardware.simulator import HardwareSimulator
from backend.app.state.manager import StateManager

logger = logging.getLogger("spatialtwin.hardware")

ACK_TIMEOUT_S = 3.0
# "device_not_armed" is the host's own reason; the firmware reports NOT_ARMED.
DISPLAY_UPDATED = "DISPLAY_UPDATED"
NOT_ARMED_FAULTS = frozenset({"device_not_armed", "not_armed"})


class HardwareUnavailable(RuntimeError):
    """No device transport can accept a command."""


def _production_mode() -> bool:
    return os.environ.get("SPATIALTWIN_MODE", "demo") == "production"


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
        self.unavailable_reason: Optional[str] = None
        self.last_display_status: Optional[str] = None

        self.boot_id: Optional[str] = None
        self.gate_epoch: int = 1
        self.armed = False
        self.is_running = False

        self._pending: Dict[str, asyncio.Future] = {}
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reader_task: Optional[asyncio.Task] = None
        # The event loop holds only weak references to tasks, so fire-and-forget work is kept here.
        self._background: Set[asyncio.Task] = set()

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._background.add(task)
        task.add_done_callback(self._background.discard)
        return task

    def _next_cmd_id(self) -> str:
        self.cmd_counter += 1
        return f"cmd-{self.cmd_counter}"

    def transport_available(self) -> bool:
        if self.is_simulator:
            return self.simulator is not None
        return bool(self.serial_conn and self.serial_conn.is_open)

    async def start(self) -> None:
        self.is_running = True
        if self.port:
            try:
                logger.info(f"Connecting to hardware serial port: {self.port} at {self.baud}...")
                self.serial_conn = serial.Serial(self.port, self.baud, timeout=0.1)
                self.is_simulator = False
                logger.info("Physical serial connection established.")
            except Exception as e:
                if _production_mode():
                    # Production never substitutes a simulator for hardware it was asked to drive.
                    self.unavailable_reason = "serial_unavailable"
                    logger.error(f"Could not open serial port {self.port}: {e}. Production mode: no simulator fallback.")
                else:
                    logger.warning(f"Could not open serial port {self.port}: {e}. Falling back to simulator.")
                    self._init_simulator()
        else:
            if _production_mode():
                self.unavailable_reason = "serial_not_configured"
                logger.error("SERIAL_PORT is not configured in production mode; no simulator fallback.")
            else:
                logger.info("No SERIAL_PORT configured; starting high-fidelity HardwareSimulator.")
                self._init_simulator()

        # Start background heartbeat and reader
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        if self.serial_conn and not self.is_simulator:
            self._reader_task = asyncio.create_task(self._physical_reader_loop())

        if self.transport_available():
            await self.send_hello()

    def _init_simulator(self) -> None:
        self.is_simulator = True
        self.simulator = HardwareSimulator(on_message=self._on_simulator_message)
        self.boot_id = self.simulator.boot_id

    def _on_simulator_message(self, line: str) -> None:
        self._handle_incoming_line(line)

    def _send_raw(self, line: str) -> None:
        """Writes one envelope. Raises HardwareUnavailable instead of dropping the write."""
        if self.is_simulator and self.simulator:
            self.simulator.handle_line(line)
            return
        if not (self.serial_conn and self.serial_conn.is_open):
            raise HardwareUnavailable(self.unavailable_reason or "serial_disconnected")
        try:
            self.serial_conn.write(line.encode("utf-8"))
        except (serial.SerialException, OSError) as error:
            raise HardwareUnavailable("serial_write_failed") from error

    async def _send_and_await_ack(self, line: str, command_id: str,
                                  timeout: float = ACK_TIMEOUT_S) -> Tuple[bool, str]:
        """Sends one command and waits for the ACK or FAULT that echoes its command_id."""
        future = asyncio.get_running_loop().create_future()
        self._pending[command_id] = future
        try:
            self._send_raw(line)
            return await asyncio.wait_for(future, timeout)
        except HardwareUnavailable as error:
            return False, str(error)
        except asyncio.TimeoutError:
            return False, "ack_timeout"
        finally:
            self._pending.pop(command_id, None)

    async def send_hello(self) -> None:
        cmd_id = self._next_cmd_id()
        line = make_hello_command(self.session_id, cmd_id)
        try:
            self._send_raw(line)
        except HardwareUnavailable as error:
            logger.warning(f"HELLO not sent: {error}")

    async def send_arm(self) -> bool:
        if not self.boot_id:
            return False
        cmd_id = self._next_cmd_id()
        line = make_arm_command(self.session_id, cmd_id, self.boot_id)
        ok, reason = await self._send_and_await_ack(line, cmd_id)
        self.armed = ok
        if not ok:
            logger.warning(f"ARM not acknowledged: {reason}")
        return ok

    async def request_gate_target(self, target: GateTarget) -> Tuple[bool, str]:
        """
        Sends a move command. Returns (True, command_id) only after the device ACKs it.
        ACK means the device accepted the command; it does not mean the gate has arrived.
        """
        if not self.boot_id:
            return False, "Hardware handshake not completed yet"
        if not self.armed and not await self.send_arm():
            return False, "device_not_armed"

        cmd_id = self._next_cmd_id()
        line = make_gate_target_command(
            session_id=self.session_id,
            command_id=cmd_id,
            target=target,
            boot_id=self.boot_id,
            gate_epoch=self.gate_epoch,
            scenario_revision=self.state_manager.context.scenario_revision,
        )
        ok, reason = await self._send_and_await_ack(line, cmd_id)
        if not ok:
            if reason.lower() in NOT_ARMED_FAULTS:
                self.armed = False
            return False, reason
        return True, cmd_id

    async def request_stop(self) -> Tuple[bool, str]:
        """Emergency stop: asks the device to stop outputs and disarms the host view either way."""
        cmd_id = self._next_cmd_id()
        line = make_stop_command(self.session_id, cmd_id)
        ok, reason = await self._send_and_await_ack(line, cmd_id)
        self.armed = False
        return (True, cmd_id) if ok else (False, reason)

    async def update_display(self) -> None:
        """Sends the LED frame and returns at once; the outcome is watched in the background.

        The display is informational: a late, missing or rejected ACK never blocks or fails a gate
        command, but it is logged and kept in `last_display_status` so it is never silent.
        """
        self.projector.project(
            current_plan=self.state_manager.current_plan,
            blocked_portals=self.state_manager.blocked_portals,
            gate_state=self.state_manager.physical_gate_state,
        )
        cmd_id = self._next_cmd_id()
        line = make_display_command(self.session_id, cmd_id, self.projector.current_px)
        future = asyncio.get_running_loop().create_future()
        self._pending[cmd_id] = future
        try:
            self._send_raw(line)
        except HardwareUnavailable as error:
            self._pending.pop(cmd_id, None)
            self.last_display_status = f"unavailable:{error}"
            logger.warning(f"Display not updated: {error}")
            return
        self._spawn(self._watch_display_ack(cmd_id, future))

    async def _watch_display_ack(self, command_id: str, future: asyncio.Future) -> None:
        try:
            ok, detail = await asyncio.wait_for(future, ACK_TIMEOUT_S)
        except asyncio.TimeoutError:
            ok, detail = False, "ack_timeout"
        finally:
            self._pending.pop(command_id, None)
        if ok and detail == DISPLAY_UPDATED:
            self.last_display_status = DISPLAY_UPDATED
        else:
            self.last_display_status = f"failed:{detail}"
            logger.warning(f"Display update not confirmed ({command_id}): {detail}")

    def _resolve_pending(self, msg_type: str, data: Dict[str, Any]) -> bool:
        """A reply resolves only the outstanding command whose command_id it echoes.

        Returns True when a pending command was resolved, False when the reply matched nothing.
        """
        command_id = data.get("command_id")
        future = self._pending.get(command_id) if isinstance(command_id, str) else None
        if future is None or future.done():
            return False
        if msg_type == SerialResponseType.ACK.value:
            future.set_result((True, str(data.get("status", "ACK"))))
        elif msg_type == SerialResponseType.FAULT.value:
            fault = str(data.get("fault", "FAULT"))
            if fault.lower() in NOT_ARMED_FAULTS:
                self.armed = False
            future.set_result((False, fault))
        return True

    def _handle_incoming_line(self, line: str) -> None:
        data = parse_device_line(line)
        if not data:
            return

        msg_type = data.get("type")
        if msg_type in (SerialResponseType.ACK.value, SerialResponseType.FAULT.value):
            if not self._resolve_pending(msg_type, data) and msg_type == SerialResponseType.FAULT.value:
                # A FAULT that answers no outstanding command (for example DEVICE_NOT_ARMED after a
                # device reset) means the host's armed view is wrong. Never keep acting on it.
                logger.warning(f"Unsolicited device FAULT: {str(data.get('fault', 'FAULT'))[:64]}; disarming host view")
                self.armed = False

        elif msg_type == SerialResponseType.HELLO_ACK.value:
            self.boot_id = data.get("boot_id")
            logger.info(f"Received HELLO_ACK from boot_id: {self.boot_id}")
            self._spawn(self.send_arm())

        elif msg_type == SerialResponseType.OBSERVATION.value:
            boot_id = data.get("boot_id", "")
            if self.boot_id and boot_id != self.boot_id:
                logger.warning("Ignoring observation from a different boot")
                return
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
            self._spawn(self.update_display())

    async def _physical_reader_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while self.is_running and self.serial_conn and self.serial_conn.is_open:
            try:
                line_bytes = await loop.run_in_executor(None, self.serial_conn.readline, MAX_LINE_BYTES)
                line = line_bytes.decode("utf-8", errors="replace")
                if line:
                    self._handle_incoming_line(line)
            except Exception as e:
                logger.error(f"Error reading physical serial: {e}")
                await asyncio.sleep(0.5)

    async def _heartbeat_loop(self) -> None:
        while self.is_running:
            try:
                if self.transport_available():
                    cmd_id = self._next_cmd_id()
                    line = make_heartbeat_command(self.session_id, cmd_id)
                    self._send_raw(line)
                await asyncio.sleep(0.25)  # 250 ms heartbeat
            except asyncio.CancelledError:
                break
            except HardwareUnavailable:
                await asyncio.sleep(1.0)
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
