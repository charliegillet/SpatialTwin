import type { EvaluationEnvelope, GroundingResult, InvestigationResult, RunContext } from '../types.ts';

const targets = new Set(['portal:P1', 'portal:P2', 'boundary:B2']);
const planStatuses = new Set(['COMPLETE_WITHIN_MODEL', 'PARTIAL_WITHIN_HORIZON', 'NO_FEASIBLE_EXIT']);

/** A missing hash is not evidence that two contexts are equal. */
export function sameContext(a: RunContext | null | undefined, b: RunContext | null | undefined): boolean {
  return Boolean(a && b && a.context_hash && b.context_hash && a.context_hash === b.context_hash
    && a.state_epoch === b.state_epoch
    && a.geometry_revision === b.geometry_revision && a.scenario_revision === b.scenario_revision
    && a.physical_revision === b.physical_revision && a.parameters_revision === b.parameters_revision
    && a.solver_version === b.solver_version);
}

export const EXPOSURE_LABEL = 'modeled people-seconds in hazard; not a casualty or survival prediction';

/** Static label for a modeled-exposure figure. The server text is not trusted to carry the caveat. */
export function exposureLabel(): string {
  return EXPOSURE_LABEL;
}

export interface GroundingLabelOptions { managedModelFallback?: boolean; mediaKind?: 'image' | 'video'; }

export function groundingLabel(result: GroundingResult | null | undefined, options: GroundingLabelOptions = {}): string {
  if (!result) return 'No model result';
  if (result.status !== 'completed') return `AI ${result.status.replace(/_/g, ' ')}`;
  if (result.provenance === 'live' && result.provider_interaction_id && result.proposal) {
    if (options.mediaKind === 'video') return 'Live Gemini video result';
    return options.managedModelFallback ? 'Live Gemini result (fallback model)' : 'Live Gemini result';
  }
  if (result.provenance === 'fixture') return 'Fixture · no Gemini call';
  return 'Provider unverified';
}

export function investigationLabel(result: InvestigationResult | null | undefined, options: Pick<GroundingLabelOptions, 'managedModelFallback'> = {}): string {
  if (!result) return 'No analysis yet';
  if (result.replayed) return `Replayed saved run · ${result.provenance === 'live' ? 'Gemini' : result.provenance === 'local' ? 'local solver' : 'unverified'} · ${result.status.replace(/_/g, ' ')}`;
  if (result.provenance === 'local') return result.status === 'completed' ? 'Local solver · no Gemini call' : `Local analysis ${result.status.replace(/_/g, ' ')}`;
  if (result.status !== 'completed') return `Gemini ${result.status.replace(/_/g, ' ')}`;
  return result.provenance === 'live' && result.provider_interaction_id ? (options.managedModelFallback ? 'Live Gemini analysis (fallback model)' : 'Live Gemini analysis') : 'Provider unverified';
}

export function canApplyGrounding(result: GroundingResult | null | undefined, context: RunContext | undefined): boolean {
  const proposal = result?.proposal;
  if (!result || result.status !== 'completed' || !result.proposal_id || !proposal || result.errors?.length
    || !['live', 'fixture'].includes(result.provenance)
    || (result.provenance === 'live' && !result.provider_interaction_id)
    || !sameContext(proposal.source_context, context)) return false;
  const selected = `${proposal.selected_entity_type}:${proposal.selected_entity_id}`;
  const box = proposal.box_2d;
  const validBox = !box || (box.length === 4 && box.every(value => Number.isInteger(value) && value >= 0 && value <= 1000)
    && box[0] < box[2] && box[1] < box[3]);
  return Boolean(proposal.capture_id) && validBox && new Set(proposal.candidate_ids).size === proposal.candidate_ids.length
    && proposal.status === 'matched' && proposal.operation === 'SET_UNAVAILABLE'
    && targets.has(selected) && proposal.candidate_ids.includes(selected)
    && proposal.candidate_ids.every(candidate => targets.has(candidate));
}

export function checkedCandidate(candidate: EvaluationEnvelope | undefined, context: RunContext | undefined): candidate is EvaluationEnvelope {
  return Boolean(candidate && context && sameContext(candidate.base_context, context)
    && candidate.validator_report.is_valid && planStatuses.has(candidate.status)
    && Number.isFinite(candidate.initial_population) && candidate.initial_population >= 0
    && Number.isFinite(candidate.completed_crossings) && candidate.completed_crossings >= 0
    && Number.isFinite(candidate.remaining_population) && candidate.remaining_population >= 0
    && candidate.completed_crossings + candidate.remaining_population === candidate.initial_population
    && Number.isFinite(candidate.horizon_seconds) && candidate.horizon_seconds > 0
    && Number.isFinite(candidate.time_step_seconds) && candidate.time_step_seconds > 0);
}

export function canCompareInvestigation(result: InvestigationResult | null | undefined, context: RunContext | undefined): boolean {
  if (!result || result.status !== 'completed' || result.errors?.length || !sameContext(result.base_context, context)
    || !['live', 'local'].includes(result.provenance ?? '')
    || (result.provenance === 'live' && !result.provider_interaction_id)) return false;
  const baseline = result.candidate_envelopes.find(candidate => candidate.alternative_id === 'KEEP_CURRENT');
  const reserve = result.candidate_envelopes.find(candidate => candidate.alternative_id === 'OPEN_P3');
  return checkedCandidate(baseline, context) && checkedCandidate(reserve, context)
    && baseline.initial_population === reserve.initial_population
    && baseline.horizon_seconds === reserve.horizon_seconds
    && baseline.time_step_seconds === reserve.time_step_seconds;
}

export function canApproveInvestigation(result: InvestigationResult | null | undefined, context: RunContext | undefined): boolean {
  if (!canCompareInvestigation(result, context) || result?.recommended_alternative !== 'OPEN_P3') return false;
  const baseline = result.candidate_envelopes.find(candidate => candidate.alternative_id === 'KEEP_CURRENT')!;
  const reserve = result.candidate_envelopes.find(candidate => candidate.alternative_id === 'OPEN_P3')!;
  return reserve.completed_crossings > baseline.completed_crossings;
}
