import type { EvaluationEnvelope, RunContext, ScenarioLabResult } from '../../types.ts';
import { checkedCandidate, sameContext } from '../../ai/policy.ts';

export type ReserveBasis = 'reported' | 'closed_benchmark';
export type LabCaseId = 'baseline' | 'p1_blocked' | 'p2_blocked' | 'b2_blocked';
export type JudgePrediction = Exclude<LabCaseId, 'baseline'>;

export const labCases: { id: LabCaseId; title: string; portals: string[]; boundaries: string[] }[] = [
  { id: 'baseline', title: 'Baseline', portals: [], boundaries: [] },
  { id: 'p1_blocked', title: 'P1 blocked', portals: ['P1'], boundaries: [] },
  { id: 'p2_blocked', title: 'P2 blocked', portals: ['P2'], boundaries: [] },
  { id: 'b2_blocked', title: 'B2 blocked', portals: [], boundaries: ['B2'] },
];

export interface LabRow {
  id: LabCaseId;
  title: string;
  available: boolean;
  reason: string;
  keep?: number;
  open?: number;
  gain?: number;
  runIds?: [string, string];
}

export interface LabReview {
  valid: boolean;
  reasons: string[];
  rows: LabRow[];
  leaders: JudgePrediction[];
  maxGain: number | null;
  parameters?: { population: number; horizon: number; timestep: number };
}

function record(value: unknown): value is Record<string, any> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function exactNames(value: unknown, expected: string[]): boolean {
  return Array.isArray(value) && value.length === expected.length
    && new Set(value).size === value.length && expected.every(name => value.includes(name));
}

function checked(value: unknown, context: RunContext | undefined): value is EvaluationEnvelope {
  if (!record(value) || !record(value.validator_report) || !checkedCandidate(value as EvaluationEnvelope, context)) return false;
  return typeof value.run_id === 'string' && value.run_id.length > 0
    && typeof value.candidate_hash === 'string' && value.candidate_hash.length > 0
    && value.validator_report.is_valid === true
    && ['initial_population', 'completed_crossings', 'remaining_population', 'horizon_seconds', 'time_step_seconds']
      .every(key => Number.isSafeInteger(value[key]))
    && value.horizon_seconds % value.time_step_seconds === 0
    && ['conservation_verified', 'unassigned_accounted', 'capacities_respected', 'quota_respected']
      .every(key => value.validator_report[key] === true);
}

export function canRunScenarioLab(reference: EvaluationEnvelope | null | undefined, context: RunContext | undefined): boolean {
  return checked(reference, context);
}

/** Fail closed before making any metric or ranking available to the component. */
export function reviewScenarioLab(
  result: ScenarioLabResult | null | undefined,
  context: RunContext | undefined,
  basis: ReserveBasis,
  reference: EvaluationEnvelope | null | undefined,
  physicalOpen: boolean,
): LabReview {
  const reasons: string[] = [];
  const unavailable = (reason: string): LabReview => ({ valid: false, reasons: [reason],
    rows: labCases.map(item => ({ id: item.id, title: item.title, available: false, reason })), leaders: [], maxGain: null });
  if (!record(result)) return unavailable('Run the four cases to see a checked comparison.');
  if (!sameContext(result.base_context, context)) return unavailable('The scenario context changed. Run the cases again.');
  if (result.hypothetical !== true || result.provenance !== 'local_scenario_lab') return unavailable('The response is not a verified hypothetical lab result.');
  if (typeof result.generated_at_iso !== 'string' || !Number.isFinite(Date.parse(result.generated_at_iso))) return unavailable('The batch receipt has no valid generation timestamp.');
  if (result.reserve_basis !== basis) return unavailable('The reserve basis changed. Run the cases again.');
  const effectiveOpen = basis === 'closed_benchmark' ? false : physicalOpen;
  if (typeof result.p3_physical_open !== 'boolean' || result.p3_physical_open !== effectiveOpen) return unavailable('The reserve state does not match the selected basis.');
  if (!Array.isArray(result.errors) || result.errors.length || result.comparable !== true) return unavailable('The case batch is incomplete or could not be compared.');
  if (!checked(reference, context)) return unavailable('A current checked board result is needed before comparing cases.');
  if (!Array.isArray(result.cases) || result.cases.length !== labCases.length
    || labCases.some(item => result.cases.filter(candidate => record(candidate) && candidate.id === item.id).length !== 1)) {
    return unavailable('The response must contain each of the four cases exactly once.');
  }
  const rows = labCases.map(spec => {
    const item = result.cases.find(candidate => candidate.id === spec.id)!;
    let issue = '';
    if (!exactNames(item.blocked_portals, spec.portals) || !exactNames(item.blocked_boundaries, spec.boundaries)) {
      issue = 'The case does not match its declared blockage.';
    } else if (item.comparable !== true || !Array.isArray(item.reasons) || item.reasons.length > 0) {
      issue = 'This case is incomplete or has an unreadable receipt.';
    } else if (!checked(item.keep_current, context) || !checked(item.open_p3, context)) {
      issue = 'A checked, current result is missing for this case.';
    } else if (item.keep_current.alternative_id !== 'KEEP_CURRENT' || item.open_p3.alternative_id !== 'OPEN_P3') {
      issue = 'The comparison alternatives do not match the requested pair.';
    } else if ([item.keep_current, item.open_p3].some(candidate =>
      candidate.initial_population !== reference.initial_population || candidate.horizon_seconds !== reference.horizon_seconds
      || candidate.time_step_seconds !== reference.time_step_seconds)) {
      issue = 'Population, horizon or timestep differs from the current board result.';
    } else if (!Number.isSafeInteger(item.net_gain) || item.net_gain !== item.open_p3.completed_crossings - item.keep_current.completed_crossings) {
      issue = 'The improvement does not match the checked crossing counts.';
    } else if (effectiveOpen && item.net_gain !== 0) {
      issue = 'An already-open reserve cannot add a new opening benefit.';
    }
    if (issue) {
      reasons.push(`${spec.title}: ${issue}`);
      return { id: spec.id, title: spec.title, available: false, reason: issue };
    }
    const gain = item.net_gain!;
    return { id: spec.id, title: spec.title, available: true,
      keep: item.keep_current.completed_crossings, open: item.open_p3.completed_crossings, gain,
      runIds: [item.keep_current.run_id, item.open_p3.run_id] as [string, string],
      reason: spec.id === 'b2_blocked'
        ? 'B2 stays blocked in both alternatives.' : gain === 0 ? 'The completed-crossing count is unchanged.'
          : gain > 0 ? 'More crossings complete within the same horizon.' : 'Fewer crossings complete within the same horizon.',
    };
  });
  if (reasons.length) return { valid: false, reasons, leaders: [], maxGain: null,
    rows: rows.map(row => ({ id: row.id, title: row.title, available: false,
      reason: row.available ? 'The complete batch could not be verified.' : row.reason })) };
  const blocked = rows.filter(row => row.id !== 'baseline');
  const maxGain = Math.max(...blocked.map(row => row.gain!));
  return { valid: true, reasons: [], rows, maxGain,
    leaders: maxGain > 0 ? blocked.filter(row => row.gain === maxGain).map(row => row.id as JudgePrediction) : [],
    parameters: { population: reference.initial_population, horizon: reference.horizon_seconds, timestep: reference.time_step_seconds },
  };
}

export function predictionOutcome(prediction: JudgePrediction | null, review: LabReview): string {
  if (!review.valid) return '';
  if (!review.leaders.length) return 'None of the blocked cases gains completed crossings from P3.';
  const names = review.leaders.map(id => labCases.find(item => item.id === id)!.title.replace(' blocked', '')).join(' and ');
  const outcome = `${review.leaders.length > 1 ? 'Largest improvement is tied: ' : 'Largest improvement: '}${names} (+${review.maxGain}).`;
  if (!prediction) return outcome;
  const name = labCases.find(item => item.id === prediction)?.title.replace(' blocked', '') ?? 'Unknown';
  return `${outcome} Your prediction: ${name}${review.leaders.includes(prediction) ? ' — matched.' : '.'}`;
}
