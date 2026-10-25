import { claimReasonCopy, teamLaneErrorCopy } from '../api/agentTeam.ts';
import { countdownLabel, isActive, isTerminalPhase } from './agentTeamFlow.ts';
import type { ClaimCheck, LaneState, LaneVerification, LaneView, TeamLane, TeamRun, TraceLine } from './agentTeamTypes.ts';
import type { DoorStateMap } from './types.ts';

/** Display derivation for the agent team panel: everything the components print is computed here so it can be tested without React. */

export const LIVE_CHIP = 'Live Gemini 4 Argon · managed agent';
export const LOCAL_CHIP = 'Local solver · no Gemini call';
export const CHECKER_NOTE = 'The checker decides; you approve.';
export const MODELED_NOTE = 'Modeled crossings in the twin, not a survival prediction. Agent numbers are claims until the checker reproduces them.';
export const NO_THOUGHTS_NOTE = 'The trace shows code, tool calls and results. Agents do not expose their reasoning.';

export const LANE_TITLES: Record<TeamLane, { title: string; role: string }> = {
  strategist: { title: 'Strategist', role: 'Fast door-state recommendation, checked through read-only tools.' },
  robustness: { title: 'Robustness', role: 'Runs fault sweeps in a network-disabled sandbox, then submits.' },
  followup: { title: 'Follow-up', role: 'Same sandbox, one new scenario.' },
};

export type Tone = 'wait' | 'run' | 'ok' | 'bad' | 'note';

export interface ClaimRow {
  key: string;
  scenario: string;
  appliesTo: string;
  claimed: string;
  verified: string;
  reproduced: boolean;
  reason: string;
  /** The agent computed this number in its sandbox: an estimate until the checker reproduces it. */
  sandboxEstimate: boolean;
}

export interface TraceRow {
  key: string;
  kind: TraceLine['kind'];
  label: string;
  head: string;
  /** The rest of a multi-line code cell or result, behind an expander; null when the head says everything. */
  body: string | null;
  isError: boolean;
  partial: boolean;
}

export interface LaneCard {
  lane: TeamLane;
  title: string;
  role: string;
  scenario: string | null;
  phase: LaneState['phase'];
  chip: { text: string; tone: Tone };
  countdown: string | null;
  elapsed: string | null;
  provenance: { tone: 'live' | 'local' | 'fallback' | 'unavailable' | 'pending'; text: string; reason: string | null };
  /** The live attempt that failed, kept visible beside its local fallback. */
  liveFailure: string | null;
  doors: { id: string; state: 'open' | 'closed' }[];
  fallbackDoors: { id: string; state: 'open' | 'closed' }[];
  recommendationNote: string | null;
  summary: string | null;
  claims: ClaimRow[];
  claimsLine: string | null;
  claimsSource: LaneVerification['source'] | null;
  cost: string | null;
  tokens: string | null;
  trace: TraceRow[];
  droppedLines: number;
  error: string | null;
}

// --- small formatters -----------------------------------------------------------------------------------------

export function elapsedLabel(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

export const compactCount = (value: number): string => value >= 10_000 ? `${(value / 1000).toFixed(0)}k` : value >= 1000 ? `${(value / 1000).toFixed(1)}k` : String(Math.round(value));

export function tokenTotal(usage: Record<string, number> | undefined | null, cost?: LaneView['cost_estimate']): number | null {
  if (usage) {
    if (Number.isFinite(usage.total_tokens)) return usage.total_tokens;
    const input = usage.total_input_tokens ?? usage.input_tokens;
    const output = usage.total_output_tokens ?? usage.output_tokens;
    if (Number.isFinite(input) || Number.isFinite(output)) return (Number.isFinite(input) ? input : 0) + (Number.isFinite(output) ? output : 0);
  }
  if (cost) return cost.input_tokens + cost.output_tokens;
  return null;
}

export const formatUsd = (usd: number): string => usd < 0.001 ? '<$0.001' : `$${usd.toFixed(usd < 1 ? 3 : 2)}`;

/** `name(k=v, ...)` arguments, shortened. Arguments are untrusted text from the agent: only ever rendered as text. */
export function argsSummary(raw: string, max = 90): string {
  const text = raw.trim();
  if (!text) return '';
  let out = text;
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      out = Object.entries(parsed).map(([key, value]) => `${key}=${typeof value === 'string' ? JSON.stringify(value.length > 28 ? `${value.slice(0, 27)}…` : value) : JSON.stringify(value)}`).join(', ');
    }
  } catch { /* partial or non-JSON arguments are shown as they are */ }
  const flat = out.replace(/\s+/g, ' ');
  return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

const KIND_LABEL: Record<TraceLine['kind'], string> = { code: 'code', result: 'result', output: 'agent', call: 'call', tool: 'checker', status: 'status', note: 'note', error: 'note' };

export function traceRows(lines: readonly TraceLine[]): TraceRow[] {
  return lines.map(line => {
    const base = { key: line.key, kind: line.kind, isError: Boolean(line.isError), partial: Boolean(line.partial) };
    if (line.kind === 'call') return { ...base, label: line.name ? `call ${line.name}` : 'call', head: argsSummary(line.text), body: null };
    if (line.kind === 'tool') return { ...base, label: line.name ? `checker ${line.name}` : 'checker', head: line.text, body: null };
    const lines2 = line.text.split('\n');
    const first = (lines2[0] ?? '').trim();
    const head = first.length > 110 ? `${first.slice(0, 109)}…` : first || (line.kind === 'code' ? '(empty cell)' : line.kind === 'result' ? '(no output)' : '');
    const multi = lines2.length > 1 || first.length > 110;
    return { ...base, label: KIND_LABEL[line.kind], head, body: multi ? line.text : null };
  });
}

const doorList = (states: DoorStateMap | null | undefined) => Object.entries(states ?? {}).map(([id, state]) => ({ id, state })).sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));

// --- claims ---------------------------------------------------------------------------------------------------

const crossings = (value: number | null | undefined) => typeof value === 'number' ? String(value) : '—';

/**
 * "Agent claimed | Checker verified" rows. Rows come from the full check list when the server sent one; otherwise only the mismatches are known by
 * name and the passing claims are summarised in `claimsLine` (a claim is never invented to fill the table).
 */
export function claimRows(verification: LaneVerification | null | undefined): ClaimRow[] {
  if (!verification) return [];
  const checks: ClaimCheck[] = verification.checks && verification.checks.length ? verification.checks : verification.mismatches;
  const sandbox = verification.source === 'sandbox';
  return checks.map((check, index) => ({
    key: `${check.index ?? index}:${check.scenario}:${check.applies_to}`,
    scenario: check.scenario,
    appliesTo: check.applies_to === 'fallback' ? 'if the door jams' : 'recommended',
    claimed: crossings(check.claimed_completed_crossings),
    verified: check.local_is_valid === false ? `${crossings(check.local_completed_crossings)} (invalid)` : crossings(check.local_completed_crossings),
    reproduced: check.reproduced,
    reason: check.reproduced ? '' : claimReasonCopy(check.reason),
    sandboxEstimate: sandbox,
  }));
}

export function claimsLine(verification: LaneVerification | null | undefined): string | null {
  if (!verification || verification.total === 0) return null;
  const { verified, total, source } = verification;
  if (source === 'local') return `Checker self-check: ${verified} of ${total}. Not agent evidence.`;
  return `${verified} of ${total} ${source === 'sandbox' ? 'sandbox ' : ''}claims reproduced by the local checker`;
}

/** The footer: only claims an agent made (source agent or sandbox) count toward "reproduced"; the local solver's self-check is reported apart. */
export function teamFooter(run: TeamRun): { claims: string | null; mismatches: number; selfCheck: string | null; note: string } {
  let verified = 0, total = 0, mismatches = 0, selfVerified = 0, selfTotal = 0;
  for (const lane of run.order) {
    const state = run.lanes[lane];
    const v = state?.verification;
    if (!v) continue;
    if (v.source === 'local') { selfVerified += v.verified; selfTotal += v.total; continue; }
    verified += v.verified; total += v.total; mismatches += v.total - v.verified;
  }
  return {
    claims: total > 0 ? `${verified} of ${total} claims reproduced by the local checker` : null,
    mismatches,
    selfCheck: total === 0 && selfTotal > 0 ? `Local solver run: the checker's own self-check passed ${selfVerified} of ${selfTotal}. No agent claims to verify.` : null,
    note: CHECKER_NOTE,
  };
}

// --- lane card ------------------------------------------------------------------------------------------------

const PHASE_CHIP: Record<LaneState['phase'], { text: string; tone: Tone }> = {
  waiting: { text: 'Waiting', tone: 'wait' }, running: { text: 'Working', tone: 'run' }, plan_ready: { text: 'Working', tone: 'run' },
  completed: { text: 'Done', tone: 'ok' }, failed: { text: 'Failed', tone: 'bad' }, cancelled: { text: 'Cancelled', tone: 'note' },
  timed_out: { text: 'Timed out', tone: 'bad' }, incomplete: { text: 'Incomplete', tone: 'bad' },
};

export function laneCard(run: TeamRun, name: TeamLane, now: number): LaneCard {
  const lane = run.lanes[name] ?? ({ lane: name, phase: 'waiting', investigationId: null, deadlineMs: null, startedAt: null, trace: [], droppedLines: 0, statesChecked: null, view: null, fallbackView: null, fallbackReason: null, verification: null, usage: null } as LaneState);
  const titles = LANE_TITLES[name];
  const live = lane.view;
  const effective: LaneView | null = lane.fallbackView ?? live;
  const active = isActive(run) && !isTerminalPhase(lane.phase);
  const fallingBack = Boolean(lane.fallbackReason) && !lane.fallbackView && active;

  let chip = PHASE_CHIP[lane.phase];
  if (fallingBack) chip = { text: 'Falling back to local', tone: 'note' };
  else if (lane.fallbackView && lane.phase === 'completed') chip = { text: 'Done · local fallback', tone: 'note' };

  // Provenance is only claimed once the server has said it; before that we state what was requested.
  let provenance: LaneCard['provenance'];
  let liveFailure: string | null = null;
  if (lane.fallbackView || fallingBack) {
    const reason = failureCopy(lane.fallbackReason, live);
    provenance = { tone: 'fallback', text: 'Local fallback', reason: reason || null };
    liveFailure = `Live lane ${lane.fallbackReason?.status ?? live?.status ?? 'failed'}${reason ? `: ${reason}` : ''}`;
  } else if (effective?.provenance === 'live') provenance = { tone: 'live', text: LIVE_CHIP, reason: null };
  else if (effective?.provenance === 'local') provenance = { tone: 'local', text: LOCAL_CHIP, reason: null };
  else if (effective?.provenance === 'unavailable') provenance = { tone: 'unavailable', text: 'Unavailable', reason: teamLaneErrorCopy(effective.errors) || null };
  else provenance = run.mode === 'local' ? { tone: 'local', text: LOCAL_CHIP, reason: null } : { tone: 'pending', text: 'Live run requested', reason: null };
  // A live lane that failed with no fallback shows its own error, so the failure is never hidden behind a green chip.
  if (!lane.fallbackView && live && live.provenance === 'live' && (live.status === 'failed' || live.status === 'timed_out' || live.status === 'incomplete')) {
    liveFailure = `Live lane ${live.status}${teamLaneErrorCopy(live.errors) ? `: ${teamLaneErrorCopy(live.errors)}` : ''}`;
  }

  const verification = effective?.verification ?? lane.verification;
  const usage = lane.usage;
  const total = tokenTotal(effective?.token_usage ?? usage?.token_usage, effective?.cost_estimate ?? usage?.cost_estimate);
  const budget = effective?.token_budget ?? usage?.token_budget ?? null;
  const cost = effective?.cost_estimate ?? usage?.cost_estimate ?? null;
  const isLocal = provenance.tone === 'local' || provenance.tone === 'fallback';

  const elapsedMs = effective?.latency_ms ?? (lane.startedAt !== null && active ? now - lane.startedAt : null);
  const errors = effective?.errors ?? [];
  const summary = (name === 'strategist' ? effective?.explanation : effective?.robustness_headline || effective?.explanation) ?? null;

  return {
    lane: name, title: name === 'followup' && run.scenario ? `${titles.title}: ${run.scenario}` : titles.title, role: titles.role, scenario: run.scenario, phase: lane.phase, chip,
    countdown: active ? countdownLabel(lane.deadlineMs, now) : null,
    elapsed: elapsedMs === null ? null : elapsedLabel(elapsedMs),
    provenance, liveFailure,
    doors: doorList(effective?.recommended_door_states), fallbackDoors: doorList(effective?.fallback_if_jammed),
    recommendationNote: effective?.agreement_note || null,
    summary: summary || null,
    claims: claimRows(verification), claimsLine: claimsLine(verification), claimsSource: verification?.source ?? null,
    cost: cost ? `≈ ${formatUsd(cost.usd)} est.` : null,
    tokens: total !== null ? `${compactCount(total)}${budget ? ` / ${compactCount(budget)}` : ''} tokens` : isLocal && effective ? 'No model tokens' : null,
    trace: traceRows(lane.trace), droppedLines: lane.droppedLines,
    error: !active && lane.phase !== 'completed' && lane.phase !== 'waiting' && errors.length && !liveFailure ? teamLaneErrorCopy(errors) : null,
  };
}

function failureCopy(reason: LaneState['fallbackReason'], live: LaneView | null): string {
  return teamLaneErrorCopy(reason?.errors?.length ? reason.errors : live?.errors);
}

/** Lane columns in a stable order; the follow-up is rendered separately under them. */
export const teamLanes = (run: TeamRun): TeamLane[] => run.order.filter(lane => lane !== 'followup');

export const connectionLabel = (run: TeamRun): string | null => {
  if (!isActive(run)) return null;
  if (run.connection === 'polling') return 'Live trace dropped · results update by polling';
  if (run.connection === 'offline') return 'Cannot reach the backend · retrying';
  return null;
};
