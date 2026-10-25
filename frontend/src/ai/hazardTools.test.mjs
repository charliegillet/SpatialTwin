import assert from 'node:assert/strict';
import test from 'node:test';
import { forecastBreakdown, forecastLine, heroForecastLine, hazardErrorMessage, HAZARD_REJECT, isValidSmokeSeconds, placementOutcome, smokeEvents, stepSmokeSeconds } from './hazardTools.ts';

test('only P1, P2 and B2 take hazards', () => {
  assert.deepEqual(placementOutcome('portal:P2'), { ok: true, target: 'portal:P2' });
  assert.deepEqual(placementOutcome('boundary:B2'), { ok: true, target: 'boundary:B2' });
  for (const bad of ['portal:P3', 'boundary:B1', 'zone:EAST', '', null, undefined]) {
    assert.deepEqual(placementOutcome(bad), { ok: false, message: HAZARD_REJECT });
  }
  assert.equal(HAZARD_REJECT, 'Hazards can only be placed on P1, P2 or B2');
});

test('smoke seconds are even values from 0 to 38', () => {
  for (const ok of [0, 2, 12, 38]) assert.equal(isValidSmokeSeconds(ok), true);
  for (const bad of [-2, 1, 13, 40, 12.5, NaN, '12']) assert.equal(isValidSmokeSeconds(bad), false);
  assert.equal(stepSmokeSeconds(12, 1), 14);
  assert.equal(stepSmokeSeconds(12, -1), 10);
  assert.equal(stepSmokeSeconds(38, 1), 38);
  assert.equal(stepSmokeSeconds(0, -1), 0);
  assert.equal(stepSmokeSeconds(13, 1), 14);
});

test('smoke events use venue ids in a stable order and drop invalid times', () => {
  assert.deepEqual(smokeEvents({ 'boundary:B2': 8, 'portal:P1': 12, 'portal:P2': 7 }), [{ element_id: 'P1', close_at_s: 12 }, { element_id: 'B2', close_at_s: 8 }]);
});

test('forecast sentence names the change or says nothing changes', () => {
  const events = [{ element_id: 'P1', close_at_s: 12 }];
  assert.equal(forecastLine({ events, forecast: 96, current: 120, population: 120 }), 'If smoke closes P1 at 12 s: 96 of 120 reach an exit (now 120)');
  assert.equal(forecastLine({ events: [{ element_id: 'P2', close_at_s: 24 }], forecast: 120, current: 120, population: 120 }), 'If smoke closes P2 at 24 s: no change \u00b7 in the model everyone has passed P2 by then');
  assert.equal(heroForecastLine(events, 96), 'Forecast \u00b7 96 if smoke closes P1 at 12 s');
});

test('forecast breakdown tolerates a missing field', () => {
  assert.equal(forecastBreakdown(undefined), null);
  assert.equal(forecastBreakdown([]), null);
  assert.deepEqual(forecastBreakdown({ B1: 60, B2: 36, junk: 'x' }), { B1: 60, B2: 36 });
});

test('invalid close time maps to the even-seconds message', () => {
  assert.equal(hazardErrorMessage(422, 'invalid_close_time'), 'Use an even number of seconds');
  assert.match(hazardErrorMessage(422, 'invalid_request'), /rejected/);
  assert.equal(hazardErrorMessage(500, ''), '');
});
