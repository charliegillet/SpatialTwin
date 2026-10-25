export interface HeroInput {
  connected: boolean;
  physicalUncertain: boolean;
  /** The plan matches the current context and passed the checker. */
  planCurrent: boolean;
  completed?: number | null;
  population?: number | null;
  horizon?: number | null;
  /** The last different result shown before this one. */
  previous?: number | null;
}

export interface Hero {
  ready: boolean;
  digits: string;
  label: string;
  delta: { text: string; tone: 'gain' | 'loss'; versus: number } | null;
  reason: string | null;
  /** Full sentence for assistive technology. */
  spoken: string;
}

const MINUS = '−';

export function deltaText(delta: number): string {
  return `${delta > 0 ? '+' : MINUS}${Math.abs(delta)}`;
}

/** The hero number: a checked count, or a dash and one short reason. Never wording about people still inside. */
export function heroView(input: HeroInput): Hero {
  const counts = [input.completed, input.population, input.horizon];
  const known = counts.every(value => typeof value === 'number' && Number.isFinite(value));
  if (!input.connected) return notReady('Reconnect to the backend to see the result.');
  if (input.physicalUncertain) return notReady('P3 is moving. Waiting for the endpoint.');
  if (!input.planCurrent || !known) return notReady('Not checked yet. Re-solving.');
  const completed = input.completed as number;
  const label = `of ${input.population} reach an exit in ${input.horizon} s`;
  const previous = input.previous;
  const delta = typeof previous === 'number' && Number.isFinite(previous) && previous !== completed
    ? { text: deltaText(completed - previous), tone: completed > previous ? 'gain' as const : 'loss' as const, versus: previous } : null;
  return { ready: true, digits: String(completed), label, delta, reason: null, spoken: `${completed} ${label}${delta ? `, ${delta.text} versus ${previous}` : ''}` };
}

function notReady(reason: string): Hero {
  return { ready: false, digits: '—', label: 'of 120 reach an exit in 40 s', delta: null, reason, spoken: `No checked result. ${reason}` };
}

export interface ResultMemory { current: number | null; previous: number | null; }

/** Remembers the last different checked count so the delta chip can compare against it. */
export function nextResultMemory(memory: ResultMemory, count: number | null): ResultMemory {
  if (count === null || count === memory.current) return memory;
  return { current: count, previous: memory.current };
}
