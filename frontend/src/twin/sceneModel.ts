// Pure scene model: venue + plan + hazards -> render data. No three.js, no React.
import { HAZARD_COLOR, LAMP_COLOR, PALETTE, ZONE_TINT } from '../scene/palette.ts';
import { polygonCentroid } from './geometry.ts';
import type {
  DoorLamp, DoorPlanResponse, ExitLamp, HazardType, PlacedHazard, Point2, VenueV2, ZoneStatus,
} from './types.ts';

const EPS = 1e-6;

export interface WallSegment {
  a: Point2;
  b: Point2;
  /** True when only one room borders this piece (outer wall). */
  exterior: boolean;
}

interface Opening {
  position: Point2;
  width: number;
}

function key(n: number): string {
  return n.toFixed(4);
}

/** An exit stair inside its room (an upper floor's stair core): the way down, not a gap in any wall. */
export function isInteriorStair(exit: VenueV2['exits'][number]): boolean {
  return exit.kind === 'stair';
}

/** Axis-aligned edges are split at every vertex on their line, deduped, and cut at openings. */
export function buildWalls(venue: VenueV2): WallSegment[] {
  const openings: Opening[] = [...venue.doors, ...venue.exits.filter((exit) => !isInteriorStair(exit))];
  // line id -> breakpoints and interval usage counts
  const lines = new Map<string, { axis: 'x' | 'y'; at: number; stops: Set<number>; edges: [number, number][] }>();
  const slanted = new Map<string, WallSegment>();

  for (const zone of venue.zones) {
    const poly = zone.polygon;
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i];
      const q = poly[(i + 1) % poly.length];
      const horizontal = Math.abs(p[1] - q[1]) < EPS;
      const vertical = Math.abs(p[0] - q[0]) < EPS;
      if (horizontal || vertical) {
        const axis = horizontal ? 'x' : 'y'; // coordinate that varies along the wall
        const at = horizontal ? p[1] : p[0];
        const lo = Math.min(horizontal ? p[0] : p[1], horizontal ? q[0] : q[1]);
        const hi = Math.max(horizontal ? p[0] : p[1], horizontal ? q[0] : q[1]);
        const id = `${axis}:${key(at)}`;
        const line = lines.get(id) ?? { axis, at, stops: new Set<number>(), edges: [] };
        line.stops.add(lo);
        line.stops.add(hi);
        line.edges.push([lo, hi]);
        lines.set(id, line);
      } else {
        const [a, b] = key(p[0]) + key(p[1]) < key(q[0]) + key(q[1]) ? [p, q] : [q, p];
        const id = `${a}|${b}`;
        const prior = slanted.get(id);
        slanted.set(id, { a, b, exterior: !prior });
        if (prior) slanted.set(id, { a, b, exterior: false });
      }
    }
  }

  const walls: WallSegment[] = [];
  for (const line of lines.values()) {
    const stops = [...line.stops].sort((x, y) => x - y);
    for (let i = 0; i + 1 < stops.length; i++) {
      const lo = stops[i];
      const hi = stops[i + 1];
      const mid = (lo + hi) / 2;
      const count = line.edges.filter(([a, b]) => a - EPS <= mid && mid <= b + EPS).length;
      if (count === 0) continue;
      const exterior = count === 1;
      // cut gaps where an opening sits on this line
      let pieces: [number, number][] = [[lo, hi]];
      for (const o of openings) {
        const along = line.axis === 'x' ? o.position[0] : o.position[1];
        const across = line.axis === 'x' ? o.position[1] : o.position[0];
        if (Math.abs(across - line.at) > EPS) continue;
        const g0 = along - o.width / 2;
        const g1 = along + o.width / 2;
        pieces = pieces.flatMap(([a, b]) => {
          if (g1 <= a + EPS || g0 >= b - EPS) return [[a, b] as [number, number]];
          const out: [number, number][] = [];
          if (g0 > a + EPS) out.push([a, g0]);
          if (g1 < b - EPS) out.push([g1, b]);
          return out;
        });
      }
      for (const [a, b] of pieces) {
        if (b - a < 1e-3) continue;
        walls.push(
          line.axis === 'x'
            ? { a: [a, line.at], b: [b, line.at], exterior }
            : { a: [line.at, a], b: [line.at, b], exterior },
        );
      }
    }
  }
  return [...walls, ...slanted.values()];
}

/** Direction the wall runs at a point: 'x' = along east-west (horizontal wall), 'y' = along north-south. */
export function wallAxisAt(venue: VenueV2, position: Point2): 'x' | 'y' {
  for (const zone of venue.zones) {
    const poly = zone.polygon;
    for (let i = 0; i < poly.length; i++) {
      const p = poly[i];
      const q = poly[(i + 1) % poly.length];
      if (Math.abs(p[1] - q[1]) < EPS && Math.abs(position[1] - p[1]) < EPS
        && position[0] >= Math.min(p[0], q[0]) - EPS && position[0] <= Math.max(p[0], q[0]) + EPS) return 'x';
      if (Math.abs(p[0] - q[0]) < EPS && Math.abs(position[0] - p[0]) < EPS
        && position[1] >= Math.min(p[1], q[1]) - EPS && position[1] <= Math.max(p[1], q[1]) + EPS) return 'y';
    }
  }
  return 'x';
}

export interface DoorRender {
  id: string;
  label: string;
  position: Point2;
  width: number;
  axis: 'x' | 'y';
  open: boolean;
  lamp: DoorLamp;
  color: string;
  flashing: boolean;
  locked: boolean;
  simulated: boolean;
  /** Doorways without a leaf (kind 'opening') are always passable. */
  hasLeaf: boolean;
  /** Which side of the wall the leaf swings toward: +1 / -1 along the wall normal. */
  swing: 1 | -1;
}

export function doorRenders(venue: VenueV2, plan: DoorPlanResponse | null): DoorRender[] {
  return venue.doors.map((door) => {
    const decided = plan?.doors.find((d) => d.id === door.id);
    const lamp: DoorLamp = decided?.lamp ?? 'off';
    const simulated = door.actuation === 'simulated_servo';
    return {
      id: door.id,
      label: simulated ? `${door.id} · simulated` : door.id,
      position: door.position,
      width: door.width,
      axis: wallAxisAt(venue, door.position),
      open: decided ? decided.state === 'open' : door.default_state === 'open',
      lamp,
      color: LAMP_COLOR[lamp],
      flashing: false,
      locked: Boolean(decided?.locked),
      simulated,
      hasLeaf: door.kind !== 'opening',
      swing: door.id.length % 2 === 0 ? 1 : -1,
    };
  });
}

export interface ExitRender {
  id: string;
  label: string;
  position: Point2;
  width: number;
  axis: 'x' | 'y';
  /** Unit vector pointing out of the building. An interior stair has no outside wall: it faces the way people walk
   * onto it, from the side of its room with the most floor (+y on a tie). */
  outward: Point2;
  /** An exit stair inside its room: drawn as a floor marker at its position, with no wall gap. */
  interior: boolean;
  /** Free floor (m) behind an interior stair along -outward, for its lead-in chevrons; Infinity for a wall exit. */
  approach: number;
  kind: 'safe' | 'unsafe' | 'idle';
  lamp: ExitLamp | null;
  color: string;
  /** Flash a few cycles after a state change; never for red_static. */
  flashes: boolean;
}

/** Distance from `p` along the axis direction `d` to the first wall of a rectilinear polygon (Infinity if none). */
export function rayToWall(polygon: Point2[], p: Point2, d: Point2): number {
  let best = Infinity;
  for (let i = 0; i < polygon.length; i++) {
    const a = polygon[i];
    const b = polygon[(i + 1) % polygon.length];
    if (d[0] !== 0 && Math.abs(a[0] - b[0]) < EPS
      && p[1] >= Math.min(a[1], b[1]) - EPS && p[1] <= Math.max(a[1], b[1]) + EPS) {
      const t = (a[0] - p[0]) * d[0];
      if (t > EPS) best = Math.min(best, t);
    } else if (d[1] !== 0 && Math.abs(a[1] - b[1]) < EPS
      && p[0] >= Math.min(a[0], b[0]) - EPS && p[0] <= Math.max(a[0], b[0]) + EPS) {
      const t = (a[1] - p[1]) * d[1];
      if (t > EPS) best = Math.min(best, t);
    }
  }
  return best;
}

const FACINGS: Point2[] = [[0, 1], [0, -1], [1, 0], [-1, 0]];

export function exitRenders(venue: VenueV2, plan: DoorPlanResponse | null): ExitRender[] {
  return venue.exits.map((exit) => {
    const interior = isInteriorStair(exit);
    const zone = venue.zones.find((z) => z.id === exit.zone);
    let outward: Point2;
    let axis: 'x' | 'y';
    let approach = Infinity;
    if (interior) {
      // On no wall (wallAxisAt would only find a nearby edge): face the way in with the longest run of floor.
      outward = [0, 1];
      approach = zone ? rayToWall(zone.polygon, exit.position, [0, -1]) : Infinity;
      for (const d of FACINGS.slice(1)) {
        const behind = zone ? rayToWall(zone.polygon, exit.position, [-d[0], -d[1]]) : -Infinity;
        if (behind > approach + EPS) [outward, approach] = [d, behind];
      }
      axis = outward[0] === 0 ? 'x' : 'y';
    } else {
      axis = wallAxisAt(venue, exit.position);
      const centre = zone ? polygonCentroid(zone.polygon) : exit.position;
      const sign = (axis === 'x' ? exit.position[1] - centre[1] : exit.position[0] - centre[0]) >= 0 ? 1 : -1;
      outward = axis === 'x' ? [0, sign] : [sign, 0];
    }
    const decided = plan?.exits.find((e) => e.id === exit.id);
    const lamp = decided?.lamp ?? null;
    const kind: ExitRender['kind'] = !decided ? 'idle' : decided.safe ? 'safe' : 'unsafe';
    return {
      id: exit.id,
      label: exit.id,
      position: exit.position,
      width: exit.width,
      axis,
      outward,
      interior,
      approach,
      kind,
      lamp,
      color: kind === 'safe' ? PALETTE.safe : kind === 'unsafe' ? PALETTE.hazard : PALETTE.lampOff,
      flashes: lamp === 'green_flash',
    };
  });
}

export interface RouteRender {
  key: string;
  origin: string;
  exitId: string;
  /** Floor points in metres: origin centroid, via doors in order, exit. */
  points: Point2[];
  people: number;
  slowed: boolean;
  /** Line width in metres, scaled by people. */
  width: number;
  color: string;
}

export function routeRenders(venue: VenueV2, plan: DoorPlanResponse | null): RouteRender[] {
  if (!plan) return [];
  const out: RouteRender[] = [];
  for (const route of plan.routes) {
    const zone = venue.zones.find((z) => z.id === route.origin);
    const exit = venue.exits.find((e) => e.id === route.exit_id);
    if (!zone || !exit) continue;
    const centroidOf = (id: string): Point2 | null => {
      const z = venue.zones.find((v) => v.id === id);
      return z ? polygonCentroid(z.polygon) : null;
    };
    const points: Point2[] = [polygonCentroid(zone.polygon)];
    // Door i joins path[i] and path[i+1]; when the path lines up, pass through each room's centre between doors.
    const aligned = route.path.length === route.via_doors.length + 1;
    route.via_doors.forEach((doorId, i) => {
      const door = venue.doors.find((d) => d.id === doorId);
      if (door) points.push(door.position);
      const next = aligned && i + 1 < route.path.length - 0 ? centroidOf(route.path[i + 1]) : null;
      if (next) points.push(next);
    });
    points.push(exit.position);
    out.push({
      key: `${route.origin}>${route.exit_id}>${route.via_doors.join('+')}#${out.length}`,
      origin: route.origin,
      exitId: route.exit_id,
      points,
      people: route.people,
      slowed: route.slowed,
      width: Math.min(1.1, 0.18 + Math.sqrt(Math.max(route.people, 0)) * 0.07),
      color: route.slowed ? PALETTE.slowed : PALETTE.safe,
    });
  }
  return out;
}

export interface ZoneRender {
  id: string;
  name: string;
  polygon: Point2[];
  centroid: Point2;
  status: ZoneStatus;
  hazardType: HazardType | null;
  tintColor: string;
  tintOpacity: number;
}

export function zoneRenders(venue: VenueV2, plan: DoorPlanResponse | null): ZoneRender[] {
  return venue.zones.map((zone) => {
    const decided = plan?.zones.find((z) => z.id === zone.id);
    const status: ZoneStatus = decided?.status ?? 'passable';
    const tint = ZONE_TINT[status];
    return {
      id: zone.id,
      name: zone.name,
      polygon: zone.polygon,
      centroid: polygonCentroid(zone.polygon),
      status,
      hazardType: decided?.hazard_type ?? null,
      tintColor: tint.color,
      tintOpacity: tint.opacity,
    };
  });
}

export interface HazardRender {
  id: string;
  type: HazardType;
  position: Point2;
  zoneId: string;
  color: string;
  selected: boolean;
  /** False when a higher-precedence hazard in the same zone decides it. */
  effective: boolean;
}

export function hazardRenders(
  plan: DoorPlanResponse | null, hazards: PlacedHazard[], selectedId: string | null,
): HazardRender[] {
  return hazards.map((h) => ({
    id: h.id,
    type: h.type,
    position: [h.x, h.y],
    zoneId: h.zone_id,
    color: HAZARD_COLOR[h.type],
    selected: h.id === selectedId,
    effective: plan?.hazards.find((e) => e.id === h.id)?.effective ?? true,
  }));
}

const HAZARD_WORD: Record<HazardType, string> = {
  FIRE: 'Fire', SMOKE: 'Smoke', GAS: 'Gas', CHEMICAL: 'Chemical spill', WATER: 'Water',
};

export function ariaSummary(venue: VenueV2, plan: DoorPlanResponse | null, hazards: PlacedHazard[]): string {
  const base = `Building twin, ${venue.zones.length} rooms, ${venue.exits.length} exits.`;
  if (hazards.length === 0) return `${base} No hazards placed.`;
  const where = hazards
    .map((h) => `${HAZARD_WORD[h.type]} in ${venue.zones.find((z) => z.id === h.zone_id)?.name ?? h.zone_id}`)
    .join(', ');
  if (!plan) return `${base} ${where}. Plan pending.`;
  const safe = plan.exits.filter((e) => e.safe).length;
  const closed = plan.doors.filter((d) => d.state === 'closed').length;
  return `${base} ${where}. ${safe} of ${plan.exits.length} exits safe, ${closed} doors closed, `
    + `${plan.chosen.completed_crossings} of ${plan.chosen.initial_population} reach an exit in the model.`;
}

export const INSTANCE_CAP = 400;
const BASE_INSTANCES: Record<HazardType, number> = { FIRE: 36, SMOKE: 28, GAS: 22, CHEMICAL: 14, WATER: 0 };

/** Particle instances per hazard, halved in low graphics and scaled so the whole scene stays within the cap. */
export function instanceBudget(types: HazardType[], lowGraphics: boolean): number[] {
  const wanted = types.map((t) => Math.round(BASE_INSTANCES[t] * (lowGraphics ? 0.5 : 1)));
  const total = wanted.reduce((s, n) => s + n, 0);
  if (total <= INSTANCE_CAP) return wanted;
  return wanted.map((n) => Math.floor((n * INSTANCE_CAP) / total));
}

/** Camera distance that frames the whole building at the given polar angle (0 = straight down). */
export function fitDistance(extent: Point2, fovDeg: number, aspect: number, polar: number): number {
  const tanHalf = Math.tan((fovDeg * Math.PI) / 360);
  const halfW = (extent[0] / 2) * 1.08;
  const halfV = (extent[1] / 2) * 1.08 * Math.cos(polar) + 1.4 * Math.sin(polar);
  const byHeight = halfV / tanHalf;
  const byWidth = halfW / (tanHalf * Math.max(aspect, 0.2));
  return Math.max(byHeight, byWidth) * 1.18;
}
