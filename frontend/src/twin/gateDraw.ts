import type { GateVisual } from './types.ts';

// A gate in transit never reaches its endpoint on screen until the endpoint switch is observed.
export const TRANSIT_CAP = 0.97;
// Unknown or faulted: frozen mid-way, so it can never be read as open or closed.
export const DOUBT_AMOUNT = 0.5;

/** How far open (0–1) a virtual gate is drawn now: from the observed endpoint, or transit time, never the plan. */
export function gateAmount(gate: GateVisual, now: number): number {
  const progress = gate.since === null ? 0 : Math.min(TRANSIT_CAP, Math.max(0, (now - gate.since) / gate.transitMs));
  switch (gate.draw) {
    case 'open': return 1;
    case 'closed': return 0;
    case 'opening': return progress;
    case 'closing': return 1 - progress;
    default: return DOUBT_AMOUNT;
  }
}
