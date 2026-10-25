import test from 'node:test';
import assert from 'node:assert/strict';
import { buildDisplayModel, formatExposureLabel, isDisplayable, summarizeAlternatives } from './hazard.ts';

const result = (overrides = {}) => ({
  scenario_label: 'Forecast closure',
  events: [{ element_id: 'P1', close_at_s: 10 }],
  alternatives: [
    { alternative_id: 'KEEP_CURRENT', completed_crossings: 60, exposure_people_seconds: 400 },
    { alternative_id: 'OPEN_P3', completed_crossings: 75, exposure_people_seconds: 250 },
  ],
  check: { status: 'passed', reasons: [] },
  ...overrides,
});

test('label carries the required caveat', () => {
  assert.ok(formatExposureLabel().includes('modeled people-seconds in hazard; not a casualty or survival prediction'));
});

test('summarizeAlternatives sums and never invents', () => {
  const summary = summarizeAlternatives(result().alternatives);
  assert.equal(summary.total_completed_crossings, 135);
  assert.equal(summary.total_exposure_people_seconds, 650);
  assert.equal(summary.rows.length, 2);
  const empty = summarizeAlternatives([]);
  assert.deepEqual(empty, { rows: [], total_completed_crossings: 0, total_exposure_people_seconds: 0 });
});

test('isDisplayable is false when not current or null', () => {
  assert.equal(isDisplayable(result(), false), false);
  assert.equal(isDisplayable(null, true), false);
  assert.equal(isDisplayable(result(), true), true);
});

test('null and stale results yield display models with no numbers', () => {
  for (const model of [buildDisplayModel(null, true), buildDisplayModel(result(), false)]) {
    assert.equal(model.summary, null);
    assert.equal(model.check, null);
    assert.deepEqual(model.events, []);
  }
  assert.equal(buildDisplayModel(null, true).kind, 'empty');
  assert.equal(buildDisplayModel(result(), false).kind, 'stale');
});

test('checker reasons pass through unchanged', () => {
  const reasons = ['flow through P1 after close  at 10s', 'Ünïcode <b>raw</b>'];
  const model = buildDisplayModel(result({ check: { status: 'failed', reasons } }), true);
  assert.equal(model.check.status, 'failed');
  assert.deepEqual(model.check.reasons, reasons);
});
