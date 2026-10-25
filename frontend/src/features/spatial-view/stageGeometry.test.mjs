import assert from 'node:assert/strict';
import test from 'node:test';
import { chevronPoints, exitArrows, plumePuffs } from './stageGeometry.ts';

test('plume is a 4 to 6 puff stack rising about 110px and fading out', () => {
  const puffs = plumePuffs();
  assert.ok(puffs.length >= 4 && puffs.length <= 6);
  assert.equal(puffs[0].dy, 0);
  assert.equal(puffs.at(-1).dy, -110);
  assert.ok(puffs[0].opacity > puffs.at(-1).opacity);
  assert.ok(puffs.at(-1).rx > puffs[0].rx);
  assert.equal(plumePuffs(99).length, 6);
  assert.equal(plumePuffs(1).length, 2);
});

test('chevron is symmetric about its direction with the tip at the target', () => {
  const [a, tip, b] = chevronPoints([100, 100], [0, 2], 20, 10);
  assert.deepEqual(tip, [100, 100]);
  assert.equal(a[1], 80);
  assert.equal(b[1], 80);
  assert.equal(a[0] + b[0], 200);
  assert.equal(Math.abs(a[0] - b[0]), 20);
});

test('exit arrows follow checked boundary flow and show blocked boundaries', () => {
  assert.deepEqual(exitArrows({ checked: true, breakdown: { B1: 60, B2: 0 }, blockedBoundaries: ['B2'] }), [{ id: 'B1', state: 'flow' }, { id: 'B2', state: 'blocked' }]);
  assert.deepEqual(exitArrows({ checked: false, breakdown: { B1: 60, B2: 60 } }).map(a => a.state), ['none', 'none']);
  assert.deepEqual(exitArrows({ checked: true, breakdown: { B1: 10, B2: 40 } }).map(a => a.state), ['flow', 'flow']);
  assert.deepEqual(exitArrows({ checked: true, breakdown: null }).map(a => a.state), ['none', 'none']);
});

test('arrow polygon has its tip at the target and a head wider than its shaft', async () => {
  const { arrowPolygon } = await import('./stageGeometry.ts');
  const shape = arrowPolygon([0, 0], [0, 100], 10, 40, 30);
  assert.equal(shape.length, 7);
  assert.deepEqual(shape[3], [0, 100]);
  const width = (a, b) => Math.abs(a[0] - b[0]);
  assert.equal(width(shape[0], shape[6]), 10);
  assert.equal(width(shape[2], shape[4]), 40);
  assert.equal(shape[2][1], 70);
});
