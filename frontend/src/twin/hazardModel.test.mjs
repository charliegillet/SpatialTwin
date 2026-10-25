import assert from 'node:assert/strict';
import test from 'node:test';
import { HAZARD_INFO, HAZARD_ORDER, hazardHint } from './hazardModel.ts';

test('every hazard type has a label, colour and hint', () => {
  assert.deepEqual([...HAZARD_ORDER], ['FIRE', 'SMOKE', 'GAS', 'CHEMICAL', 'WATER']);
  for (const type of HAZARD_ORDER) {
    assert.match(HAZARD_INFO[type].color, /^#[0-9a-f]{6}$/);
    assert.ok(hazardHint(type).length > 10, type);
  }
});

test('fire and smoke hints carry the untenable time', () => {
  assert.equal(hazardHint('FIRE'), 'No entry · fire doors close to entry · people inside leave until 6 s');
  assert.equal(hazardHint('SMOKE', 20), 'Half speed · no entry · untenable at 20 s');
  assert.equal(hazardHint('CHEMICAL'), 'No entry · doors close to confine · people inside leave until 10 s');
});

test('the gas hint never says a door opens or closes', () => {
  const hint = hazardHint('GAS');
  assert.doesNotMatch(hint, /\b(open|opens|opened|close|closes|closed|unlock|lock)\b/i);
  assert.match(hint, /nothing near it is switched or moved/);
  assert.match(hint, /responders vent to the outside/);
});

test('the water hint says no door changes and half speed', () => {
  const hint = hazardHint('WATER');
  assert.match(hint, /no door changes/);
  assert.match(hint, /half speed/);
});
