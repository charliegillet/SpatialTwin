import { createWorkflowEpoch } from '../ai/workflowEpoch.ts';
import type { HazardInput } from './types.ts';

export const DOOR_PLAN_DEBOUNCE_MS = 250;

export interface FlowState<R> {
  status: 'idle' | 'pending' | 'ready' | 'error';
  /** The last accepted response; kept while the next one is pending so the scene does not blank. */
  plan: R | null;
  error: string | null;
  /** Wall-clock milliseconds of the last accepted round trip. */
  roundTripMs: number | null;
}

interface Options<R> {
  fetchPlan: (hazards: HazardInput[], signal: AbortSignal) => Promise<R>;
  onState: (state: FlowState<R>) => void;
  /** Called once per accepted response, never for a dropped one. */
  onPlan?: (plan: R, hazards: HazardInput[], roundTripMs: number) => void;
  debounceMs?: number;
  describeError?: (error: unknown) => string;
}

export const idleFlow = <R>(): FlowState<R> => ({ status: 'idle', plan: null, error: null, roundTripMs: null });

/**
 * Debounced door-plan requests. A newer request aborts the older one; a response that began before a
 * reset, or that is no longer the latest request, is dropped before it touches state.
 */
export function createTwinFlow<R>({ fetchPlan, onState, onPlan, debounceMs = DOOR_PLAN_DEBOUNCE_MS, describeError }: Options<R>) {
  const epoch = createWorkflowEpoch();
  let sequence = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | null = null;
  let state: FlowState<R> = idleFlow<R>();
  const publish = (next: FlowState<R>) => { state = next; onState(next); };

  const cancel = () => {
    clearTimeout(timer);
    timer = undefined;
    controller?.abort();
    controller = null;
  };

  const run = async (hazards: HazardInput[], request: number, started: number) => {
    controller = new AbortController();
    const signal = controller.signal;
    const began = Date.now();
    try {
      const plan = await fetchPlan(hazards, signal);
      if (signal.aborted || request !== sequence || !epoch.isCurrent(started)) return;
      const roundTripMs = Date.now() - began;
      publish({ status: 'ready', plan, error: null, roundTripMs });
      onPlan?.(plan, hazards, roundTripMs);
    } catch (error) {
      if (signal.aborted || request !== sequence || !epoch.isCurrent(started)) return;
      publish({ ...state, status: 'error', error: describeError ? describeError(error) : error instanceof Error ? error.message : 'The door plan could not be calculated.' });
    }
  };

  return {
    state: () => state,
    /** Schedules a plan for these hazards (an empty list is the no-hazard baseline). `immediate` skips the debounce. */
    request(hazards: HazardInput[], { immediate = false }: { immediate?: boolean } = {}) {
      cancel();
      const request = ++sequence;
      const started = epoch.current();
      publish({ ...state, status: 'pending', error: null });
      if (immediate) { void run(hazards, request, started); return; }
      timer = setTimeout(() => { timer = undefined; void run(hazards, request, started); }, debounceMs);
    },
    /** Mode switch or Next judge: abort, drop anything in flight and forget the plan. */
    reset() {
      epoch.bump();
      sequence += 1;
      cancel();
      publish(idleFlow<R>());
    },
  };
}
