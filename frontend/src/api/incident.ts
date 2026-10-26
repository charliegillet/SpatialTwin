import { ApiError, requestJson } from './client.ts';
import { TWIN_ERRORS, parseDoorPlan } from './twin.ts';
import type { DoorPlanResponse, DoorStateMap, HazardInput } from '../twin/types.ts';

/** Types of the virtual door controller API (docs/plans/contracts/incident.md). Everything is a simulated device. */
export type GateState = 'CLOSED' | 'OPENING' | 'OPEN' | 'CLOSING' | 'UNKNOWN' | 'FAULT';
export type GateFault = 'stall' | 'switch_disagreement' | 'dropped_ack' | 'heartbeat_timeout';
export type GateApplied = 'open' | 'closed' | 'moving' | 'unknown' | 'sign';
export type ApprovalStatus = 'actuating' | 'applied' | 'failed';
export type ApprovalActor = 'operator' | 'fail_safe';
export type FailSafeStatus = 'off' | 'standing_by' | 'counting_down' | 'acted' | 'approved';

export interface IncidentGate {
  gate_id: string;
  state: GateState;
  open_switch: boolean;
  closed_switch: boolean;
  /** +1 on every observed arrival. */
  epoch: number;
  target: 'OPEN' | 'CLOSED' | null;
  fault: GateFault | null;
  last_command_id: string | null;
  /** The device heard the command. It says nothing about arrival. */
  last_ack: string | null;
  /** Set only by an endpoint-switch observation. */
  observed: 'open' | 'closed' | null;
  applied: GateApplied;
  detail: string;
}

export interface IncidentController {
  label: string;
  boot_id: string;
  heartbeat: 'ok' | 'stale';
  transit_seconds: number;
  gates: IncidentGate[];
}

export interface IncidentPlanDoor {
  id: string;
  state: string;
  lamp: string;
  actuation: string;
  controllable: boolean;
  changed: boolean;
  stuck: boolean;
  reason: string;
  applied: GateApplied;
}

export interface IncidentPlan {
  plan_id: string;
  plan_revision: number;
  candidate_hash: string;
  label: 'primary' | 'fallback';
  note: string | null;
  reason: string;
  /** Checker-valid. When false the server refuses approval and the UI shows no numbers. */
  valid: boolean;
  initial_population: number;
  completed_crossings: number;
  baseline_completed: number | null;
  count_label: string;
  door_states: DoorStateMap;
  doors: IncidentPlanDoor[];
  stuck_doors: string[];
  /** Gates the unattended fail-safe holds closed in this plan: each opens into a room with a hazard. */
  held_doors: string[];
  advisories: unknown[];
  announcement: string;
}

export interface IncidentApproval {
  approval_id: string;
  plan_revision: number;
  candidate_hash: string;
  door_states: DoorStateMap;
  status: ApprovalStatus;
  commands: Record<string, string>;
  results: Record<string, string>;
  reason: string | null;
  fallback_plan_revision: number | null;
  /** fail_safe: nobody approved within the armed window, so the fail-safe approved its own checked plan. */
  actor: ApprovalActor;
}

export type FailSafeVoice = 'gemini' | 'browser';

export interface FailSafeAction {
  at: string; plan_revision: number; approval_id: string; summary: string;
  /** gemini: the server is making (or made) the spoken clip with Gemini TTS; null: the browser speaks. */
  voice: FailSafeVoice | null; voice_status: 'pending' | 'ready' | 'failed' | null; voice_model: string | null; voice_error: string | null;
}

/** The unattended fail-safe (off by default). Armed, it approves a checked plan nobody approved in its window, never
 *  opening a gate into a room with a hazard. */
export interface FailSafe {
  armed: boolean;
  window_seconds: number;
  status: FailSafeStatus;
  plan_revision: number | null;
  /** Server wall clock (ISO) when the window ends; the presenter laptop serves and shows it, so the clocks agree. */
  deadline_at: string | null;
  seconds_left: number | null;
  /** Gate -> the hazard rooms it opens into, for the gates held closed in the current plan. */
  held_doors: Record<string, string[]>;
  /** Before it acts: gates in the current plan it would hold closed, and gates in doubt it would treat as stuck. */
  would_hold: string[];
  in_doubt: string[];
  note: string;
  last_action: FailSafeAction | null;
  voice: FailSafeVoice;
  /** The server has GEMINI_API_KEY (configuration, not proof of model access). */
  voice_available: boolean;
  voice_model: string | null;
}

export const FAILSAFE_OFF: FailSafe = {
  armed: false, window_seconds: 15, status: 'off', plan_revision: null, deadline_at: null, seconds_left: null, held_doors: {},
  would_hold: [], in_doubt: [], note: 'Off: a person approves every door move.', last_action: null, voice: 'browser',
  voice_available: false, voice_model: null,
};

export interface IncidentState {
  venue_id: string;
  plan_revision: number;
  hazards: HazardInput[];
  plan: IncidentPlan | null;
  plan_error: string | null;
  controller: IncidentController;
  stuck_doors: string[];
  approvals: IncidentApproval[];
  approval_in_progress: boolean;
  failsafe: FailSafe;
  last_event_id: number;
}

export type IncidentEventType = 'snapshot' | 'plan' | 'approval' | 'gate' | 'fault' | 'reset' | 'failsafe';
export interface IncidentEvent {
  type: IncidentEventType;
  seq: number;
  ts: string;
  plan_revision: number;
  /** Serial-style console text, when the event carries one. */
  line: string | null;
  state?: IncidentState;
  plan?: IncidentPlan | null;
  hazards?: HazardInput[];
  stuck_doors?: string[];
  plan_error?: string | null;
  approval?: IncidentApproval;
  failsafe?: FailSafe;
  gate?: IncidentGate;
  phase?: string;
  fault?: string;
  gate_id?: string;
}

export const GATE_STATES: readonly GateState[] = ['CLOSED', 'OPENING', 'OPEN', 'CLOSING', 'UNKNOWN', 'FAULT'];
export const FAULT_KINDS: readonly GateFault[] = ['stall', 'switch_disagreement', 'dropped_ack', 'heartbeat_timeout'];
const APPLIED: readonly string[] = ['open', 'closed', 'moving', 'unknown', 'sign'];

/** Judge-readable copy for every code in incident.md; planner codes reuse the door-plan wording. */
export const INCIDENT_ERRORS: Record<string, string> = {
  stale_plan: 'The plan changed — review the new one',
  approval_in_progress: 'Doors are still moving — wait for the result',
  no_plan: 'There is no plan to approve yet',
  plan_not_valid: 'The checker did not accept this plan, so it cannot be approved',
  unknown_gate: 'That door has no motor to jam',
  gate_required: 'Choose which door to jam',
  unknown_venue: 'That venue is not available any more',
};

export function incidentErrorMessage(status: number, code: string): string {
  if (code && INCIDENT_ERRORS[code]) return INCIDENT_ERRORS[code];
  if (status === 422 && code) return TWIN_ERRORS[code] ?? 'The request was not accepted';
  if (status === 409) return INCIDENT_ERRORS.stale_plan;
  if (status === 404) return INCIDENT_ERRORS.unknown_venue;
  return '';
}

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const bad = (what: string): never => { throw new ApiError(`The door controller returned an unexpected ${what}.`, 502, 'invalid_response'); };
const str = (value: unknown, fallback = ''): string => typeof value === 'string' ? value : fallback;
const num = (value: unknown, fallback = 0): number => typeof value === 'number' && Number.isFinite(value) ? value : fallback;
const strList = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const strMap = (value: unknown): Record<string, string> =>
  isRecord(value) ? Object.fromEntries(Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === 'string')) : {};

export function parseGate(raw: unknown): IncidentGate {
  if (!isRecord(raw) || typeof raw.gate_id !== 'string' || !GATE_STATES.includes(raw.state as GateState)) return bad('gate');
  return {
    gate_id: raw.gate_id, state: raw.state as GateState,
    open_switch: raw.open_switch === true, closed_switch: raw.closed_switch === true, epoch: num(raw.epoch),
    target: raw.target === 'OPEN' || raw.target === 'CLOSED' ? raw.target : null,
    fault: FAULT_KINDS.includes(raw.fault as GateFault) ? raw.fault as GateFault : null,
    last_command_id: typeof raw.last_command_id === 'string' ? raw.last_command_id : null,
    last_ack: typeof raw.last_ack === 'string' ? raw.last_ack : null,
    observed: raw.observed === 'open' || raw.observed === 'closed' ? raw.observed : null,
    applied: APPLIED.includes(raw.applied as string) ? raw.applied as GateApplied : 'unknown',
    detail: str(raw.detail),
  };
}

export function parseController(raw: unknown): IncidentController {
  if (!isRecord(raw) || !Array.isArray(raw.gates)) return bad('controller');
  return {
    label: str(raw.label, 'Simulated device: no hardware is connected'), boot_id: str(raw.boot_id),
    heartbeat: raw.heartbeat === 'stale' ? 'stale' : 'ok', transit_seconds: num(raw.transit_seconds, 1.75),
    gates: raw.gates.map(parseGate),
  };
}

export function parseApproval(raw: unknown): IncidentApproval {
  if (!isRecord(raw) || typeof raw.approval_id !== 'string' || !['actuating', 'applied', 'failed'].includes(raw.status as string)
    || typeof raw.plan_revision !== 'number') return bad('approval');
  return {
    approval_id: raw.approval_id, plan_revision: raw.plan_revision, candidate_hash: str(raw.candidate_hash),
    door_states: strMap(raw.door_states) as DoorStateMap, status: raw.status as ApprovalStatus,
    commands: strMap(raw.commands), results: strMap(raw.results), reason: typeof raw.reason === 'string' ? raw.reason : null,
    fallback_plan_revision: typeof raw.fallback_plan_revision === 'number' ? raw.fallback_plan_revision : null,
    actor: raw.actor === 'fail_safe' ? 'fail_safe' : 'operator',
  };
}

const FAILSAFE_STATUSES: readonly string[] = ['off', 'standing_by', 'counting_down', 'acted', 'approved'];

/** Tolerant: a server without the fail-safe (or a broken field) reads as "off", never as armed. */
const VOICE_STATUSES: readonly string[] = ['pending', 'ready', 'failed'];
const voiceAvailability = (raw: Record<string, unknown>) => ({
  voice_available: raw.voice_available === true, voice_model: typeof raw.voice_model === 'string' ? raw.voice_model : null,
});

export function parseFailSafe(raw: unknown): FailSafe {
  if (!isRecord(raw) || raw.armed !== true) {
    return { ...FAILSAFE_OFF, window_seconds: isRecord(raw) ? num(raw.window_seconds, 15) : 15, ...(isRecord(raw) ? voiceAvailability(raw) : {}) };
  }
  const last = raw.last_action;
  const action: FailSafeAction | null = isRecord(last) && typeof last.approval_id === 'string' ? {
    at: str(last.at), plan_revision: num(last.plan_revision), approval_id: last.approval_id, summary: str(last.summary),
    voice: last.voice === 'gemini' ? 'gemini' : last.voice === 'browser' ? 'browser' : null,
    voice_status: VOICE_STATUSES.includes(last.voice_status as string) ? last.voice_status as FailSafeAction['voice_status'] : null,
    voice_model: typeof last.voice_model === 'string' ? last.voice_model : null,
    voice_error: typeof last.voice_error === 'string' ? last.voice_error : null,
  } : null;
  const held = isRecord(raw.held_doors) ? Object.fromEntries(Object.entries(raw.held_doors).map(([gate, rooms]) => [gate, strList(rooms)])) : {};
  return {
    armed: true, window_seconds: num(raw.window_seconds, 15),
    status: FAILSAFE_STATUSES.includes(raw.status as string) && raw.status !== 'off' ? raw.status as FailSafeStatus : 'standing_by',
    plan_revision: typeof raw.plan_revision === 'number' ? raw.plan_revision : null,
    deadline_at: typeof raw.deadline_at === 'string' ? raw.deadline_at : null,
    seconds_left: typeof raw.seconds_left === 'number' ? raw.seconds_left : null,
    held_doors: held, would_hold: strList(raw.would_hold), in_doubt: strList(raw.in_doubt), note: str(raw.note), last_action: action,
    voice: raw.voice === 'gemini' ? 'gemini' : 'browser', ...voiceAvailability(raw),
  };
}

/** Null is a legal plan (none yet, or withdrawn). A present plan must carry what Approve quotes. */
export function parsePlan(raw: unknown): IncidentPlan | null {
  if (raw === null || raw === undefined) return null;
  if (!isRecord(raw) || typeof raw.plan_revision !== 'number' || typeof raw.candidate_hash !== 'string' || !isRecord(raw.door_states)
    || typeof raw.valid !== 'boolean') return bad('plan');
  return {
    plan_id: str(raw.plan_id), plan_revision: raw.plan_revision, candidate_hash: raw.candidate_hash,
    label: raw.label === 'fallback' ? 'fallback' : 'primary', note: typeof raw.note === 'string' ? raw.note : null,
    reason: str(raw.reason), valid: raw.valid, initial_population: num(raw.initial_population), completed_crossings: num(raw.completed_crossings),
    baseline_completed: typeof raw.baseline_completed === 'number' ? raw.baseline_completed : null,
    count_label: str(raw.count_label, 'modeled crossings'), door_states: strMap(raw.door_states) as DoorStateMap,
    doors: Array.isArray(raw.doors) ? raw.doors.filter(isRecord).map(door => ({
      id: str(door.id), state: str(door.state), lamp: str(door.lamp), actuation: str(door.actuation), controllable: door.controllable === true,
      changed: door.changed === true, stuck: door.stuck === true, reason: str(door.reason),
      applied: APPLIED.includes(door.applied as string) ? door.applied as GateApplied : 'unknown',
    })) : [],
    stuck_doors: strList(raw.stuck_doors), held_doors: strList(raw.held_doors),
    advisories: Array.isArray(raw.advisories) ? raw.advisories : [], announcement: str(raw.announcement),
  };
}

export function parseIncidentState(raw: unknown): IncidentState {
  if (!isRecord(raw) || typeof raw.venue_id !== 'string' || typeof raw.plan_revision !== 'number' || !Array.isArray(raw.hazards)
    || !Array.isArray(raw.approvals)) return bad('incident state');
  return {
    venue_id: raw.venue_id, plan_revision: raw.plan_revision, hazards: raw.hazards as HazardInput[],
    plan: parsePlan(raw.plan), plan_error: typeof raw.plan_error === 'string' ? raw.plan_error : null,
    controller: parseController(raw.controller), stuck_doors: strList(raw.stuck_doors), approvals: raw.approvals.map(parseApproval),
    approval_in_progress: raw.approval_in_progress === true, failsafe: parseFailSafe(raw.failsafe), last_event_id: num(raw.last_event_id),
  };
}

/** One SSE frame. Returns null for a frame this client does not understand, so a new event kind never breaks the stream. */
export function parseIncidentEvent(type: string, data: string): IncidentEvent | null {
  let raw: unknown;
  try { raw = JSON.parse(data); } catch { return null; }
  if (!isRecord(raw)) return null;
  const common = { seq: num(raw.seq), ts: str(raw.ts), plan_revision: num(raw.plan_revision), line: typeof raw.line === 'string' ? raw.line : null };
  try {
    switch (type) {
      case 'snapshot': return { ...common, type, seq: num(raw.last_id, common.seq), state: parseIncidentState(raw.state) };
      case 'reset': return { ...common, type, state: parseIncidentState(raw.state) };
      case 'plan': return {
        ...common, type, plan: parsePlan(raw.plan), hazards: Array.isArray(raw.hazards) ? raw.hazards as HazardInput[] : undefined,
        stuck_doors: strList(raw.stuck_doors), plan_error: typeof raw.plan_error === 'string' ? raw.plan_error : null,
      };
      case 'approval': return { ...common, type, approval: parseApproval(raw.approval) };
      case 'failsafe': return { ...common, type, failsafe: parseFailSafe(raw.failsafe) };
      case 'gate': return { ...common, type, gate: parseGate(raw), phase: str(raw.phase) };
      case 'fault': return { ...common, type, fault: str(raw.fault), gate_id: str(raw.gate_id), phase: str(raw.phase) };
      default: return null;
    }
  } catch { return null; }
}

const base = '/api/incident';
const describe = (status: number, _text: string, code: string) => incidentErrorMessage(status, code);

export const fetchIncident = async (signal?: AbortSignal): Promise<IncidentState> =>
  parseIncidentState(await requestJson<unknown>(base, { signal, timeoutMs: 8_000, fallback: 'The door controller could not be read' }));

/** The full checked plan behind the incident's current plan (after a jam: the fallback the doors now follow). */
export async function fetchIncidentDoorPlan(venueId: string, signal?: AbortSignal): Promise<{ plan_revision: number; door_plan: DoorPlanResponse | null }> {
  const raw = await requestJson<unknown>(`${base}/door-plan`, { signal, timeoutMs: 8_000, fallback: 'The executed plan could not be read' });
  if (typeof raw !== 'object' || raw === null || !Number.isInteger((raw as { plan_revision?: unknown }).plan_revision)) throw new ApiError('Unexpected executed plan', 0);
  const { plan_revision, door_plan } = raw as { plan_revision: number; door_plan: unknown };
  return { plan_revision, door_plan: door_plan == null ? null : parseDoorPlan(door_plan, venueId) };
}

export const postIncidentHazards = async (venueId: string, expectedPlanRevision: number, hazards: HazardInput[], signal?: AbortSignal): Promise<IncidentState> =>
  parseIncidentState(await requestJson<unknown>(`${base}/hazards`, {
    method: 'POST', body: { venue_id: venueId, expected_plan_revision: expectedPlanRevision, hazards }, signal, timeoutMs: 20_000,
    fallback: 'The hazards could not be sent to the door controller', describe,
  }));

/** Quotes the plan exactly as shown; the server rejects it with 409 stale_plan if anything differs. */
export const approveIncidentPlan = async (plan: Pick<IncidentPlan, 'plan_revision' | 'candidate_hash' | 'door_states'>): Promise<IncidentApproval> =>
  parseApproval(await requestJson<unknown>(`${base}/approve`, {
    method: 'POST', body: { plan_revision: plan.plan_revision, candidate_hash: plan.candidate_hash, door_states: plan.door_states },
    timeoutMs: 10_000, fallback: 'The approval was not accepted', describe,
  }));

export const injectIncidentFault = async (gateId: string | null, fault: GateFault): Promise<IncidentController> =>
  parseController((await requestJson<{ controller: unknown }>(`${base}/faults`, {
    method: 'POST', body: gateId ? { gate_id: gateId, fault } : { fault }, timeoutMs: 8_000, fallback: 'The fault could not be injected', describe,
  })).controller);

export const clearIncidentFault = async (gateId?: string): Promise<IncidentController> =>
  parseController((await requestJson<{ controller: unknown }>(`${base}/faults/clear`, {
    method: 'POST', body: gateId ? { gate_id: gateId } : {}, timeoutMs: 8_000, fallback: 'The fault could not be cleared', describe,
  })).controller);

export const resetIncident = async (): Promise<IncidentState> =>
  parseIncidentState(await requestJson<unknown>(`${base}/reset`, { method: 'POST', body: {}, timeoutMs: 8_000, fallback: 'The devices could not be reset', describe }));

/** Arm (window 5-120 s, voice) or disarm the unattended fail-safe. Disarming is a person taking over. */
export const setIncidentFailsafe = async (armed: boolean, windowSeconds = 15, voice: FailSafeVoice = 'browser'): Promise<FailSafe> =>
  parseFailSafe(await requestJson<unknown>(`${base}/failsafe`, {
    method: 'POST', body: armed ? { armed, window_seconds: windowSeconds, voice } : { armed }, timeoutMs: 20_000,
    fallback: armed ? 'The fail-safe could not be armed' : 'The fail-safe could not be turned off', describe,
  }));

/** The fail-safe's spoken announcement for one approval (Gemini TTS, made on the server). The server waits for a clip
 *  still being made; an error carries its code (no_voice, voice_pending, provider_timeout, ...). */
export async function fetchFailsafeVoice(approvalId: string, signal?: AbortSignal): Promise<{ blob: Blob; model: string | null }> {
  const response = await fetch(`${base}/failsafe/voice/${encodeURIComponent(approvalId)}`, { signal, cache: 'no-store' });
  if (!response.ok) {
    let code = `http_${response.status}`;
    try { const body = await response.json() as { detail?: { code?: unknown } }; if (typeof body.detail?.code === 'string') code = body.detail.code; } catch { /* keep the status */ }
    throw new ApiError(code, response.status, code);
  }
  return { blob: await response.blob(), model: response.headers.get('x-voice-model') };
}

export const INCIDENT_EVENTS_URL = `${base}/events`;
