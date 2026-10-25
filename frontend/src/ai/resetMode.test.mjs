import assert from 'node:assert/strict';
import test from 'node:test';
import { modeAfterReset } from './resetFlow.ts';
import { canSwitchMode, CAMERA_TWIN_ENABLED, visibleModes } from '../twin/modes.ts';

test('Next judge always returns to the building twin', () => {
  assert.equal(modeAfterReset('tabletop'), 'sim');
  assert.equal(modeAfterReset('camera'), 'sim');
  assert.equal(modeAfterReset(), 'sim');
});

test('Camera twin shows in the toggle and can be hidden by the constant', () => {
  assert.equal(CAMERA_TWIN_ENABLED, true);
  assert.deepEqual(visibleModes(), ['sim', 'camera', 'tabletop']);
  assert.deepEqual(visibleModes(false), ['sim', 'tabletop']);
});

test('the mode control is locked while an analysis runs', () => {
  assert.equal(canSwitchMode(true), false);
  assert.equal(canSwitchMode(false), true);
});
