import assert from 'node:assert/strict';
import test from 'node:test';
import { modeAfterReset } from './resetFlow.ts';
import { canSwitchMode, CAMERA_TWIN_ENABLED, visibleModes } from '../twin/modes.ts';

test('Next judge always returns to Act 1 (Build)', () => {
  assert.equal(modeAfterReset('tabletop'), 'build');
  assert.equal(modeAfterReset('sim'), 'build');
  assert.equal(modeAfterReset(), 'build');
});

test('Camera twin shows in the toggle and can be hidden by the constant', () => {
  assert.equal(CAMERA_TWIN_ENABLED, true);
  assert.deepEqual(visibleModes(), ['build', 'sim', 'camera', 'tabletop']);
  assert.deepEqual(visibleModes(false), ['build', 'sim', 'tabletop']);
});

test('the mode control is locked while an analysis runs', () => {
  assert.equal(canSwitchMode(true), false);
  assert.equal(canSwitchMode(false), true);
});
