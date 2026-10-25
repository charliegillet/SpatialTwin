import { createRequestGate } from '../ai/requestGate.ts';
import { createWorkflowEpoch } from '../ai/workflowEpoch.ts';

export interface ReadState<R> {
  phase: 'idle' | 'reading' | 'done' | 'error';
  result: R | null;
  error: string | null;
  startedAt: number | null;
}
export const idleRead = <R>(): ReadState<R> => ({ phase: 'idle', result: null, error: null, startedAt: null });

/** One camera read at a time. A response that arrives after reset or dismiss is dropped before it touches state. */
export function createReadFlow<R>({ run, onState, describeError }: {
  run: (signal: AbortSignal) => Promise<R>;
  onState: (state: ReadState<R>) => void;
  describeError?: (error: unknown) => string;
}) {
  const epoch = createWorkflowEpoch();
  const gate = createRequestGate();
  let controller: AbortController | null = null;
  let state = idleRead<R>();
  const publish = (next: ReadState<R>) => { state = next; onState(next); };
  const stop = () => { controller?.abort(); controller = null; gate.invalidate(); };

  return {
    state: () => state,
    async start(): Promise<boolean> {
      const token = gate.start();
      if (token === null) return false;
      const started = epoch.current();
      controller = new AbortController();
      const signal = controller.signal;
      publish({ phase: 'reading', result: null, error: null, startedAt: Date.now() });
      try {
        const result = await run(signal);
        if (signal.aborted || !epoch.isCurrent(started) || !gate.isCurrent(token)) return false;
        publish({ phase: 'done', result, error: null, startedAt: state.startedAt });
        return true;
      } catch (error) {
        if (signal.aborted || !epoch.isCurrent(started) || !gate.isCurrent(token)) return false;
        publish({ phase: 'error', result: null, error: describeError ? describeError(error) : error instanceof Error ? error.message : 'The camera read failed.', startedAt: state.startedAt });
        return false;
      } finally { gate.finish(token); }
    },
    /** Next judge, mode switch or Dismiss. */
    reset() {
      epoch.bump();
      stop();
      publish(idleRead<R>());
    },
  };
}
