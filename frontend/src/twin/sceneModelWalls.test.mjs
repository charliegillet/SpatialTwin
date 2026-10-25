// Walls with substance: merged runs, ends that keep every opening at full width, jambs, door kinds, floor kinds.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildWalls, doorRenders, floorKind, openingFrames, wallRuns, zoneRenders } from './sceneModel.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));
const len = (w) => Math.hypot(w.b[0] - w.a[0], w.b[1] - w.a[1]);
const total = (walls) => walls.reduce((s, w) => s + len(w), 0);

test('runs cover exactly the same wall as buildWalls, in fewer boxes', () => {
  const runs = wallRuns(venue);
  const pieces = buildWalls(venue);
  assert.ok(Math.abs(total(runs) - total(pieces)) < 1e-6);
  assert.ok(runs.length < pieces.length, `${runs.length} runs vs ${pieces.length} pieces`);
  assert.equal(runs.filter((w) => w.exterior).reduce((s, w) => s + len(w), 0),
    pieces.filter((w) => w.exterior).reduce((s, w) => s + len(w), 0));
});

test('no two runs of one kind overlap or touch end to end on the same line (they would z-fight)', () => {
  const runs = wallRuns(venue);
  for (let i = 0; i < runs.length; i++) {
    for (let j = i + 1; j < runs.length; j++) {
      const a = runs[i];
      const b = runs[j];
      if (a.exterior !== b.exterior) continue;
      const horiz = a.a[1] === a.b[1] && b.a[1] === b.b[1] && a.a[1] === b.a[1];
      const vert = a.a[0] === a.b[0] && b.a[0] === b.b[0] && a.a[0] === b.a[0];
      if (!horiz && !vert) continue;
      const [a0, a1] = horiz ? [a.a[0], a.b[0]] : [a.a[1], a.b[1]];
      const [b0, b1] = horiz ? [b.a[0], b.b[0]] : [b.a[1], b.b[1]];
      const touching = Math.min(a1, b1) - Math.max(a0, b0) >= -1e-9;
      // Two runs may meet only across an opening (then they do not touch) — never share an end.
      assert.ok(!touching, `runs ${JSON.stringify(a)} and ${JSON.stringify(b)} touch`);
    }
  }
});

test('every door and wall exit is flanked by open run ends, at exactly half its width', () => {
  const runs = wallRuns(venue);
  const ends = runs.flatMap((w) => [[w.a, w.openA], [w.b, w.openB]]);
  for (const o of [...venue.doors, ...venue.exits]) {
    const f = openingFrames(venue).find((frame) => frame.id === o.id);
    for (const jamb of f.jambs) {
      const at = ends.find(([p]) => Math.abs(p[0] - jamb[0]) < 1e-6 && Math.abs(p[1] - jamb[1]) < 1e-6);
      if (!at) continue; // an opening reaching a corner has a wall end only on one side
      assert.equal(at[1], true, `${o.id} edge ${jamb} is marked open`);
    }
    const [x, y] = o.position;
    const h = o.width / 2;
    assert.deepEqual(f.jambs, f.axis === 'x' ? [[x - h, y], [x + h, y]] : [[x, y - h], [x, y + h]]);
  }
  // building-v2 D1 sits on the LOBBY|HALL wall at (20, 8), 3 m wide: the runs either side end at 18.5 and 21.5.
  const d1 = runs.filter((w) => w.a[1] === 8 && w.b[1] === 8 && !w.exterior);
  assert.ok(d1.some((w) => w.b[0] === 18.5 && w.openB));
  assert.ok(d1.some((w) => w.a[0] === 21.5 && w.openA));
});

test('corner ends are joints (they overlap to close the corner), not openings', () => {
  const runs = wallRuns(venue);
  const south = runs.find((w) => w.exterior && w.a[1] === 0 && w.b[1] === 0 && w.a[0] === 8);
  assert.ok(south, 'south wall run starting at the notch corner (8, 0)');
  assert.equal(south.openA, false);
});

test('an interior stair cuts no wall and gets no jambs', () => {
  const stair = structuredClone(venue);
  stair.exits = stair.exits.map((e) => (e.id === 'E2' ? { ...e, kind: 'stair', position: [20, 22] } : e));
  assert.ok(!openingFrames(stair).some((f) => f.id === 'E2'));
  assert.ok(openingFrames(venue).some((f) => f.id === 'E2' && f.role === 'exit'));
  assert.ok(total(wallRuns(stair)) > total(wallRuns(venue)));
});

test('door renders carry the venue door kind (fire doors stay distinct)', () => {
  const by = Object.fromEntries(doorRenders(venue, null).map((d) => [d.id, d]));
  assert.equal(by.D1.kind, 'fire_door');
  assert.equal(by.D5.kind, 'smoke_door');
  assert.equal(by.D4.kind, 'servo_door');
  assert.equal(by.D10.kind, 'opening');
  assert.equal(by.D10.hasLeaf, false);
});

test('floor kind is read conservatively from the room name', () => {
  assert.equal(floorKind('North Exit Stair'), 'stair');
  assert.equal(floorKind('Northeast Core / Stair Area'), 'stair');
  assert.equal(floorKind('Main Corridor'), 'circulation');
  assert.equal(floorKind('South Stair Lobby'), 'stair');
  assert.equal(floorKind('North/Bay Side Floor Space & Walkway'), 'circulation');
  assert.equal(floorKind('Elevators'), 'service');
  assert.equal(floorKind('Loading dock'), 'service');
  for (const name of ['Northwest Room', 'Kitchen', 'Bedroom 2', 'West Wing Floor Space', 'Hallmark Store Office']) {
    assert.notEqual(floorKind(name), 'stair', name);
  }
  assert.equal(floorKind('Northwest Room'), 'room');
  assert.equal(floorKind('Stairmaster gym'), 'room');
  const kinds = Object.fromEntries(zoneRenders(venue, null).map((z) => [z.id, z.floorKind]));
  assert.deepEqual(kinds, {
    HALL: 'circulation', LOBBY: 'circulation', ROOM_A: 'room', KITCHEN: 'room', WEST_CORR: 'circulation',
    EAST_CORR: 'circulation', STAIR_N: 'stair', DOCK: 'service',
  });
});
