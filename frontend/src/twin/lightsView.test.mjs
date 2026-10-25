import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { legendFor, LIGHT_CODES, lightsView, PIXEL_COUNT } from './lightsView.ts';
import { makePlan } from './planFixture.mjs';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));

test('pixels group by led_map element in strip order and cover all 24', () => {
  const groups = lightsView(makePlan(), venue.led_map);
  assert.deepEqual(groups.map(group => group.id), ['E1', 'E2', 'E3', 'E4', 'D4']);
  assert.equal(groups.reduce((sum, group) => sum + group.pixels.length, 0), PIXEL_COUNT);
  assert.deepEqual(groups[0].pixels.map(pixel => pixel.index), [0, 1, 2, 3, 4, 5]);
});

test('flashing codes flash, and nothing flashes under reduced motion', () => {
  const plan = makePlan({ lights: { px: 'F'.repeat(24), segments: [], held: [] } });
  assert.ok(lightsView(plan, venue.led_map)[0].pixels.every(pixel => pixel.flashing));
  assert.ok(lightsView(plan, venue.led_map, true).every(group => group.pixels.every(pixel => !pixel.flashing)));
});

test('a missing or malformed px string yields no groups', () => {
  assert.deepEqual(lightsView(null, venue.led_map), []);
  assert.deepEqual(lightsView(makePlan({ lights: { px: 'FF', segments: [], held: [] } }), venue.led_map), []);
});

test('an unknown code is shown as unknown, not hidden', () => {
  const plan = makePlan({ lights: { px: '?'.repeat(24), segments: [], held: [] } });
  const pixel = lightsView(plan, venue.led_map)[0].pixels[0];
  assert.equal(pixel.known, false);
  assert.equal(pixel.meaning.label, 'Unknown code');
});

test('the legend lists only codes on screen', () => {
  const groups = lightsView(makePlan({ lights: { px: `F${'0'.repeat(23)}`, segments: [], held: [] } }), venue.led_map);
  assert.deepEqual(legendFor(groups).map(item => item.code), ['F']);
  assert.ok(Object.keys(LIGHT_CODES).length >= 8);
});

test('an unchecked plan shows no light values', () => {
  const plan = makePlan();
  plan.chosen.validator_report = { is_valid: false, checks_run: [], reasons: [] };
  assert.deepEqual(lightsView(plan, { E1: [0, 5] }), []);
});
