import assert from 'node:assert/strict';
import test from 'node:test';
import { modeAfterReset } from './resetFlow.ts';
import { canSwitchMode, CAMERA_TWIN_ENABLED, visibleModes } from '../twin/modes.ts';

test('Next judge always returns to Tabletop', () => {
  assert.equal(modeAfterReset('sim'), 'tabletop');
  assert.equal(modeAfterReset('camera'), 'tabletop');
  assert.equal(modeAfterReset(), 'tabletop');
});

test('Camera twin shows in the toggle and can be hidden by the constant', () => {
  assert.equal(CAMERA_TWIN_ENABLED, true);
  assert.deepEqual(visibleModes(), ['tabletop', 'camera', 'sim']);
  assert.deepEqual(visibleModes(false), ['tabletop', 'sim']);
});

test('the mode control is locked while an analysis runs', () => {
  assert.equal(canSwitchMode(true), false);
  assert.equal(canSwitchMode(false), true);
});
