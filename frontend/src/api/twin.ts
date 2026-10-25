import { ApiError, requestJson } from './client.ts';
import { errorCopy } from '../twin/camera.ts';
import type { CalibrationRequest, CalibrationResponse, ConfirmResponse, DoorAgentMode, DoorAgentProgress, DoorPlanResponse, HazardInput, HazardReadRequest, HazardReadResponse, VenueV2 } from '../twin/types.ts';

/** 422 codes from the door-plan endpoint, in short words a judge can read. */
export const TWIN_ERRORS: Record<string, string> = {
  too_many_hazards: 'Up to 6 hazards',
  duplicate_hazard_id: 'That hazard is already placed',
  outside_building: 'Drop inside a room',
  zone_mismatch: 'That spot is not in the chosen room',
  invalid_untenable_time: 'Use an even number of seconds from 0 to 38',
  invalid_horizon: 'That time window is not accepted',
  unconfirmed_camera_hazard: 'Confirm the camera card first',
  camera_hazard_mismatch: 'The camera card changed. Read the board again.',
};

export function twinErrorMessage(status: number, code: string): string {
  if (status === 422 && code) return TWIN_ERRORS[code] ?? 'The hazards were not accepted';
  if (status === 409) return 'The venue changed. Reload to continue.';
  return '';
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const bad = (what: string): never => { throw new ApiError(`The planner returned an unexpected ${what}.`, 502, 'invalid_response'); };

/** Minimal shape check: enough that the UI never reads through an undefined. Extra fields pass. */
export function parseDoorPlan(raw: unknown): DoorPlanResponse {
  if (!isRecord(raw)) return bad('response');
  const { chosen, baseline, lights } = raw;
  for (const key of ['hazards', 'doors', 'exits', 'zones', 'routes', 'alternatives', 'advisories'] as const) {
    if (!Array.isArray(raw[key])) bad(key);
  }
  if (!isRecord(chosen) || ![chosen.completed_crossings, chosen.initial_population, chosen.horizon_seconds].every(Number.isFinite)) bad('result');
  if (!isRecord(baseline) || !Number.isFinite(baseline.completed_crossings)) bad('baseline');
  if (!isRecord(lights) || typeof lights.px !== 'string') bad('light plan');
  if (typeof raw.plan_id !== 'string' || raw.venue_id !== 'building-v2') bad('plan');
  return raw as unknown as DoorPlanResponse;
}

export function parseVenue(raw: unknown): VenueV2 {
  if (!isRecord(raw) || raw.venue_id !== 'building-v2') return bad('venue');
  for (const key of ['zones', 'doors', 'exits'] as const) if (!Array.isArray(raw[key]) || raw[key].length === 0) bad(key);
  if (!isRecord(raw.led_map) || !Array.isArray(raw.extent)) bad('venue');
  return raw as unknown as VenueV2;
}

export const fetchVenue = async (signal?: AbortSignal): Promise<VenueV2> =>
  parseVenue(await requestJson<unknown>('/api/venues/building-v2', { signal, timeoutMs: 10_000, fallback: 'The building could not be loaded' }));

export const postDoorPlan = async (hazards: HazardInput[], signal?: AbortSignal): Promise<DoorPlanResponse> =>
  parseDoorPlan(await requestJson<unknown>('/api/venues/building-v2/door-plan', {
    method: 'POST', body: { hazards }, signal, timeoutMs: 30_000, fallback: 'The door plan could not be calculated',
    describe: (status, _detail, code) => twinErrorMessage(status, code),
  }));

// --- Camera twin ----------------------------------------------------------------------------------------

export function cameraErrorMessage(status: number, code: string): string {
  if (!code) return '';
  if (status === 429 || status === 422 || status === 404) return errorCopy(code);
  return '';
}

export const postCalibration = (body: CalibrationRequest, signal?: AbortSignal) =>
  requestJson<CalibrationResponse>('/api/venues/building-v2/camera/calibration', {
    method: 'POST', body, signal, timeoutMs: 10_000, fallback: 'The calibration could not be saved',
    describe: (status, _detail, code) => cameraErrorMessage(status, code),
  });

export async function postHazardRead(body: HazardReadRequest, signal?: AbortSignal): Promise<HazardReadResponse> {
  const read = await requestJson<HazardReadResponse>('/api/venues/building-v2/camera/hazard-read', {
    method: 'POST', body, signal, timeoutMs: 70_000, fallback: 'The board could not be read',
    describe: (status, _detail, code) => cameraErrorMessage(status, code),
  });
  if (!Array.isArray(read?.candidates) || !Array.isArray(read.errors) || typeof read.status !== 'string') throw new ApiError('The camera read returned an unexpected response.', 502, 'invalid_response');
  return read;
}

export const confirmRead = (readId: string, candidateIds: string[], signal?: AbortSignal) =>
  requestJson<ConfirmResponse>(`/api/venues/building-v2/camera/reads/${encodeURIComponent(readId)}/confirm`, {
    method: 'POST', body: { candidate_ids: candidateIds }, signal, timeoutMs: 10_000, fallback: 'The cards could not be confirmed',
    describe: (status, _detail, code) => cameraErrorMessage(status, code),
  });

// --- Door agent -------------------------------------------------------------------------------------------

export const DOOR_AGENT_ERRORS: Record<string, string> = {
  configuration_missing: 'Gemini is not configured on this machine.',
  provider_unavailable: 'Gemini could not be reached.',
  provider_timeout: 'Gemini did not answer in time.',
  provider_rate_limited: 'Gemini is rate limited right now.',
  provider_access_denied: 'Gemini refused the request.',
  provider_model_mismatch: 'The agent ran on an unexpected model, so the run was discarded.',
  tool_call_limit: 'The agent asked for too many checks.',
  investigation_deadline: 'The agent did not finish within 60 seconds.',
  investigation_cancelled: 'The run was cancelled.',
};

/** Short, judge-readable copy for a failed run; the checker's plan always stands. */
export function doorAgentErrorMessage(errors: readonly string[]): string {
  const first = errors.find(code => DOOR_AGENT_ERRORS[code]);
  const detail = first ? DOOR_AGENT_ERRORS[first] : 'The agent run did not complete.';
  return `${detail} The checker's plan above still stands.`;
}

export function agentStartError(status: number, code: string): string {
  if (status === 429) return 'Too many analyses are running. Try again shortly.';
  if (status === 403) return 'Local runs are disabled on this server.';
  return twinErrorMessage(status, code);
}

const DONE_STATUSES = new Set(['completed', 'failed', 'incomplete', 'cancelled', 'timed_out']);
export const isDoorAgentDone = (status: string): boolean => DONE_STATUSES.has(status);

export function parseDoorAgentProgress(raw: unknown): DoorAgentProgress {
  if (!isRecord(raw) || typeof raw.investigation_id !== 'string' || typeof raw.status !== 'string' || !Array.isArray(raw.provider_progress)) return bad('agent progress');
  const result = raw.investigation;
  if (result !== null && result !== undefined) {
    if (!isRecord(result) || typeof result.status !== 'string' || !isRecord(result.checked_best_door_states) || !Array.isArray(result.tool_ledger) || !Array.isArray(result.errors)
      || typeof result.explanation !== 'string' || typeof result.agrees_with_checker !== 'boolean') bad('agent result');
  }
  return { ...raw, investigation: (result ?? null) as DoorAgentProgress['investigation'] } as unknown as DoorAgentProgress;
}

export async function startDoorInvestigation(hazards: HazardInput[], mode: DoorAgentMode, signal?: AbortSignal): Promise<string> {
  const started = await requestJson<{ investigation_id?: unknown }>('/api/venues/building-v2/investigate', {
    method: 'POST', body: { hazards, mode }, signal, timeoutMs: 15_000, fallback: 'The agent could not be started',
    describe: (status, _detail, code) => agentStartError(status, code),
  });
  if (typeof started?.investigation_id !== 'string' || !started.investigation_id) return bad('agent start');
  return started.investigation_id;
}

export const fetchDoorInvestigation = async (id: string, signal?: AbortSignal): Promise<DoorAgentProgress> =>
  parseDoorAgentProgress(await requestJson<unknown>(`/api/venues/building-v2/investigations/${encodeURIComponent(id)}`, {
    signal, timeoutMs: 10_000, fallback: 'The agent progress could not be read',
  }));

export const cancelDoorInvestigation = (id: string) =>
  requestJson<{ status: string }>(`/api/venues/building-v2/investigations/${encodeURIComponent(id)}/cancel`, {
    method: 'POST', timeoutMs: 10_000, fallback: 'The agent could not be cancelled',
  });
