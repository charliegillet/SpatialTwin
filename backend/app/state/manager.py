"""
Authoritative State Manager for SpatialTwin
Single source of truth for scenario state, revisions, physical observations,
and SSE event distribution.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
import threading
from functools import wraps
from uuid import uuid4
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple

from backend.app.contracts import (
    AlternativeId,
    ApplyBlockageCommand,
    ClearBlockageCommand,
    ComputationStatus,
    EntityType,
    EvaluationEnvelope,
    GateObservedState,
    ResetScenarioCommand,
    RunContext,
    SUPPORTED_TARGET_PAIRS,
)
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.planner.model import get_default_venue_graph
from backend.app.state.store import SQLiteStore


def synchronized(method):
    @wraps(method)
    def locked(self, *args, **kwargs):
        with self._state_lock:
            return method(self, *args, **kwargs)
    return locked


# Bounded per-client buffer for the live event stream.
SUBSCRIBER_QUEUE_LIMIT = 256

class StateManager:
    def __init__(self, store: Optional[SQLiteStore] = None):
        self._state_lock = threading.RLock()
        self.store = store or SQLiteStore()
        self.venue_graph = get_default_venue_graph()
        self.planner = FlowPlanner(self.venue_graph)

        # Initial context
        self.context = RunContext(
            geometry_revision=self.venue_graph.geometry_revision,
            scenario_revision=1,
            physical_revision=1,
            parameters_revision="params-v1",
            solver_version="spatialtwin-flow-v1.1",
            state_epoch=uuid4().hex,
        )

        # Active blockage sets
        self.blocked_portals: Set[str] = set()
        self.blocked_boundaries: Set[str] = set()

        # Physical gate state, as last reported by a device observation. The bridge only forwards an
        # observation whose boot_id matches the handshaken device; the device derives the state from
        # its endpoint switches. This manager does not re-check the switches itself.
        self.physical_gate_state = GateObservedState.UNKNOWN
        self.last_hardware_boot_id: Optional[str] = None
        self.last_gate_epoch: int = 0
        self.last_hardware_seq: int = 0

        # Current published plan
        self.current_plan: Optional[EvaluationEnvelope] = None

        # SSE listeners
        # Each subscriber keeps the event loop that owns its queue, so broadcasts from worker threads
        # are handed to that loop instead of touching the queue directly.
        self._subscribers: List[Tuple[asyncio.Queue, asyncio.AbstractEventLoop]] = []

        # Run initial solve
        self._solve_and_publish_current()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _solve_for(self, context: RunContext, portals: Set[str], boundaries: Set[str],
                   gate_state: GateObservedState) -> EvaluationEnvelope:
        """Pure: solves a candidate state without touching live state or the database."""
        return self.planner.solve(
            base_context=context,
            alternative_id=AlternativeId.KEEP_CURRENT,
            blocked_portals=set(portals),
            blocked_boundaries=set(boundaries),
            p3_physical_open=(gate_state == GateObservedState.OPEN),
        )

    def _persist_run(self, envelope: EvaluationEnvelope, context: RunContext) -> None:
        self.store.save_run(
            run_id=envelope.run_id,
            candidate_hash=envelope.candidate_hash,
            scenario_revision=context.scenario_revision,
            physical_revision=context.physical_revision,
            alternative_id=envelope.alternative_id.value,
            status=envelope.status.value,
            envelope_json=envelope.model_dump_json(),
            created_at_iso=self._now_iso(),
        )

    def _solve_and_publish_current(self) -> EvaluationEnvelope:
        envelope = self._solve_for(self.context, self.blocked_portals, self.blocked_boundaries,
                                   self.physical_gate_state)
        self._persist_run(envelope, self.context)
        self.current_plan = envelope
        return envelope

    def _next_scenario_context(self) -> RunContext:
        return RunContext(
            geometry_revision=self.context.geometry_revision,
            scenario_revision=self.context.scenario_revision + 1,
            physical_revision=self.context.physical_revision,
            parameters_revision=self.context.parameters_revision,
            solver_version=self.context.solver_version,
            state_epoch=self.context.state_epoch,
        )

    def _commit_scenario_change(self, cmd, event_type: str, portals: Set[str], boundaries: Set[str]
                                ) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        """Solve the candidate state first, then record the event, then mutate memory.

        A failure in the solve or in either write leaves memory untouched and the idempotency key
        unburned (the event insert is the last fallible step and rolls back on error).
        """
        new_context = self._next_scenario_context()
        envelope = self._solve_for(new_context, portals, boundaries, self.physical_gate_state)
        self._persist_run(envelope, new_context)
        saved = self.store.save_event(
            scenario_id=cmd.scenario_id,
            scenario_revision=self.context.scenario_revision,
            event_type=event_type,
            payload=cmd.model_dump(),
            idempotency_key=cmd.idempotency_key,
            created_at_iso=self._now_iso(),
        )
        if not saved:
            return False, f"Duplicate idempotency key rejected: {cmd.idempotency_key}", None
        self.blocked_portals = set(portals)
        self.blocked_boundaries = set(boundaries)
        self.context = new_context
        self.current_plan = envelope
        self.broadcast_event("scenario_updated", self.get_current_snapshot())
        return True, None, envelope

    @synchronized
    def hazard_inputs(self) -> Tuple[RunContext, frozenset, frozenset, bool]:
        """Consistent (context, blocked portals, blocked boundaries, P3 physically open) under one lock."""
        return (self.context, frozenset(self.blocked_portals), frozenset(self.blocked_boundaries),
                self.physical_gate_state == GateObservedState.OPEN)

    @synchronized
    def get_current_context(self) -> RunContext:
        return self.context

    @synchronized
    def get_current_snapshot(self) -> Dict[str, Any]:
        return {
            "context": self.context.model_dump(),
            "blocked_portals": sorted(self.blocked_portals),
            "blocked_boundaries": sorted(self.blocked_boundaries),
            "physical_gate_state": self.physical_gate_state.value,
            "last_hardware_boot_id": self.last_hardware_boot_id,
            "last_gate_epoch": self.last_gate_epoch,
            "current_plan": self.current_plan.model_dump() if self.current_plan else None,
            "timestamp_iso": self._now_iso(),
        }

    async def subscribe(self) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_LIMIT)
        entry = (queue, asyncio.get_running_loop())
        self._subscribers.append(entry)
        try:
            # Send initial snapshot immediately on connection
            initial_event = {
                "event": "snapshot",
                "data": self.get_current_snapshot(),
            }
            yield f"event: snapshot\ndata: {json.dumps(initial_event['data'])}\n\n"

            while True:
                msg = await queue.get()
                yield msg
        finally:
            if entry in self._subscribers:
                self._subscribers.remove(entry)

    @staticmethod
    def _deliver(queue: asyncio.Queue, payload: str) -> None:
        """Runs on the queue's own loop. A slow client loses its oldest message, never the newest state."""
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        queue.put_nowait(payload)

    def broadcast_event(self, event_name: str, data: Dict[str, Any]) -> None:
        payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        for queue, loop in list(self._subscribers):
            if loop is current:
                self._deliver(queue, payload)
            elif not loop.is_closed():
                loop.call_soon_threadsafe(self._deliver, queue, payload)

    @synchronized
    def apply_blockage(self, cmd: ApplyBlockageCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        if cmd.expected_context and not self.context.is_current(cmd.expected_context):
            return False, "Stale full context", None
        if cmd.proposal_id:
            record = self.store.get_grounding_result(cmd.proposal_id)
            if not record or record["reviewed_command_id"] or not cmd.reviewed or not cmd.expected_context:
                return False, "A current unreviewed saved proposal and explicit review are required", None
            result = record["result"]
            if result.get("provenance") == "live":
                capture = self.store.get_capture(record["capture_id"])
                try:
                    timestamp = datetime.fromisoformat(capture["timestamp_iso"].replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - timestamp).total_seconds()
                    if age > 120 or age < -5:
                        return False, "Live capture expired; capture and review again", None
                except (TypeError, KeyError, ValueError):
                    return False, "Live capture metadata is unavailable", None
            proposal = result.get("proposal")
            if (result.get("status") != "completed" or result.get("provenance") not in ("live", "fixture")
                or not proposal or proposal.get("status") != "matched"
                or proposal.get("selected_entity_type") != cmd.target_type.value
                or proposal.get("selected_entity_id") != cmd.target_id.value
                or not self.context.is_current(RunContext.model_validate(proposal["source_context"]))):
                return False, "Proposal evidence does not authorize this reviewed target", None
        # 1. Expected revision check
        if cmd.expected_scenario_revision != self.context.scenario_revision:
            return (
                False,
                f"Stale scenario revision: expected {cmd.expected_scenario_revision}, current {self.context.scenario_revision}",
                None,
            )

        # 2. Allowlisted target check
        pair = (cmd.target_type.value, cmd.target_id.value)
        if pair not in SUPPORTED_TARGET_PAIRS:
            return False, f"Target {pair} is not in allowlisted stage targets {SUPPORTED_TARGET_PAIRS}", None

        spec = (self.venue_graph.portals if cmd.target_type == EntityType.PORTAL else self.venue_graph.boundaries).get(cmd.target_id.value)
        if spec is None or not spec.can_be_blocked:
            return False, f"Target {pair} cannot be blocked in the venue model", None

        portals, boundaries = set(self.blocked_portals), set(self.blocked_boundaries)
        (portals if cmd.target_type == EntityType.PORTAL else boundaries).add(cmd.target_id.value)
        return self._commit_scenario_change(cmd, "APPLY_BLOCKAGE", portals, boundaries)

    @synchronized
    def clear_blockage(self, cmd: ClearBlockageCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        if cmd.expected_context and not self.context.is_current(cmd.expected_context):
            return False, "Stale full context", None
        if cmd.expected_scenario_revision != self.context.scenario_revision:
            return (
                False,
                f"Stale scenario revision: expected {cmd.expected_scenario_revision}, current {self.context.scenario_revision}",
                None,
            )

        pair = (cmd.target_type.value, cmd.target_id.value)
        if pair not in SUPPORTED_TARGET_PAIRS:
            return False, f"Target {pair} is not in allowlisted stage targets {SUPPORTED_TARGET_PAIRS}", None

        portals, boundaries = set(self.blocked_portals), set(self.blocked_boundaries)
        (portals if cmd.target_type == EntityType.PORTAL else boundaries).discard(cmd.target_id.value)
        return self._commit_scenario_change(cmd, "CLEAR_BLOCKAGE", portals, boundaries)

    @synchronized
    def reset_scenario(self, cmd: ResetScenarioCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        if cmd.expected_context and not self.context.is_current(cmd.expected_context):
            return False, "Stale full context", None
        if cmd.expected_scenario_revision != self.context.scenario_revision:
            return (
                False,
                f"Stale scenario revision: expected {cmd.expected_scenario_revision}, current {self.context.scenario_revision}",
                None,
            )

        return self._commit_scenario_change(cmd, "RESET_SCENARIO", set(), set())

    @synchronized
    def update_physical_observation(
        self,
        new_state: GateObservedState,
        boot_id: str,
        seq: int,
        gate_epoch: int,
    ) -> Tuple[bool, Optional[EvaluationEnvelope]]:
        """
        Invoked ONLY when fresh debounced endpoint telemetry arrives from the hardware bridge.
        """
        old_state = self.physical_gate_state
        if old_state != new_state:
            # Availability changes immediately in transit/unknown/fault as well.
            # Any change invalidates investigations based on the previous physical revision.
            # Solve first so a failure leaves the previous state and plan intact.
            new_context = RunContext(
                geometry_revision=self.context.geometry_revision,
                scenario_revision=self.context.scenario_revision,
                physical_revision=self.context.physical_revision + 1,
                parameters_revision=self.context.parameters_revision,
                solver_version=self.context.solver_version,
                state_epoch=self.context.state_epoch,
            )
            envelope = self._solve_for(new_context, self.blocked_portals, self.blocked_boundaries, new_state)
            self._persist_run(envelope, new_context)
            self.physical_gate_state = new_state
            self.context = new_context
            self.current_plan = envelope
            self.last_hardware_boot_id = boot_id
            self.last_hardware_seq = seq
            self.last_gate_epoch = gate_epoch
            self.broadcast_event("physical_state_confirmed", self.get_current_snapshot())
            return True, envelope

        self.last_hardware_boot_id = boot_id
        self.last_hardware_seq = seq
        self.last_gate_epoch = gate_epoch
        self.broadcast_event("hardware_telemetry", {
            "physical_gate_state": self.physical_gate_state.value,
            "boot_id": boot_id,
            "seq": seq,
            "gate_epoch": gate_epoch,
        })
        return False, None
