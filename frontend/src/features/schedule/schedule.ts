import type { ScenarioSnapshot, TimelineStep } from '../../types.ts';
import { checkedCandidate, sameContext } from '../../ai/policy.ts';

export const SCHEDULE_CHECKS = [
  'timeline_population_conservation',
  'timeline_boundary_rates',
  'timeline_terminal_consistency',
  'timeline_matches_flow',
] as const;

export const HOLDING_ZONES = [
  { id: 'EVENT', field: 'event_occupancy', label: 'Event hall' },
  { id: 'WEST', field: 'west_occupancy', label: 'West corridor' },
  { id: 'EAST', field: 'east_occupancy', label: 'East corridor' },
  { id: 'RESERVE', field: 'reserve_occupancy', label: 'Reserve' },
] as const;

export interface ScheduleFrame extends TimelineStep {
  in_transit_occupancy: number;
}

export interface CheckedSchedule {
  available: true;
  key: string;
  runId: string;
  population: number;
  horizonSeconds: number;
  stepSeconds: number;
  frames: readonly ScheduleFrame[];
}

export interface UnavailableSchedule {
  available: false;
  kind: 'missing' | 'stale' | 'legacy' | 'invalid';
  message: string;
}

export type ScheduleResult = CheckedSchedule | UnavailableSchedule;

const countFields = [
  'event_occupancy', 'west_occupancy', 'east_occupancy', 'reserve_occupancy',
  'in_transit_occupancy', 'b1_cumulative', 'b2_cumulative', 'total_completed',
] as const;

const isCount = (value: unknown): value is number => typeof value === 'number'
  && Number.isSafeInteger(value) && value >= 0;

function invalid(): UnavailableSchedule {
  return {
    available: false,
    kind: 'invalid',
    message: 'This result has an inconsistent schedule. Recompute using the updated backend before playback.',
  };
}

/** Validate the complete schedule before exposing any frame, including historical frames. */
export function getCheckedSchedule(snapshot: ScenarioSnapshot | null, isCurrent: boolean): ScheduleResult {
  if (!isCurrent) return {
    available: false,
    kind: 'stale',
    message: 'A current checked result is required. Reconnect or recompute before exploring the schedule.',
  };
  const plan = snapshot?.current_plan;
  if (!snapshot || !plan) return {
    available: false,
    kind: 'missing',
    message: 'No computed schedule is available yet. Apply a reviewed scenario to create a current result.',
  };
  if (!plan.validator_report || !checkedCandidate(plan, snapshot.context)
    || !sameContext(plan.base_context, snapshot.context) || plan.alternative_id !== 'KEEP_CURRENT'
    || ['UNKNOWN', 'TRANSIT', 'FAULT'].includes(snapshot.physical_gate_state)) return {
    available: false,
    kind: 'stale',
    message: 'The result no longer matches a confirmed model context. Recompute before exploring its schedule.',
  };

  const report = plan.validator_report;
  if (!Array.isArray(report.checks_run) || !SCHEDULE_CHECKS.every(check => report.checks_run.includes(check))) return {
    available: false,
    kind: 'legacy',
    message: 'This result has no verified timeline. Recompute using the updated backend.',
  };
  if (!report.conservation_verified || !report.unassigned_accounted || !report.capacities_respected || !report.quota_respected
    || !isCount(plan.initial_population) || !isCount(plan.completed_crossings) || !isCount(plan.remaining_population)
    || !isCount(plan.horizon_seconds) || plan.horizon_seconds === 0
    || !isCount(plan.time_step_seconds) || plan.time_step_seconds === 0
    || plan.horizon_seconds % plan.time_step_seconds !== 0 || !plan.run_id) return invalid();

  const source = plan.timeline;
  const lastStep = plan.horizon_seconds / plan.time_step_seconds;
  if (!Array.isArray(source) || source.length !== lastStep + 1) return invalid();
  const frames: ScheduleFrame[] = [];
  let previousB1 = 0;
  let previousB2 = 0;
  for (let index = 0; index < source.length; index += 1) {
    const frame = source[index] as ScheduleFrame;
    if (!frame || typeof frame !== 'object' || Array.isArray(frame)
      || !isCount(frame.step) || !isCount(frame.time_seconds)
      || frame.step !== index || frame.time_seconds !== index * plan.time_step_seconds
      || !countFields.every(field => isCount(frame[field]))) return invalid();
    if (frame.b1_cumulative < previousB1 || frame.b2_cumulative < previousB2
      || frame.b1_cumulative + frame.b2_cumulative !== frame.total_completed
      || frame.total_completed > plan.initial_population) return invalid();
    const holding = HOLDING_ZONES.reduce((sum, zone) => sum + frame[zone.field], 0);
    if (holding + frame.in_transit_occupancy + frame.total_completed !== plan.initial_population) return invalid();
    previousB1 = frame.b1_cumulative;
    previousB2 = frame.b2_cumulative;
    frames.push({ ...frame });
  }

  const terminal = frames[frames.length - 1];
  if (terminal.total_completed !== plan.completed_crossings
    || plan.initial_population - terminal.total_completed !== plan.remaining_population
    || terminal.in_transit_occupancy !== 0
    || terminal.b1_cumulative !== plan.boundary_breakdown.B1
    || terminal.b2_cumulative !== plan.boundary_breakdown.B2
    || !HOLDING_ZONES.every(zone => terminal[zone.field] === plan.zone_occupancy[zone.id])) return invalid();

  return {
    available: true,
    key: JSON.stringify([plan.run_id, plan.candidate_hash, snapshot.context.state_epoch ?? '',
      snapshot.context.geometry_revision, snapshot.context.scenario_revision, snapshot.context.physical_revision,
      snapshot.context.parameters_revision, snapshot.context.solver_version, snapshot.context.context_hash]),
    runId: plan.run_id,
    population: plan.initial_population,
    horizonSeconds: plan.horizon_seconds,
    stepSeconds: plan.time_step_seconds,
    frames,
  };
}

/** Clamp direct manipulation to a stored frame; never invent intermediate states. */
export function clampFrameIndex(value: number, frameCount: number): number {
  if (!Number.isFinite(value) || frameCount < 1) return 0;
  return Math.max(0, Math.min(frameCount - 1, Math.trunc(value)));
}
