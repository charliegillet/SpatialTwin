import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../api/client.ts';
import { isParentFinishing, parseTeamProgress, parseTraceEvent } from '../api/agentTeam.ts';
import {
  CANCEL_RESERVE_MS, MAX_TRACE_LINES, applyProgress, applyStart, askAvailability, beginRun, cancelRun, countdownLabel, createTeamRunner, createTraceConnection, followUpSuggestions,
  followUpUnavailable, giveUpAt, hazardsKeyOf, idleRun, isActive, normalizeScenario, reduceTrace, remainingSeconds, resolveDeadline, withRetry,
} from './agentTeamFlow.ts';
import { TRACE_EVENT_NAMES } from './agentTeamTypes.ts';

const NOW = 1_000_000;
const start = (over = {}) => ({
  investigation_id: 'dinv-1', deadline_at_ms: NOW + 150_000, trace_url: '/trace',
  lanes: {
    strategist: { investigation_id: 'dinv-1.strategist', deadline_seconds: 45, deadline_at_ms: NOW + 45_000 },
    robustness: { investigation_id: 'dinv-1.robustness', deadline_seconds: 150, deadline_at_ms: NOW + 150_000 },
  }, ...over,
});
const running = (over = {}) => applyStart(beginRun({ mode: 'live', hazardsKey: 'k', now: NOW, lanes: ['strategist', 'robustness'] }), start(over), NOW);

let seqCounter = 0;
const ev = (event, lane, data = {}, seq = ++seqCounter) => ({ seq, event, lane, elapsed_ms: seq * 10, data: { seq, event, lane, elapsed_ms: seq * 10, ...data } });
const feed = (run, events, now = NOW) => events.reduce((state, event) => reduceTrace(state, event, now), run);

const check = (over = {}) => ({ index: 0, scenario: 'baseline', applies_to: 'recommended', claimed_completed_crossings: 18, local_completed_crossings: 18, local_is_valid: true, reproduced: true, reason: null, ...over });
const view = (lane, over = {}) => ({
  investigation_id: `dinv-1.${lane}`, lane, status: 'completed', provenance: 'live', recommended_door_states: { D4: 'open', D9: 'open' }, fallback_if_jammed: { D4: 'open', D9: 'closed' },
  verification: { verified: 2, total: 2, source: 'sandbox', mismatches: [] }, errors: [], ...over,
});

// A recorded two-lane live run: the Strategist finishes first; the Robustness lane runs sandbox code, fails, and falls back to the local solver.
const recorded = () => {
  seqCounter = 0;
  return [
    ev('deadline', null, { lanes: { strategist: { deadline_at_ms: NOW + 45_000, deadline_seconds: 45 }, robustness: { deadline_at_ms: NOW + 150_000, deadline_seconds: 150 } } }),
    ev('lane', 'strategist', { status: 'started', mode: 'live', token_budget: 40000 }),
    ev('lane', 'robustness', { status: 'started', mode: 'live', token_budget: 150000 }),
    ev('lane', 'strategist', { status: 'plan_ready', states_checked: 4 }),
    ev('status', 'strategist', { status: 'in_progress' }),
    ev('step', 'strategist', { kind: 'step', index: 0, step_type: 'function_call', name: 'plan_doors', text: '{"hazard":"h0"}' }),
    ev('tool', 'strategist', { function_name: 'plan_doors', status: 'executed', execution_time_ms: 15.4 }),
    ev('step', 'robustness', { kind: 'step', index: 0, step_type: 'thought', text: 'SECRET' }),
    ev('delta', 'robustness', { kind: 'step_start', index: 1, step_type: 'code_execution_call' }),
    ev('delta', 'robustness', { kind: 'delta', index: 1, step_type: 'code_execution_call', text: 'import json\nrun_sweep(' }),
    ev('step', 'robustness', { kind: 'step', index: 1, step_type: 'code_execution_call', text: 'import json\nrun_sweep()' }),
    ev('step', 'robustness', { kind: 'step', index: 2, step_type: 'code_execution_result', text: 'holds 8 of 16' }),
    ev('usage', 'strategist', { token_usage: { total_tokens: 12000 }, token_budget: 40000, cost_estimate: { usd: 0.03, input_tokens: 9000, output_tokens: 3000 } }),
    ev('verification', 'strategist', { verified: 2, total: 2, source: 'agent', mismatches: [] }),
    ev('result', 'strategist', view('strategist')),
    ev('fallback', 'robustness', { reason: { investigation_id: 'dinv-1.robustness', status: 'failed', errors: ['provider_timeout'] } }),
    ev('lane', 'robustness', { status: 'started', fallback_for: { status: 'failed' } }),
    ev('result', 'robustness', view('robustness', { provenance: 'local', verification: { verified: 12, total: 12, source: 'local', mismatches: [] }, fallback_for: { investigation_id: 'dinv-1.robustness', status: 'failed', errors: ['provider_timeout'] } })),
    ev('done', null, { team_status: 'finished' }),
  ];
};

test('a recorded two-lane run ends done with the failed live lane kept beside its local fallback', () => {
  const run = feed(running(), recorded());
  assert.equal(run.status, 'done');
  assert.equal(run.connection, 'closed');
  assert.equal(run.lanes.strategist.phase, 'completed');
  assert.equal(run.lanes.strategist.usage.cost_estimate.usd, 0.03);
  assert.equal(run.lanes.strategist.statesChecked, 4);
  assert.equal(run.lanes.robustness.fallbackView.provenance, 'local');
  assert.deepEqual(run.lanes.robustness.fallbackReason.errors, ['provider_timeout']);
  assert.equal(run.lanes.robustness.phase, 'completed');
  // The delta-built code cell was replaced by its durable step, not duplicated, and the thought step left no line.
  const code = run.lanes.robustness.trace.filter(line => line.kind === 'code');
  assert.equal(code.length, 1);
  assert.equal(code[0].partial, undefined);
  assert.equal(code[0].text, 'import json\nrun_sweep()');
  assert.ok(!JSON.stringify(run.lanes.robustness.trace).includes('SECRET'));
  assert.ok(run.lanes.strategist.trace.some(line => line.kind === 'call' && line.name === 'plan_doors'));
  assert.ok(run.lanes.strategist.trace.some(line => line.kind === 'tool' && /15 ms/.test(line.text)));
});

test('frames are deduplicated by seq, so a reconnect replay changes nothing', () => {
  const events = recorded();
  const once = feed(running(), events.slice(0, 8));
  const replayed = feed(once, events.slice(0, 8));
  assert.equal(replayed, once);
  assert.equal(once.lastSeq, events[7].seq);
});

test('a status line keeps only the latest provider status', () => {
  const run = feed(running(), [ev('status', 'strategist', { status: 'in_progress' }), ev('status', 'strategist', { status: 'in_progress' }), ev('status', 'strategist', { status: 'requires_action' })]);
  const lines = run.lanes.strategist.trace.filter(line => line.kind === 'status');
  assert.deepEqual(lines.map(line => line.text), ['requires_action']);
});

test('the trace is bounded and counts what fell off', () => {
  const events = Array.from({ length: MAX_TRACE_LINES + 25 }, (_, i) => ev('step', 'robustness', { kind: 'step', index: i, step_type: 'model_output', text: `line ${i}` }));
  const run = feed(running(), events);
  assert.equal(run.lanes.robustness.trace.length, MAX_TRACE_LINES);
  assert.equal(run.lanes.robustness.droppedLines, 25);
  assert.equal(run.lanes.robustness.trace.at(-1).text, `line ${MAX_TRACE_LINES + 24}`);
});

test('a cancelled done frame marks unfinished lanes cancelled', () => {
  seqCounter = 0;
  const run = feed(running(), [ev('lane', 'strategist', { status: 'started' }), ev('done', null, { team_status: 'cancelled' })]);
  assert.equal(run.status, 'cancelled');
  assert.equal(run.lanes.strategist.phase, 'cancelled');
});

test('frames before the run is running, or after it ended, are ignored', () => {
  seqCounter = 0;
  const starting = beginRun({ mode: 'live', hazardsKey: 'k', now: NOW, lanes: ['strategist'] });
  assert.equal(reduceTrace(starting, ev('lane', 'strategist', { status: 'started' }), NOW), starting);
  const ended = cancelRun(running());
  assert.equal(reduceTrace(ended, ev('result', 'strategist', view('strategist')), NOW), ended);
});

test('polled progress is authoritative: nested fallback, effective lane, and a finished team', () => {
  const progress = parseTeamProgress({
    investigation_id: 'dinv-1', status: 'completed', team_status: 'finished', deadline_at_ms: NOW,
    lanes: {
      strategist: view('strategist'),
      robustness: view('robustness', { status: 'failed', effective: 'local_fallback', errors: ['investigation_deadline'], fallback: view('robustness', { provenance: 'local', verification: { verified: 12, total: 12, source: 'local', mismatches: [] } }) }),
    },
  });
  const run = applyProgress(running(), progress, NOW);
  assert.equal(run.status, 'done');
  assert.equal(run.lanes.robustness.phase, 'completed');
  assert.equal(run.lanes.robustness.view.status, 'failed');
  assert.equal(run.lanes.robustness.fallbackView.provenance, 'local');
  assert.deepEqual(run.lanes.robustness.fallbackReason.errors, ['investigation_deadline']);
  assert.equal(run.lanes.robustness.verification.source, 'local');
});

test('polled progress with a lane still running keeps the team running', () => {
  const progress = parseTeamProgress({
    investigation_id: 'dinv-1', status: 'running', team_status: 'running', deadline_at_ms: NOW,
    lanes: { strategist: view('strategist'), robustness: { investigation_id: 'dinv-1.robustness', lane: 'robustness', status: 'running' } },
  });
  const run = applyProgress(running(), progress, NOW);
  assert.equal(run.status, 'running');
  assert.equal(run.lanes.strategist.phase, 'completed');
  assert.equal(run.lanes.robustness.phase, 'running');
});

// --- deadlines -----------------------------------------------------------------------------------------------

test('deadline math: server deadline, skew correction, countdown and give-up', () => {
  assert.equal(resolveDeadline(NOW + 45_000, 45, NOW), NOW + 45_000);
  assert.equal(resolveDeadline(NOW + 45_000 + 120_000, 45, NOW), NOW + 45_000, 'a server clock two minutes ahead is ignored');
  assert.equal(resolveDeadline(NOW + 3000, null, NOW), NOW + 3000);
  assert.equal(remainingSeconds(NOW + 42_300, NOW), 43);
  assert.equal(remainingSeconds(NOW - 5, NOW), 0);
  assert.equal(remainingSeconds(null, NOW), null);
  assert.equal(countdownLabel(NOW + 65_000, NOW), '1:05 left');
  assert.equal(countdownLabel(NOW + 9_000, NOW), '0:09 left');
  assert.equal(countdownLabel(NOW - 1000, NOW), 'finishing…');
  const run = running();
  assert.equal(run.deadlineMs, NOW + 150_000);
  assert.equal(giveUpAt(run), NOW + 150_000 + CANCEL_RESERVE_MS);
  assert.equal(run.lanes.strategist.deadlineMs, NOW + 45_000);
});

// --- availability and follow-up helpers ----------------------------------------------------------------------

test('the Ask button says why it is disabled', () => {
  assert.equal(askAvailability({ hazardCount: 0, planReady: false, pending: false, active: false }), 'Place a hazard first');
  assert.equal(askAvailability({ hazardCount: 1, planReady: false, pending: false, active: false }), 'Waiting for the planner');
  assert.equal(askAvailability({ hazardCount: 1, planReady: true, pending: true, active: false }), 'Waiting for the planner');
  assert.equal(askAvailability({ hazardCount: 1, planReady: true, pending: false, active: true }), 'The agent team is working');
  assert.equal(askAvailability({ hazardCount: 1, planReady: true, pending: false, active: false }), null);
});

test('scenario input: grammar passes through, natural phrases map to stuck_closed, nonsense is rejected', () => {
  assert.equal(normalizeScenario('stuck_closed:D3'), 'stuck_closed:D3');
  assert.equal(normalizeScenario('exit_blocked:E2+stuck_closed:D3'), 'exit_blocked:E2+stuck_closed:D3');
  assert.equal(normalizeScenario('What if D3 jams?'), 'stuck_closed:D3');
  assert.equal(normalizeScenario('what if d10 gets stuck'), 'stuck_closed:D10');
  assert.equal(normalizeScenario('what about lunch'), null);
  assert.equal(normalizeScenario('   '), null);
});

test('follow-up chips come from the recommended open doors, at most three', () => {
  const done = feed(running(), recorded());
  assert.deepEqual(followUpSuggestions(done), [{ label: 'What if D4 jams?', scenario: 'stuck_closed:D4' }, { label: 'What if D9 jams?', scenario: 'stuck_closed:D9' }]);
  assert.deepEqual(followUpSuggestions(idleRun()), []);
  const many = { ...done, lanes: { strategist: { ...done.lanes.strategist, view: view('strategist', { recommended_door_states: { D1: 'open', D2: 'open', D3: 'open', D4: 'open', D5: 'closed' } }) } }, order: ['strategist'] };
  assert.equal(followUpSuggestions(many).length, 3);
});

test('follow-up is offered only after the team stopped and not after Cancel', () => {
  assert.equal(followUpUnavailable(idleRun()), 'Ask the agent team first');
  assert.equal(followUpUnavailable(running()), 'The team is still working');
  assert.equal(followUpUnavailable(cancelRun(running())), 'The run was cancelled');
  assert.equal(followUpUnavailable(feed(running(), recorded())), null);
});

test('follow-up retry: 409 parent_finishing waits and retries, then succeeds; other errors surface immediately', async () => {
  const waits = [];
  let calls = 0;
  const result = await withRetry(async () => {
    if (++calls < 3) throw new ApiError('wrapping up', 409, 'parent_finishing');
    return 'ok';
  }, { shouldRetry: isParentFinishing, sleep: async ms => { waits.push(ms); }, onWait: attempt => waits.push(`wait${attempt}`) });
  assert.equal(result, 'ok');
  assert.equal(calls, 3);
  assert.deepEqual(waits, ['wait1', 2000, 'wait2', 2000]);

  let tries = 0;
  await assert.rejects(withRetry(async () => { tries++; throw new ApiError('running', 409, 'parent_running'); }, { shouldRetry: isParentFinishing, sleep: async () => {} }), /running/);
  assert.equal(tries, 1);

  let exhausted = 0;
  await assert.rejects(withRetry(async () => { exhausted++; throw new ApiError('wrapping up', 409, 'parent_finishing'); }, { retries: 2, shouldRetry: isParentFinishing, sleep: async () => {} }), /wrapping up/);
  assert.equal(exhausted, 3);
});

// --- connection: SSE first, polling when it drops -------------------------------------------------------------

class FakeSource {
  constructor(url) { this.url = url; this.readyState = 0; this.listeners = {}; this.onopen = null; this.onerror = null; this.closed = false; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  close() { this.closed = true; this.readyState = 2; }
  open() { this.readyState = 1; this.onopen?.({}); }
  emit(type, data) { this.listeners[type]?.({ data: JSON.stringify(data) }); }
  drop(readyState = 0) { this.readyState = readyState; this.onerror?.({}); }
}

function harness() {
  const sources = [];
  const timers = [];
  const polled = [];
  const statuses = [];
  const events = [];
  let seq = 0;
  let pollResult = () => Promise.resolve({ team_status: 'running', lanes: {} });
  const connection = createTraceConnection({
    makeSource: after => { const source = new FakeSource(`/trace${after ? `?after=${after}` : ''}`); sources.push(source); return source; },
    poll: () => pollResult(), lastSeq: () => seq, parse: parseTraceEvent, eventTypes: TRACE_EVENT_NAMES,
    onEvent: event => { seq = event.seq; events.push(event); }, onPolled: progress => polled.push(progress), onStatus: status => statuses.push(status),
    setTimer: (fn) => { const timer = { fn, cleared: false }; timers.push(timer); return timer; }, clearTimer: timer => { timer.cleared = true; },
  });
  return { connection, sources, timers, polled, statuses, events, setPoll: fn => { pollResult = fn; } };
}
const settle = () => new Promise(resolve => setImmediate(resolve));

test('connection: frames go live, a drop polls every tick, the next frame stops polling', async () => {
  const h = harness();
  h.connection.start();
  const [source] = h.sources;
  source.open();
  source.emit('lane', { seq: 4, lane: 'strategist', status: 'started' });
  assert.deepEqual(h.statuses.slice(0, 2), ['connecting', 'live']);
  assert.equal(h.events.length, 1);

  source.drop();
  await settle();
  assert.equal(h.statuses.at(-1), 'polling');
  assert.equal(h.polled.length, 1, 'polls immediately when the stream drops');
  h.timers[0].fn();
  await settle();
  assert.equal(h.polled.length, 2);

  source.emit('lane', { seq: 5, lane: 'strategist', status: 'plan_ready' });
  assert.equal(h.statuses.at(-1), 'live');
  assert.equal(h.timers[0].cleared, true);
});

test('connection: a source the browser gave up on is reopened from the last seq while polling', async () => {
  const h = harness();
  h.connection.start();
  h.sources[0].open();
  h.sources[0].emit('lane', { seq: 9, lane: 'strategist', status: 'started' });
  h.sources[0].drop(2);
  await settle();
  assert.equal(h.sources.length, 2);
  assert.equal(h.sources[1].url, '/trace?after=9');
  assert.equal(h.sources[0].closed, true);
});

test('connection: a failing poll reports offline; stop closes everything and ignores late frames', async () => {
  const h = harness();
  h.setPoll(() => Promise.reject(new Error('down')));
  h.connection.start();
  const [source] = h.sources;
  source.drop();
  await settle();
  assert.equal(h.statuses.at(-1), 'offline');
  h.connection.stop();
  assert.equal(source.closed, true);
  assert.equal(h.timers[0].cleared, true);
  source.emit('lane', { seq: 1, lane: 'strategist', status: 'started' });
  assert.equal(h.events.length, 0);
});

test('connection: skips frames that do not parse', () => {
  const h = harness();
  h.connection.start();
  h.sources[0].listeners.lane({ data: '{broken' });
  assert.equal(h.events.length, 0);
});

// --- runner: stale guards, cancel, polling fallback ------------------------------------------------------------

function runnerHarness(overrides = {}) {
  const runs = [];
  const cancelled = [];
  const connections = [];
  const afterTasks = [];
  let clock = NOW;
  let startResolve;
  const deps = {
    poll: async () => ({ investigation_id: 'dinv-1', status: 'completed', team_status: 'finished', deadline_at_ms: NOW, trace_url: '/trace', parent_investigation_id: null, lanes: { strategist: view('strategist'), robustness: view('robustness') } }),
    cancel: async id => { cancelled.push(id); },
    openConnection: opts => { const connection = { opts, started: false, stopped: false, start() { this.started = true; }, stop() { this.stopped = true; } }; connections.push(connection); return connection; },
    onRun: run => runs.push(run), now: () => clock,
    after: (fn, ms) => { const task = { fn, ms, cancelled: false }; afterTasks.push(task); return () => { task.cancelled = true; }; },
    ...overrides,
  };
  const runner = createTeamRunner(deps);
  const beginWith = (startFn) => runner.begin({ mode: 'live', hazardsKey: 'k', lanes: ['strategist', 'robustness'], start: startFn });
  const deferredStart = () => new Promise(resolve => { startResolve = resolve; });
  return { runner, runs, cancelled, connections, afterTasks, beginWith, deferredStart, resolveStart: value => startResolve(value), tick: ms => { clock += ms; } };
}

test('runner: start, stream events, done reconciles with a final GET and closes the stream', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  assert.equal(h.runner.state().status, 'running');
  assert.equal(h.connections.length, 1);
  assert.equal(h.connections[0].started, true);
  seqCounter = 0;
  for (const event of recorded()) h.connections[0].opts.onEvent(event);
  assert.equal(h.runner.state().status, 'done');
  assert.equal(h.connections[0].stopped, true);
  assert.equal(h.afterTasks[0].cancelled, true, 'the give-up watchdog is cleared when the run ends');
  await settle();
  // The reconcile GET replaced the streamed robustness lane with the authoritative view.
  assert.equal(h.runner.state().lanes.robustness.view.provenance, 'live');
});

test('runner: a second Ask while active is refused', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  assert.equal(h.beginWith(async () => start()), false);
});

test('runner: reset while the start request is in flight drops the late start and releases the server run', async () => {
  const h = runnerHarness();
  const pending = h.beginWith(h.deferredStart);
  h.runner.reset();
  assert.equal(h.runner.state().status, 'idle');
  h.resolveStart(start());
  await pending;
  assert.equal(h.runner.state().status, 'idle', 'late start never repopulates');
  assert.deepEqual(h.cancelled, ['dinv-1']);
  assert.equal(h.connections.length, 0);
});

test('runner: new hazards (reset) mid-run cancel the server run, close the stream and ignore late frames', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  seqCounter = 0;
  h.connections[0].opts.onEvent(ev('lane', 'strategist', { status: 'started' }));
  h.runner.reset();
  assert.equal(h.runner.state().status, 'idle');
  assert.deepEqual(h.cancelled, ['dinv-1']);
  assert.equal(h.connections[0].stopped, true);
  h.connections[0].opts.onEvent(ev('result', 'strategist', view('strategist')));
  h.connections[0].opts.onPolled(parseTeamProgress({ investigation_id: 'dinv-1', status: 'completed', team_status: 'finished', lanes: { strategist: view('strategist') } }));
  assert.equal(h.runner.state().status, 'idle');
  assert.equal(h.runner.state().lanes.strategist, undefined);
});

test('runner: a run from before a reset cannot overwrite the run after it', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  const old = h.connections[0];
  h.runner.reset();
  await h.beginWith(async () => start({ investigation_id: 'dinv-2' }));
  seqCounter = 0;
  old.opts.onEvent(ev('done', null, { team_status: 'finished' }));
  assert.equal(h.runner.state().status, 'running');
  assert.equal(h.runner.state().teamId, 'dinv-2');
});

test('runner: Cancel keeps the partial trace, marks lanes cancelled and releases the server run', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  seqCounter = 0;
  h.connections[0].opts.onEvent(ev('step', 'robustness', { kind: 'step', index: 0, step_type: 'model_output', text: 'working' }));
  h.runner.cancel();
  const run = h.runner.state();
  assert.equal(run.status, 'cancelled');
  assert.equal(run.lanes.robustness.phase, 'cancelled');
  assert.equal(run.lanes.robustness.trace.length, 1);
  assert.deepEqual(h.cancelled, ['dinv-1']);
});

test('runner: a failed start surfaces the error copy and is not active', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => { throw new ApiError('An agent team is already working. Cancel it, or try again in a moment.', 429, ''); });
  assert.equal(h.runner.state().status, 'failed');
  assert.match(h.runner.state().error, /already working/);
  assert.equal(isActive(h.runner.state()), false);
});

test('runner: polling fallback finishes the run when the stream never recovers', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  h.connections[0].opts.onStatus('polling');
  assert.equal(h.runner.state().connection, 'polling');
  const progress = await h.connections[0].opts.poll();
  h.connections[0].opts.onPolled(progress);
  assert.equal(h.runner.state().status, 'done');
  assert.equal(h.connections[0].stopped, true);
  assert.equal(h.runner.state().lanes.strategist.phase, 'completed');
});

test('runner: gives up after the lane deadline plus the cancel reserve, cancelling the server run', async () => {
  const h = runnerHarness();
  await h.beginWith(async () => start());
  const watchdog = h.afterTasks[0];
  assert.equal(watchdog.ms, 150_000 + CANCEL_RESERVE_MS);
  watchdog.fn();
  const run = h.runner.state();
  assert.equal(run.status, 'failed');
  assert.match(run.error, /did not finish in time/);
  assert.deepEqual(h.cancelled, ['dinv-1']);
  assert.equal(h.connections[0].stopped, true);
});

test('runner: follow-up start notices flow through while the retry waits', async () => {
  const h = runnerHarness();
  await h.runner.begin({
    mode: 'live', hazardsKey: 'k', lanes: ['followup'], scenario: 'stuck_closed:D3', parentId: 'dinv-1',
    start: async (_signal, notify) => { notify('The earlier agent is still wrapping up. Retrying (1)…'); assert.match(h.runner.state().notice, /wrapping up/); return start({ lanes: { followup: { investigation_id: 'dinv-3.followup', deadline_seconds: 90, deadline_at_ms: NOW + 90_000 } } }); },
  });
  const run = h.runner.state();
  assert.equal(run.status, 'running');
  assert.equal(run.notice, null);
  assert.equal(run.scenario, 'stuck_closed:D3');
  assert.deepEqual(run.order, ['followup']);
});

test('hazard key changes when the hazard set changes', () => {
  const a = [{ id: 'h0', type: 'FIRE', position: { x: 1, y: 2 }, source: 'simulated' }];
  assert.notEqual(hazardsKeyOf(a), hazardsKeyOf([...a, { ...a[0], id: 'h1' }]));
  assert.equal(hazardsKeyOf(a), hazardsKeyOf(structuredClone(a)));
});
