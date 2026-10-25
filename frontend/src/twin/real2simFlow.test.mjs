import assert from 'node:assert/strict';
import test from 'node:test';
import { createReal2SimFlow, MAX_THOUGHTS, isRunning } from './real2simFlow.ts';
import { ApiError } from '../api/client.ts';
import { parseDraftView } from '../api/real2sim.ts';
import { DRAFT_ID, LIVE_EVENTS, acceptResponse, makeView } from './real2simFixture.ts';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const tick = () => wait(0);

class FakeSource {
  constructor(id) { this.id = id; this.listeners = {}; this.closed = false; }
  addEventListener(type, fn) { (this.listeners[type] ??= []).push(fn); }
  close() { this.closed = true; }
  /** Delivers like a browser would, even after close() if the test asks (queued events). */
  emit(name, data, { force = false } = {}) {
    if (this.closed && !force) return;
    for (const fn of this.listeners[name] ?? []) fn({ data: typeof data === 'string' ? data : JSON.stringify(data) });
  }
  connectionError() { for (const fn of this.listeners.error ?? []) fn({}); }
}

function harness(overrides = {}) {
  const sources = [];
  const states = [];
  const calls = { create: [], fetch: [], accept: [] };
  const deps = {
    createDraft: async request => { calls.create.push(request); return { draft_id: DRAFT_ID, revision: 1, status: 'extracting' }; },
    fetchDraft: async id => { calls.fetch.push(id); return parseDraftView(makeView()); },
    acceptDraft: async (id, request) => { calls.accept.push([id, request]); return acceptResponse(); },
    openEvents: id => { const source = new FakeSource(id); sources.push(source); return source; },
    onState: state => states.push(state),
    pollMs: 5,
    ...overrides,
  };
  const flow = createReal2SimFlow(deps);
  return { flow, sources, states, calls, last: () => flow.getState() };
}

const play = (source, events) => { for (const [name, body] of events) source.emit(name, body); };
const live = { mode: 'live', image_base64: 'AAAA', mime_type: 'image/png', source_kind: 'photo' };

test('a recorded live sequence walks idle -> uploading -> extracting -> checking -> critiquing -> ready', async () => {
  const { flow, sources, last, calls } = harness();
  assert.equal(last().stage, 'idle');
  const started = flow.startLive(async () => live);
  assert.equal(last().stage, 'uploading');
  assert.ok(isRunning(last().stage));
  await started;
  assert.equal(last().stage, 'extracting');
  assert.equal(last().draftId, DRAFT_ID);
  assert.deepEqual(calls.create, [live]);
  assert.equal(sources.length, 1);
  assert.equal(last().transport, 'sse');

  const seen = [];
  const original = sources[0].emit.bind(sources[0]);
  for (const [name, body] of LIVE_EVENTS.slice(0, -1)) { original(name, body); seen.push(last().stage); }
  assert.deepEqual(seen.filter((stage, i) => stage !== seen[i - 1]), ['extracting', 'checking', 'critiquing', 'ready'].filter(stage => stage !== 'ready'));
  assert.equal(last().stage, 'critiquing');
  assert.deepEqual(last().thoughts.map(t => t.text), ['**Reading the walls** first.', 'Found three exits.', 'Add a door to the bath.']);
  assert.deepEqual(last().counts, { rooms: 9, doors: 11, exits: 4 });
  assert.equal(last().rounds.length, 1);
  assert.equal(last().checks.errors, 0);
  assert.deepEqual(last().unreadable, []);

  original(...LIVE_EVENTS.at(-1));
  await tick();
  assert.equal(last().stage, 'ready');
  assert.equal(sources[0].closed, true, 'closes the EventSource on done');
  assert.equal(last().view.draft_id, DRAFT_ID);
  assert.equal(last().provenanceLabel.startsWith('Live Gemini 4 Argon'), true);
  assert.equal(last().finishedAt !== null, true);
});

test('thoughts are appended once, bounded, and capped in length', async () => {
  const { flow, sources, last } = harness();
  await flow.startLive(async () => live);
  const source = sources[0];
  source.emit('thought', { phase: 'extract', index: 0, text: 'same', recorded: false });
  source.emit('thought', { phase: 'extract', index: 0, text: 'same', recorded: false });
  assert.equal(last().thoughts.length, 1);
  for (let i = 1; i < MAX_THOUGHTS + 30; i += 1) source.emit('thought', { phase: 'extract', index: i, text: 'x'.repeat(3000), recorded: false });
  assert.equal(last().thoughts.length, MAX_THOUGHTS);
  assert.equal(last().thoughts.at(-1).text.length, 1500);
  assert.equal(last().thoughts.at(-1).id, `extract:${MAX_THOUGHTS + 29}`);
});

test('malformed events are skipped and do not break the stream', async () => {
  const { flow, sources, last } = harness();
  await flow.startLive(async () => live);
  sources[0].emit('status', 'not json');
  sources[0].emit('thought', { text: 5 });
  sources[0].emit('checks', { issues: 'x' });
  sources[0].emit('thought', { phase: 'extract', index: 0, text: 'ok', recorded: false });
  assert.equal(last().thoughts.length, 1);
  assert.equal(last().stage, 'extracting');
});

test('a server error event fails the draft with judge copy and closes the stream', async () => {
  const { flow, sources, last } = harness({ fetchDraft: async () => parseDraftView(makeView({ status: 'failed', errors: ['provider_timeout'], draft: null })) });
  await flow.startLive(async () => live);
  sources[0].emit('error', { draft_id: DRAFT_ID, status: 'failed', revision: 2, code: 'provider_timeout', provenance: 'live' });
  await tick();
  assert.equal(last().stage, 'failed');
  assert.equal(last().errorCode, 'provider_timeout');
  assert.match(last().error, /took too long/);
  assert.equal(sources[0].closed, true);
  // A failed live reading stays failed: no saved run is substituted.
  assert.equal(last().accepted, null);
});

test('the server error code wins even if the follow-up view fetch fails', async () => {
  const { flow, sources, last } = harness({ fetchDraft: async () => { throw new ApiError('down', 500); } });
  await flow.startLive(async () => live);
  sources[0].emit('error', { code: 'provider_rate_limited', revision: 2 });
  await tick();
  assert.equal(last().stage, 'failed');
  assert.equal(last().errorCode, 'provider_rate_limited');
});

test('create failures surface the ApiError copy (busy, not configured)', async () => {
  for (const [status, code, message] of [[429, 'real2sim_busy', 'Another reading is running.'], [503, 'configuration_missing', 'Gemini is not configured on this server. Use a saved run instead.']]) {
    const { flow, last, sources } = harness({ createDraft: async () => { throw new ApiError(message, status, code); } });
    await flow.startLive(async () => live);
    assert.equal(last().stage, 'failed');
    assert.equal(last().errorCode, code);
    assert.equal(last().error, message);
    assert.equal(sources.length, 0);
  }
});

test('a failing file preparation fails cleanly and never calls the server', async () => {
  const { flow, last, calls } = harness();
  await flow.startLive(async () => { throw new ApiError('That file is over 8 MB. Use a smaller photo.', 413, 'source_too_large'); });
  assert.equal(last().stage, 'failed');
  assert.equal(last().errorCode, 'source_too_large');
  assert.equal(calls.create.length, 0);
});

test('saved runs create in fixture mode', async () => {
  const { flow, calls, last } = harness({ fetchDraft: async () => parseDraftView(makeView({ status: 'ready', provenance: 'synthetic', provenance_label: 'Synthetic saved run: x' })) });
  await flow.startSaved('sketch-home', 'Home');
  assert.deepEqual(calls.create, [{ mode: 'fixture', fixture_id: 'sketch-home', name: 'Home' }]);
  await tick();
  assert.equal(last().provenanceLabel, 'Synthetic saved run: x');
});

test('Start over invalidates the stream: late events and responses cannot repopulate state', async () => {
  const { flow, sources, last } = harness();
  await flow.startLive(async () => live);
  const stale = sources[0];
  stale.emit('thought', { phase: 'extract', index: 0, text: 'before', recorded: false });
  flow.reset();
  assert.equal(last().stage, 'idle');
  assert.equal(stale.closed, true);
  // Events already queued in the browser after close() are delivered anyway: the epoch drops them.
  stale.emit('thought', { phase: 'extract', index: 1, text: 'late', recorded: false }, { force: true });
  stale.emit('status', { status: 'checking', revision: 9, provenance: 'live' }, { force: true });
  stale.emit('done', { revision: 9, errors: 0, warnings: 0 }, { force: true });
  await tick();
  assert.equal(last().stage, 'idle');
  assert.deepEqual(last().thoughts, []);
  assert.equal(last().draftId, null);
});

test('a slow create response after Start over is ignored', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const { flow, sources, last } = harness({ createDraft: async () => { await gate; return { draft_id: DRAFT_ID, revision: 1, status: 'extracting' }; } });
  const started = flow.startLive(async () => live);
  flow.reset();
  release();
  await started;
  assert.equal(last().stage, 'idle');
  assert.equal(sources.length, 0);
});

test('starting a second run supersedes the first stream', async () => {
  const { flow, sources, last } = harness();
  await flow.startLive(async () => live);
  await flow.startSaved('evac-office');
  assert.equal(sources.length, 2);
  assert.equal(sources[0].closed, true);
  sources[0].emit('thought', { phase: 'extract', index: 0, text: 'old', recorded: false }, { force: true });
  assert.deepEqual(last().thoughts, []);
});

test('a connection error falls back to polling every interval until the draft is ready', async () => {
  const views = [makeView({ status: 'extracting', draft: null, thoughts: [] }), makeView({ status: 'checking', thoughts: [{ phase: 'extract', text: 'polled', recorded: false }] }), makeView({ status: 'ready', thoughts: [{ phase: 'extract', text: 'polled', recorded: false }] })];
  let n = 0;
  const { flow, sources, last, calls } = harness({ fetchDraft: async () => { calls.fetch.push('x'); return parseDraftView(views[Math.min(n++, views.length - 1)]); } });
  await flow.startLive(async () => live);
  await tick();
  const before = calls.fetch.length;
  sources[0].connectionError();
  assert.equal(last().transport, 'polling');
  assert.equal(sources[0].closed, true);
  await wait(80);
  assert.equal(last().stage, 'ready');
  assert.ok(calls.fetch.length > before);
  const afterReady = calls.fetch.length;
  await wait(30);
  assert.equal(calls.fetch.length, afterReady, 'polling stops once ready');
  assert.equal(last().thoughts[0].text, 'polled');
  assert.deepEqual(last().counts, { rooms: 2, doors: 1, exits: 1 });
});

test('polling reports a failed draft and gives up on 404 or repeated failures', async () => {
  const failed = harness({ fetchDraft: async () => parseDraftView(makeView({ status: 'failed', errors: ['pipeline_interrupted'], draft: null })) });
  await failed.flow.startLive(async () => live);
  failed.sources[0].connectionError();
  await wait(40);
  assert.equal(failed.last().stage, 'failed');
  assert.match(failed.last().error, /restarted/);

  let created = false;
  const gone = harness({ fetchDraft: async () => { if (!created) { created = true; return parseDraftView(makeView({ status: 'extracting' })); } throw new ApiError('x', 404, 'unknown_draft'); } });
  await gone.flow.startLive(async () => live);
  gone.sources[0].connectionError();
  await wait(40);
  assert.equal(gone.last().stage, 'failed');
  assert.equal(gone.last().errorCode, 'unknown_draft');

  let first = true;
  const flaky = harness({ fetchDraft: async () => { if (first) { first = false; return parseDraftView(makeView({ status: 'extracting' })); } throw new ApiError('down', 500); } });
  await flaky.flow.startLive(async () => live);
  flaky.sources[0].connectionError();
  await wait(80);
  assert.equal(flaky.last().stage, 'failed');
  assert.equal(flaky.last().errorCode, 'view_unavailable');
});

test('polling is cancelled by Start over', async () => {
  const { flow, sources, last, calls } = harness({ fetchDraft: async () => parseDraftView(makeView({ status: 'checking' })) });
  await flow.startLive(async () => live);
  sources[0].connectionError();
  await wait(12);
  flow.reset();
  const count = calls.fetch.length;
  await wait(40);
  assert.equal(calls.fetch.length, count);
  assert.equal(last().stage, 'idle');
});

async function readyHarness(extra = {}) {
  const h = harness(extra);
  await h.flow.startLive(async () => live);
  h.sources[0].emit('done', { revision: 3, errors: 0, warnings: 1 });
  await tick();
  assert.equal(h.last().stage, 'ready');
  return h;
}

test('Accept sends the current revision and choices, then lands on accepted', async () => {
  const { flow, last, calls } = await readyHarness();
  await flow.accept({ controllableDoors: ['KD1', 'KD2'], headcount: 40, buildingWidthM: 24 });
  assert.equal(last().stage, 'accepted');
  assert.equal(last().accepted.venue_id, 'meridian-level-1-24a745');
  assert.deepEqual(calls.accept[0], [DRAFT_ID, { expected_revision: 3, controllable_doors: ['KD1', 'KD2'], make_active: true, headcount: 40, building_width_m: 24 }]);
});

test('Accept omits empty optional fields', async () => {
  const { flow, calls } = await readyHarness();
  await flow.accept({ controllableDoors: [], makeActive: false });
  assert.deepEqual(calls.accept[0][1], { expected_revision: 3, controllable_doors: [], make_active: false });
});

test('more than 3 controllable doors never reaches the server', async () => {
  const { flow, last, calls } = await readyHarness();
  await flow.accept({ controllableDoors: ['KD1', 'KD2', 'KD3', 'KD4'] });
  assert.equal(calls.accept.length, 0);
  assert.equal(last().stage, 'ready');
  assert.match(last().acceptError, /at most 3/);
});

test('Accept is ignored unless the draft is ready (double click, wrong stage)', async () => {
  const idle = harness();
  await idle.flow.accept({ controllableDoors: [] });
  assert.equal(idle.calls.accept.length, 0);
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const { flow, calls, last } = await readyHarness({ acceptDraft: async () => { await gate; return acceptResponse(); } });
  const first = flow.accept({ controllableDoors: [] });
  assert.equal(last().stage, 'accepting');
  await flow.accept({ controllableDoors: [] });
  release();
  await first;
  assert.equal(last().stage, 'accepted');
  assert.equal(calls.fetch.length >= 1, true);
});

test('a stale revision (409) refreshes the view and the next Accept uses the new revision', async () => {
  let revision = 3;
  let acceptCalls = 0;
  const { flow, last, calls } = await readyHarness({
    fetchDraft: async () => parseDraftView(makeView({ revision })),
    acceptDraft: async (id, request) => {
      acceptCalls += 1;
      calls.accept.push([id, request]);
      if (acceptCalls === 1) { revision = 5; throw new ApiError('The draft changed while you were reviewing it.', 409, 'stale_draft_revision'); }
      return acceptResponse();
    },
  });
  await flow.accept({ controllableDoors: ['KD1'] });
  assert.equal(last().stage, 'ready');
  assert.equal(last().revision, 5);
  assert.match(last().acceptNotice, /changed/);
  assert.equal(last().acceptError, null);
  await flow.accept({ controllableDoors: ['KD1'] });
  assert.equal(calls.accept[1][1].expected_revision, 5);
  assert.equal(last().stage, 'accepted');
});

test('409 on a draft that is no longer ready settles to the server status', async () => {
  let closed = false;
  const { flow, last } = await readyHarness({
    fetchDraft: async () => parseDraftView(closed ? makeView({ status: 'accepted', accepted: { venue_id: 'other-venue' } }) : makeView()),
    acceptDraft: async () => { closed = true; throw new ApiError('closed', 409, 'draft_closed'); },
  });
  await flow.accept({ controllableDoors: [] });
  assert.equal(last().stage, 'accepted');
});

test('a 422 keeps the draft ready with the reason, ready to retry', async () => {
  const { flow, last } = await readyHarness({ acceptDraft: async () => { throw new ApiError('The building checks still report errors, so it cannot be accepted.', 422, 'graph_check_errors'); } });
  await flow.accept({ controllableDoors: [] });
  assert.equal(last().stage, 'ready');
  assert.match(last().acceptError, /cannot be accepted/);
});

test('Start over after accepting clears everything; a late accept response is ignored', async () => {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const { flow, last } = await readyHarness({ acceptDraft: async () => { await gate; return acceptResponse(); } });
  const pending = flow.accept({ controllableDoors: [] });
  flow.reset();
  release();
  await pending;
  assert.equal(last().stage, 'idle');
  assert.equal(last().accepted, null);
});

test('dispose stops all work without publishing again', async () => {
  const { flow, sources, states } = harness();
  await flow.startLive(async () => live);
  const count = states.length;
  flow.dispose();
  sources[0].emit('thought', { phase: 'extract', index: 0, text: 'late', recorded: false }, { force: true });
  await tick();
  assert.equal(states.length, count);
  assert.equal(sources[0].closed, true);
});
