// Interior exit stairs (kind 'stair'): the way down inside a stair core, lobby or corridor, never a gap in a wall.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildWalls, exitRenders, isInteriorStair, rayToWall } from './sceneModel.ts';

const base = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));

/** building-v2 with E2 (STAIR_N's north wall exit) replaced, or removed when `exit` is null. */
function withE2(exit) {
  const venue = structuredClone(base);
  venue.exits = venue.exits.flatMap((e) => (e.id !== 'E2' ? [e] : exit ? [{ ...e, ...exit }] : []));
  return venue;
}

const total = (walls) => walls.reduce((s, w) => s + Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]), 0);

test('an interior stair exit cuts no wall: the walls are those of the venue without it', () => {
  const inside = buildWalls(withE2({ kind: 'stair', position: [20, 22] }));
  const without = buildWalls(withE2(null));
  assert.deepEqual(inside, without);
  // ...and the north wall of the stair core is whole again (E2's 2.4 m gap is gone).
  assert.ok(Math.abs(total(inside) - total(buildWalls(base)) - 2.4) < 1e-6);
});

test('a stair exit on a shared wall (stale data) still opens nothing into the next room', () => {
  // On D4's wall between HALL and STAIR_N, beside the door: a wall exit here would cut a gap into the hall.
  const onWall = buildWalls(withE2({ kind: 'stair', position: [25, 20] }));
  assert.deepEqual(onWall, buildWalls(withE2(null)));
  const asDoorExit = buildWalls(withE2({ kind: 'door', position: [25, 20] }));
  assert.ok(total(asDoorExit) < total(onWall) - 2.3, 'a wall exit there would cut a gap');
});

test('an interior stair renders at its point, approached from the side of its room with the most floor', () => {
  // STAIR_N is x 12-28, y 20-24. At (20, 21) there is 1 m of floor to the south, 3 m north, 8 m east and west.
  const venue = withE2({ kind: 'stair', position: [20, 21] });
  const ex = Object.fromEntries(exitRenders(venue, null).map((e) => [e.id, e]));
  assert.equal(ex.E2.interior, true);
  assert.deepEqual(ex.E2.position, [20, 21]);
  assert.deepEqual(ex.E2.outward, [1, 0]);           // walked onto eastwards, from the 8 m run on the west
  assert.equal(ex.E2.axis, 'y');
  assert.equal(ex.E2.approach, 8);
  for (const id of ['E1', 'E3', 'E4']) assert.equal(ex[id].interior, false);
  for (const id of ['E1', 'E3', 'E4']) assert.equal(ex[id].approach, Infinity);
  assert.deepEqual([ex.E1.outward, ex.E3.outward, ex.E4.outward], [[0, -1], [1, 0], [-1, 0]]);
});

test('an interior stair faces +y on a tie, and the run-up never leaves its room', () => {
  // ROOM_A is x 0-8, y 8-24: from its centre (4, 16) there are 8 m south and north, 4 m east and west.
  const venue = structuredClone(base);
  venue.exits.push({ id: 'E5', zone: 'ROOM_A', name: 'Stair', position: [4, 16], width: 1.2,
    service_rate_per_sec: 0.7, kind: 'stair' });
  const e5 = exitRenders(venue, null).find((e) => e.id === 'E5');
  assert.deepEqual([e5.outward, e5.axis, e5.approach], [[0, 1], 'x', 8]);
  assert.equal(rayToWall(venue.zones.find((z) => z.id === 'ROOM_A').polygon, [4, 16], [1, 0]), 4);
});

test('only kind stair is interior; building-v2 exits (no kind), doors and windows are wall exits', () => {
  assert.equal(base.exits.some(isInteriorStair), false);
  assert.equal(isInteriorStair({ ...base.exits[0], kind: 'door' }), false);
  assert.equal(isInteriorStair({ ...base.exits[0], kind: 'window' }), false);
  assert.equal(isInteriorStair({ ...base.exits[0], kind: 'stair' }), true);
});
