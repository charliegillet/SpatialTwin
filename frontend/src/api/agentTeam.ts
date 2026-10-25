import { ApiError, requestJson } from './client.ts';
import { TWIN_ERRORS } from './twin.ts';
import type { HazardInput } from '../twin/types.ts';
import {
  TEAM_LANES, TRACE_EVENT_NAMES,
  type LaneDeadline, type LaneView, type TeamLane, type TeamMode, type TeamProgress, type TeamStart, type TraceEvent, type TraceEventName,
} from '../twin/agentTeamTypes.ts';

/** Client for the managed-agent team routes (docs/plans/contracts/agent-team.md). Every number an agent claims is re-run by the local checker. */

const venuePath = (venueId: string) => `/api/venues/${encodeURIComponent(venueId)}`;
const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const bad = (what: string): never => { throw new ApiError(`The agent service returned an unexpected ${what}.`, 502, 'invalid_response'); };
const isLane = (value: unknown): value is TeamLane => typeof value === 'string' && (TEAM_LANES as readonly string[]).includes(value);

/** Lane failure codes found in `LaneView.errors`; shown next to a fallback so the live failure stays visible. */
export const TEAM_LANE_ERRORS: Record<string, string> = {
  configuration_missing: 'Gemini is not configured on this machine.',
  provider_unavailable: 'Gemini could not be reached.',
  provider_timeout: 'Gemini did not answer in time.',
  provider_rate_limited: 'Gemini is rate limited right now.',
  provider_access_denied: 'Gemini refused the request.',
  provider_model_mismatch: 'The agent ran on an unexpected model, so the run was discarded.',
  tool_call_limit: 'The agent asked for too many checks.',
  investigation_deadline: 'The agent did not finish within its deadline.',
  investigation_cancelled: 'The run was cancelled.',
  submission_missing: 'The agent ended without submitting a recommendation.',
  followup_parent_unavailable: 'The earlier live run is no longer available, so the follow-up ran locally.',
};

/** The first known code's copy, or a neutral line. Never raw server text. */
export function teamLaneErrorCopy(errors: readonly string[] | undefined): string {
  const first = (errors ?? []).find(code => TEAM_LANE_ERRORS[code]);
  return first ? TEAM_LANE_ERRORS[first] : (errors?.length ? 'The agent run did not complete.' : '');
}

/** Why a claim failed the local re-run (`ClaimCheck.reason`). */
export const CLAIM_REASONS: Record<string, string> = {
  crossings_mismatch: 'The checker got a different number of crossings.',
  candidate_hash_mismatch: 'The claim was about a different door state than the one recommended.',
  scenario_unrecognized: 'The scenario was not one the checker understands.',
  unknown_fault_door: 'The scenario named a door that does not exist.',
  local_plan_invalid: 'The checker rejected that door state, so its number does not count.',
};
export const claimReasonCopy = (reason: string | null | undefined): string => reason ? CLAIM_REASONS[reason] ?? 'The checker could not reproduce this claim.' : '';

/** Start errors. 429 covers both the shared provider slots and the one-live-team slot. */
export function teamStartError(status: number, code: string): string {
  if (status === 429) return 'An agent team is already working. Cancel it, or try again in a moment.';
  if (status === 403) return 'Local runs are disabled on this server.';
  if (status === 404) return 'That venue is not available any more.';
  if (status === 422 && code) return TWIN_ERRORS[code] ?? (code === 'duplicate_lane' ? 'A lane was requested twice.' : 'The hazards were not accepted.');
  if (status === 422) return 'The hazards were not accepted.';
  return '';
}

export const FOLLOWUP_PARENT_FINISHING = 'parent_finishing';
/** Follow-up errors. `parent_finishing` is a retry hint, not a failure: the earlier agent is still acknowledging. */
export function followupError(status: number, code: string): string {
  if (status === 404) return 'The earlier run is no longer available. Ask the agent team again.';
  if (status === 409 && code === FOLLOWUP_PARENT_FINISHING) return 'The earlier agent is still wrapping up. Retrying…';
  if (status === 409 && code === 'parent_geometry_changed') return 'The venue changed since this investigation. Ask the agent team again.';
  if (status === 409 && code === 'followup_in_progress') return 'A follow-up is already running in this sandbox. Try again in a few seconds.';
  if (status === 409) return 'The agent team is still working. Ask the follow-up when it finishes.';
  if (status === 429) return 'An agent team is already working. Try again in a moment.';
  if (status === 403) return 'Local runs are disabled on this server.';
  if (status === 422) return code === 'scenario_unrecognized' ? 'That scenario was not recognised. Try "stuck_closed:D3".' : 'That scenario was not accepted.';
  return '';
}

/** Read and cancel share one copy: an id from another venue, or one the server restarted past, is a 404 `unknown_investigation`. */
export function teamReadError(status: number, code: string): string {
  if (status === 404 && code === 'unknown_investigation') return 'That agent run is no longer available. Ask again.';
  return '';
}

// --- parsers --------------------------------------------------------------------------------------------------

function parseDeadline(raw: unknown): LaneDeadline | null {
  if (!isRecord(raw) || typeof raw.investigation_id !== 'string' || !Number.isFinite(raw.deadline_at_ms) || !Number.isFinite(raw.deadline_seconds)) return null;
  return { investigation_id: raw.investigation_id, deadline_seconds: raw.deadline_seconds as number, deadline_at_ms: raw.deadline_at_ms as number };
}

export function parseTeamStart(raw: unknown): TeamStart {
  if (!isRecord(raw) || typeof raw.investigation_id !== 'string' || !raw.investigation_id || !Number.isFinite(raw.deadline_at_ms) || !isRecord(raw.lanes) || typeof raw.trace_url !== 'string') return bad('start response');
  const lanes: TeamStart['lanes'] = {};
  for (const [key, value] of Object.entries(raw.lanes)) {
    const parsed = parseDeadline(value);
    if (!isLane(key) || !parsed) return bad('lane deadline');
    lanes[key] = parsed;
  }
  if (Object.keys(lanes).length === 0) return bad('start response');
  return {
    investigation_id: raw.investigation_id, deadline_at_ms: raw.deadline_at_ms as number, lanes, trace_url: raw.trace_url,
    parent_investigation_id: typeof raw.parent_investigation_id === 'string' ? raw.parent_investigation_id : null,
    scenario: typeof raw.scenario === 'string' ? raw.scenario : null,
  };
}

/** A lane view needs only an id and a status; everything else is optional and read defensively by the flow. */
export function parseLaneView(raw: unknown, fallbackLane?: TeamLane): LaneView {
  if (!isRecord(raw) || typeof raw.investigation_id !== 'string' || typeof raw.status !== 'string') return bad('lane result');
  const lane = isLane(raw.lane) ? raw.lane : fallbackLane;
  if (!lane) return bad('lane result');
  const verification = raw.verification;
  if (verification !== null && verification !== undefined) {
    if (!isRecord(verification) || !Number.isFinite(verification.verified) || !Number.isFinite(verification.total) || !Array.isArray(verification.mismatches)) bad('verification');
  }
  const fallback = raw.fallback ? parseLaneView(raw.fallback, lane) : null;
  return { ...raw, lane, fallback } as unknown as LaneView;
}

export function parseTeamProgress(raw: unknown): TeamProgress {
  if (!isRecord(raw) || typeof raw.investigation_id !== 'string' || typeof raw.status !== 'string' || !isRecord(raw.lanes)) return bad('progress');
  if (raw.team_status !== 'running' && raw.team_status !== 'finished' && raw.team_status !== 'cancelled') return bad('progress');
  const lanes: TeamProgress['lanes'] = {};
  for (const [key, value] of Object.entries(raw.lanes)) {
    if (!isLane(key)) continue;
    lanes[key] = parseLaneView(value, key);
  }
  return {
    investigation_id: raw.investigation_id, status: raw.status, team_status: raw.team_status,
    deadline_at_ms: Number.isFinite(raw.deadline_at_ms) ? raw.deadline_at_ms as number : null,
    lanes, trace_url: typeof raw.trace_url === 'string' ? raw.trace_url : null,
    parent_investigation_id: typeof raw.parent_investigation_id === 'string' ? raw.parent_investigation_id : null,
  };
}

/** One SSE frame. An unknown event name or non-JSON data yields null (the frame is skipped, the stream continues). */
export function parseTraceEvent(type: string, data: string): TraceEvent | null {
  if (!(TRACE_EVENT_NAMES as readonly string[]).includes(type)) return null;
  let body: unknown;
  try { body = JSON.parse(data); } catch { return null; }
  if (!isRecord(body) || !Number.isFinite(body.seq)) return null;
  const lane = isLane(body.lane) ? body.lane : null;
  return { seq: body.seq as number, event: type as TraceEventName, lane, elapsed_ms: Number.isFinite(body.elapsed_ms) ? body.elapsed_ms as number : 0, data: body };
}

// --- requests -------------------------------------------------------------------------------------------------

export interface StartTeamOptions { lanes?: TeamLane[]; supersede?: boolean; signal?: AbortSignal }

export async function startAgentTeam(venueId: string, hazards: HazardInput[], mode: TeamMode, options: StartTeamOptions = {}): Promise<TeamStart> {
  const { lanes = ['strategist', 'robustness'], supersede = true, signal } = options;
  return parseTeamStart(await requestJson<unknown>(`${venuePath(venueId)}/investigate`, {
    method: 'POST', body: { hazards, mode, lanes, supersede }, signal, timeoutMs: 15_000, fallback: 'The agent team could not be started',
    describe: (status, _detail, code) => teamStartError(status, code),
  }));
}

export async function fetchAgentTeam(venueId: string, id: string, signal?: AbortSignal): Promise<TeamProgress> {
  return parseTeamProgress(await requestJson<unknown>(`${venuePath(venueId)}/investigations/${encodeURIComponent(id)}`, {
    signal, timeoutMs: 10_000, fallback: 'The agent progress could not be read',
    describe: (status, _detail, code) => teamReadError(status, code),
  }));
}

export const cancelAgentTeam = (venueId: string, id: string) =>
  requestJson<{ status: string }>(`${venuePath(venueId)}/investigations/${encodeURIComponent(id)}/cancel`, {
    method: 'POST', timeoutMs: 10_000, fallback: 'The agent team could not be cancelled',
    describe: (status, _detail, code) => teamReadError(status, code),
  });

export async function followUpAgentTeam(venueId: string, parentId: string, scenario: string, mode: TeamMode, signal?: AbortSignal): Promise<TeamStart> {
  return parseTeamStart(await requestJson<unknown>(`${venuePath(venueId)}/investigations/${encodeURIComponent(parentId)}/followup`, {
    method: 'POST', body: { scenario, mode }, signal, timeoutMs: 20_000, fallback: 'The follow-up could not be started',
    describe: (status, _detail, code) => followupError(status, code),
  }));
}

/** The trace is a server-relative path; `?after=<seq>` replays everything newer than the last frame we hold. */
export const traceUrl = (path: string, after = 0): string => after > 0 ? `${path}${path.includes('?') ? '&' : '?'}after=${after}` : path;

/** A 409 whose code says the parent is still acknowledging: the follow-up is worth retrying a moment later. */
export const isParentFinishing = (error: unknown): boolean => error instanceof ApiError && error.status === 409 && error.detail === FOLLOWUP_PARENT_FINISHING;
