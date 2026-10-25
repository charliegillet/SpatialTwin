import { createRequestGate } from '../ai/requestGate.ts';
import { createWorkflowEpoch } from '../ai/workflowEpoch.ts';
import type { DoorAgentMode, DoorAgentProgress, DoorAgentProgressEvent, DoorAgentResult, DoorAgentToolCall, DoorStateMap, HazardInput } from './types.ts';

export const LOCAL_LABEL = 'Local solver · no Gemini call';
export const LIVE_LABEL = 'Live Gemini';
export const POLL_INTERVAL_MS = 700;
/** The backend deadline is 60 s; the client gives up slightly later and says so. */
export const CLIENT_DEADLINE_MS = 75_000;
const MAX_POLL_FAILURES = 3;

export type DoorAgentStatusKind = 'idle' | 'running' | 'finished' | 'failed';

export interface DoorAgentState {
  status: DoorAgentStatusKind;
  mode: DoorAgentMode | null;
  investigationId: string | null;
  /** Date.now() when Ask was pressed; the view derives elapsed time from it. */
  startedAt: number | null;
  events: DoorAgentProgressEvent[];
  result: DoorAgentResult | null;
  error: string | null;
}

export const idleAgent = (): DoorAgentState => ({ status: 'idle', mode: null, investigationId: null, startedAt: null, events: [], result: null, error: null });

export const NO_CHECKED_BEST = 'No checked plan \u2014 the checker rejected its best state. The agent\'s suggestion is not verified.';
export const modeLabel = (mode: DoorAgentMode): string => mode === 'live' ? LIVE_LABEL : LOCAL_LABEL;
export const askLabel = (mode: DoorAgentMode): string => `Ask the agent · ${mode === 'live' ? LIVE_LABEL : 'Local solver'}`;

/** Whether the Ask action is available, and if not, why. */
export function askAvailability(input: { hazardCount: number; planReady: boolean; pending: boolean; running: boolean }): string | null {
  if (input.running) return 'The agent is working';
  if (input.hazardCount === 0) return 'Place a hazard first';
  if (!input.planReady || input.pending) return 'Waiting for the planner';
  return null;
}

export function elapsedLabel(ms: number): string {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)} min ${seconds % 60} s`;
}

const status = (event: DoorAgentProgressEvent) => typeof event.status === 'string' ? event.status : '';
const at = (event: DoorAgentProgressEvent) => typeof event.elapsed_ms === 'number' && Number.isFinite(event.elapsed_ms) ? event.elapsed_ms : 0;

export interface AgentPhase { label: string; atMs: number }

/** Receipts collapse into one entry per phase, the first time it was reached. */
export function agentPhases(events: readonly DoorAgentProgressEvent[]): AgentPhase[] {
  const phases: AgentPhase[] = [];
  const add = (label: string, atMs: number) => { if (!phases.some(phase => phase.label === label)) phases.push({ label, atMs }); };
  for (const event of events) {
    if (event.phase === 'plan_ready') add('plan checked', at(event));
    else if (event.phase === 'provider_request') add('submitted', at(event));
    else if (event.phase === 'local_tool_complete') add('checked locally', at(event));
    else if (event.phase === 'provider_cancel_response') add('cancelled', at(event));
    else if (event.phase === 'provider_response') {
      const s = status(event);
      add(s === 'completed' ? 'finished' : s === 'requires_action' ? 'tool requested' : ['failed', 'cancelled', 'incomplete'].includes(s) ? s : 'running', at(event));
    }
  }
  return phases;
}

/** "plan checked 0 s · submitted 0 s · running 4 s · tool requested 11 s" */
export function phaseLine(events: readonly DoorAgentProgressEvent[]): string {
  return agentPhases(events).map(phase => `${phase.label} ${Math.round(phase.atMs / 1000)} s`).join(' · ');
}

export function formatStates(states: DoorStateMap | null | undefined): string {
  const entries = Object.entries(states ?? {}).sort(([a], [b]) => a.localeCompare(b));
  return entries.length ? entries.map(([door, state]) => `${door} ${state}`).join(' · ') : 'no controllable doors';
}

export function toolLine(call: DoorAgentToolCall): string {
  const known = call.function_name === 'plan_doors' || call.function_name === 'compare_door_states';
  const args = known && call.function_name === 'compare_door_states'
    ? ` (${Object.entries(call.arguments).map(([door, state]) => `${door} ${String(state)}`).join(', ').slice(0, 48)})` : '';
  return `${known ? call.function_name : 'rejected tool request'}${args} · ${Math.max(0, Math.round(call.execution_time_ms))} ms${call.status === 'executed' ? '' : ` · ${call.status}`}`;
}

export interface ResultView {
  tone: 'agree' | 'differ' | 'local' | 'failed' | 'note';
  chip: string;
  /** Agent text, attributed; empty when the run produced none. */
  explanation: string;
  attribution: string;
  decided: string;
  agreement: string;
  tools: string[];
  disclaimer: string;
}

export function resultView(result: DoorAgentResult): ResultView {
  const done = result.status === 'completed';
  const population = result.initial_population ?? 125;
  const unchecked = result.checked_best_is_valid === false;
  const decided = unchecked ? NO_CHECKED_BEST : result.checked_best_completed == null ? '' : `Checker decided: ${formatStates(result.checked_best_door_states)} · ${result.checked_best_completed} of ${population}`;
  const chip = result.provenance === 'local' ? LOCAL_LABEL : result.provenance === 'live' ? `${LIVE_LABEL}${result.provider_model ? ` · ${result.provider_model}` : ''}` : 'Unavailable';
  const tone: ResultView['tone'] = !done ? 'failed' : unchecked ? 'note' : result.provenance === 'local' ? 'local' : result.agrees_with_checker ? 'agree' : result.recommended_door_states ? 'differ' : 'note';
  return {
    tone, chip, decided,
    explanation: done ? result.explanation : '',
    attribution: !done ? '' : result.provenance === 'live' ? `Agent (${result.provider_model ?? 'Gemini'}) said` : 'Local solver summary',
    agreement: done && !unchecked ? result.agreement_note : '',
    tools: result.tool_ledger.map(toolLine),
    disclaimer: 'Modeled crossings, not a survival prediction. Doors in the twin are simulated.',
  };
}

export const hazardKey = (hazards: readonly HazardInput[]): string => JSON.stringify(hazards);

interface Options {
  start: (hazards: HazardInput[], mode: DoorAgentMode, signal: AbortSignal) => Promise<string>;
  poll: (id: string, signal: AbortSignal) => Promise<DoorAgentProgress>;
  cancel: (id: string) => Promise<unknown>;
  onState: (state: DoorAgentState) => void;
  isDone: (status: string) => boolean;
  describeFailure: (errors: readonly string[]) => string;
  now?: () => number;
  intervalMs?: number;
  deadlineMs?: number;
  sleep?: (ms: number, signal: AbortSignal) => Promise<void>;
}

const abortableSleep = (ms: number, signal: AbortSignal) => new Promise<void>(resolve => {
  const timer = setTimeout(done, ms);
  function done() { clearTimeout(timer); signal.removeEventListener('abort', done); resolve(); }
  signal.addEventListener('abort', done);
});

/**
 * One agent run at a time. A request gate refuses a second Ask; the workflow epoch drops every result of a run that
 * was cancelled or reset (new hazards, mode switch, Next judge), including a late poll or start response.
 */
export function createDoorAgentFlow({ start, poll, cancel, onState, isDone, describeFailure, now = Date.now, intervalMs = POLL_INTERVAL_MS, deadlineMs = CLIENT_DEADLINE_MS, sleep = abortableSleep }: Options) {
  const gate = createRequestGate();
  const epoch = createWorkflowEpoch();
  let controller: AbortController | null = null;
  let activeId: string | null = null;
  let state = idleAgent();
  const publish = (next: DoorAgentState) => { state = next; onState(next); };

  const stop = () => { controller?.abort(); controller = null; };
  const release = (id: string | null) => { if (id) void cancel(id).catch(() => undefined); };

  async function run(hazards: HazardInput[], mode: DoorAgentMode, token: number, started: number) {
    controller = new AbortController();
    const { signal } = controller;
    const current = () => !signal.aborted && gate.isCurrent(token) && epoch.isCurrent(started);
    const began = now();
    publish({ ...idleAgent(), status: 'running', mode, startedAt: began });
    let failures = 0;
    try {
      const id = await start(hazards, mode, signal);
      if (!current()) { release(id); return; }
      activeId = id;
      publish({ ...state, investigationId: id });
      while (current()) {
        if (now() - began > deadlineMs) {
          release(id);
          publish({ ...state, status: 'failed', error: 'The agent did not finish in time. The checker\'s plan above still stands.' });
          return;
        }
        try {
          const progress = await poll(id, signal);
          failures = 0;
          if (!current()) return;
          if (progress.investigation && isDone(progress.status)) {
            const result = progress.investigation;
            publish({ ...state, status: result.status === 'completed' ? 'finished' : 'failed', events: progress.provider_progress, result,
              error: result.status === 'completed' ? null : describeFailure(result.errors) });
            return;
          }
          publish({ ...state, events: progress.provider_progress });
        } catch (error) {
          if (!current()) return;
          if (++failures >= MAX_POLL_FAILURES) throw error;
        }
        await sleep(intervalMs, signal);
      }
    } catch (error) {
      if (!current()) return;
      publish({ ...state, status: 'failed', error: error instanceof Error ? error.message : 'The agent could not be reached.' });
    } finally {
      if (gate.isCurrent(token)) gate.finish(token);
    }
  }

  return {
    state: () => state,
    /** Returns false when a run is already active (the gate refuses a second Ask). */
    ask(hazards: HazardInput[], mode: DoorAgentMode): boolean {
      const token = gate.start();
      if (token === null) return false;
      activeId = null;
      void run(hazards, mode, token, epoch.current());
      return true;
    },
    /** The presenter pressed Cancel: stop polling, ask the backend to cancel, show idle. */
    cancel() {
      const id = activeId;
      activeId = null;
      epoch.bump(); gate.invalidate(); stop();
      release(id);
      publish(idleAgent());
    },
    /** New hazard set, mode switch or Next judge: same as cancel, but silent when nothing was running. */
    reset() {
      const wasActive = state.status !== 'idle';
      const id = state.status === 'running' ? activeId : null;
      activeId = null;
      epoch.bump(); gate.invalidate(); stop();
      release(id);
      if (wasActive) publish(idleAgent());
    },
  };
}
