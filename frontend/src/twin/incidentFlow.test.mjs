import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../api/client.ts';
import { incidentErrorMessage, INCIDENT_ERRORS, parseIncidentEvent, parseIncidentState } from '../api/incident.ts';
import {
  applyIncidentState, approveAvailability, createHazardSync, createIncidentConnection, createStaleGuard, doorVisuals, drawGate, fallbackBanner,
  gateViews, initialIncidentState, MAX_CONSOLE_LINES, reduceIncidentEvent,
} from './incidentFlow.ts';

const gate = (id, over = {}) => ({
  gate_id: id, state: 'CLOSED', open_switch: false, closed_switch: true, epoch: 1, target: null, fault: null, last_command_id: null,
  last_ack: null, observed: 'closed', applied: 'closed', detail: 'initial', simulated: true, ...over,
});
const doorStates = { D1: 'open', D4: 'closed', D9: 'open' };
const plan = (over = {}) => ({
  plan_id: 'dp-1', plan_revision: 2, candidate_hash: 'h2', label: 'primary', note: null, reason: 'hazards updated', valid: true,
  initial_population: 125, completed_crossings: 102, baseline_completed: 80, count_label: 'modeled crossings', door_states: doorStates,
  doors: [{ id: 'D9', state: 'open', lamp: 'green', actuation: 'motorized', controllable: true, changed: true, stuck: false, reason: 'x', applied: 'closed' }],
  stuck_doors: [], advisories: [], announcement: 'a', ...over,
});
const incident = (over = {}) => ({
  simulated: true, venue_id: 'building-v2', plan_revision: 2, hazards: [{ id: 'h0' }], plan: plan(), plan_error: null,
  controller: { label: 'Simulated device: no hardware is connected', boot_id: 'b', heartbeat: 'ok', transit_seconds: 1.75, gates: [gate('D4'), gate('D9')] },
  stuck_doors: [], approvals: [], approval_in_progress: false, last_event_id: 5, ...over,
});
const withGate = (state, id, over) => ({ ...state, controller: { ...state.controller, gates: state.controller.gates.map(item => item.gate_id === id ? { ...item, ...over } : item) } });

const ev = (type, seq, extra = {}) => ({ type, seq, ts: `t${seq}`, plan_revision: 2, line: null, ...extra });
const apply = (state, ...events) => events.reduce((acc, event) => reduceIncidentEvent(acc, event, 1000 + event.seq * 100), state);
const approval = (status, over = {}) => ({
  approval_id: 'apv-1', plan_revision: 2, candidate_hash: 'h2', door_states: doorStates, status, commands: { D9: 'OPEN' }, results: {}, reason: null,
  fallback_plan_revision: null, ...over,
});

test('parsers accept the documented shapes and reject broken ones', () => {
  const parsed = parseIncidentState(incident());
  assert.equal(parsed.plan.candidate_hash, 'h2');
  assert.equal(parsed.controller.gates[1].gate_id, 'D9');
  assert.equal(parseIncidentState(incident({ plan: null })).plan, null);
  assert.throws(() => parseIncidentState({ venue_id: 'x' }), ApiError);
  assert.throws(() => parseIncidentState(incident({ plan: { plan_revision: 1 } })), ApiError);
  assert.throws(() => parseIncidentState(incident({ controller: { gates: [{ gate_id: 'D9', state: 'AJAR' }] } })), ApiError);
  const frame = parseIncidentEvent('gate', JSON.stringify({ ...gate('D9', { state: 'OPENING' }), seq: 7, ts: 't', plan_revision: 2, phase: 'command', line: 'CMD vcmd-1 SET_GATE_TARGET D9 OPEN' }));
  assert.equal(frame.type, 'gate');
  assert.equal(frame.gate.state, 'OPENING');
  assert.equal(frame.line, 'CMD vcmd-1 SET_GATE_TARGET D9 OPEN');
  const snap = parseIncidentEvent('snapshot', JSON.stringify({ type: 'snapshot', last_id: 9, state: incident() }));
  assert.equal(snap.seq, 9);
  assert.equal(parseIncidentEvent('mystery', '{"seq":1}'), null);
  assert.equal(parseIncidentEvent('plan', 'not json'), null);
});

test('every documented error code has judge-readable copy', () => {
  for (const code of ['stale_plan', 'approval_in_progress', 'no_plan', 'plan_not_valid', 'unknown_gate', 'gate_required', 'unknown_venue']) {
    assert.ok(INCIDENT_ERRORS[code], code);
    assert.equal(incidentErrorMessage(409, code), INCIDENT_ERRORS[code]);
  }
  assert.equal(incidentErrorMessage(409, 'stale_plan'), 'The plan changed — review the new one');
  assert.equal(incidentErrorMessage(422, 'outside_building'), 'Drop inside a room');
  assert.equal(incidentErrorMessage(422, 'something_new'), 'The request was not accepted');
  assert.equal(incidentErrorMessage(500, ''), '');
});

test('happy path: snapshot, plan, approval actuating, gate opening, observed open, approval applied', () => {
  let state = apply(initialIncidentState(), ev('snapshot', 5, { state: incident({ plan: null, hazards: [] }) }));
  assert.equal(approveAvailability(state.incident).reason, 'Place a hazard to get a plan');
  state = apply(state, ev('plan', 6, { plan: plan(), hazards: [{ id: 'h0' }], stuck_doors: [], plan_revision: 2, line: null }));
  assert.equal(state.incident.plan.plan_revision, 2);
  assert.equal(approveAvailability(state.incident).allowed, true);

  state = apply(state, ev('approval', 7, { approval: approval('actuating') }));
  assert.equal(state.incident.approval_in_progress, true);
  assert.equal(approveAvailability(state.incident).allowed, false);
  assert.match(approveAvailability(state.incident).reason, /moving/);

  state = apply(state, ev('gate', 8, { phase: 'command', gate: gate('D9', { state: 'OPENING', target: 'OPEN', observed: null, applied: 'moving', closed_switch: false, last_ack: 'ACCEPTED' }), line: 'CMD vcmd-1 SET_GATE_TARGET D9 OPEN' }));
  let [, d9] = gateViews(state.incident, state.movingSince, 1800 + 500);
  assert.equal(d9.draw, 'opening');
  assert.equal(d9.moving, true);
  assert.equal(d9.elapsedMs, 1800 + 500 - (1000 + 8 * 100));
  assert.equal(d9.overdue, false);
  assert.equal(d9.ack.label, 'ACK · heard, not arrived');
  assert.equal(d9.openSwitch, false);

  state = apply(state, ev('gate', 9, { phase: 'observed', gate: gate('D9', { state: 'OPEN', target: 'OPEN', observed: 'open', applied: 'open', open_switch: true, closed_switch: false, epoch: 2, last_ack: 'ACCEPTED' }), line: 'OBSERVATION D9 OPEN open_switch=1 closed_switch=0 epoch=2' }));
  [, d9] = gateViews(state.incident, state.movingSince, 5000);
  assert.equal(d9.draw, 'open');
  assert.equal(d9.openSwitch, true);
  assert.equal(d9.epoch, 2);
  assert.equal(d9.moving, false);
  assert.equal(state.movingSince.D9, undefined);

  state = apply(state, ev('approval', 10, { approval: approval('applied') }));
  assert.equal(state.incident.approval_in_progress, false);
  assert.equal(state.incident.approvals.length, 1);
  assert.equal(approveAvailability(state.incident).reason, 'This plan is already approved');
  assert.deepEqual(state.log.map(line => line.text).slice(-2), ['OBSERVATION D9 OPEN open_switch=1 closed_switch=0 epoch=2', 'APPROVAL apv-1 applied r2']);
  assert.equal(state.log[state.log.length - 1].tone, 'ok');
  assert.equal(state.log[state.log.length - 2].tone, 'ok');
  assert.deepEqual(Object.keys(doorVisuals(state.incident, state.movingSince)), ['D4', 'D9']);
});

test('ACK without an endpoint switch is never drawn open', () => {
  const heardOnly = gate('D9', { state: 'OPENING', last_ack: 'ACCEPTED', applied: 'open', observed: null, open_switch: false, closed_switch: false });
  assert.equal(drawGate(heardOnly), 'opening');
  // Even a contradictory payload (state OPEN, applied open) needs the observed endpoint and exactly one switch.
  assert.equal(drawGate(gate('D9', { state: 'OPEN', applied: 'open', observed: null, last_ack: 'ACCEPTED' })), 'unknown');
  assert.equal(drawGate(gate('D9', { state: 'OPEN', applied: 'open', observed: 'open', open_switch: true, closed_switch: true })), 'unknown');
  assert.equal(drawGate(gate('D9', { state: 'UNKNOWN', applied: 'open', observed: null })), 'unknown');
  assert.equal(drawGate(gate('D9', { state: 'FAULT', observed: 'open', open_switch: true, closed_switch: false })), 'fault');
  // A stalled transit past its expected time keeps the bar honest.
  const state = apply(initialIncidentState(), ev('snapshot', 1, { state: incident({ controller: { ...incident().controller, gates: [heardOnly] } }) }));
  const stalled = apply(state, ev('gate', 2, { phase: 'command', gate: heardOnly }));
  const [view] = gateViews(stalled.incident, stalled.movingSince, 1200 + 4000);
  assert.equal(view.overdue, true);
  assert.equal(view.transitFraction, 1);
  assert.equal(view.draw, 'opening');
});

test('jam path: gate FAULT, approval failed, fallback plan, Approve allowed only on the fallback', () => {
  let state = apply(initialIncidentState(), ev('snapshot', 5, { state: incident() }));
  state = apply(state, ev('fault', 6, { phase: 'fault_injected', fault: 'stall', gate_id: 'D9', line: 'FAULT_INJECT D9 stall' }));
  let views = gateViews(state.incident, state.movingSince, 0);
  assert.equal(views[1].armedFault, 'stall');
  assert.equal(views[1].warn, false);
  assert.equal(approveAvailability(state.incident).allowed, true, 'an armed fault does not block the approval that will expose it');

  state = apply(state, ev('approval', 7, { approval: approval('actuating') }));
  state = apply(state, ev('gate', 8, { phase: 'command', gate: gate('D9', { state: 'OPENING', target: 'OPEN', fault: 'stall', observed: null, applied: 'moving', last_ack: 'ACCEPTED', closed_switch: false }) }));
  state = apply(state, ev('gate', 9, { phase: 'fault', gate: gate('D9', { state: 'FAULT', target: 'OPEN', fault: 'stall', observed: null, applied: 'unknown', last_ack: 'ACCEPTED', closed_switch: false, detail: 'no endpoint switch after 3.25s' }), line: 'FAULT D9 stall: no endpoint switch after 3.25s' }));
  views = gateViews(state.incident, state.movingSince, 0);
  assert.equal(views[1].draw, 'fault');
  assert.equal(views[1].warn, true);
  assert.equal(state.log[state.log.length - 1].tone, 'warn');

  state = apply(state, ev('approval', 10, { approval: approval('failed', { reason: 'D9 fault:stall', results: { D9: 'fault:stall' }, fallback_plan_revision: 3 }) }));
  // Between the failure and the fallback the old plan must not be approvable: D9 is FAULT and the plan is primary.
  assert.equal(approveAvailability(state.incident).allowed, false);
  assert.match(approveAvailability(state.incident).reason, /D9 is FAULT/);

  const fallback = plan({ plan_revision: 3, candidate_hash: 'h3', label: 'fallback', note: 'with D9 stuck closed', reason: 'fallback: D9 open never observed (stall); re-planned with D9 stuck closed', stuck_doors: ['D9'], door_states: { D1: 'open', D4: 'closed', D9: 'closed' }, completed_crossings: 90 });
  state = apply(state, ev('plan', 11, { plan: fallback, hazards: [{ id: 'h0' }], stuck_doors: ['D9'], plan_revision: 3 }));
  assert.equal(state.incident.plan.label, 'fallback');
  assert.equal(state.incident.plan_revision, 3);
  assert.deepEqual(approveAvailability(state.incident), { allowed: true, reason: null });
  assert.equal(fallbackBanner(state.incident).headline, 'D9 never reached its open endpoint — re-planned with D9 stuck closed. Approve the fallback?');
  assert.equal(gateViews(state.incident, {}, 0)[1].stuck, true, 'stuck comes from the server list');
  assert.equal(gateViews(state.incident, {}, 0)[0].stuck, false);

  // The same fallback does not excuse a second gate that is in doubt.
  const second = { ...state.incident, controller: { ...state.incident.controller, gates: state.incident.controller.gates.map(item => item.gate_id === 'D4' ? { ...item, state: 'UNKNOWN', observed: null } : item) } };
  assert.match(approveAvailability(second).reason, /D4 is UNKNOWN/);
  // A stale controller blocks everything, fallback or not.
  assert.equal(approveAvailability({ ...state.incident, controller: { ...state.incident.controller, heartbeat: 'stale' } }).allowed, false);
  assert.equal(approveAvailability({ ...state.incident, plan: { ...fallback, valid: false } }).allowed, false);
  assert.equal(approveAvailability({ ...state.incident, plan: null, plan_error: 'outside_building' }).reason, 'No plan: Drop inside a room');
});

test('replays, stale polls and late events are dropped after a reset', () => {
  let state = apply(initialIncidentState(), ev('snapshot', 5, { state: incident() }));
  state = apply(state, ev('gate', 6, { phase: 'command', gate: gate('D9', { state: 'OPENING', target: 'OPEN' }) }));
  const replay = apply(state, ev('gate', 6, { phase: 'command', gate: gate('D9', { state: 'OPENING', target: 'OPEN' }) }));
  assert.equal(replay, state, 'a replayed seq changes nothing');
  assert.equal(state.log.length, 0, 'no line, nothing logged');

  state = apply(state, ev('reset', 10, { line: 'RESET devices', state: incident({ plan: null, hazards: [], plan_revision: 5, last_event_id: 10 }) }));
  assert.equal(state.incident.plan, null);
  assert.equal(state.lastSeq, 10);
  assert.deepEqual(state.movingSince, {});
  // A GET that left before the reset and landed after it carries an older last_event_id.
  assert.equal(applyIncidentState(state, incident({ last_event_id: 8, plan_revision: 4 }), 0), state);
  // Late SSE frames from before the reset too.
  assert.equal(apply(state, ev('plan', 9, { plan: plan(), plan_revision: 4 })), state);
  assert.equal(applyIncidentState(state, incident({ plan: null, last_event_id: 10 }), 0).lastSeq, 10);

  const guard = createStaleGuard();
  const token = guard.begin();
  assert.equal(guard.isCurrent(token), true);
  guard.invalidate();
  assert.equal(guard.isCurrent(token), false);
  assert.equal(guard.isCurrent(guard.begin()), true);
});

test('the console is bounded and keeps the newest line last', () => {
  let state = apply(initialIncidentState(), ev('snapshot', 0, { state: incident({ last_event_id: 0 }) }));
  for (let seq = 1; seq <= MAX_CONSOLE_LINES + 30; seq += 1) state = apply(state, ev('fault', seq, { phase: 'fault_cleared', gate_id: 'D9', line: `LINE ${seq}` }));
  assert.equal(state.log.length, MAX_CONSOLE_LINES);
  assert.equal(state.log[state.log.length - 1].text, `LINE ${MAX_CONSOLE_LINES + 30}`);
  assert.equal(state.log[0].text, 'LINE 31');
});

// ---- hazard sync ----

const fakeTimers = (repeat = false) => {
  const queue = [];
  return {
    setTimer: (fn, ms) => { const handle = { fn, ms, live: true }; queue.push(handle); return handle; },
    clearTimer: handle => { handle.live = false; },
    fire: () => { const due = queue.splice(0).filter(item => item.live); due.forEach(item => item.fn()); if (repeat) queue.push(...due); return due.length; },
  };
};
const flush = () => new Promise(resolve => setImmediate(resolve));

function syncHarness({ post, read, revision = () => 2 } = {}) {
  const timers = fakeTimers();
  const posts = [];
  const states = [];
  const errors = [];
  const sync = createHazardSync({
    post: post ?? (async (venue, rev, hazards) => { posts.push({ venue, rev, hazards }); return incident({ plan_revision: rev + 1 }); }),
    read: read ?? (async () => incident({ plan_revision: 7 })),
    revision, onState: state => states.push(state), onError: message => errors.push(message), debounceMs: 350, ...timers,
  });
  return { sync, timers, posts, states, errors };
}
const fire = { id: 'h0', type: 'FIRE', position: { x: 1, y: 2 }, source: 'simulated' };
const smoke = { id: 'h1', type: 'SMOKE', position: { x: 3, y: 4 }, source: 'simulated' };

test('hazard sync debounces to the newest set and quotes the known revision', async () => {
  const { sync, timers, posts, errors } = syncHarness();
  sync.update('building-v2', [fire]);
  sync.update('building-v2', [fire, smoke]);
  assert.equal(posts.length, 0);
  timers.fire();
  await flush();
  assert.equal(posts.length, 1);
  assert.deepEqual(posts[0], { venue: 'building-v2', rev: 2, hazards: [fire, smoke] });
  assert.deepEqual(errors, [null]);
  // The same set again sends nothing.
  sync.update('building-v2', [fire, smoke]);
  assert.equal(timers.fire(), 0);
  // An empty set is a real change (back to the no-hazard baseline).
  sync.update('building-v2', []);
  timers.fire();
  await flush();
  assert.equal(posts.length, 2);
  assert.deepEqual(posts[1].hazards, []);
});

test('hazard sync re-reads and retries once on 409 stale_plan, then gives up with a readable message', async () => {
  const calls = [];
  const post = async (venue, rev, hazards) => {
    calls.push(rev);
    if (rev === 2) throw new ApiError('The plan changed — review the new one', 409, 'stale_plan');
    return incident({ plan_revision: rev + 1 });
  };
  const { sync, timers, states, errors } = syncHarness({ post });
  sync.update('building-v2', [fire]);
  timers.fire();
  await flush();
  assert.deepEqual(calls, [2, 7], 'second attempt quotes the re-read revision');
  assert.equal(states[0].plan_revision, 7);
  assert.equal(states[states.length - 1].plan_revision, 8);
  assert.deepEqual(errors, [null]);

  const always = async () => { throw new ApiError('The plan changed — review the new one', 409, 'stale_plan'); };
  const second = syncHarness({ post: always });
  second.sync.update('building-v2', [fire]);
  second.timers.fire();
  await flush();
  assert.deepEqual(second.errors, ['The plan changed — review the new one']);
  // A failed send is retried by kick(), for example when the approval that blocked it ends.
  second.sync.kick();
  assert.equal(second.timers.fire(), 1);
});

test('hazard sync reads first when no revision is known and resends after a device reset', async () => {
  const { sync, timers, posts } = syncHarness({ revision: () => null });
  sync.update('building-v2', [fire]);
  timers.fire();
  await flush();
  assert.equal(posts[0].rev, 7);
  sync.resend();
  timers.fire();
  await flush();
  assert.equal(posts.length, 2);
});

// ---- connection ----

class FakeSource {
  constructor(url) { this.url = url; this.readyState = 0; this.onopen = null; this.onerror = null; this.listeners = {}; this.closed = false; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  close() { this.closed = true; this.readyState = 2; }
  emit(type, payload) { this.listeners[type]({ data: JSON.stringify(payload) }); }
}

test('connection streams events, falls back to polling on error, and resumes when frames flow', async () => {
  const timers = fakeTimers(true);
  const sources = [];
  const events = [];
  const polled = [];
  const statuses = [];
  let lastSeq = 0;
  let pollResult = incident();
  const connection = createIncidentConnection({
    makeSource: url => { const source = new FakeSource(url); sources.push(source); return source; },
    poll: async () => pollResult, lastSeq: () => lastSeq,
    onEvent: event => { events.push(event); lastSeq = event.seq; }, onPolled: state => polled.push(state), onStatus: status => statuses.push(status), ...timers,
  });
  connection.start();
  assert.equal(sources[0].url, '/api/incident/events');
  sources[0].onopen();
  sources[0].emit('gate', { ...gate('D9', { state: 'OPENING' }), seq: 3, ts: 't', plan_revision: 2, phase: 'command', line: 'CMD' });
  assert.equal(events.length, 1);
  assert.equal(statuses[statuses.length - 1], 'live');

  sources[0].onerror();
  assert.equal(statuses[statuses.length - 1], 'polling');
  await flush();
  assert.equal(polled.length, 1, 'polls at once, then on the interval');
  assert.equal(timers.fire(), 1);
  await flush();
  assert.equal(polled.length, 2);

  // The browser gave up on the stream: the poll tick builds a new one that resumes after the last applied event.
  sources[0].readyState = 2;
  timers.fire();
  await flush();
  assert.equal(sources.length, 2);
  assert.equal(sources[1].url, '/api/incident/events?last_event_id=3');
  sources[1].onopen();
  assert.equal(statuses[statuses.length - 1], 'live');
  connection.stop();
  assert.equal(sources[1].closed, true);
});

test('polling failure reports offline instead of pretending to be live', async () => {
  const timers = fakeTimers(true);
  const statuses = [];
  const sources = [];
  const connection = createIncidentConnection({
    makeSource: url => { const source = new FakeSource(url); sources.push(source); return source; },
    poll: async () => { throw new Error('down'); }, lastSeq: () => 0,
    onEvent: () => {}, onPolled: () => {}, onStatus: status => statuses.push(status), ...timers,
  });
  connection.start();
  sources[0].onerror();
  await flush();
  assert.equal(statuses[statuses.length - 1], 'offline');
  // An unparseable frame is ignored and does not flip the connection to live.
  sources[0].listeners.gate({ data: 'garbage' });
  assert.equal(statuses[statuses.length - 1], 'offline');
  connection.stop();
});
