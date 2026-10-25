"""
Authoritative State Manager for SpatialTwin
Single source of truth for scenario state, revisions, physical observations,
and SSE event distribution.
"""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
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


class StateManager:
    def __init__(self, store: Optional[SQLiteStore] = None):
        self.store = store or SQLiteStore()
        self.venue_graph = get_default_venue_graph()
        self.planner = FlowPlanner(self.venue_graph)

        # Initial context
        self.context = RunContext(
            geometry_revision=self.venue_graph.geometry_revision,
            scenario_revision=1,
            physical_revision=1,
            parameters_revision="params-v1",
            solver_version="spatialtwin-flow-v1.0",
        )

        # Active blockage sets
        self.blocked_portals: Set[str] = set()
        self.blocked_boundaries: Set[str] = set()

        # Physical gate state (confirmed by independent endpoint switches)
        self.physical_gate_state = GateObservedState.CLOSED
        self.last_hardware_boot_id: Optional[str] = None
        self.last_gate_epoch: int = 0
        self.last_hardware_seq: int = 0

        # Current published plan
        self.current_plan: Optional[EvaluationEnvelope] = None

        # SSE listeners
        self._subscribers: List[asyncio.Queue] = []

        # Run initial solve
        self._solve_and_publish_current()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _solve_and_publish_current(self) -> EvaluationEnvelope:
        is_p3_open = (self.physical_gate_state == GateObservedState.OPEN)
        envelope = self.planner.solve(
            base_context=self.context,
            alternative_id=AlternativeId.KEEP_CURRENT,
            blocked_portals=self.blocked_portals,
            blocked_boundaries=self.blocked_boundaries,
            p3_physical_open=is_p3_open,
        )
        self.current_plan = envelope

        # Persist run
        self.store.save_run(
            run_id=envelope.run_id,
            candidate_hash=envelope.candidate_hash,
            scenario_revision=self.context.scenario_revision,
            physical_revision=self.context.physical_revision,
            alternative_id=envelope.alternative_id.value,
            status=envelope.status.value,
            envelope_json=envelope.model_dump_json(),
            created_at_iso=self._now_iso(),
        )

        return envelope

    def get_current_context(self) -> RunContext:
        return self.context

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
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
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
            if queue in self._subscribers:
                self._subscribers.remove(queue)

    def broadcast_event(self, event_name: str, data: Dict[str, Any]) -> None:
        payload = f"event: {event_name}\ndata: {json.dumps(data)}\n\n"
        for queue in self._subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def apply_blockage(self, cmd: ApplyBlockageCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
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

        # 3. Idempotency persistence
        saved = self.store.save_event(
            scenario_id=cmd.scenario_id,
            scenario_revision=self.context.scenario_revision,
            event_type="APPLY_BLOCKAGE",
            payload=cmd.model_dump(),
            idempotency_key=cmd.idempotency_key,
            created_at_iso=self._now_iso(),
        )
        if not saved:
            return False, f"Duplicate idempotency key rejected: {cmd.idempotency_key}", None

        # 4. Apply mutation
        if cmd.target_type == EntityType.PORTAL:
            self.blocked_portals.add(cmd.target_id.value)
        else:
            self.blocked_boundaries.add(cmd.target_id.value)

        # 5. Advance scenario revision
        self.context = RunContext(
            geometry_revision=self.context.geometry_revision,
            scenario_revision=self.context.scenario_revision + 1,
            physical_revision=self.context.physical_revision,
            parameters_revision=self.context.parameters_revision,
            solver_version=self.context.solver_version,
        )

        # 6. Solve and publish
        envelope = self._solve_and_publish_current()

        # 7. Broadcast update
        self.broadcast_event("scenario_updated", self.get_current_snapshot())

        return True, None, envelope

    def clear_blockage(self, cmd: ClearBlockageCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        if cmd.expected_scenario_revision != self.context.scenario_revision:
            return (
                False,
                f"Stale scenario revision: expected {cmd.expected_scenario_revision}, current {self.context.scenario_revision}",
                None,
            )

        pair = (cmd.target_type.value, cmd.target_id.value)
        if pair not in SUPPORTED_TARGET_PAIRS:
            return False, f"Target {pair} is not in allowlisted stage targets {SUPPORTED_TARGET_PAIRS}", None

        saved = self.store.save_event(
            scenario_id=cmd.scenario_id,
            scenario_revision=self.context.scenario_revision,
            event_type="CLEAR_BLOCKAGE",
            payload=cmd.model_dump(),
            idempotency_key=cmd.idempotency_key,
            created_at_iso=self._now_iso(),
        )
        if not saved:
            return False, f"Duplicate idempotency key rejected: {cmd.idempotency_key}", None

        if cmd.target_type == EntityType.PORTAL:
            self.blocked_portals.discard(cmd.target_id.value)
        else:
            self.blocked_boundaries.discard(cmd.target_id.value)

        self.context = RunContext(
            geometry_revision=self.context.geometry_revision,
            scenario_revision=self.context.scenario_revision + 1,
            physical_revision=self.context.physical_revision,
            parameters_revision=self.context.parameters_revision,
            solver_version=self.context.solver_version,
        )

        envelope = self._solve_and_publish_current()
        self.broadcast_event("scenario_updated", self.get_current_snapshot())

        return True, None, envelope

    def reset_scenario(self, cmd: ResetScenarioCommand) -> Tuple[bool, Optional[str], Optional[EvaluationEnvelope]]:
        if cmd.expected_scenario_revision != self.context.scenario_revision:
            return (
                False,
                f"Stale scenario revision: expected {cmd.expected_scenario_revision}, current {self.context.scenario_revision}",
                None,
            )

        saved = self.store.save_event(
            scenario_id=cmd.scenario_id,
            scenario_revision=self.context.scenario_revision,
            event_type="RESET_SCENARIO",
            payload=cmd.model_dump(),
            idempotency_key=cmd.idempotency_key,
            created_at_iso=self._now_iso(),
        )
        if not saved:
            return False, f"Duplicate idempotency key rejected: {cmd.idempotency_key}", None

        self.blocked_portals.clear()
        self.blocked_boundaries.clear()

        self.context = RunContext(
            geometry_revision=self.context.geometry_revision,
            scenario_revision=self.context.scenario_revision + 1,
            physical_revision=self.context.physical_revision,
            parameters_revision=self.context.parameters_revision,
            solver_version=self.context.solver_version,
        )

        envelope = self._solve_and_publish_current()
        self.broadcast_event("scenario_updated", self.get_current_snapshot())

        return True, None, envelope

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
        self.physical_gate_state = new_state
        self.last_hardware_boot_id = boot_id
        self.last_hardware_seq = seq
        self.last_gate_epoch = gate_epoch

        # If gate position changed between confirmed states (e.g. CLOSED -> OPEN)
        if (old_state != new_state) and (new_state in (GateObservedState.OPEN, GateObservedState.CLOSED)):
            # Advance physical revision
            self.context = RunContext(
                geometry_revision=self.context.geometry_revision,
                scenario_revision=self.context.scenario_revision,
                physical_revision=self.context.physical_revision + 1,
                parameters_revision=self.context.parameters_revision,
                solver_version=self.context.solver_version,
            )

            envelope = self._solve_and_publish_current()
            self.broadcast_event("physical_state_confirmed", self.get_current_snapshot())
            return True, envelope

        self.broadcast_event("hardware_telemetry", {
            "physical_gate_state": self.physical_gate_state.value,
            "boot_id": boot_id,
            "seq": seq,
            "gate_epoch": gate_epoch,
        })
        return False, None
