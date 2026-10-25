import assert from 'node:assert/strict';
import test from 'node:test';
import { createTwinFlow } from './twinFlow.ts';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const hazard = id => ({ id, type: 'FIRE', position: { x: 1, y: 1 }, source: 'simulated' });

function harness(fetchImpl, debounceMs = 15) {
  const states = [];
  const accepted = [];
  const calls = [];
  const flow = createTwinFlow({
    fetchPlan: (hazards, signal) => { calls.push({ hazards, signal }); return fetchImpl(hazards, signal, calls.length); },
    onState: state => states.push(state),
    onPlan: (plan) => accepted.push(plan),
    debounceMs,
  });
  return { flow, states, accepted, calls };
}

test('rapid changes collapse into one request after the debounce', async () => {
  const { flow, calls, accepted } = harness(async hazards => ({ n: hazards.length }));
  flow.request([hazard('a')]);
  flow.request([hazard('a'), hazard('b')]);
  flow.request([hazard('a'), hazard('b'), hazard('c')]);
  assert.equal(calls.length, 0);
  await wait(60);
  assert.equal(calls.length, 1);
  assert.deepEqual(accepted, [{ n: 3 }]);
  assert.equal(flow.state().status, 'ready');
});

test('a newer request aborts the one in flight and its late response is dropped', async () => {
  const resolvers = [];
  const { flow, calls, accepted } = harness((hazards, signal) => new Promise((resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')));
    resolvers.push(() => resolve({ n: hazards.length }));
  }));
  flow.request([hazard('a')], { immediate: true });
  flow.request([hazard('a'), hazard('b')], { immediate: true });
  assert.equal(calls[0].signal.aborted, true);
  assert.equal(calls[1].signal.aborted, false);
  resolvers[0]?.();
  resolvers[1]();
  await wait(10);
  assert.deepEqual(accepted, [{ n: 2 }]);
});

test('a response that arrives after reset is dropped and the state stays idle', async () => {
  let finish;
  const { flow, accepted, states } = harness(() => new Promise(resolve => { finish = () => resolve({ n: 1 }); }));
  flow.request([hazard('a')], { immediate: true });
  flow.reset();
  finish();
  await wait(10);
  assert.deepEqual(accepted, []);
  assert.equal(flow.state().status, 'idle');
  assert.equal(flow.state().plan, null);
  assert.equal(states.at(-1).status, 'idle');
});

test('reset cancels a debounce that has not fired yet', async () => {
  const { flow, calls } = harness(async () => ({}));
  flow.request([hazard('a')]);
  flow.reset();
  await wait(50);
  assert.equal(calls.length, 0);
});

test('a request made after reset still works (new epoch)', async () => {
  const { flow, accepted } = harness(async hazards => ({ n: hazards.length }));
  flow.request([hazard('a')], { immediate: true });
  flow.reset();
  flow.request([hazard('a'), hazard('b')], { immediate: true });
  await wait(10);
  assert.deepEqual(accepted, [{ n: 2 }]);
});

test('the previous plan stays while the next one is pending; errors keep it too', async () => {
  let fail = false;
  const { flow } = harness(async () => { if (fail) throw new Error('Up to 6 hazards'); return { ok: 1 }; });
  flow.request([], { immediate: true });
  await wait(10);
  flow.request([hazard('a')], { immediate: true });
  assert.equal(flow.state().status, 'pending');
  assert.deepEqual(flow.state().plan, { ok: 1 });
  await wait(10);
  fail = true;
  flow.request([hazard('b')], { immediate: true });
  await wait(10);
  assert.equal(flow.state().status, 'error');
  assert.equal(flow.state().error, 'Up to 6 hazards');
  assert.deepEqual(flow.state().plan, { ok: 1 });
});

test('an aborted request never reports an error', async () => {
  const { flow, states } = harness((_h, signal) => new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('aborted')))));
  flow.request([hazard('a')], { immediate: true });
  flow.reset();
  await wait(10);
  assert.ok(states.every(state => state.status !== 'error'));
});
