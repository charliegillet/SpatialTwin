"""Helpers for review tests: real state manager and solver, no provider or device."""
from copy import deepcopy

from backend.app.contracts import (
    AlternativeId, ApplyBlockageCommand, EntityType, InvestigationResult, InvestigationStatus, TargetId,
)
from backend.app.state.service import ScenarioService


def block(state, target_type, target_id, key):
    context = state.get_current_context()
    ok, error, _ = state.apply_blockage(ApplyBlockageCommand(
        expected_scenario_revision=context.scenario_revision, idempotency_key=key,
        target_type=EntityType(target_type), target_id=TargetId(target_id),
        source="manual_override", expected_context=context))
    assert ok, error
    return state.get_current_context()


def local_investigation(state, investigation_id="inv-review"):
    """Real checked envelopes from the scenario service, labeled local: no Gemini call."""
    service = ScenarioService(state)
    context = state.get_current_context()
    keep = service.evaluate_alternative(context, AlternativeId.KEEP_CURRENT, f"{investigation_id}-keep")
    opened = service.evaluate_alternative(context, AlternativeId.OPEN_P3, f"{investigation_id}-open")
    return InvestigationResult(investigation_id=investigation_id, base_context=context,
        status=InvestigationStatus.COMPLETED, candidate_envelopes=[keep, opened],
        recommended_alternative=AlternativeId.OPEN_P3 if opened.completed_crossings > keep.completed_crossings
        else AlternativeId.KEEP_CURRENT, agent_explanation="Local comparison.", provenance="local")


def authoritative(state):
    snapshot = state.get_current_snapshot()
    snapshot.pop("timestamp_iso")
    return deepcopy(snapshot)
