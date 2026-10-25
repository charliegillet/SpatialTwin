"""
AI-facing ScenarioService Port
Exposes immutable evaluation methods for direct model and managed agent tool calls.
Never mutates authoritative state, never executes physical actuation.
"""

from __future__ import annotations
import threading
from typing import Any, Dict, List, Optional
from backend.app.contracts import (
    AlternativeId,
    EvaluationEnvelope,
    RunContext,
    SUPPORTED_TARGET_IDS,
)
from backend.app.planner.flow_solver import FlowPlanner
from backend.app.state.manager import StateManager


class ScenarioService:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self.planner = FlowPlanner(self.state_manager.venue_graph)
        self._evaluation_lock = threading.RLock()

    def get_reviewed_context(self, context: Optional[RunContext] = None) -> Dict[str, Any]:
        """
        Returns the active reviewed context, allowed alternatives, and target catalog.
        """
        with self.state_manager._state_lock:
            return self._reviewed_context(context)

    def _reviewed_context(self, context):
        current_ctx = self.state_manager.get_current_context()
        if context and not current_ctx.is_current(context):
            return {
                "error": f"Stale context provided. Current context revision is {current_ctx.scenario_revision}",
                "is_current": False,
                "current_context": current_ctx.model_dump(),
            }

        return {
            "context": current_ctx.model_dump(),
            "geometry_revision": current_ctx.geometry_revision,
            "scenario_revision": current_ctx.scenario_revision,
            "physical_revision": current_ctx.physical_revision,
            "permitted_alternatives": [AlternativeId.KEEP_CURRENT.value, AlternativeId.OPEN_P3.value],
            "supported_targets": list(SUPPORTED_TARGET_IDS),
            "blocked_portals": sorted(self.state_manager.blocked_portals),
            "blocked_boundaries": sorted(self.state_manager.blocked_boundaries),
            "physical_gate_state": self.state_manager.physical_gate_state.value,
        }

    def evaluate_alternative(
        self,
        context: RunContext,
        alternative_id: AlternativeId,
        request_id: str,
    ) -> EvaluationEnvelope:
        """
        Evaluates an immutable copy of the context with the declared alternative.
        Does NOT mutate application state or trigger physical actuation.
        """
        with self._evaluation_lock:
            return self._evaluate_once(context, alternative_id, request_id)

    def _evaluate_once(self, context: RunContext, alternative_id: AlternativeId, request_id: str) -> EvaluationEnvelope:
        with self.state_manager._state_lock:
            current_ctx = self.state_manager.get_current_context()
            blocked_portals = set(self.state_manager.blocked_portals)
            blocked_boundaries = set(self.state_manager.blocked_boundaries)
            physical_open = self.state_manager.physical_gate_state.value == "OPEN"
        # Verify context currentness
        if not current_ctx.is_current(context):
            raise ValueError(
                f"Cannot evaluate alternative on stale context. Request context: "
                f"scen={context.scenario_revision}, phys={context.physical_revision}. "
                f"Current context: scen={current_ctx.scenario_revision}, phys={current_ctx.physical_revision}"
            )

        cached = self.state_manager.store.get_evaluation(request_id)
        if cached:
            if cached["context_hash"] != context.context_hash or cached["alternative_id"] != alternative_id.value:
                raise ValueError("Evaluation request ID reused with different inputs")
            return EvaluationEnvelope.model_validate_json(cached["envelope_json"])

        envelope = self.planner.solve(
            base_context=context,
            alternative_id=alternative_id,
            blocked_portals=blocked_portals,
            blocked_boundaries=blocked_boundaries,
            p3_physical_open=physical_open,
        )

        if not context.is_current(self.state_manager.get_current_context()):
            raise ValueError("Context changed during numerical evaluation")

        # Persist candidate run in store
        self.state_manager.store.save_run(
            run_id=envelope.run_id,
            candidate_hash=envelope.candidate_hash,
            scenario_revision=context.scenario_revision,
            physical_revision=context.physical_revision,
            alternative_id=alternative_id.value,
            status=envelope.status.value,
            envelope_json=envelope.model_dump_json(),
            created_at_iso=self.state_manager._now_iso(),
        )

        self.state_manager.store.save_evaluation(request_id, context.context_hash, alternative_id.value, envelope.model_dump_json())

        return envelope

    def get_checked_run(self, run_id: str) -> Optional[EvaluationEnvelope]:
        run_data = self.state_manager.store.get_run(run_id)
        if run_data:
            return EvaluationEnvelope.model_validate(run_data)
        return None

    def get_scenario_lab(self, context: RunContext, reserve_basis: str = "reported") -> Dict[str, Any]:
        """Eight bounded local solves. No accepted edits, stored runs or device effects.

        Each preset replaces blockages in its own numerical input. The original
        context anchors geometry/parameters; it never makes a preview observed.
        """
        if reserve_basis not in {"reported", "closed_benchmark"}:
            raise ValueError("Choose reported or closed_benchmark reserve basis")
        with self._evaluation_lock:
            with self.state_manager._state_lock:
                if not context.is_current(self.state_manager.get_current_context()):
                    raise ValueError("Scenario changed. Run the lab again on the current context")
                state = self.state_manager.physical_gate_state.value
                if reserve_basis == "reported" and state not in {"OPEN", "CLOSED"}:
                    raise ValueError("P3 is unconfirmed. Wait for an endpoint or choose the explicit closed benchmark")
                physical_open = state == "OPEN" if reserve_basis == "reported" else False
            definitions = [
                ("baseline", "All targets available", set(), set()),
                ("p1_blocked", "P1 west passage blocked", {"P1"}, set()),
                ("p2_blocked", "P2 east passage blocked", {"P2"}, set()),
                ("b2_blocked", "B2 east boundary blocked", set(), {"B2"}),
            ]
            cases = []
            all_errors = []
            venue = self.state_manager.venue_graph
            conditions = (venue.zones["EVENT"].initial_occupants, venue.default_horizon_seconds, venue.time_step_seconds)
            for case_id, title, portals, boundaries in definitions:
                pair = []
                for alternative in (AlternativeId.KEEP_CURRENT, AlternativeId.OPEN_P3):
                    if not context.is_current(self.state_manager.get_current_context()):
                        raise ValueError("Scenario changed during lab calculation. Run the lab again")
                    pair.append(self.planner.solve(
                        base_context=context, alternative_id=alternative,
                        blocked_portals=set(portals), blocked_boundaries=set(boundaries),
                        p3_physical_open=physical_open,
                    ))
                reasons = []
                for candidate, alternative in zip(pair, (AlternativeId.KEEP_CURRENT, AlternativeId.OPEN_P3)):
                    if not candidate.validator_report.is_valid or candidate.status.value not in {"COMPLETE_WITHIN_MODEL", "PARTIAL_WITHIN_HORIZON", "NO_FEASIBLE_EXIT"}:
                        reasons.append("A candidate failed independent validation")
                    if not context.is_current(candidate.base_context) or candidate.alternative_id != alternative:
                        reasons.append("A candidate does not match the requested context or alternative")
                    if (candidate.initial_population, candidate.horizon_seconds, candidate.time_step_seconds) != conditions:
                        reasons.append("Candidates must use the same fixed population, horizon and timestep")
                    if candidate.completed_crossings < 0 or candidate.remaining_population < 0 or candidate.completed_crossings + candidate.remaining_population != candidate.initial_population:
                        reasons.append("A candidate does not account for every occupant")
                    if sum(candidate.boundary_breakdown.values()) != candidate.completed_crossings or any(candidate.boundary_breakdown.get(boundary, 0) for boundary in boundaries):
                        reasons.append("A candidate has invalid boundary accounting")
                reasons = list(dict.fromkeys(reasons))
                cases.append({
                    "id": case_id, "title": title, "blocked_portals": sorted(portals), "blocked_boundaries": sorted(boundaries),
                    "keep_current": pair[0].model_dump(mode="json"), "open_p3": pair[1].model_dump(mode="json"),
                    "net_gain": pair[1].completed_crossings - pair[0].completed_crossings if not reasons else None,
                    "comparable": not reasons, "reasons": reasons,
                })
                all_errors.extend(f"{case_id}: {reason}" for reason in reasons)
            with self.state_manager._state_lock:
                if not context.is_current(self.state_manager.get_current_context()):
                    raise ValueError("Scenario changed during lab calculation. Run the lab again")
                return {
                    "base_context": context.model_dump(mode="json"), "generated_at_iso": self.state_manager._now_iso(),
                    "hypothetical": True, "provenance": "local_scenario_lab", "reserve_basis": reserve_basis,
                    "p3_physical_open": physical_open, "cases": cases,
                    "comparable": not all_errors, "errors": all_errors,
                }

    def get_checked_comparison(
        self,
        context: RunContext,
        request_id: str,
    ) -> Dict[str, Any]:
        """
        Calculates side-by-side comparison between KEEP_CURRENT and OPEN_P3.
        Both share the exact same base context, initial population, and horizon.
        """
        keep_env = self.evaluate_alternative(context, AlternativeId.KEEP_CURRENT, f"{request_id}-keep")
        open_env = self.evaluate_alternative(context, AlternativeId.OPEN_P3, f"{request_id}-open")

        net_gain = open_env.completed_crossings - keep_env.completed_crossings
        has_benefit = net_gain > 0

        return {
            "context": context.model_dump(),
            "keep_current": keep_env.model_dump(),
            "open_p3": open_env.model_dump(),
            "net_gain_completed": net_gain,
            "has_benefit": has_benefit,
            "recommendation": AlternativeId.OPEN_P3.value if has_benefit else AlternativeId.KEEP_CURRENT.value,
            "explanation": (
                f"Opening P3 allows {open_env.completed_crossings} completed modeled crossings "
                f"(gain of +{net_gain}) versus {keep_env.completed_crossings} with KEEP_CURRENT."
                if has_benefit
                else f"Opening P3 provides no additional exit capacity (+0 gain). "
                f"Downstream boundary B2 is blocked or bottlenecked; KEEP_CURRENT is mathematically equivalent."
            ),
        }
