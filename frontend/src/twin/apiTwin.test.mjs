import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { parseDoorPlan, parseVenue, twinErrorMessage, TWIN_ERRORS } from '../api/twin.ts';
import { ApiError } from '../api/client.ts';
import { makePlan } from './planFixture.mjs';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));

test('a well-formed plan passes through unchanged', () => {
  const plan = makePlan();
  assert.equal(parseDoorPlan(plan), plan);
});

test('a malformed plan throws an ApiError instead of reaching the UI', () => {
  for (const broken of [null, [], {}, { ...makePlan(), doors: null }, { ...makePlan(), chosen: { completed_crossings: 'x' } }, { ...makePlan(), lights: {} }, { ...makePlan(), venue_id: 'tabletop-v1' }, { ...makePlan(), baseline: {} }]) {
    assert.throws(() => parseDoorPlan(broken), error => error instanceof ApiError && error.status === 502);
  }
});

test('every real door-plan fixture the backend provides validates', async () => {
  const { readdirSync } = await import('node:fs');
  const dir = new URL('./fixtures/', import.meta.url);
  for (const name of readdirSync(dir).filter(file => /^door-plan-.*\.json$/.test(file))) {
    const plan = parseDoorPlan(JSON.parse(readFileSync(new URL(name, dir), 'utf8')));
    assert.equal(plan.chosen.validator_report.is_valid, true, name);
  }
});

test('the venue is validated minimally', () => {
  assert.equal(parseVenue(venue), venue);
  assert.throws(() => parseVenue({ ...venue, zones: [] }), ApiError);
  assert.throws(() => parseVenue({ ...venue, venue_id: 'x' }), ApiError);
  assert.throws(() => parseVenue(null), ApiError);
});

test('422 codes map to short copy', () => {
  for (const code of ['too_many_hazards', 'duplicate_hazard_id', 'outside_building', 'zone_mismatch', 'invalid_untenable_time', 'invalid_horizon']) {
    assert.equal(twinErrorMessage(422, code), TWIN_ERRORS[code]);
    assert.ok(TWIN_ERRORS[code].length < 60);
  }
  assert.equal(twinErrorMessage(422, 'something_new'), 'The hazards were not accepted');
  assert.equal(twinErrorMessage(500, ''), '');
});
