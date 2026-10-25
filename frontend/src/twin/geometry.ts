import type { Point2, VenueV2, VenueZone } from './types.ts';

/** Metres from a wall inside which a drop is refused ("Drop inside a room"). */
export const WALL_MARGIN_M = 0.4;

export type ZoneHit =
  | { ok: true; zone_id: string }
  | { ok: false; reason: 'outside' | 'on_wall' | 'in_doorway' };

export const DROP_REFUSED: Record<'outside' | 'on_wall' | 'in_doorway', string> = {
  outside: 'Drop inside a room',
  on_wall: 'Drop inside a room, away from the wall',
  in_doorway: 'Drop inside a room, not in a doorway',
};

/** Even-odd ray cast; points exactly on an edge count as inside. */
export function pointInPolygon(x: number, y: number, polygon: Point2[]): boolean {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    if (distanceToSegment(x, y, xi, yi, xj, yj) < 1e-9) return true;
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

export function distanceToSegment(px: number, py: number, ax: number, ay: number, bx: number, by: number): number {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSq = dx * dx + dy * dy;
  const t = lengthSq === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/** Area-weighted centroid of a simple polygon (falls back to the vertex mean when degenerate). */
export function polygonCentroid(polygon: Point2[]): Point2 {
  let area = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i];
    const [xj, yj] = polygon[j];
    const cross = xj * yi - xi * yj;
    area += cross;
    cx += (xj + xi) * cross;
    cy += (yj + yi) * cross;
  }
  if (Math.abs(area) < 1e-9) {
    const n = polygon.length || 1;
    return [polygon.reduce((s, p) => s + p[0], 0) / n, polygon.reduce((s, p) => s + p[1], 0) / n];
  }
  return [cx / (3 * area), cy / (3 * area)];
}

function edgeDistance(x: number, y: number, zone: VenueZone): number {
  let best = Infinity;
  const poly = zone.polygon;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    best = Math.min(best, distanceToSegment(x, y, poly[j][0], poly[j][1], poly[i][0], poly[i][1]));
  }
  return best;
}

/** Which room a floor point falls in. Walls, doorways and points outside the building are refused. */
export function locateZone(venue: VenueV2, point: { x: number; y: number }, margin = WALL_MARGIN_M): ZoneHit {
  const { x, y } = point;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return { ok: false, reason: 'outside' };
  for (const opening of [...venue.doors, ...venue.exits]) {
    const [dx, dy] = opening.position;
    if (Math.abs(x - dx) <= opening.width / 2 + margin && Math.abs(y - dy) <= opening.width / 2 + margin
      && Math.hypot(x - dx, y - dy) <= opening.width / 2 + margin) {
      return { ok: false, reason: 'in_doorway' };
    }
  }
  const containing = venue.zones.filter((zone) => pointInPolygon(x, y, zone.polygon));
  if (containing.length === 0) return { ok: false, reason: 'outside' };
  const zone = containing[0];
  if (containing.length > 1 || edgeDistance(x, y, zone) < margin) return { ok: false, reason: 'on_wall' };
  return { ok: true, zone_id: zone.id };
}

export function zoneById(venue: VenueV2, id: string): VenueZone | undefined {
  return venue.zones.find((zone) => zone.id === id);
}
