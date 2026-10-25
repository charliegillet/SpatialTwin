import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  buildWalls, instanceBudget, fitDistance, doorRenders, exitRenders, routeRenders, zoneRenders, hazardRenders, ariaSummary, wallAxisAt,
} from './sceneModel.ts';
import { polygonCentroid } from './geometry.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));

const plan = {
  hazards: [{ id: 'h1', type: 'FIRE', zone_id: 'LOBBY', effective: true }],
  doors: venue.doors.map((d) => ({
    id: d.id, state: d.id === 'D1' ? 'closed' : 'open',
    lamp: d.id === 'D1' ? 'red' : d.id === 'D5' ? 'red_static' : 'green', locked: d.id === 'D4',
  })),
  exits: [
    { id: 'E1', safe: false, lamp: 'red_x' },
    { id: 'E2', safe: true, lamp: 'green_flash' },
    { id: 'E3', safe: true, lamp: 'green' },
    { id: 'E4', safe: false, lamp: 'red_static' },
  ],
  zones: venue.zones.map((z) => ({
    id: z.id, status: z.id === 'LOBBY' ? 'no_entry' : z.id === 'WEST_CORR' ? 'slowed' : 'passable',
    hazard_type: z.id === 'LOBBY' ? 'FIRE' : null,
  })),
  routes: [{ origin: 'HALL', path: ['HALL', 'STAIR_N'], via_doors: ['D4'], exit_id: 'E2', people: 80, slowed: false }],
  chosen: { completed_crossings: 117, initial_population: 125 },
};

const len = (w) => Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]);
const sameSeg = (w, a, b) =>
  (w.a[0] === a[0] && w.a[1] === a[1] && w.b[0] === b[0] && w.b[1] === b[1])
  || (w.b[0] === a[0] && w.b[1] === a[1] && w.a[0] === b[0] && w.a[1] === b[1]);

test('shared walls are deduped: no two pieces overlap', () => {
  const walls = buildWalls(venue);
  for (let i = 0; i < walls.length; i++) {
    for (let j = i + 1; j < walls.length; j++) {
      const a = walls[i];
      const b = walls[j];
      const horiz = a.a[1] === a.b[1] && b.a[1] === b.b[1] && a.a[1] === b.a[1];
      const vert = a.a[0] === a.b[0] && b.a[0] === b.b[0] && a.a[0] === b.a[0];
      if (!horiz && !vert) continue;
      const [a0, a1] = horiz ? [a.a[0], a.b[0]].sort((x, y) => x - y) : [a.a[1], a.b[1]].sort((x, y) => x - y);
      const [b0, b1] = horiz ? [b.a[0], b.b[0]].sort((x, y) => x - y) : [b.a[1], b.b[1]].sort((x, y) => x - y);
      assert.ok(Math.min(a1, b1) - Math.max(a0, b0) <= 1e-9, `overlap ${JSON.stringify([a, b])}`);
    }
  }
});

test('total wall length = perimeter + interior edges minus openings', () => {
  const walls = buildWalls(venue);
  const total = walls.reduce((s, w) => s + len(w), 0);
  // perimeter 2*(40+24)=128; interior: y=8 (x12-28, 32-40, 0-8 = 16+8+8), y=20 x12-28 =16,
  // x=8 y8-24=16, x=12 y0-24=24, x=28 y0-24=24, x=32 y0-24=24, y=8 on x8-12 and x28-32 corridors do not exist
  const openings = [...venue.doors, ...venue.exits].reduce((s, o) => s + o.width, 0);
  const expectedEdges = 128 + 16 + 8 + 16 + 16 + 24 + 24 + 24; // 128 includes the notch walls at x=8 y0-8 and y=8 x0-8
  assert.ok(Math.abs(total - (expectedEdges - openings)) < 1e-6, `${total} vs ${expectedEdges - openings}`);
});

test('a gap exists at every door and exit position', () => {
  const walls = buildWalls(venue);
  for (const o of [...venue.doors, ...venue.exits]) {
    const [x, y] = o.position;
    for (const w of walls) {
      const horiz = w.a[1] === w.b[1];
      if (horiz && Math.abs(w.a[1] - y) < 1e-9) {
        const lo = Math.min(w.a[0], w.b[0]);
        const hi = Math.max(w.a[0], w.b[0]);
        assert.ok(!(x > lo + 1e-9 && x < hi - 1e-9), `wall covers opening at ${o.id}`);
      }
      if (!horiz && Math.abs(w.a[0] - x) < 1e-9) {
        const lo = Math.min(w.a[1], w.b[1]);
        const hi = Math.max(w.a[1], w.b[1]);
        assert.ok(!(y > lo + 1e-9 && y < hi - 1e-9), `wall covers opening at ${o.id}`);
      }
    }
  }
});

test('outer wall is flagged exterior, shared wall is not', () => {
  const walls = buildWalls(venue);
  const south = walls.find((w) => w.a[1] === 0 && w.b[1] === 0 && Math.min(w.a[0], w.b[0]) >= 0);
  assert.equal(south.exterior, true);
  const d1Left = walls.find((w) => sameSeg(w, [12, 8], [18.5, 8]));
  assert.ok(d1Left, 'LOBBY|HALL wall piece left of D1');
  assert.equal(d1Left.exterior, false);
});

test('wall axis at doors', () => {
  assert.equal(wallAxisAt(venue, [20, 8]), 'x');
  assert.equal(wallAxisAt(venue, [12, 14]), 'y');
});

test('lamp to colour mapping and open state', () => {
  const doors = doorRenders(venue, plan);
  const by = Object.fromEntries(doors.map((d) => [d.id, d]));
  assert.equal(by.D1.color, '#ff4d4f');
  assert.equal(by.D1.open, false);
  assert.equal(by.D2.color, '#5cf28a');
  assert.equal(by.D5.color, '#ff4d4f');
  assert.equal(by.D5.flashing, false);
  assert.equal(by.D4.label, 'D4 · simulated');
  assert.equal(by.D4.locked, true);
  assert.equal(by.D2.label, 'D2');
});

test('exit render kinds, outward direction, flash rules', () => {
  const ex = Object.fromEntries(exitRenders(venue, plan).map((e) => [e.id, e]));
  assert.equal(ex.E1.kind, 'unsafe');
  assert.deepEqual(ex.E1.outward, [0, -1]);
  assert.deepEqual(ex.E2.outward, [0, 1]);
  assert.deepEqual(ex.E3.outward, [1, 0]);
  assert.deepEqual(ex.E4.outward, [-1, 0]);
  assert.equal(ex.E2.flashes, true);
  assert.equal(ex.E3.flashes, false);
  assert.equal(ex.E4.flashes, false);
  assert.equal(ex.E4.kind, 'unsafe');
});

test('route polyline starts at origin centroid, passes via-door positions, ends at exit', () => {
  const [r] = routeRenders(venue, plan);
  assert.deepEqual(r.points[0], polygonCentroid(venue.zones.find((z) => z.id === 'HALL').polygon));
  assert.deepEqual(r.points[1], [20, 20]);
  assert.deepEqual(r.points.at(-1), [20, 24]);
  assert.ok(r.width > 0.18 && r.width <= 1.1);
});

test('zone tints follow plan status', () => {
  const z = Object.fromEntries(zoneRenders(venue, plan).map((x) => [x.id, x]));
  assert.equal(z.LOBBY.tintColor, '#ff4d4f');
  assert.ok(z.LOBBY.tintOpacity > 0);
  assert.equal(z.LOBBY.hazardType, 'FIRE');
  assert.equal(z.WEST_CORR.status, 'slowed');
  assert.equal(z.HALL.tintOpacity, 0);
});

test('works with plan = null', () => {
  assert.ok(buildWalls(venue).length > 0);
  const doors = doorRenders(venue, null);
  assert.ok(doors.every((d) => d.lamp === 'off'));
  assert.equal(doors.find((d) => d.id === 'D1').open, venue.doors.find((d) => d.id === 'D1').default_state === 'open');
  assert.ok(exitRenders(venue, null).every((e) => e.kind === 'idle' && !e.flashes));
  assert.deepEqual(routeRenders(venue, null), []);
  assert.ok(zoneRenders(venue, null).every((z) => z.status === 'passable'));
  assert.match(ariaSummary(venue, null, []), /No hazards placed/);
});

test('hazard renders and aria summary with a plan', () => {
  const hz = [{ id: 'h1', type: 'FIRE', x: 20, y: 4, zone_id: 'LOBBY' }];
  const [h] = hazardRenders(plan, hz, 'h1');
  assert.equal(h.selected, true);
  assert.equal(h.color, '#ff5a36');
  assert.match(ariaSummary(venue, plan, hz), /Fire in Lobby.*2 of 4 exits safe.*117 of 125/i);
  assert.match(ariaSummary(venue, null, hz), /Plan pending/);
});

test('instance budget halves in low graphics and respects the global cap', () => {
  assert.deepEqual(instanceBudget(['FIRE', 'WATER'], false), [36, 0]);
  assert.deepEqual(instanceBudget(['FIRE', 'SMOKE'], true), [18, 14]);
  const many = instanceBudget(Array(20).fill('FIRE'), false);
  assert.ok(many.reduce((s, n) => s + n, 0) <= 400);
});

test('fitDistance grows for narrow viewports and is finite', () => {
  const wide = fitDistance([40, 24], 40, 1.6, 0.9);
  const narrow = fitDistance([40, 24], 40, 0.45, 0.9);
  assert.ok(Number.isFinite(wide) && wide > 20);
  assert.ok(narrow > wide);
});

test('route keys are unique even when origin and exit repeat', () => {
  const dup = { ...plan, routes: [plan.routes[0], { ...plan.routes[0], via_doors: ['D1'] }, { ...plan.routes[0] }] };
  const keys = routeRenders(venue, dup).map((r) => r.key);
  assert.equal(new Set(keys).size, keys.length);
});
