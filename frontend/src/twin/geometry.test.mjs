import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { DROP_REFUSED, locateZone, pointInPolygon, polygonCentroid } from './geometry.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));
const canonical = JSON.parse(readFileSync(new URL('../../../venue/building_v2.json', import.meta.url), 'utf8'));

test('the frontend fixture is the canonical venue file', () => {
  assert.deepEqual(venue, canonical);
});

test('zone polygons tile the plan without overlap at their centroids', () => {
  for (const zone of venue.zones) {
    const [cx, cy] = polygonCentroid(zone.polygon);
    const hit = locateZone(venue, { x: cx, y: cy });
    assert.deepEqual(hit, { ok: true, zone_id: zone.id }, zone.id);
  }
});

test('drops in a room resolve to that room', () => {
  assert.deepEqual(locateZone(venue, { x: 16, y: 4 }), { ok: true, zone_id: 'LOBBY' });
  assert.deepEqual(locateZone(venue, { x: 36, y: 4 }), { ok: true, zone_id: 'KITCHEN' });
  assert.deepEqual(locateZone(venue, { x: 10, y: 10 }), { ok: true, zone_id: 'WEST_CORR' });
});

test('walls, doorways and the outside are refused', () => {
  assert.deepEqual(locateZone(venue, { x: 4, y: 4 }), { ok: false, reason: 'outside' });
  assert.deepEqual(locateZone(venue, { x: -1, y: 10 }), { ok: false, reason: 'outside' });
  assert.deepEqual(locateZone(venue, { x: 16, y: 8.1 }), { ok: false, reason: 'on_wall' });
  assert.deepEqual(locateZone(venue, { x: 20, y: 8.2 }), { ok: false, reason: 'in_doorway' });
  assert.deepEqual(locateZone(venue, { x: 39.8, y: 16 }), { ok: false, reason: 'in_doorway' });
  assert.deepEqual(locateZone(venue, { x: Number.NaN, y: 1 }), { ok: false, reason: 'outside' });
  assert.equal(DROP_REFUSED.outside, 'Drop inside a room');
});

test('point in polygon counts edges as inside', () => {
  const square = [[0, 0], [2, 0], [2, 2], [0, 2]];
  assert.equal(pointInPolygon(1, 1, square), true);
  assert.equal(pointInPolygon(2, 1, square), true);
  assert.equal(pointInPolygon(3, 1, square), false);
});

test('every door joins two zones that share the wall it sits on', () => {
  const ids = new Set(venue.zones.map((zone) => zone.id));
  const pairs = new Set();
  for (const door of venue.doors) {
    assert.equal(door.zones.length, 2);
    for (const id of door.zones) assert.ok(ids.has(id), `${door.id} names unknown zone ${id}`);
    const key = [...door.zones].sort().join('|');
    assert.ok(!pairs.has(key), `two doors join ${key}`);
    pairs.add(key);
    for (const id of door.zones) {
      const zone = venue.zones.find((z) => z.id === id);
      assert.ok(pointInPolygon(door.position[0], door.position[1], zone.polygon), `${door.id} not on ${id}`);
    }
  }
});

test('printed corner markers in types.ts match venue/print/sheet_v2.json', async () => {
  const { SHEET_FIDUCIALS_M } = await import('./types.ts');
  const sheet = JSON.parse(readFileSync(new URL('../../../venue/print/sheet_v2.json', import.meta.url), 'utf8'));
  assert.deepEqual(SHEET_FIDUCIALS_M, sheet.fiducial_floor_m);
});
