import assert from 'node:assert/strict';
import test from 'node:test';
import { createReadFlow } from './cameraFlow.ts';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));

function harness(run) {
  const states = [];
  const flow = createReadFlow({ run, onState: state => states.push(state) });
  return { flow, states };
}

test('a read completes into done', async () => {
  const { flow } = harness(async () => ({ read_id: 'r1' }));
  assert.equal(await flow.start(), true);
  assert.equal(flow.state().phase, 'done');
  assert.deepEqual(flow.state().result, { read_id: 'r1' });
});

test('a second start while reading is refused', async () => {
  let finish;
  const { flow } = harness(() => new Promise(resolve => { finish = () => resolve({}); }));
  const first = flow.start();
  assert.equal(await flow.start(), false);
  finish();
  assert.equal(await first, true);
});

test('a response after reset is dropped and the state stays idle', async () => {
  let finish;
  const { flow } = harness(() => new Promise(resolve => { finish = () => resolve({ read_id: 'late' }); }));
  const pending = flow.start();
  flow.reset();
  finish();
  assert.equal(await pending, false);
  assert.equal(flow.state().phase, 'idle');
  assert.equal(flow.state().result, null);
});

test('an error after reset is dropped too, and a new read works', async () => {
  let fail;
  const { flow } = harness(() => new Promise((_resolve, reject) => { fail = () => reject(new Error('late')); }));
  const pending = flow.start();
  flow.reset();
  fail();
  await pending;
  assert.equal(flow.state().phase, 'idle');
  const second = createReadFlow({ run: async () => 1, onState: () => undefined });
  assert.equal(await second.start(), true);
});

test('reset aborts the request in flight', async () => {
  let signal;
  const { flow } = harness(s => { signal = s; return new Promise(() => undefined); });
  void flow.start();
  await wait(5);
  flow.reset();
  assert.equal(signal.aborted, true);
  assert.equal(flow.state().phase, 'idle');
});

test('a failed read reports the error and can be retried', async () => {
  let fail = true;
  const { flow } = harness(async () => { if (fail) throw new Error('Gemini took too long. Read again.'); return { ok: 1 }; });
  assert.equal(await flow.start(), false);
  assert.equal(flow.state().phase, 'error');
  assert.equal(flow.state().error, 'Gemini took too long. Read again.');
  fail = false;
  assert.equal(await flow.start(), true);
});
