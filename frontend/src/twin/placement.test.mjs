import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { DROP_REFUSED } from './geometry.ts';
import { clearHazards, emptyPlacement, MAX_HAZARDS, placeHazard, removeHazard, setSmokeSeconds, toHazardInputs, TOO_MANY_HAZARDS, undoPlacement, zoneDropPoint } from './placement.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));
const lobby = { x: 16, y: 4 };

test('a drop inside a room is placed with its zone and a stable id', () => {
  const result = placeHazard(emptyPlacement(), venue, 'FIRE', lobby);
  assert.equal(result.ok, true);
  assert.equal(result.hazard.zone_id, 'LOBBY');
  assert.equal(result.hazard.id, 'h1');
  assert.equal(result.hazard.untenable_s, null);
});

test('refused drops return the geometry copy and leave state untouched', () => {
  const state = emptyPlacement();
  const outside = placeHazard(state, venue, 'GAS', { x: -5, y: -5 });
  assert.deepEqual(outside, { ok: false, message: DROP_REFUSED.outside });
  const doorway = placeHazard(state, venue, 'GAS', { x: venue.doors[0].position[0], y: venue.doors[0].position[1] });
  assert.equal(doorway.ok, false);
  assert.equal(doorway.message, DROP_REFUSED.in_doorway);
});

test('smoke carries its untenable time; other types send none', () => {
  const smoke = placeHazard(emptyPlacement(), venue, 'SMOKE', lobby, 20);
  assert.equal(smoke.hazard.untenable_s, 20);
  assert.equal(toHazardInputs(smoke.state.hazards)[0].untenable_s, 20);
  const water = placeHazard(emptyPlacement(), venue, 'WATER', lobby, 20);
  assert.equal(toHazardInputs(water.state.hazards)[0].untenable_s, null);
});

test('stacking in one room is allowed; the cap is six', () => {
  let state = emptyPlacement();
  for (let i = 0; i < MAX_HAZARDS; i += 1) {
    const result = placeHazard(state, venue, i % 2 ? 'SMOKE' : 'FIRE', lobby);
    assert.equal(result.ok, true, `placement ${i}`);
    state = result.state;
  }
  assert.deepEqual(placeHazard(state, venue, 'FIRE', lobby), { ok: false, message: TOO_MANY_HAZARDS });
  assert.equal(TOO_MANY_HAZARDS, 'Up to 6 hazards');
  assert.equal(new Set(state.hazards.map(item => item.id)).size, MAX_HAZARDS);
});

test('undo restores earlier states and ids are never reused', () => {
  let state = placeHazard(emptyPlacement(), venue, 'FIRE', lobby).state;
  state = placeHazard(state, venue, 'GAS', { x: 20, y: 14 }).state;
  assert.deepEqual(state.hazards.map(item => item.id), ['h1', 'h2']);
  state = undoPlacement(state);
  assert.deepEqual(state.hazards.map(item => item.id), ['h1']);
  const again = placeHazard(state, venue, 'WATER', { x: 10, y: 10 });
  assert.equal(again.hazard.id, 'h3');
  assert.equal(undoPlacement(emptyPlacement()).hazards.length, 0);
});

test('remove and clear are undoable', () => {
  let state = placeHazard(emptyPlacement(), venue, 'FIRE', lobby).state;
  state = placeHazard(state, venue, 'WATER', { x: 10, y: 10 }).state;
  const removed = removeHazard(state, 'h1');
  assert.deepEqual(removed.hazards.map(item => item.id), ['h2']);
  assert.equal(removeHazard(removed, 'missing'), removed);
  const cleared = clearHazards(removed);
  assert.equal(cleared.hazards.length, 0);
  assert.deepEqual(undoPlacement(cleared).hazards.map(item => item.id), ['h2']);
  assert.equal(clearHazards(cleared), cleared);
});

test('only smoke changes its time', () => {
  const smoke = placeHazard(emptyPlacement(), venue, 'SMOKE', lobby, 12);
  assert.equal(setSmokeSeconds(smoke.state, 'h1', 20).hazards[0].untenable_s, 20);
  const fire = placeHazard(emptyPlacement(), venue, 'FIRE', lobby);
  assert.equal(setSmokeSeconds(fire.state, 'h1', 20), fire.state);
});

test('every room has a keyboard drop point that placement accepts', () => {
  for (const zone of venue.zones) {
    const point = zoneDropPoint(venue, zone.id);
    const result = placeHazard(emptyPlacement(), venue, 'FIRE', point);
    assert.equal(result.ok, true, zone.id);
    assert.equal(result.hazard.zone_id, zone.id);
  }
  assert.equal(zoneDropPoint(venue, 'NOPE'), null);
});

test('hazard inputs match the request contract', () => {
  const [input] = toHazardInputs(placeHazard(emptyPlacement(), venue, 'FIRE', lobby).state.hazards);
  assert.deepEqual(Object.keys(input).sort(), ['id', 'position', 'proposal_id', 'source', 'type', 'untenable_s', 'zone_id']);
  assert.deepEqual(input.position, lobby);
  assert.equal(input.source, 'simulated');
});

test('camera hazards never send untenable_s and the smoke stepper leaves them alone', () => {
  const camera = { id: 'c1', type: 'SMOKE', x: lobby.x, y: lobby.y, zone_id: 'LOBBY', untenable_s: 12, source: 'camera', proposal_id: 'p1' };
  const [input] = toHazardInputs([camera]);
  assert.equal('untenable_s' in input, false);
  assert.equal(input.proposal_id, 'p1');
  const state = { hazards: [camera], history: [], seq: 1 };
  assert.equal(setSmokeSeconds(state, 'c1', 20), state);
});
