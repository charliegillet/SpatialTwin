import type { HazardClosureEvent } from '../types.ts';

export type HazardTool = 'fire' | 'smoke' | 'clear';
export type HazardTargetId = 'portal:P1' | 'portal:P2' | 'boundary:B2';

export const HAZARD_TARGETS: readonly HazardTargetId[] = ['portal:P1', 'portal:P2', 'boundary:B2'];
export const HAZARD_REJECT = 'Hazards can only be placed on P1, P2 or B2';
export const ANALYSIS_RUNNING = 'Analysis running — wait or cancel';
export const EVEN_SECONDS_MESSAGE = 'Use an even number of seconds';

export const FIRE_HINT = 'Closed from 0 s \u00b7 can be approved';
export const smokeHint = (seconds: number) => `Closed from ${seconds} s \u00b7 forecast, never approved`;

export const SMOKE_MIN = 0;
export const SMOKE_MAX = 38;
export const SMOKE_DEFAULT = 12;

export type Placement = { ok: true; target: HazardTargetId } | { ok: false; message: string };

/** Only the three hotspots take a hazard; anything else, or no target at all, is rejected with one fixed message. */
export function placementOutcome(targetId: string | null | undefined): Placement {
  return HAZARD_TARGETS.includes(targetId as HazardTargetId) ? { ok: true, target: targetId as HazardTargetId } : { ok: false, message: HAZARD_REJECT };
}

export function isValidSmokeSeconds(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) && value % 2 === 0 && value >= SMOKE_MIN && value <= SMOKE_MAX;
}

/** Steps by two seconds and stays on an even value inside 0-38, even if the starting value was off. */
export function stepSmokeSeconds(current: number, direction: 1 | -1): number {
  const base = Number.isFinite(current) ? Math.round(current) : SMOKE_DEFAULT;
  const even = base % 2 === 0 ? base : base - 1;
  return Math.max(SMOKE_MIN, Math.min(SMOKE_MAX, even + direction * 2));
}

export const venueId = (target: HazardTargetId) => target.split(':')[1];

/** One closure event per smoke hotspot, in a stable order, for POST /api/hazard/simulate. */
export function smokeEvents(smoke: Readonly<Partial<Record<HazardTargetId, number>>>): HazardClosureEvent[] {
  return HAZARD_TARGETS.filter(target => isValidSmokeSeconds(smoke[target])).map(target => ({ element_id: venueId(target), close_at_s: smoke[target] as number }));
}

export function smokeLabel(events: readonly HazardClosureEvent[]): string {
  return `smoke closes ${events.map(event => `${event.element_id} at ${event.close_at_s} s`).join(' and ')}`;
}

/** The one-line forecast. Equal counts get plain wording instead of a false drop. */
export function forecastLine(input: { events: readonly HazardClosureEvent[]; forecast: number; current: number | null; population: number }): string {
  const lead = `If ${smokeLabel(input.events)}`;
  if (input.current !== null && input.forecast === input.current) {
    const pad = input.events.length === 1 ? input.events[0].element_id : 'those pads';
    return `${lead}: no change \u00b7 in the model everyone has passed ${pad} by then`;
  }
  return `${lead}: ${input.forecast} of ${input.population} reach an exit${input.current === null ? '' : ` (now ${input.current})`}`;
}

/** Dashed second line under the hero number. */
export function heroForecastLine(events: readonly HazardClosureEvent[], forecast: number): string {
  return `Forecast \u00b7 ${forecast} if ${smokeLabel(events)}`;
}

/** Exit flow of a forecast: the count per boundary, or null when the backend did not send it. */
export function forecastBreakdown(value: unknown): Record<string, number> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const entries = Object.entries(value as Record<string, unknown>).filter(([, count]) => typeof count === 'number' && Number.isFinite(count));
  return entries.length ? Object.fromEntries(entries) as Record<string, number> : null;
}

/** Plain text for a failed simulate call. */
export function hazardErrorMessage(status: number, code: string): string {
  if (status === 422 && code === 'invalid_close_time') return EVEN_SECONDS_MESSAGE;
  if (status === 422) return `The hazard schedule was rejected (${(code || 'invalid_request').replace(/_/g, ' ')}).`;
  return '';
}
