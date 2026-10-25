// WebGL capability probe and motion preference. Decision logic is pure so tests can inject fakes.

export interface ProbeCanvas {
  getContext(kind: string): unknown;
}

/** Gives the probe context back to the browser so repeated probes cannot exhaust its limited WebGL contexts. */
function release(context: unknown): void {
  try {
    const lose = (context as { getExtension?: (name: string) => { loseContext?: () => void } | null }).getExtension?.('WEBGL_lose_context');
    lose?.loseContext?.();
  } catch {
    // a context that cannot be released is left to the garbage collector
  }
}

/** Pure: true when a canvas yields a webgl2 or webgl context, which is released straight away. Never throws. */
export function probeWebGL(createCanvas: () => ProbeCanvas): boolean {
  try {
    const canvas = createCanvas();
    for (const kind of ['webgl2', 'webgl']) {
      const context = canvas.getContext(kind);
      if (context) { release(context); return true; }
    }
  } catch {
    // fall through: any failure means no usable WebGL
  }
  return false;
}

/** The probe runs once; every later call returns the first answer. */
export function memoizeProbe(probe: () => boolean): () => boolean {
  let answer: boolean | null = null;
  return () => answer ?? (answer = probe());
}

const probeOnce = memoizeProbe(() => probeWebGL(() => document.createElement('canvas')));

export function canUseWebGL(): boolean {
  if (typeof document === 'undefined') return false;
  return probeOnce();
}

/** Pure: reads a matchMedia-like function. */
export function readReducedMotion(matchMedia: ((query: string) => { matches: boolean }) | undefined): boolean {
  try {
    return Boolean(matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  } catch {
    return false;
  }
}

export function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return readReducedMotion(window.matchMedia?.bind(window));
}
