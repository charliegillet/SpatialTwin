import type { HazardClosureEvent, HazardSimulateResponse } from '../types.ts';
import type { HazardResultView } from '../features/hazard-exposure/hazard.ts';

export const hazardElements = ['portal:P1', 'portal:P2', 'boundary:B2'] as const;

/** Simulation horizon of the default venue graph (backend/app/planner/model.py default_horizon_seconds). */
export const HAZARD_HORIZON_SECONDS = 40;

/** UI target ids (portal:P1, boundary:B2) map to the venue ids the backend accepts (P1, B2). */
export function venueElementId(targetId: string): string {
  return targetId.replace(/^(portal|boundary):/, '');
}

/** Drop incomplete rows, keep the first row per element, and cap at the 6 events the server accepts. */
export function cleanHazardEvents(rows: readonly { element_id: string; close_at_s: string }[]): HazardClosureEvent[] {
  const seen = new Set<string>();
  const events: HazardClosureEvent[] = [];
  for (const row of rows) {
    const seconds = Number(row.close_at_s);
    const elementId = venueElementId(row.element_id);
    if (row.close_at_s.trim() === '' || !Number.isInteger(seconds) || seconds < 0 || seconds >= HAZARD_HORIZON_SECONDS || seen.has(elementId)) continue;
    seen.add(elementId);
    events.push({ element_id: elementId, close_at_s: seconds });
  }
  return events.slice(0, 6);
}

/** One simulate response per alternative becomes one table. The checker verdict is passed only if every response is valid. */
export function toHazardView(events: HazardClosureEvent[], responses: readonly HazardSimulateResponse[]): HazardResultView {
  const valid = responses.length > 0 && responses.every(response => response.is_valid);
  return {
    scenario_label: 'Forecast closures · facility-demo',
    events: events.map(event => ({ ...event })),
    alternatives: responses.map(response => ({
      alternative_id: response.alternative_id,
      completed_crossings: response.completed_crossings,
      exposure_people_seconds: response.modeled_exposure_people_seconds,
    })),
    check: { status: valid ? 'passed' : 'failed', reasons: responses.flatMap(response => response.reasons) },
  };
}
