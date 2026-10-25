import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { BUILTIN_VENUE_ID, parseActiveVenue, parseDoorPlan, parseVenue, twinErrorMessage, VENUE_CHANGED, VENUE_ID_PATTERN } from '../api/twin.ts';
import { ApiError } from '../api/client.ts';
import { lightsView } from './lightsView.ts';
import { modelTag, twinHero } from './twinHero.ts';
import { makePlan } from './planFixture.mjs';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));

test('a compiled venue id passes; the plan must be for the venue that was asked for', () => {
  assert.equal(BUILTIN_VENUE_ID, 'building-v2');
  assert.ok(VENUE_ID_PATTERN.test('shack15-floor-3'));
  assert.ok(!VENUE_ID_PATTERN.test('Bad_Id') && !VENUE_ID_PATTERN.test('ab'));
  const home = { ...venue, venue_id: 'home-flat' };
  assert.equal(parseVenue(home), home);
  assert.equal(parseVenue(home, 'home-flat'), home);
  assert.throws(() => parseVenue(home, 'building-v2'), ApiError);
  const plan = makePlan({ venue_id: 'home-flat' });
  assert.equal(parseDoorPlan(plan, 'home-flat'), plan);
  assert.throws(() => parseDoorPlan(plan), ApiError);
});

test('a plan solved on other geometry for the same venue id is refused as venue_changed', () => {
  const plan = makePlan({ venue_id: 'home-flat', geometry_revision: 'geom-new' });
  assert.equal(parseDoorPlan(plan, 'home-flat', 'geom-new'), plan);
  assert.throws(() => parseDoorPlan(plan, 'home-flat', 'geom-old'),
    error => error instanceof ApiError && error.status === 409 && error.detail === VENUE_CHANGED);
});

test('a single-room venue with no interior door opens', () => {
  const single = { ...venue, venue_id: 'studio', zones: venue.zones.slice(0, 1), doors: [], exits: venue.exits.slice(0, 1) };
  assert.equal(parseVenue(single, 'studio'), single);
  assert.throws(() => parseVenue({ ...single, doors: null }), ApiError);
  assert.throws(() => parseVenue({ ...single, exits: [] }), ApiError);
});

test('the active pointer is validated', () => {
  assert.deepEqual(parseActiveVenue({ venue_id: 'home-flat', revision: 3, extra: true }), { venue_id: 'home-flat', revision: 3 });
  for (const broken of [null, { venue_id: 'home-flat' }, { venue_id: 'x', revision: 1 }, { venue_id: 'home-flat', revision: 1.5 }]) {
    assert.throws(() => parseActiveVenue(broken), ApiError);
  }
  assert.equal(twinErrorMessage(404, 'unknown_venue'), 'That venue is not available any more.');
});

test('the hero names the venue it planned', () => {
  assert.equal(modelTag(null), 'building-v2 model');
  assert.equal(modelTag('home-flat'), 'home-flat model');
  assert.equal(twinHero({ plan: makePlan({ venue_id: 'home-flat' }), pending: false }).tag, 'home-flat model');
  assert.equal(twinHero({ plan: null, pending: true, venueId: 'home-flat' }).tag, 'home-flat model');
});

test('a longer light strip renders; one shorter than its led_map does not', () => {
  const ledMap = { ...venue.led_map, E5: [24, 26] };
  const long = makePlan({ lights: { px: 'g'.repeat(27), segments: [], held: [] } });
  assert.deepEqual(lightsView(long, ledMap).map(group => group.id), ['E1', 'E2', 'E3', 'E4', 'D4', 'E5']);
  assert.deepEqual(lightsView(makePlan(), ledMap), []);
});
