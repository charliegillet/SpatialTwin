export type SpatialTargetId = 'portal:P1' | 'portal:P2' | 'boundary:B2';
export interface Pan { x: number; y: number; }
export interface PanBounds { width: number; height: number; }
export interface ForecastClosure { element_id: string; close_at_s: number; }

export const PAN_STEP = 40;
export const PAN_REACH = 0.4;
export const CLICK_SLOP = 6;

const VENUE_TO_TARGET: Record<string, SpatialTargetId> = { P1: 'portal:P1', P2: 'portal:P2', B2: 'boundary:B2' };

/** Keep the floor plan partly on screen: offset is limited to a fraction of the zoomed viewBox size. */
export function clampPan(pan: Pan, zoom: number, bounds: PanBounds): Pan {
  const limitX = bounds.width * zoom * PAN_REACH;
  const limitY = bounds.height * zoom * PAN_REACH;
  const fit = (value: number, limit: number) => (Number.isFinite(value) ? Math.max(-limit, Math.min(limit, value)) : 0);
  return { x: fit(pan.x, limitX), y: fit(pan.y, limitY) };
}

/** A press becomes a drag only once it moves past the click slop, in screen pixels. */
export function isDrag(down: Pan, current: Pan, slop: number = CLICK_SLOP): boolean {
  return Math.hypot(current.x - down.x, current.y - down.y) > slop;
}

/** Arrow keys move the model in the key's direction; any other key returns null. */
export function panByKey(key: string, step: number = PAN_STEP): Pan | null {
  switch (key) {
    case 'ArrowLeft': return { x: -step, y: 0 };
    case 'ArrowRight': return { x: step, y: 0 };
    case 'ArrowUp': return { x: 0, y: -step };
    case 'ArrowDown': return { x: 0, y: step };
    default: return null;
  }
}

export function formatForecastClosure(seconds: number): string {
  return `forecast closes at ${seconds}s`;
}

/** Map venue ids (P1, P2, B2) to model targets; unknown ids and invalid times are dropped, first event per target wins. */
export function forecastTargets(events: readonly ForecastClosure[] | null | undefined): { target: SpatialTargetId; close_at_s: number }[] {
  const seen = new Set<SpatialTargetId>();
  const result: { target: SpatialTargetId; close_at_s: number }[] = [];
  for (const event of events ?? []) {
    const target = Object.prototype.hasOwnProperty.call(VENUE_TO_TARGET, event.element_id) ? VENUE_TO_TARGET[event.element_id] : undefined;
    if (!target || seen.has(target)) continue;
    if (typeof event.close_at_s !== 'number' || !Number.isFinite(event.close_at_s) || event.close_at_s < 0) continue;
    seen.add(target);
    result.push({ target, close_at_s: event.close_at_s });
  }
  return result;
}
