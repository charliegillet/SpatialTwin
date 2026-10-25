import test from 'node:test';
import assert from 'node:assert/strict';
import { getActivityView, pauseActivity } from './interactions.ts';

test('paused activity stays frozen while new events buffer; resuming reveals the current stream', () => {
  const original = [{ id: 1, message: 'Scenario accepted' }, { id: 2, message: 'Checked result' }];
  const held = pauseActivity(original);
  const live = [...original, { id: 3, message: 'Endpoint observed' }];
  assert.deepEqual(getActivityView(live, held).events, original);
  assert.equal(getActivityView(live, held).bufferedCount, 1);
  assert.deepEqual(getActivityView(live, null).events, live);
});

test('parent buffer rollover and array changes cannot alter the paused display', () => {
  const original = [{ id: 1 }, { id: 2 }];
  const held = pauseActivity(original);
  original.push({ id: 3 });
  const rolledBuffer = [{ id: 2 }, { id: 3 }, { id: 4 }];
  assert.deepEqual(getActivityView(rolledBuffer, held).events, [{ id: 1 }, { id: 2 }]);
  assert.equal(getActivityView(rolledBuffer, held).bufferedCount, 2);
  assert.deepEqual(getActivityView(rolledBuffer, null).events, rolledBuffer);
});

test('clearing a paused display holds it empty until resume while recording subsequent events', () => {
  const held = pauseActivity([]);
  assert.deepEqual(getActivityView([], held), { events: [], bufferedCount: 0 });
  const incoming = [{ id: 8, message: 'New scenario after clear' }];
  assert.deepEqual(getActivityView(incoming, held), { events: [], bufferedCount: 1 });
  assert.deepEqual(getActivityView(incoming, null).events, incoming);
});
