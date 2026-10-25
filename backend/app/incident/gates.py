"""VirtualDoorController: the tabletop gate, made software and still honest.

Generalizes backend/app/hardware/simulator.py to one virtual gate per controllable door (actuation "motorized" or
"simulated_servo"; every other door is a sign and cannot be commanded). The safety story is unchanged:

    command  ->  ACK (ACCEPTED, means "heard", NOT "arrived")  ->  TRANSIT (1.5-2 s)  ->  endpoint switch seen

A gate counts as OPEN or CLOSED only after its endpoint switch is observed, and the epoch counter then moves, like the
firmware's gate_epoch. Anything else is never reported as arrived: a stall ends in FAULT, a lost ACK or a stale
controller ends in UNKNOWN, and two disagreeing switches end in FAULT. Everything here is labelled "simulated".
"""
from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

FaultKind = Literal["stall", "switch_disagreement", "dropped_ack", "heartbeat_timeout"]
FAULT_KINDS = ("stall", "switch_disagreement", "dropped_ack", "heartbeat_timeout")
GateTargetName = Literal["OPEN", "CLOSED"]
Emit = Callable[[str, Dict[str, Any]], None]


class GateState(str, Enum):
    CLOSED = "CLOSED"
    OPENING = "OPENING"
    OPEN = "OPEN"
    CLOSING = "CLOSING"
    UNKNOWN = "UNKNOWN"
    FAULT = "FAULT"


class ControllerConfig(BaseModel):
    """Timings in seconds. The demo default transit is visible on screen; tests shrink everything to ~10 ms."""
    model_config = ConfigDict(extra="forbid")
    transit_s: float = Field(default=1.75, ge=0, le=5)
    ack_timeout_s: float = Field(default=0.6, ge=0)
    stall_timeout_s: float = Field(default=1.5, ge=0)
    heartbeat_timeout_s: float = Field(default=3.0, ge=0)


class GateOutcome(BaseModel):
    """What one command ended in. Only result == "arrived" means the endpoint switch was observed."""
    model_config = ConfigDict(extra="forbid")
    gate_id: str
    command_id: str
    target: GateTargetName
    result: Literal["arrived", "unknown", "fault", "rejected", "cancelled"]
    state: GateState
    detail: str


class _Gate:
    def __init__(self, gate_id: str, state: GateState):
        self.gate_id = gate_id
        self.state = state
        self.open_switch = state == GateState.OPEN
        self.closed_switch = state == GateState.CLOSED
        self.epoch = 1
        self.fault: Optional[str] = None
        self.target: Optional[str] = None
        self.last_command_id: Optional[str] = None
        self.last_ack: Optional[str] = None
        self.busy = False
        self.detail = "initial"

    def snapshot(self) -> Dict[str, Any]:
        observed = {GateState.OPEN: "open", GateState.CLOSED: "closed"}.get(self.state)
        moving = self.state in (GateState.OPENING, GateState.CLOSING)
        return {
            "gate_id": self.gate_id, "state": self.state.value, "open_switch": self.open_switch,
            "closed_switch": self.closed_switch, "epoch": self.epoch, "target": self.target,
            "fault": self.fault, "last_command_id": self.last_command_id, "last_ack": self.last_ack,
            # "observed" is only ever set from an endpoint switch; "moving"/"unknown" never read as open.
            "observed": observed, "applied": observed or ("moving" if moving else "unknown"),
            "detail": self.detail, "simulated": True,
        }


class VirtualDoorController:
    def __init__(self, initial_states: Dict[str, Literal["open", "closed"]], config: Optional[ControllerConfig] = None,
                 emit: Optional[Emit] = None, on_stale: Optional[Callable[[], None]] = None):
        self.config = config or ControllerConfig()
        self._emit_cb = emit
        self._on_stale = on_stale
        self._defaults = dict(initial_states)
        self.boot_id = f"virtual-boot-{int(time.time())}"
        self._seq = 0
        self._command_seq = 0
        self.gates: Dict[str, _Gate] = {}
        self.stale = False
        self._beats_suppressed = False
        self._abort = asyncio.Event()
        self._watchdog: Optional[asyncio.Task] = None
        self._install_defaults()

    # -- lifecycle ---------------------------------------------------------------------------------------------

    def _install_defaults(self) -> None:
        self.gates = {gid: _Gate(gid, GateState.OPEN if s == "open" else GateState.CLOSED)
                      for gid, s in self._defaults.items()}
        self.stale = False
        self._beats_suppressed = False

    def reset(self, *, quiet: bool = False) -> None:
        """Back to power-on: faults cleared, every gate at its default endpoint, in-flight commands cancelled."""
        self._abort.set()
        self._abort = asyncio.Event()
        if self._watchdog and not self._watchdog.done():
            self._watchdog.cancel()
        self._watchdog = None
        self._install_defaults()
        if not quiet:
            self._emit("reset", {"phase": "reset", "line": f"RESET boot_id={self.boot_id} gates={self.states()}"})

    def has_gate(self, gate_id: str) -> bool:
        return gate_id in self.gates

    def states(self) -> Dict[str, str]:
        return {gid: g.state.value for gid, g in self.gates.items()}

    def view(self) -> Dict[str, Any]:
        return {
            "simulated": True, "label": "Simulated device: no hardware is connected",
            "boot_id": self.boot_id, "heartbeat": "stale" if self.stale else "ok",
            "transit_seconds": self.config.transit_s,
            "gates": [g.snapshot() for g in self.gates.values()],
        }

    # -- plumbing ----------------------------------------------------------------------------------------------

    def _emit(self, kind: str, payload: Dict[str, Any]) -> None:
        self._seq += 1
        if self._emit_cb:
            self._emit_cb(kind, {"seq_dev": self._seq, "boot_id": self.boot_id, **payload})

    def _gate_event(self, g: _Gate, phase: str, line: str, **extra: Any) -> None:
        self._emit("gate", {**g.snapshot(), "phase": phase, "line": line, **extra})

    async def _sleep(self, seconds: float, abort: asyncio.Event) -> bool:
        """False when a reset interrupted the wait."""
        if abort.is_set():
            return False
        try:
            await asyncio.wait_for(abort.wait(), timeout=seconds)
            return False
        except asyncio.TimeoutError:
            return True

    # -- faults ------------------------------------------------------------------------------------------------

    def inject_fault(self, kind: str, gate_id: Optional[str] = None) -> None:
        if kind == "heartbeat_timeout":
            if self._beats_suppressed or self.stale:
                return
            self._beats_suppressed = True
            self._emit("fault", {"fault": kind, "gate_id": None, "phase": "fault_injected",
                                 "line": "FAULT heartbeat_timeout injected: device heartbeats stop"})
            self._watchdog = asyncio.ensure_future(self._heartbeat_watchdog(self._abort))
            return
        if kind not in FAULT_KINDS or gate_id not in self.gates:
            raise KeyError(kind if kind not in FAULT_KINDS else str(gate_id))
        g = self.gates[gate_id]
        g.fault = kind
        self._emit("fault", {"fault": kind, "gate_id": gate_id, "phase": "fault_injected",
                             "line": f"FAULT {kind} injected on {gate_id}"})

    def clear_fault(self, gate_id: Optional[str] = None) -> List[str]:
        """Removes injected faults (all, or one gate's). A cleared gate stays UNKNOWN/FAULT until it is observed again."""
        cleared: List[str] = []
        for gid, g in self.gates.items():
            if (gate_id is None or gate_id == gid) and g.fault:
                cleared.append(f"{gid}:{g.fault}")
                g.fault = None
        if gate_id is None and (self._beats_suppressed or self.stale):
            self._beats_suppressed = False
            self.stale = False
            cleared.append("controller:heartbeat_timeout")
            if self._watchdog and not self._watchdog.done():
                self._watchdog.cancel()
        if cleared:
            self._emit("fault", {"fault": None, "gate_id": gate_id, "phase": "fault_cleared", "cleared": cleared,
                                 "line": "FAULT cleared " + ", ".join(cleared)})
        return cleared

    async def _heartbeat_watchdog(self, abort: asyncio.Event) -> None:
        if not await self._sleep(self.config.heartbeat_timeout_s, abort) or not self._beats_suppressed:
            return
        self._go_stale("heartbeat missed for %.2fs" % self.config.heartbeat_timeout_s)

    def _go_stale(self, why: str) -> None:
        if self.stale:
            return
        self.stale = True
        for g in self.gates.values():
            # A gate we can no longer hear from is unknown, even if it was last seen open.
            g.state = GateState.UNKNOWN
            g.open_switch = g.closed_switch = False
            g.detail = "controller stale"
        self._emit("fault", {"fault": "heartbeat_timeout", "gate_id": None, "phase": "controller_stale",
                             "line": f"WATCHDOG controller stale ({why}); every gate UNKNOWN", "gates": self.states()})
        if self._on_stale:
            self._on_stale()

    # -- the command ---------------------------------------------------------------------------------------------

    async def command(self, gate_id: str, target: GateTargetName) -> GateOutcome:
        """Runs one SET_GATE_TARGET to its end; the outcome says whether an endpoint switch was observed."""
        g = self.gates[gate_id]
        abort = self._abort
        self._command_seq += 1
        cmd_id = f"vcmd-{self._command_seq}"

        def done(result: str, detail: str) -> GateOutcome:
            g.busy = False
            g.detail = detail
            return GateOutcome(gate_id=gate_id, command_id=cmd_id, target=target, result=result, state=g.state, detail=detail)

        if g.busy:
            return GateOutcome(gate_id=gate_id, command_id=cmd_id, target=target, result="rejected", state=g.state,
                               detail="gate_busy")
        if self._beats_suppressed and not self.stale:
            self._go_stale("command found the heartbeat missing")
        if self.stale:
            self._gate_event(g, "rejected", f"CMD {cmd_id} {gate_id} {target} REJECTED controller_stale")
            return done("unknown", "controller_stale")
        g.busy = True
        g.target = target
        g.last_command_id = cmd_id
        g.last_ack = None
        self._gate_event(g, "command", f"CMD {cmd_id} SET_GATE_TARGET {gate_id} {target}")

        if g.fault == "dropped_ack":
            # The device may or may not have moved: with no ACK the host cannot know, so it must not assume.
            if not await self._sleep(self.config.ack_timeout_s, abort):
                return done("cancelled", "reset")
            g.state = GateState.UNKNOWN
            g.open_switch = g.closed_switch = False
            self._gate_event(g, "ack_timeout", f"TIMEOUT {cmd_id} no ACK within {self.config.ack_timeout_s:.2f}s; {gate_id} UNKNOWN")
            return done("unknown", "ack_timeout")

        g.last_ack = "ACCEPTED"
        g.state = GateState.OPENING if target == "OPEN" else GateState.CLOSING
        g.open_switch = g.closed_switch = False
        self._gate_event(g, "ack", f"ACK {cmd_id} ACCEPTED (not arrival)")
        self._gate_event(g, "transit", f"TRANSIT {gate_id} {g.state.value} both endpoint switches released")

        if not await self._sleep(self.config.transit_s, abort):
            return done("cancelled", "reset")
        if self.stale:
            return done("unknown", "controller_stale")  # _go_stale already set the gate and published it

        # The fault is read at the end of transit, so a jam injected while the gate is moving still bites.
        if g.fault == "stall":
            if not await self._sleep(self.config.stall_timeout_s, abort):
                return done("cancelled", "reset")
            g.state = GateState.FAULT
            self._gate_event(g, "fault", f"FAULT {gate_id} stall: no endpoint switch after {self.config.transit_s + self.config.stall_timeout_s:.2f}s")
            return done("fault", "stall")
        if g.fault == "switch_disagreement":
            g.state = GateState.FAULT
            g.open_switch = g.closed_switch = True
            self._gate_event(g, "fault", f"FAULT {gate_id} switch_disagreement: open_switch=1 closed_switch=1")
            return done("fault", "switch_disagreement")

        g.state = GateState.OPEN if target == "OPEN" else GateState.CLOSED
        g.open_switch = target == "OPEN"
        g.closed_switch = target == "CLOSED"
        g.epoch += 1
        self._gate_event(g, "observed", f"OBSERVATION {gate_id} {g.state.value} open_switch={int(g.open_switch)} "
                                         f"closed_switch={int(g.closed_switch)} epoch={g.epoch}")
        return done("arrived", "endpoint_observed")

    async def command_many(self, targets: Dict[str, GateTargetName]) -> List[GateOutcome]:
        return list(await asyncio.gather(*(self.command(g, t) for g, t in sorted(targets.items()))))
