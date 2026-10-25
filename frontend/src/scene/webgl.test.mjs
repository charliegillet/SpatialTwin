import test from 'node:test';
import assert from 'node:assert/strict';
import { probeWebGL, readReducedMotion, canUseWebGL, prefersReducedMotion } from './webgl.ts';

test('probeWebGL prefers webgl2 then webgl', () => {
  const asked = [];
  assert.equal(probeWebGL(() => ({ getContext: (k) => (asked.push(k), k === 'webgl' ? {} : null) })), true);
  assert.deepEqual(asked, ['webgl2', 'webgl']);
});
test('probeWebGL false when no context or when it throws', () => {
  assert.equal(probeWebGL(() => ({ getContext: () => null })), false);
  assert.equal(probeWebGL(() => { throw new Error('no dom'); }), false);
  assert.equal(probeWebGL(() => ({ getContext: () => { throw new Error('blocked'); } })), false);
});
test('readReducedMotion handles missing and throwing matchMedia', () => {
  assert.equal(readReducedMotion(undefined), false);
  assert.equal(readReducedMotion(() => ({ matches: true })), true);
  assert.equal(readReducedMotion(() => { throw new Error('x'); }), false);
});
test('browser wrappers are safe outside a browser', () => {
  assert.equal(canUseWebGL(), false);
  assert.equal(prefersReducedMotion(), false);
});

import { memoizeProbe } from './webgl.ts';
test('probeWebGL releases the context it created', () => {
  let lost = 0;
  const context = { getExtension: name => name === 'WEBGL_lose_context' ? { loseContext: () => { lost += 1; } } : null };
  assert.equal(probeWebGL(() => ({ getContext: () => context })), true);
  assert.equal(lost, 1);
  assert.equal(probeWebGL(() => ({ getContext: () => ({ getExtension: () => { throw new Error('x'); } }) })), true);
});
test('memoizeProbe runs the probe once', () => {
  let runs = 0;
  const once = memoizeProbe(() => (runs += 1, false));
  assert.equal(once(), false); assert.equal(once(), false);
  assert.equal(runs, 1);
});
