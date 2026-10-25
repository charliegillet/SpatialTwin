import { DROP_REFUSED, locateZone, polygonCentroid, zoneById } from './geometry.ts';
import { HAZARD_INFO } from './hazardModel.ts';
import type { HazardInput, HazardType, PlacedHazard, VenueV2 } from './types.ts';

export const MAX_HAZARDS = 6;
export const TOO_MANY_HAZARDS = 'Up to 6 hazards';

/** Hazards on the floor plus an undo stack. Ids come from a counter that never goes back, so they stay stable. */
export interface PlacementState {
  hazards: PlacedHazard[];
  history: PlacedHazard[][];
  seq: number;
}

export const emptyPlacement = (): PlacementState => ({ hazards: [], history: [], seq: 0 });

export type PlaceResult =
  | { ok: true; state: PlacementState; hazard: PlacedHazard }
  | { ok: false; message: string };

const commit = (state: PlacementState, hazards: PlacedHazard[], seq = state.seq): PlacementState =>
  ({ hazards, history: [...state.history, state.hazards], seq });

/** Validates the drop with locateZone, caps at 6, and allows stacking in one room (the backend decides precedence). */
export function placeHazard(state: PlacementState, venue: VenueV2, type: HazardType, point: { x: number; y: number }, smokeSeconds?: number): PlaceResult {
  if (state.hazards.length >= MAX_HAZARDS) return { ok: false, message: TOO_MANY_HAZARDS };
  const hit = locateZone(venue, point);
  if (!hit.ok) return { ok: false, message: DROP_REFUSED[hit.reason] };
  const seq = state.seq + 1;
  const hazard: PlacedHazard = {
    id: `h${seq}`,
    type,
    x: point.x,
    y: point.y,
    zone_id: hit.zone_id,
    untenable_s: type === 'SMOKE' ? (smokeSeconds ?? HAZARD_INFO.SMOKE.untenable_s) : null,
    source: 'simulated',
  };
  return { ok: true, state: commit(state, [...state.hazards, hazard], seq), hazard };
}

/** Keyboard route: the hazard goes to the room's centroid. */
export function zoneDropPoint(venue: VenueV2, zoneId: string): { x: number; y: number } | null {
  const zone = zoneById(venue, zoneId);
  if (!zone) return null;
  const [x, y] = polygonCentroid(zone.polygon);
  return { x, y };
}

/** Confirmed camera hazards join the floor unchanged; anything past the cap of six is left out and counted. */
export function addCameraHazards(state: PlacementState, incoming: readonly PlacedHazard[]): { state: PlacementState; added: number; skipped: number } {
  const room = Math.max(0, MAX_HAZARDS - state.hazards.length);
  const fresh = incoming.filter(item => !state.hazards.some(existing => existing.id === item.id)).slice(0, room);
  if (!fresh.length) return { state, added: 0, skipped: incoming.length };
  return { state: commit(state, [...state.hazards, ...fresh]), added: fresh.length, skipped: incoming.length - fresh.length };
}

export function removeHazard(state: PlacementState, id: string): PlacementState {
  return state.hazards.some(item => item.id === id) ? commit(state, state.hazards.filter(item => item.id !== id)) : state;
}

export function setSmokeSeconds(state: PlacementState, id: string, seconds: number): PlacementState {
  const target = state.hazards.find(item => item.id === id);
  if (!target || target.type !== 'SMOKE' || target.source === 'camera' || target.untenable_s === seconds) return state;
  return commit(state, state.hazards.map(item => item.id === id ? { ...item, untenable_s: seconds } : item));
}

export function clearHazards(state: PlacementState): PlacementState {
  return state.hazards.length ? commit(state, []) : state;
}

export function undoPlacement(state: PlacementState): PlacementState {
  if (!state.history.length) return state;
  return { hazards: state.history[state.history.length - 1], history: state.history.slice(0, -1), seq: state.seq };
}

export function toHazardInputs(hazards: readonly PlacedHazard[]): HazardInput[] {
  return hazards.map(item => {
    const input: HazardInput = { id: item.id, type: item.type, position: { x: item.x, y: item.y }, zone_id: item.zone_id, source: item.source };
    // A camera hazard's time comes from the backend; a client-set untenable_s is rejected (camera_hazard_mismatch).
    if (item.source !== 'camera') input.untenable_s = item.type === 'SMOKE' ? item.untenable_s : null;
    input.proposal_id = item.proposal_id ?? null;
    return input;
  });
}
