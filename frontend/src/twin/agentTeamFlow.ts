import type { HazardInput } from './types.ts';
import {
  TEAM_LANES,
  type LaneState, type LaneView, type LaneVerification, type TeamLane, type TeamMode, type TeamProgress, type TeamRun, type TeamStart, type TraceConnection,
  type TraceEvent, type TraceLine, type TraceKind,
} from './agentTeamTypes.ts';

/**
 * Pure state machine for the managed-agent team (Strategist + Robustness, then follow-ups). No React, no network: the runner at the bottom takes its
 * I/O as dependencies so the whole life cycle (start, stream, polling fallback, cancel, stale guards) is tested without a browser.
 * Thoughts are never in the trace: `thought` steps are dropped on purpose (agents do not expose them), so nothing here can imply them.
 */

/** Per lane; older lines fall off the front and are counted, so a chatty sandbox cannot grow the DOM without bound. */
export const MAX_TRACE_LINES = 120;
const MAX_LINE_CHARS = 4000;
/** The server cancels at the lane deadline and needs a moment to reserve the fallback; the client gives up only after that. */
export const CANCEL_RESERVE_MS = 15_000;
export const POLL_MS = 1000;
/** If the server's clock and ours disagree by more than this, trust our own elapsed time over `deadline_at_ms`. */
const MAX_CLOCK_SKEW_MS = 5000;
const TERMINAL_PHASES = new Set(['completed', 'failed', 'cancelled', 'timed_out', 'incomplete']);

export const idleRun = (): TeamRun => ({
  status: 'idle', mode: null, teamId: null, hazardsKey: '', startedAt: null, deadlineMs: null, lanes: {}, order: [], lastSeq: 0,
  connection: 'idle', error: null, notice: null, scenario: null, parentId: null,
});

export const hazardsKeyOf = (hazards: readonly HazardInput[]): string => JSON.stringify(hazards);
export const isActive = (run: TeamRun): boolean => run.status === 'starting' || run.status === 'running';
export const isTerminalPhase = (phase: LaneState['phase']): boolean => TERMINAL_PHASES.has(phase);

export const newLane = (lane: TeamLane): LaneState => ({
  lane, phase: 'waiting', investigationId: null, deadlineMs: null, startedAt: null, trace: [], droppedLines: 0, statesChecked: null,
  view: null, fallbackView: null, fallbackReason: null, verification: null, usage: null,
});

/** Whether the Ask button is available, and if not, why. */
export function askAvailability(input: { hazardCount: number; planReady: boolean; pending: boolean; active: boolean }): string | null {
  if (input.active) return 'The agent team is working';
  if (input.hazardCount === 0) return 'Place a hazard first';
  if (!input.planReady || input.pending) return 'Waiting for the planner';
  return null;
}

// --- deadlines ------------------------------------------------------------------------------------------------

/** The server's absolute deadline, unless its clock disagrees with ours (a projector laptop with a drifting clock must not show a negative countdown). */
export function resolveDeadline(serverMs: number, seconds: number | null, now: number): number {
  if (seconds === null || !Number.isFinite(seconds)) return serverMs;
  const local = now + seconds * 1000;
  return Math.abs(local - serverMs) > MAX_CLOCK_SKEW_MS ? local : serverMs;
}

/** Whole seconds left, never negative; null when there is no deadline. */
export function remainingSeconds(deadlineMs: number | null, now: number): number | null {
  if (deadlineMs === null) return null;
  return Math.max(0, Math.ceil((deadlineMs - now) / 1000));
}

export function countdownLabel(deadlineMs: number | null, now: number): string | null {
  const left = remainingSeconds(deadlineMs, now);
  if (left === null) return null;
  if (left === 0) return 'finishing…';
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')} left`;
}

/** When the client stops waiting for a run: the latest lane deadline plus the server's cancel and fallback reserve. */
export const giveUpAt = (run: TeamRun): number | null => run.deadlineMs === null ? null : run.deadlineMs + CANCEL_RESERVE_MS;

// --- run transitions ------------------------------------------------------------------------------------------

export function beginRun(input: { mode: TeamMode; hazardsKey: string; now: number; lanes: readonly TeamLane[]; scenario?: string | null; parentId?: string | null }): TeamRun {
  const lanes: TeamRun['lanes'] = {};
  for (const lane of input.lanes) lanes[lane] = newLane(lane);
  return { ...idleRun(), status: 'starting', mode: input.mode, hazardsKey: input.hazardsKey, startedAt: input.now, lanes, order: [...input.lanes], scenario: input.scenario ?? null, parentId: input.parentId ?? null };
}

export function applyStart(run: TeamRun, start: TeamStart, now: number): TeamRun {
  const lanes: TeamRun['lanes'] = { ...run.lanes };
  const order = TEAM_LANES.filter(lane => start.lanes[lane] || run.lanes[lane]);
  for (const lane of order) {
    const info = start.lanes[lane];
    const base = lanes[lane] ?? newLane(lane);
    lanes[lane] = info ? { ...base, investigationId: info.investigation_id, deadlineMs: resolveDeadline(info.deadline_at_ms, info.deadline_seconds, now) } : base;
  }
  const latest = Math.max(...order.map(lane => lanes[lane]?.deadlineMs ?? 0));
  return { ...run, status: 'running', teamId: start.investigation_id, lanes, order, deadlineMs: latest > 0 ? latest : null, scenario: start.scenario ?? run.scenario, parentId: start.parent_investigation_id ?? run.parentId, connection: 'connecting', notice: null };
}

export const failRun = (run: TeamRun, message: string): TeamRun => ({ ...run, status: 'failed', error: message, notice: null, connection: run.connection === 'idle' ? 'idle' : 'closed' });

/** Cancel keeps the partial trace on screen (it is evidence of what ran) but marks every unfinished lane cancelled; a cancelled lane never falls back. */
export function cancelRun(run: TeamRun): TeamRun {
  const lanes: TeamRun['lanes'] = {};
  for (const lane of run.order) {
    const state = run.lanes[lane];
    if (state) lanes[lane] = isTerminalPhase(state.phase) ? state : { ...state, phase: 'cancelled' };
  }
  return { ...run, status: 'cancelled', lanes, connection: 'closed', notice: null };
}

export const setConnection = (run: TeamRun, connection: TraceConnection): TeamRun => run.connection === connection ? run : { ...run, connection };

// --- trace events ---------------------------------------------------------------------------------------------

const str = (value: unknown): string => typeof value === 'string' ? value : '';
const num = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const clip = (text: string, max = MAX_LINE_CHARS) => text.length > max ? `${text.slice(0, max)}…` : text;

function withLine(lane: LaneState, line: TraceLine): LaneState {
  const index = lane.trace.findIndex(item => item.key === line.key);
  if (index >= 0) {
    const trace = lane.trace.slice();
    trace[index] = line;
    return { ...lane, trace };
  }
  const trace = [...lane.trace, line];
  const over = trace.length - MAX_TRACE_LINES;
  return over > 0 ? { ...lane, trace: trace.slice(over), droppedLines: lane.droppedLines + over } : { ...lane, trace };
}

const note = (key: string, atMs: number, text: string, kind: TraceKind = 'note', isError = false): TraceLine => ({ key, kind, atMs, text, isError });

const STEP_KIND: Record<string, TraceKind> = { code_execution_call: 'code', code_execution_result: 'result', model_output: 'output', function_call: 'call' };

/** A lane event arriving for a lane we have no state for (a follow-up id, say) creates it rather than being lost. */
function laneOf(run: TeamRun, name: TeamLane): [LaneState, TeamRun] {
  const existing = run.lanes[name];
  if (existing) return [existing, run];
  const created = newLane(name);
  return [created, { ...run, lanes: { ...run.lanes, [name]: created }, order: TEAM_LANES.filter(lane => lane === name || run.order.includes(lane)) }];
}

function phaseOf(status: string): LaneState['phase'] {
  return status === 'completed' || status === 'failed' || status === 'cancelled' || status === 'timed_out' || status === 'incomplete' ? status : 'running';
}

const toVerification = (raw: unknown): LaneVerification | null => {
  if (typeof raw !== 'object' || raw === null) return null;
  const item = raw as Record<string, unknown>;
  const verified = num(item.verified);
  const total = num(item.total);
  if (verified === null || total === null) return null;
  const source = item.source === 'sandbox' || item.source === 'agent' ? item.source : 'local';
  return { verified, total, source, mismatches: Array.isArray(item.mismatches) ? item.mismatches as LaneVerification['mismatches'] : [], ...(Array.isArray(item.checks) ? { checks: item.checks as LaneVerification['mismatches'] } : {}),
    ...(num(item.sandbox_matched) !== null ? { sandbox_matched: num(item.sandbox_matched) as number } : {}) };
};

/** Applies one SSE frame. Frames at or below `lastSeq` are replays and are ignored; frames after the run ended never repopulate it. */
export function reduceTrace(run: TeamRun, event: TraceEvent, now: number): TeamRun {
  if (run.status !== 'running' || event.seq <= run.lastSeq) return run;
  const base: TeamRun = { ...run, lastSeq: event.seq };
  const d = event.data;

  if (event.event === 'deadline') {
    const lanes = { ...base.lanes };
    const raw = typeof d.lanes === 'object' && d.lanes !== null ? d.lanes as Record<string, Record<string, unknown>> : {};
    for (const name of TEAM_LANES) {
      const info = raw[name];
      const current = lanes[name];
      const ms = info ? num(info.deadline_at_ms) : null;
      if (current && ms !== null && current.deadlineMs === null) lanes[name] = { ...current, deadlineMs: resolveDeadline(ms, num(info?.deadline_seconds), now) };
    }
    return { ...base, lanes };
  }

  if (event.event === 'done') {
    const cancelled = d.team_status === 'cancelled';
    const next: TeamRun = { ...base, status: cancelled ? 'cancelled' : 'done', connection: 'closed', notice: null };
    return cancelled ? cancelRun(next) : next;
  }

  if (!event.lane) return base;
  const [lane0, withLane] = laneOf(base, event.lane);
  const stage = (next: LaneState): TeamRun => ({ ...withLane, lanes: { ...withLane.lanes, [event.lane as TeamLane]: next } });
  const at = event.elapsed_ms;

  switch (event.event) {
    case 'lane': {
      const status = str(d.status);
      const fallback = d.fallback_for !== undefined && d.fallback_for !== null;
      let next: LaneState = lane0;
      if (status === 'started') {
        next = { ...lane0, phase: 'running', startedAt: lane0.startedAt ?? now };
        const ms = num(d.deadline_at_ms);
        if (ms !== null && next.deadlineMs === null) next = { ...next, deadlineMs: resolveDeadline(ms, num(d.deadline_seconds), now) };
        if (fallback) next = withLine(next, note(`lane:${event.seq}`, at, 'Running the local fallback for the live lane that failed.'));
      } else if (status === 'plan_ready') {
        next = { ...lane0, phase: lane0.phase === 'waiting' || lane0.phase === 'running' ? 'plan_ready' : lane0.phase, statesChecked: num(d.states_checked) };
        next = withLine(next, note(`lane:${event.seq}`, at, `Checker solved ${next.statesChecked ?? '?'} door states${fallback ? ' (local fallback)' : ''}.`));
      }
      return stage(next);
    }
    case 'status': {
      const text = str(d.status);
      if (!text) return stage(lane0);
      const last = lane0.trace[lane0.trace.length - 1];
      if (last?.kind === 'status' && last.text === text) return stage(lane0);
      // Only the latest provider status is kept; a run of "in_progress" lines is noise.
      const trimmed = { ...lane0, trace: lane0.trace.filter(line => line.kind !== 'status') };
      return stage(withLine(trimmed, note(`status:${event.seq}`, at, text, 'status')));
    }
    case 'delta': {
      const stepType = str(d.step_type);
      if (stepType === 'thought') return stage(lane0);
      const kind = STEP_KIND[stepType] ?? 'note';
      const key = `step:${num(d.index) ?? event.seq}`;
      const existing = lane0.trace.find(line => line.key === key);
      if (existing && !existing.partial) return stage(lane0);
      const chunk = d.kind === 'delta' ? str(d.text) : '';
      const text = clip(`${existing?.text ?? ''}${chunk}`);
      return stage(withLine(lane0, { key, kind, atMs: existing?.atMs ?? at, name: existing?.name, text, partial: true }));
    }
    case 'step': {
      const stepType = str(d.step_type);
      if (stepType === 'thought') return stage(lane0);
      const kind = STEP_KIND[stepType] ?? 'note';
      const key = `step:${num(d.index) ?? event.seq}`;
      const text = clip(str(d.text));
      const name = str(d.name) || undefined;
      return stage(withLine(lane0, { key, kind, atMs: at, name, text: text || (kind === 'note' ? stepType : ''), isError: d.is_error === true }));
    }
    case 'tool': {
      const name = str(d.function_name) || 'tool';
      const status = str(d.status) || 'executed';
      const verified = num(d.verified);
      const total = num(d.total);
      const ms = num(d.execution_time_ms);
      const parts = [status, ms === null ? '' : `${Math.round(ms)} ms`, verified !== null && total !== null ? `${verified} of ${total} claims reproduced` : '', str(d.error)].filter(Boolean);
      return stage(withLine(lane0, { key: `tool:${event.seq}`, kind: 'tool', atMs: at, name, text: parts.join(' · '), isError: status === 'failed' }));
    }
    case 'verification': {
      const verification = toVerification(d);
      if (!verification) return stage(lane0);
      const text = `Local checker re-ran the claims: ${verification.verified} of ${verification.total} reproduced (${verification.source}).`;
      return stage(withLine({ ...lane0, verification }, note(`verification:${event.seq}`, at, text, 'note', verification.verified < verification.total)));
    }
    case 'usage': {
      const usage = { token_usage: (typeof d.token_usage === 'object' && d.token_usage !== null ? d.token_usage : {}) as Record<string, number>, token_budget: num(d.token_budget), cost_estimate: (d.cost_estimate ?? null) as LaneView['cost_estimate'] ?? null };
      return stage({ ...lane0, usage });
    }
    case 'retry':
      return stage(withLine(lane0, note(`retry:${event.seq}`, at, `Retry ${num(d.attempt) ?? '?'} after ${str(d.code) || 'an error'}${num(d.delay_ms) !== null ? ` (${Math.round(num(d.delay_ms) as number)} ms)` : ''}`)));
    case 'stream':
      return stage(withLine(lane0, note(`stream:${event.seq}`, at, d.action === 'resumed' ? 'Provider stream resumed.' : 'Provider stream dropped; reading steps by polling.')));
    case 'fallback': {
      const reason = typeof d.reason === 'object' && d.reason !== null ? d.reason as Record<string, unknown> : {};
      const errors = Array.isArray(reason.errors) ? reason.errors.filter((item): item is string => typeof item === 'string') : [];
      const next = { ...lane0, fallbackReason: { status: str(reason.status) || 'failed', errors } };
      return stage(withLine(next, note(`fallback:${event.seq}`, at, `Live lane ${next.fallbackReason.status}${errors.length ? ` (${errors.join(', ')})` : ''}. Switching to the local solver.`, 'error', true)));
    }
    case 'result': {
      const view = d as unknown as LaneView;
      const isFallback = d.fallback_for !== undefined && d.fallback_for !== null;
      const status = str(d.status);
      const verification = toVerification(d.verification) ?? lane0.verification;
      const usage = d.cost_estimate || (typeof d.token_usage === 'object' && d.token_usage !== null && Object.keys(d.token_usage).length)
        ? { token_usage: (d.token_usage ?? {}) as Record<string, number>, token_budget: num(d.token_budget), cost_estimate: (d.cost_estimate ?? null) as LaneView['cost_estimate'] ?? null }
        : lane0.usage;
      const next: LaneState = isFallback
        ? { ...lane0, fallbackView: view, phase: phaseOf(status), verification, usage, fallbackReason: lane0.fallbackReason ?? { status: str((d.fallback_for as Record<string, unknown>).status) || 'failed', errors: Array.isArray((d.fallback_for as Record<string, unknown>).errors) ? ((d.fallback_for as Record<string, unknown>).errors as string[]) : [] } }
        : { ...lane0, view, phase: phaseOf(status), verification, usage };
      return stage(next);
    }
    default:
      return stage(lane0);
  }
}

// --- polling reconcile ----------------------------------------------------------------------------------------

/**
 * Applies GET /investigations/{id}. Used when the stream is down and once more after `done`, because the polled view is authoritative about
 * `effective` and the nested fallback (a failed live lane stays visible, its local fallback is shown beside it, never substituted).
 */
export function applyProgress(run: TeamRun, progress: TeamProgress, now: number): TeamRun {
  const lanes: TeamRun['lanes'] = { ...run.lanes };
  for (const name of TEAM_LANES) {
    const view = progress.lanes[name];
    if (!view) continue;
    const current = lanes[name] ?? newLane(name);
    const running = view.status === 'running';
    if (running) {
      lanes[name] = current.phase === 'waiting' ? { ...current, phase: 'running', startedAt: current.startedAt ?? now } : current;
      continue;
    }
    const fallbackView = view.fallback ?? current.fallbackView;
    const effective = view.effective === 'local_fallback' && fallbackView ? fallbackView : view;
    const reason = fallbackView ? current.fallbackReason ?? { status: view.status, errors: view.errors ?? [] } : current.fallbackReason;
    lanes[name] = {
      ...current, view: { ...view, fallback: null }, fallbackView: fallbackView ?? null, fallbackReason: reason, phase: phaseOf(effective.status),
      verification: effective.verification ?? current.verification,
      usage: effective.token_usage || effective.cost_estimate ? { token_usage: effective.token_usage ?? {}, token_budget: effective.token_budget ?? null, cost_estimate: effective.cost_estimate ?? null } : current.usage,
    };
  }
  const order = TEAM_LANES.filter(name => lanes[name]);
  if (progress.team_status === 'running') return { ...run, lanes, order, deadlineMs: run.deadlineMs ?? progress.deadline_at_ms };
  const cancelled = progress.team_status === 'cancelled';
  // A finished team may carry lanes whose stub never became a result (cancelled mid-way); they stop reading as running.
  const settled = cancelled ? cancelRun({ ...run, lanes, order }) : { ...run, lanes, order };
  return { ...settled, status: cancelled ? 'cancelled' : run.status === 'failed' ? 'failed' : 'done', connection: 'closed', notice: null };
}

// --- follow-ups -----------------------------------------------------------------------------------------------

/** Natural-language or grammar input to the scenario grammar the backend accepts; null when it cannot be understood. */
export function normalizeScenario(input: string): string | null {
  const text = input.trim();
  if (!text) return null;
  if (/^[a-z_]+(:[A-Za-z0-9_@.=-]+)?(\+[a-z_]+:[A-Za-z0-9_@.=-]+){0,2}$/.test(text)) return text;
  const door = text.match(/\bD\d+\b/i);
  if (door && /(jam|stuck|stick|fail|clos|lock|block)/i.test(text)) return `stuck_closed:${door[0].toUpperCase()}`;
  return null;
}

/** Up to three "What if Dn jams?" chips: the doors the lane recommends opening first (an open door is the one that can jam), then the jam fallback's doors. */
export function followUpSuggestions(run: TeamRun): { label: string; scenario: string }[] {
  const ids: string[] = [];
  for (const lane of run.order) {
    const state = run.lanes[lane];
    const view = state?.fallbackView ?? state?.view;
    if (!view || lane === 'followup') continue;
    const states = view.recommended_door_states ?? {};
    for (const [id, value] of Object.entries(states)) if (value === 'open' && !ids.includes(id)) ids.push(id);
  }
  for (const lane of run.order) {
    const view = run.lanes[lane]?.fallbackView ?? run.lanes[lane]?.view;
    for (const [id, value] of Object.entries(view?.fallback_if_jammed ?? {})) if (value === 'open' && !ids.includes(id)) ids.push(id);
  }
  return ids.slice(0, 3).map(id => ({ label: `What if ${id} jams?`, scenario: `stuck_closed:${id}` }));
}

/** Follow-up is possible once the team has stopped and at least one lane produced a recommendation; returns the reason it is not, or null. */
export function followUpUnavailable(run: TeamRun): string | null {
  if (run.status === 'idle') return 'Ask the agent team first';
  if (isActive(run)) return 'The team is still working';
  if (run.status === 'cancelled') return 'The run was cancelled';
  if (!run.teamId) return 'The run did not start';
  return null;
}

export interface RetryOptions { retries?: number; waitMs?: number; sleep?: (ms: number) => Promise<void>; onWait?: (attempt: number) => void; shouldRetry: (error: unknown) => boolean }

/** 409 parent_finishing means the earlier agent is still acknowledging; wait a moment and ask again, a few times, then surface the error. */
export async function withRetry<T>(work: () => Promise<T>, options: RetryOptions): Promise<T> {
  const { retries = 3, waitMs = 2000, sleep = ms => new Promise<void>(resolve => setTimeout(resolve, ms)), onWait, shouldRetry } = options;
  for (let attempt = 0; ; attempt++) {
    try { return await work(); } catch (error) {
      if (attempt >= retries || !shouldRetry(error)) throw error;
      onWait?.(attempt + 1);
      await sleep(waitMs);
    }
  }
}

// --- connection (SSE first, polling when it drops) ------------------------------------------------------------

/** The slice of EventSource the connection needs; a fake implements it in tests. */
export interface EventSourceLike {
  readyState: number;
  onopen: ((event: unknown) => void) | null;
  onerror: ((event: unknown) => void) | null;
  addEventListener(type: string, listener: (message: { data: string }) => void): void;
  close(): void;
}
const CLOSED = 2;

export interface ConnectionOptions {
  makeSource: (after: number) => EventSourceLike;
  poll: () => Promise<TeamProgress>;
  lastSeq: () => number;
  parse: (type: string, data: string) => TraceEvent | null;
  eventTypes: readonly string[];
  onEvent: (event: TraceEvent) => void;
  onPolled: (progress: TeamProgress) => void;
  onStatus: (status: TraceConnection) => void;
  pollMs?: number;
  setTimer?: (fn: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
}

/** SSE first. When the stream errors, GET the investigation every second until frames flow again; a source the browser gave up on is reopened from `lastSeq`. */
export function createTraceConnection(options: ConnectionOptions) {
  const { pollMs = POLL_MS, setTimer = (fn: () => void, ms: number) => setInterval(fn, ms), clearTimer = (handle: unknown) => clearInterval(handle as ReturnType<typeof setInterval>) } = options;
  let source: EventSourceLike | null = null;
  let poller: unknown = null;
  let polling = false;
  let stopped = false;

  function stopPolling() { if (poller !== null) { clearTimer(poller); poller = null; } }
  const live = () => { stopPolling(); options.onStatus('live'); };

  async function pollOnce() {
    if (polling || stopped) return;
    polling = true;
    try {
      const progress = await options.poll();
      if (!stopped && poller !== null) { options.onPolled(progress); options.onStatus('polling'); }
    } catch { if (!stopped && poller !== null) options.onStatus('offline'); }
    finally { polling = false; }
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
    const next = options.makeSource(options.lastSeq());
    source = next;
    next.onopen = () => { if (source === next) live(); };
    next.onerror = () => { if (source === next) startPolling(); };
    for (const type of options.eventTypes) {
      next.addEventListener(type, message => {
        if (source !== next || stopped) return;
        const event = options.parse(type, message.data);
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

// --- runner ---------------------------------------------------------------------------------------------------

export interface RunnerDeps {
  poll: (id: string, signal: AbortSignal) => Promise<TeamProgress>;
  cancel: (id: string) => Promise<unknown>;
  openConnection: (run: { teamId: string; traceUrl: string; lastSeq: () => number; onEvent: (event: TraceEvent) => void; onPolled: (progress: TeamProgress) => void; onStatus: (status: TraceConnection) => void; poll: () => Promise<TeamProgress> }) => { start(): void; stop(): void };
  onRun: (run: TeamRun) => void;
  describeError?: (error: unknown) => string;
  now?: () => number;
  /** One-shot timer; returns a cancel function. */
  after?: (fn: () => void, ms: number) => () => void;
}

export interface BeginOptions {
  mode: TeamMode;
  hazardsKey: string;
  lanes: readonly TeamLane[];
  scenario?: string | null;
  parentId?: string | null;
  start: (signal: AbortSignal, notify: (message: string | null) => void) => Promise<TeamStart>;
}

const defaultAfter = (fn: () => void, ms: number) => { const timer = setTimeout(fn, ms); return () => clearTimeout(timer); };

/**
 * One team run at a time. Every async continuation re-checks a token, so a result of a run that was cancelled, reset (new hazards, venue switch,
 * Next judge) or superseded can never repopulate the state, including a late start response or a late stream frame.
 */
export function createTeamRunner({ poll, cancel, openConnection, onRun, describeError = error => error instanceof Error && error.message ? error.message : 'The agent team could not be reached.', now = Date.now, after = defaultAfter }: RunnerDeps) {
  let token = 0;
  let run = idleRun();
  let controller: AbortController | null = null;
  let connection: { start(): void; stop(): void } | null = null;
  let cancelWatchdog: (() => void) | null = null;
  const publish = (next: TeamRun) => { run = next; onRun(next); };

  function teardown() {
    controller?.abort();
    controller = null;
    connection?.stop();
    connection = null;
    cancelWatchdog?.();
    cancelWatchdog = null;
  }

  const release = (id: string | null) => { if (id) void cancel(id).catch(() => undefined); };

  async function reconcile(mine: number, signal: AbortSignal) {
    const id = run.teamId;
    if (!id) return;
    try {
      const progress = await poll(id, signal);
      if (mine === token) publish(applyProgress(run, progress, now()));
    } catch { /* the trace already carries the result; a failed final read leaves it as is */ }
  }

  function finishIfTerminal(mine: number) {
    if (mine !== token || isActive(run)) return;
    connection?.stop();
    connection = null;
    cancelWatchdog?.();
    cancelWatchdog = null;
  }

  async function begin(options: BeginOptions): Promise<void> {
    teardown();
    const mine = ++token;
    const started = now();
    controller = new AbortController();
    const { signal } = controller;
    publish(beginRun({ mode: options.mode, hazardsKey: options.hazardsKey, now: started, lanes: options.lanes, scenario: options.scenario, parentId: options.parentId }));
    let start: TeamStart;
    try {
      start = await options.start(signal, message => { if (mine === token) publish({ ...run, notice: message }); });
    } catch (error) {
      if (mine !== token) return;
      publish(failRun(run, describeError(error)));
      return;
    }
    if (mine !== token) { release(start.investigation_id); return; }
    publish(applyStart(run, start, now()));
    const id = start.investigation_id;

    connection = openConnection({
      teamId: id,
      traceUrl: start.trace_url,
      lastSeq: () => run.lastSeq,
      poll: () => poll(id, signal),
      onEvent: event => {
        if (mine !== token) return;
        publish(reduceTrace(run, event, now()));
        // `done` is the last frame: close the stream, then ask once for the authoritative lane views (effective, nested fallback).
        if (event.event === 'done') { finishIfTerminal(mine); void reconcile(mine, signal); }
      },
      onPolled: progress => { if (mine === token) { publish(applyProgress(run, progress, now())); finishIfTerminal(mine); } },
      onStatus: status => { if (mine === token && isActive(run)) publish(setConnection(run, status)); },
    });
    connection.start();

    const limit = giveUpAt(run);
    if (limit !== null) {
      cancelWatchdog = after(() => {
        if (mine !== token || !isActive(run)) return;
        release(id);
        teardown();
        publish(failRun(run, 'The agent team did not finish in time. The checker\'s plan above still stands.'));
      }, Math.max(0, limit - now()));
    }
  }

  return {
    state: () => run,
    /** Resolves when the start request settles (not when the run ends); false when a run is already active. */
    begin(options: BeginOptions): Promise<void> | false {
      if (isActive(run)) return false;
      return begin(options);
    },
    cancel() {
      if (!isActive(run) && run.status === 'idle') return;
      const id = run.teamId;
      const wasActive = isActive(run);
      token++;
      teardown();
      if (wasActive) release(id);
      publish(cancelRun(run));
    },
    /** New hazard set, venue switch, mode change or Next judge: same as cancel, but back to idle and silent when nothing ran. */
    reset() {
      const wasActive = isActive(run);
      const id = wasActive ? run.teamId : null;
      const wasIdle = run.status === 'idle';
      token++;
      teardown();
      release(id);
      if (!wasIdle) publish(idleRun());
    },
  };
}
