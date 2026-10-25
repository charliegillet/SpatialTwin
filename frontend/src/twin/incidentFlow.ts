import { TWIN_ERRORS } from '../api/twin.ts';
import { INCIDENT_EVENTS_URL, parseIncidentEvent } from '../api/incident.ts';
import type { GateFault, IncidentApproval, IncidentEvent, IncidentGate, IncidentPlan, IncidentState } from '../api/incident.ts';
import type { HazardInput } from './types.ts';

/** Pure state for the virtual door controller. No React, no fetch: the hook feeds events in and renders the views out. */

export const MAX_CONSOLE_LINES = 200;
export const POLL_MS = 1500;
export const SIM_LABEL = 'Simulated device';
export const ACK_COPY = 'ACK · heard, not arrived';
/** After the endpoint switch reports, the ACK is history: arrival came from the switch, not from the ACK. */
export const ARRIVED_COPY = 'Endpoint confirmed';
const MOVING: readonly string[] = ['OPENING', 'CLOSING'];

export type ConnectionStatus = 'connecting' | 'live' | 'polling' | 'offline';
export interface ConsoleLine { seq: number; ts: string; text: string; tone: 'info' | 'ok' | 'warn' }

export interface IncidentFlowState {
  incident: IncidentState | null;
  /** Highest event sequence applied. Anything at or below it is a replay or a late response and is dropped. */
  lastSeq: number;
  log: ConsoleLine[];
  /** gate id -> Date.now() when its transit was first seen; elapsed time is derived from it, never a fake timer. */
  movingSince: Record<string, number>;
  connection: ConnectionStatus;
}

export const initialIncidentState = (): IncidentFlowState => ({ incident: null, lastSeq: -1, log: [], movingSince: {}, connection: 'connecting' });

const isMoving = (gate: IncidentGate) => MOVING.includes(gate.state);
const hasActuating = (approvals: readonly IncidentApproval[]) => approvals.some(approval => approval.status === 'actuating');

function lineTone(text: string): ConsoleLine['tone'] {
  if (/\b(FAULT|UNKNOWN|TIMEOUT|stale|failed|rejected|stall)\b/i.test(text)) return 'warn';
  if (/\b(OBSERVATION|applied)\b/i.test(text)) return 'ok';
  return 'info';
}

function append(log: ConsoleLine[], seq: number, ts: string, text: string | null): ConsoleLine[] {
  if (!text) return log;
  const next = [...log, { seq, ts, text, tone: lineTone(text) }];
  return next.length > MAX_CONSOLE_LINES ? next.slice(next.length - MAX_CONSOLE_LINES) : next;
}

/** Keeps `movingSince` honest against a full state: a gate that is in transit keeps its start, a gate at rest loses it. */
function syncMoving(previous: Record<string, number>, gates: readonly IncidentGate[], now: number): Record<string, number> {
  const next: Record<string, number> = {};
  for (const gate of gates) if (isMoving(gate)) next[gate.gate_id] = previous[gate.gate_id] ?? now;
  return next;
}

function eventText(event: IncidentEvent): string | null {
  if (event.line) return event.line;
  if (event.type === 'plan') {
    const plan = event.plan;
    return plan ? `PLAN r${plan.plan_revision} ${plan.label}${plan.valid ? ` ${plan.completed_crossings}/${plan.initial_population} ${plan.count_label}` : ' not checker-valid'}` : `PLAN withdrawn${event.plan_error ? ` (${event.plan_error})` : ''}`;
  }
  if (event.type === 'approval' && event.approval) return `APPROVAL ${event.approval.approval_id} ${event.approval.status} r${event.approval.plan_revision}`;
  return null;
}

/** Replaces the whole incident from a response that reads the server (GET, POST, reset). Late responses are dropped by sequence. */
export function applyIncidentState(state: IncidentFlowState, incident: IncidentState, now: number): IncidentFlowState {
  if (state.incident && incident.last_event_id < state.lastSeq) return state;
  return {
    ...state, incident, lastSeq: Math.max(state.lastSeq, incident.last_event_id),
    movingSince: syncMoving(state.movingSince, incident.controller.gates, now),
  };
}

/** Folds one SSE event in. Snapshot and reset are authoritative; everything else must be newer than what is applied. */
export function reduceIncidentEvent(state: IncidentFlowState, event: IncidentEvent, now: number): IncidentFlowState {
  if (event.type === 'snapshot' && event.state) {
    return { ...state, incident: event.state, lastSeq: event.seq, movingSince: syncMoving({}, event.state.controller.gates, now) };
  }
  if (event.seq <= state.lastSeq) return state;
  const log = append(state.log, event.seq, event.ts, eventText(event));
  const base = { ...state, lastSeq: event.seq, log };
  if (event.type === 'reset' && event.state) return { ...base, incident: event.state, movingSince: syncMoving({}, event.state.controller.gates, now) };
  const incident = state.incident;
  if (!incident) return base;
  switch (event.type) {
    case 'plan': return {
      ...base, incident: {
        ...incident, plan: event.plan ?? null, hazards: event.hazards ?? incident.hazards, stuck_doors: event.stuck_doors ?? incident.stuck_doors,
        plan_error: event.plan_error ?? null, plan_revision: Math.max(incident.plan_revision, event.plan_revision),
      },
    };
    case 'approval': {
      if (!event.approval) return base;
      const approvals = incident.approvals.some(item => item.approval_id === event.approval!.approval_id)
        ? incident.approvals.map(item => item.approval_id === event.approval!.approval_id ? event.approval! : item) : [...incident.approvals, event.approval];
      return { ...base, incident: { ...incident, approvals, approval_in_progress: hasActuating(approvals) } };
    }
    case 'gate': {
      if (!event.gate) return base;
      const gate = event.gate;
      const gates = incident.controller.gates.some(item => item.gate_id === gate.gate_id)
        ? incident.controller.gates.map(item => item.gate_id === gate.gate_id ? gate : item) : [...incident.controller.gates, gate];
      // A fresh command restarts the clock; any other event inside the same transit keeps it.
      const since = { ...state.movingSince };
      if (isMoving(gate)) since[gate.gate_id] = event.phase === 'command' ? now : since[gate.gate_id] ?? now;
      else delete since[gate.gate_id];
      return { ...base, movingSince: since, incident: { ...incident, controller: { ...incident.controller, gates } } };
    }
    case 'fault': {
      // The fault frame names the gate; the badge must show before the gate's own state changes.
      const target = event.gate_id;
      const kind = event.fault as GateFault | undefined;
      let controller = incident.controller;
      if (event.phase === 'controller_stale') controller = { ...controller, heartbeat: 'stale' };
      else if (event.phase === 'fault_injected' && target && kind && kind !== 'heartbeat_timeout') {
        controller = { ...controller, gates: controller.gates.map(gate => gate.gate_id === target ? { ...gate, fault: kind } : gate) };
      } else if (event.phase === 'fault_cleared') {
        controller = { ...controller, gates: controller.gates.map(gate => !target || gate.gate_id === target ? { ...gate, fault: null } : gate) };
      }
      return { ...base, incident: { ...incident, controller } };
    }
    default: return base;
  }
}

/** The POST /approve answer arrives before (or after) the SSE approval frames. It only fills a gap: a record the stream already
 *  advanced to applied/failed must never be pushed back to actuating by the slower HTTP answer. */
export function addApprovalIfNew(state: IncidentFlowState, approval: IncidentApproval): IncidentFlowState {
  const incident = state.incident;
  if (!incident || incident.approvals.some(item => item.approval_id === approval.approval_id)) return state;
  const approvals = [...incident.approvals, approval];
  return { ...state, incident: { ...incident, approvals, approval_in_progress: hasActuating(approvals) } };
}

/** Request identity: a response that began before a reset (or a venue switch) must not land after it. */
export function createStaleGuard() {
  let generation = 0;
  return {
    begin: (): number => generation,
    isCurrent: (token: number): boolean => token === generation,
    invalidate: (): number => ++generation,
  };
}

// ---- derived view --------------------------------------------------------------------------------------------

/** What a door is allowed to look like. `open`/`closed` need the endpoint switch; an ACK alone never gets there. */
export type GateDraw = 'open' | 'closed' | 'opening' | 'closing' | 'unknown' | 'fault';

export interface GateView {
  id: string;
  state: IncidentGate['state'];
  draw: GateDraw;
  label: string;
  target: 'OPEN' | 'CLOSED' | null;
  openSwitch: boolean;
  closedSwitch: boolean;
  observed: 'open' | 'closed' | null;
  epoch: number;
  /** Injected, waiting for the next command. */
  armedFault: GateFault | null;
  /** The gate is in FAULT/UNKNOWN: warning colour, never drawn open. */
  warn: boolean;
  moving: boolean;
  stuck: boolean;
  ack: { heard: boolean; label: string };
  elapsedMs: number | null;
  /** 0..1 of the expected transit, for the bar only; `overdue` means the endpoint switch is late. */
  transitFraction: number | null;
  overdue: boolean;
  detail: string;
}

export function drawGate(gate: IncidentGate): GateDraw {
  if (gate.state === 'OPENING') return 'opening';
  if (gate.state === 'CLOSING') return 'closing';
  if (gate.state === 'FAULT') return 'fault';
  if (gate.state === 'OPEN' && gate.observed === 'open' && gate.open_switch && !gate.closed_switch) return 'open';
  if (gate.state === 'CLOSED' && gate.observed === 'closed' && gate.closed_switch && !gate.open_switch) return 'closed';
  return 'unknown';
}

const DRAW_LABEL: Record<GateDraw, string> = {
  open: 'Open · endpoint seen', closed: 'Closed · endpoint seen', opening: 'Opening…', closing: 'Closing…',
  unknown: 'Unknown · position not seen', fault: 'Fault · never reached its endpoint',
};

export const FAULT_COPY: Record<GateFault, string> = {
  stall: 'Stall: ACK, then no endpoint switch',
  switch_disagreement: 'Switch disagreement: both switches on',
  dropped_ack: 'Dropped ACK: the command is never heard',
  heartbeat_timeout: 'Heartbeat timeout: controller silent',
};

export function gateViews(incident: IncidentState | null, movingSince: Record<string, number>, now: number): GateView[] {
  if (!incident) return [];
  const transitMs = Math.max(1, incident.controller.transit_seconds * 1000);
  return incident.controller.gates.map(gate => {
    const draw = drawGate(gate);
    const moving = isMoving(gate);
    const started = moving ? movingSince[gate.gate_id] : undefined;
    const elapsedMs = started === undefined ? null : Math.max(0, now - started);
    const warn = gate.state === 'FAULT' || gate.state === 'UNKNOWN';
    return {
      id: gate.gate_id, state: gate.state, draw, label: DRAW_LABEL[draw], target: gate.target,
      openSwitch: gate.open_switch, closedSwitch: gate.closed_switch, observed: gate.observed, epoch: gate.epoch,
      armedFault: gate.fault && !warn ? gate.fault : null, warn, moving, stuck: incident.stuck_doors.includes(gate.gate_id),
      ack: !gate.last_ack ? { heard: false, label: 'No ACK' }
        : !moving && !warn && gate.observed && gate.target && gate.observed === gate.target.toLowerCase()
          ? { heard: true, label: `${ARRIVED_COPY} · ${gate.observed}` } : { heard: true, label: ACK_COPY },
      elapsedMs, transitFraction: elapsedMs === null ? null : Math.min(1, elapsedMs / transitMs), overdue: elapsedMs !== null && elapsedMs > transitMs,
      detail: gate.detail,
    };
  });
}

/** For the 3D door leaves: door id -> how to draw it and when its transit began. Signs and unlisted doors follow the plan. */
export function doorVisuals(incident: IncidentState | null, movingSince: Record<string, number>): Record<string, { draw: GateDraw; since: number | null; transitMs: number }> {
  const out: Record<string, { draw: GateDraw; since: number | null; transitMs: number }> = {};
  if (!incident) return out;
  for (const gate of incident.controller.gates) out[gate.gate_id] = { draw: drawGate(gate), since: movingSince[gate.gate_id] ?? null, transitMs: incident.controller.transit_seconds * 1000 };
  return out;
}

export interface Availability { allowed: boolean; reason: string | null }

const hazardKey = (h: HazardInput) => [h.id, h.type, h.position.x.toFixed(3), h.position.y.toFixed(3), h.source, h.untenable_s ?? ''].join('|');

/** The server's incident hazards are the ones this screen shows. Another tab, phone or judge can change them; until
 *  this screen's own set is synced, the plan on the server is not the plan this screen is showing. */
export function hazardsInSync(server: readonly HazardInput[], local: readonly HazardInput[]): boolean {
  if (server.length !== local.length) return false;
  const a = server.map(hazardKey).sort();
  const b = local.map(hazardKey).sort();
  return a.every((key, index) => key === b[index]);
}

/** Approve is only for the current checker-valid plan, never while actuating, never with a gate in doubt unless the plan is the fallback that excludes it. */
export function approveAvailability(incident: IncidentState | null, localHazards?: readonly HazardInput[]): Availability {
  const no = (reason: string): Availability => ({ allowed: false, reason });
  if (!incident) return no('Connecting to the door controller');
  if (localHazards && !hazardsInSync(incident.hazards, localHazards)) return no('Syncing this screen\u2019s hazards with the door controller\u2026');
  if (incident.approval_in_progress || hasActuating(incident.approvals)) return no('Doors are moving — wait for the result');
  if (incident.controller.heartbeat === 'stale') return no('Controller heartbeat lost — reset the devices');
  if (incident.plan_error) return no(`No plan: ${TWIN_ERRORS[incident.plan_error] ?? incident.plan_error}`);
  const plan = incident.plan;
  if (!plan) return no('Place a hazard to get a plan');
  if (!plan.valid) return no('The checker did not accept this plan');
  if (incident.approvals.some(item => item.plan_revision === plan.plan_revision && item.candidate_hash === plan.candidate_hash && item.status !== 'failed')) return no('This plan is already approved');
  const excluded = plan.label === 'fallback' ? plan.stuck_doors : [];
  const doubtful = incident.controller.gates.filter(gate => (gate.state === 'FAULT' || gate.state === 'UNKNOWN') && !excluded.includes(gate.gate_id));
  if (doubtful.length) return no(`${doubtful.map(gate => `${gate.gate_id} is ${gate.state}`).join(', ')} — reset the devices before approving`);
  return { allowed: true, reason: null };
}

const listJoin = (items: readonly string[]) => items.length <= 1 ? items.join('') : `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;

/** The fallback banner. Null unless the current plan is a fallback. */
export function fallbackBanner(incident: IncidentState | null): { headline: string; reason: string } | null {
  const plan = incident?.plan;
  if (!incident || !plan || plan.label !== 'fallback') return null;
  const stuck = plan.stuck_doors.length ? plan.stuck_doors : incident.stuck_doors;
  if (incident.controller.heartbeat === 'stale') {
    return { headline: 'The door controller stopped reporting — every door is held closed in this plan. Approve the fallback?', reason: plan.reason };
  }
  const names = listJoin(stuck) || 'A door';
  return { headline: `${names} never reached its open endpoint — re-planned with ${names} stuck closed. Approve the fallback?`, reason: plan.reason };
}

export function latestApproval(incident: IncidentState | null): IncidentApproval | null {
  return incident?.approvals.length ? incident.approvals[incident.approvals.length - 1] : null;
}

/** One honest sentence about the last approval: heard is not arrived. */
export function approvalSummary(approval: IncidentApproval | null): string | null {
  if (!approval) return null;
  const commands = Object.entries(approval.commands).map(([id, target]) => `${id} ${target.toLowerCase()}`);
  if (approval.status === 'actuating') return `Actuating r${approval.plan_revision}${commands.length ? `: ${commands.join(', ')}` : ''} — waiting for endpoint switches`;
  if (approval.status === 'applied') return commands.length ? `Applied r${approval.plan_revision}: every endpoint observed` : `Applied r${approval.plan_revision}: nothing needed to move`;
  return `Failed r${approval.plan_revision}: ${approval.reason ?? 'an endpoint was never observed'}`;
}

export function planSummary(plan: IncidentPlan | null): string | null {
  if (!plan || !plan.valid) return null;
  return `${plan.completed_crossings} of ${plan.initial_population} ${plan.count_label}`;
}

// ---- hazard sync ---------------------------------------------------------------------------------------------

export const hazardSyncKey = (venueId: string, hazards: readonly HazardInput[]): string => `${venueId}|${JSON.stringify(hazards)}`;

interface HazardSyncOptions {
  post: (venueId: string, expectedPlanRevision: number, hazards: HazardInput[]) => Promise<IncidentState>;
  read: () => Promise<IncidentState>;
  /** The plan_revision the client last saw, or null before anything was read. */
  revision: () => number | null;
  onState: (state: IncidentState) => void;
  onError: (message: string | null) => void;
  debounceMs?: number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
}

const errorStatus = (error: unknown): { status: number; detail: string } => {
  const item = error as { status?: unknown; detail?: unknown } | null;
  return { status: typeof item?.status === 'number' ? item.status : 0, detail: typeof item?.detail === 'string' ? item.detail : '' };
};

/** Posts the twin's hazards to the incident planner once they stop changing. The server bumps plan_revision on every change, so each
 *  post quotes the revision it last saw; a 409 stale_plan means someone else changed it, so read once and retry once. */
export function createHazardSync(options: HazardSyncOptions) {
  const { debounceMs = 350, setTimer = (fn: () => void, ms: number) => setTimeout(fn, ms), clearTimer = (handle: unknown) => clearTimeout(handle as ReturnType<typeof setTimeout>) } = options;
  let desired: { venueId: string; hazards: HazardInput[]; key: string } | null = null;
  let sentKey: string | null = null;
  let timer: unknown = null;
  let inFlight = false;
  let disposed = false;

  const cancelTimer = () => { if (timer !== null) { clearTimer(timer); timer = null; } };
  const schedule = (ms: number) => { cancelTimer(); timer = setTimer(() => { timer = null; void run(); }, ms); };

  async function run(): Promise<void> {
    if (inFlight || disposed || !desired || desired.key === sentKey) return;
    inFlight = true;
    const target = desired;
    try {
      let revision = options.revision();
      if (revision === null) { const state = await options.read(); options.onState(state); revision = state.plan_revision; }
      let state: IncidentState;
      try {
        state = await options.post(target.venueId, revision, target.hazards);
      } catch (error) {
        if (errorStatus(error).status !== 409 || errorStatus(error).detail !== 'stale_plan') throw error;
        const fresh = await options.read();
        options.onState(fresh);
        state = await options.post(target.venueId, fresh.plan_revision, target.hazards);
      }
      options.onState(state);
      sentKey = target.key;
      options.onError(null);
    } catch (error) {
      sentKey = null;
      options.onError(error instanceof Error ? error.message : 'The hazards could not be sent to the door controller');
    } finally {
      inFlight = false;
      // Hazards changed while the request was out: send the newest set (the failure case waits for the next change or kick).
      if (!disposed && desired && desired.key !== target.key && desired.key !== sentKey) schedule(0);
    }
  }

  return {
    update(venueId: string, hazards: HazardInput[]): void {
      const key = hazardSyncKey(venueId, hazards);
      desired = { venueId, hazards, key };
      if (key === sentKey && !inFlight) { cancelTimer(); return; }
      if (key !== sentKey) schedule(debounceMs);
    },
    /** Retry a send that failed (for example while an approval was running). */
    kick(): void { if (desired && desired.key !== sentKey && !inFlight) schedule(0); },
    /** Forget what was sent, e.g. after Reset devices cleared the server's hazards, and send the current set again. */
    resend(): void { sentKey = null; if (desired) schedule(0); },
    dispose(): void { disposed = true; cancelTimer(); },
  };
}

// ---- connection ----------------------------------------------------------------------------------------------

export interface EventSourceLike {
  readyState: number;
  onopen: ((event: unknown) => void) | null;
  onerror: ((event: unknown) => void) | null;
  addEventListener: (type: string, listener: (event: { data: string }) => void) => void;
  close: () => void;
}

interface ConnectionOptions {
  makeSource: (url: string) => EventSourceLike;
  poll: () => Promise<IncidentState>;
  onEvent: (event: IncidentEvent) => void;
  onPolled: (state: IncidentState) => void;
  onStatus: (status: ConnectionStatus) => void;
  /** Highest applied sequence; a re-created source resumes after it. */
  lastSeq: () => number;
  pollMs?: number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
}

const EVENT_TYPES = ['snapshot', 'plan', 'approval', 'gate', 'fault', 'reset'] as const;
const CLOSED = 2;

/** SSE first (the browser reconnects with Last-Event-ID by itself). When the stream errors, GET /api/incident every 1.5 s until frames flow again. */
export function createIncidentConnection(options: ConnectionOptions) {
  const { pollMs = POLL_MS, setTimer = (fn: () => void, ms: number) => setInterval(fn, ms), clearTimer = (handle: unknown) => clearInterval(handle as ReturnType<typeof setInterval>) } = options;
  let source: EventSourceLike | null = null;
  let poller: unknown = null;
  let polling = false;
  let stopped = false;

  const live = () => { stopPolling(); options.onStatus('live'); };
  function stopPolling() { if (poller !== null) { clearTimer(poller); poller = null; } }

  async function pollOnce() {
    if (polling || stopped) return;
    polling = true;
    try {
      const state = await options.poll();
      if (!stopped && poller !== null) { options.onPolled(state); options.onStatus('polling'); }
    } catch { if (!stopped && poller !== null) options.onStatus('offline'); }
    finally { polling = false; }
    // A source the browser gave up on never reconnects by itself.
    if (!stopped && poller !== null && source?.readyState === CLOSED) open();
  }

  function startPolling() {
    if (poller !== null || stopped) return;
    options.onStatus('polling');
    poller = setTimer(() => { void pollOnce(); }, pollMs);
    void pollOnce();
  }

  function open() {
    source?.close();
    const last = options.lastSeq();
    const next = options.makeSource(last > 0 ? `${INCIDENT_EVENTS_URL}?last_event_id=${last}` : INCIDENT_EVENTS_URL);
    source = next;
    next.onopen = () => { if (source === next) live(); };
    next.onerror = () => { if (source === next) startPolling(); };
    for (const type of EVENT_TYPES) {
      next.addEventListener(type, message => {
        if (source !== next) return;
        const event = parseIncidentEvent(type, message.data);
        if (!event) return;
        live();
        options.onEvent(event);
      });
    }
  }

  return {
    start(): void { stopped = false; options.onStatus('connecting'); open(); },
    stop(): void { stopped = true; stopPolling(); source?.close(); source = null; },
  };
}
