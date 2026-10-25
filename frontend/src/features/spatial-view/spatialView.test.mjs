import test from 'node:test';
import assert from 'node:assert/strict';
import { clampPan, panByKey, formatForecastClosure, forecastTargets } from './spatialView.ts';

const bounds = { width: 1000, height: 500 };

test('clampPan leaves in-range offsets and limits extremes', () => {
  assert.deepEqual(clampPan({ x: 10, y: -20 }, 1, bounds), { x: 10, y: -20 });
  assert.deepEqual(clampPan({ x: 9999, y: -9999 }, 1, bounds), { x: 400, y: -200 });
});

test('clampPan scales with zoom and rejects non-finite input', () => {
  assert.equal(clampPan({ x: 9999, y: 0 }, 2, bounds).x, 800);
  assert.deepEqual(clampPan({ x: NaN, y: Infinity }, 1, bounds), { x: 0, y: 0 });
});

test('panByKey maps arrows and ignores others', () => {
  assert.deepEqual(panByKey('ArrowLeft'), { x: -40, y: 0 });
  assert.deepEqual(panByKey('ArrowDown', 10), { x: 0, y: 10 });
  assert.equal(panByKey('Enter'), null);
  assert.equal(panByKey('a'), null);
});

test('formatForecastClosure says forecast, never blocked or checked', () => {
  const text = formatForecastClosure(12);
  assert.match(text, /forecast/);
  assert.match(text, /12s/);
  assert.doesNotMatch(text, /blocked|checked/i);
});

test('forecastTargets maps venue ids and drops unknown ids and bad times', () => {
  const result = forecastTargets([
    { element_id: 'P1', close_at_s: 5 },
    { element_id: 'B2', close_at_s: 0 },
    { element_id: 'P3', close_at_s: 4 },
    { element_id: 'toString', close_at_s: 4 },
    { element_id: 'P2', close_at_s: -1 },
    { element_id: 'P2', close_at_s: Number.NaN },
    { element_id: 'P1', close_at_s: 9 },
  ]);
  assert.deepEqual(result, [{ target: 'portal:P1', close_at_s: 5 }, { target: 'boundary:B2', close_at_s: 0 }]);
  assert.deepEqual(forecastTargets(undefined), []);
});
