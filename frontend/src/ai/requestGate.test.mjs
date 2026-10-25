import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequestGate } from './requestGate.ts';

test('a second activation cannot start work before busy state renders', () => {
  const gate = createRequestGate();
  const token = gate.start();
  assert.notEqual(token, null);
  assert.equal(gate.start(), null);
  gate.finish(token);
  assert.notEqual(gate.start(), null);
});

test('late completion after a reset cannot release the new request', () => {
  const gate = createRequestGate();
  const oldToken = gate.start();
  gate.invalidate();
  const currentToken = gate.start();
  assert.notEqual(currentToken, oldToken);
  assert.equal(gate.isCurrent(oldToken), false);
  gate.finish(oldToken);
  assert.equal(gate.isCurrent(currentToken), true);
  assert.equal(gate.start(), null);
  gate.finish(currentToken);
  assert.notEqual(gate.start(), null);
});

test('preparation failure releases the guard for a retry', async () => {
  const gate = createRequestGate();
  const token = gate.start();
  try { await Promise.reject(new Error('Image could not decode')); }
  catch { /* The UI renders its preparation error. */ }
  finally { gate.finish(token); }
  assert.notEqual(gate.start(), null);
});
