import assert from 'node:assert/strict';
import test from 'node:test';
import { DOUBT_AMOUNT, gateAmount, TRANSIT_CAP } from './gateDraw.ts';

test('only an observed endpoint draws a gate fully open or closed', () => {
  assert.equal(gateAmount({ draw: 'open', since: null, transitMs: 1750 }, 0), 1);
  assert.equal(gateAmount({ draw: 'closed', since: null, transitMs: 1750 }, 0), 0);
  // Long after the expected transit, a gate still "opening" (ACK, no endpoint) stops short of open.
  assert.equal(gateAmount({ draw: 'opening', since: 0, transitMs: 1750 }, 60_000), TRANSIT_CAP);
  assert.ok(gateAmount({ draw: 'closing', since: 0, transitMs: 1750 }, 60_000) > 0);
});

test('transit follows the controller clock from the command time', () => {
  assert.equal(gateAmount({ draw: 'opening', since: 1000, transitMs: 2000 }, 2000), 0.5);
  assert.equal(gateAmount({ draw: 'closing', since: 1000, transitMs: 2000 }, 2000), 0.5);
  assert.equal(gateAmount({ draw: 'opening', since: null, transitMs: 2000 }, 2000), 0);
});

test('a faulted or unknown gate is frozen mid-way, never read as open or closed', () => {
  for (const draw of ['unknown', 'fault']) assert.equal(gateAmount({ draw, since: 0, transitMs: 1750 }, 500), DOUBT_AMOUNT);
});
