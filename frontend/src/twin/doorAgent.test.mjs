import assert from 'node:assert/strict';
import test from 'node:test';
import {
  agentPhases, askAvailability, askLabel, createDoorAgentFlow, elapsedLabel, formatStates, hazardKey, idleAgent, LOCAL_LABEL, phaseLine, resultView, toolLine,
} from './doorAgent.ts';
import { doorAgentErrorMessage, isDoorAgentDone, parseDoorAgentProgress, agentStartError } from '../api/twin.ts';
import { ApiError } from '../api/client.ts';

const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
const fire = { id: 'h0', type: 'FIRE', position: { x: 20, y: 4 }, source: 'simulated' };
const BEST = { D4: 'closed', D9: 'open' };

const result = (over = {}) => ({
  investigation_id: 'dinv-1', status: 'completed', provenance: 'live', free_doors: ['D4', 'D9'],
  recommended_door_states: BEST, checked_best_door_states: BEST, checked_best_completed: 125, checked_best_is_valid: true,
  baseline_completed: 96, initial_population: 125, total_states: 4, agrees_with_checker: true, agreement_note: 'Agent and checker agree: D4 closed, D9 open.',
  explanation: 'Keeping D4 closed and D9 open preserves every modeled crossing.', tool_ledger: [], token_usage: {}, provider_interaction_id: 'i-1',
  provider_model: 'gemini-4-argon', latency_ms: 1000, errors: [], disclaimer: 'x', ...over,
});
const progress = (status, investigation = null, events = []) => ({ investigation_id: 'dinv-1', status, provider_progress: events, investigation });

function harness({ poll, start = async () => 'dinv-1', ...rest } = {}) {
  const states = [];
  const cancelled = [];
  const flow = createDoorAgentFlow({
    start, poll: poll ?? (async () => progress('running')), cancel: async id => { cancelled.push(id); },
    onState: state => states.push(state), isDone: isDoorAgentDone, describeFailure: doorAgentErrorMessage, intervalMs: 5, ...rest,
  });
  return { flow, states, cancelled };
}

test('labels follow the analysis mode and say when no Gemini call is made', () => {
  assert.equal(askLabel('live'), 'Ask the agent · Live Gemini');
  assert.equal(askLabel('local'), 'Ask the agent · Local solver');
  assert.equal(LOCAL_LABEL, 'Local solver · no Gemini call');
});

test('Ask is unavailable without hazards, before the plan, or while running', () => {
  const ok = { hazardCount: 1, planReady: true, pending: false, running: false };
  assert.equal(askAvailability(ok), null);
  assert.equal(askAvailability({ ...ok, hazardCount: 0 }), 'Place a hazard first');
  assert.equal(askAvailability({ ...ok, planReady: false }), 'Waiting for the planner');
  assert.equal(askAvailability({ ...ok, pending: true }), 'Waiting for the planner');
  assert.equal(askAvailability({ ...ok, running: true }), 'The agent is working');
});

test('elapsed time and phases read as short lines', () => {
  assert.equal(elapsedLabel(0), '0 s');
  assert.equal(elapsedLabel(12_900), '12 s');
  assert.equal(elapsedLabel(75_000), '1 min 15 s');
  const events = [
    { phase: 'plan_ready', elapsed_ms: 40 }, { phase: 'provider_request', elapsed_ms: 50 }, { phase: 'provider_response', status: 'in_progress', elapsed_ms: 800 },
    { phase: 'provider_response', status: 'in_progress', elapsed_ms: 1900 }, { phase: 'provider_response', status: 'requires_action', elapsed_ms: 4200 },
    { phase: 'local_tool_complete', elapsed_ms: 4300 }, { phase: 'provider_response', status: 'completed', elapsed_ms: 9100 },
  ];
  assert.deepEqual(agentPhases(events).map(phase => phase.label), ['plan checked', 'submitted', 'running', 'tool requested', 'checked locally', 'finished']);
  assert.equal(phaseLine(events), 'plan checked 0 s · submitted 0 s · running 1 s · tool requested 4 s · checked locally 4 s · finished 9 s');
});

test('the result view always leads with the checked best and states disagreement', () => {
  assert.equal(formatStates(BEST), 'D4 closed · D9 open');
  const agree = resultView(result());
  assert.equal(agree.decided, 'Checker decided: D4 closed · D9 open · 125 of 125');
  assert.equal(agree.tone, 'agree');
  assert.equal(agree.chip, 'Live Gemini · gemini-4-argon');
  assert.match(agree.attribution, /^Agent \(gemini-4-argon\) said/);
  const differ = resultView(result({ recommended_door_states: { D4: 'open', D9: 'closed' }, agrees_with_checker: false,
    agreement_note: "Agent suggested D4 open, D9 closed; the checker's best is D4 closed, D9 open." }));
  assert.equal(differ.tone, 'differ');
  assert.match(differ.agreement, /Agent suggested D4 open, D9 closed; the checker's best is D4 closed, D9 open\./);
  assert.equal(differ.decided, agree.decided);
  const none = resultView(result({ recommended_door_states: null, agrees_with_checker: false, agreement_note: 'The agent gave no usable recommendation.' }));
  assert.equal(none.tone, 'note');
});

test('local and failed results are labelled honestly', () => {
  const local = resultView(result({ provenance: 'local', provider_model: null, explanation: 'Local solver · no Gemini call. Checked best ...' }));
  assert.equal(local.chip, LOCAL_LABEL);
  assert.equal(local.attribution, 'Local solver summary');
  assert.equal(local.tone, 'local');
  const failed = resultView(result({ status: 'failed', provenance: 'unavailable', recommended_door_states: null, agrees_with_checker: false, errors: ['configuration_missing'], explanation: 'Investigation incomplete.' }));
  assert.equal(failed.tone, 'failed');
  assert.equal(failed.chip, 'Unavailable');
  assert.equal(failed.explanation, '');
  assert.equal(failed.agreement, '');
  assert.equal(failed.decided, 'Checker decided: D4 closed · D9 open · 125 of 125');
  assert.match(doorAgentErrorMessage(['configuration_missing']), /not configured.*checker's plan above still stands/);
  assert.match(doorAgentErrorMessage(['weird']), /did not complete/);
  assert.match(resultView(result()).disclaimer, /not a survival prediction/);
});

test('tool lines never print an unknown tool name or its arguments', () => {
  assert.equal(toolLine({ function_name: 'plan_doors', arguments: {}, status: 'executed', execution_time_ms: 0.4 }), 'plan_doors · 0 ms');
  assert.equal(toolLine({ function_name: 'compare_door_states', arguments: BEST, status: 'executed', execution_time_ms: 2 }), 'compare_door_states (D4 closed, D9 open) · 2 ms');
  assert.equal(toolLine({ function_name: 'rm -rf', arguments: { a: 1 }, status: 'failed', execution_time_ms: 1 }), 'rejected tool request · 1 ms · failed');
});

test('start errors map to short copy', () => {
  assert.match(agentStartError(429, ''), /Too many analyses/);
  assert.equal(agentStartError(422, 'unconfirmed_camera_hazard'), 'Confirm the camera card first');
});

test('progress responses are validated', () => {
  const ok = parseDoorAgentProgress(progress('completed', result()));
  assert.equal(ok.investigation.status, 'completed');
  assert.equal(parseDoorAgentProgress(progress('running')).investigation, null);
  for (const broken of [null, {}, { ...progress('running'), provider_progress: null }, progress('completed', { status: 'completed' })]) {
    assert.throws(() => parseDoorAgentProgress(broken), error => error instanceof ApiError && error.status === 502);
  }
  assert.equal(hazardKey([fire]), hazardKey([{ ...fire }]));
  assert.notEqual(hazardKey([fire]), hazardKey([{ ...fire, untenable_s: 10 }]));
  assert.equal(idleAgent().status, 'idle');
});

test('a run polls until the result is saved and publishes it', async () => {
  let calls = 0;
  const { flow, states } = harness({ poll: async () => (++calls < 3 ? progress('running', null, [{ phase: 'plan_ready', elapsed_ms: 1 }]) : progress('completed', result())) });
  assert.equal(flow.ask([fire], 'live'), true);
  await wait(80);
  const last = states.at(-1);
  assert.equal(last.status, 'finished');
  assert.equal(last.result.agrees_with_checker, true);
  assert.equal(last.mode, 'live');
  assert.equal(last.investigationId, 'dinv-1');
  assert.ok(states.some(state => state.status === 'running' && state.events.length === 1));
});

test('the gate refuses a second Ask while one is running, then allows the next after it finishes', async () => {
  const { flow, states } = harness({ poll: async () => progress('completed', result()) });
  assert.equal(flow.ask([fire], 'local'), true);
  assert.equal(flow.ask([fire], 'local'), false);
  await wait(40);
  assert.equal(states.at(-1).status, 'finished');
  assert.equal(flow.ask([fire], 'local'), true);
  await wait(40);
});

test('a failed run keeps the result, reports the reason and never claims success', async () => {
  const { flow, states } = harness({ poll: async () => progress('failed', result({ status: 'failed', provenance: 'unavailable', errors: ['configuration_missing'], recommended_door_states: null, agrees_with_checker: false })) });
  flow.ask([fire], 'live');
  await wait(40);
  const last = states.at(-1);
  assert.equal(last.status, 'failed');
  assert.match(last.error, /not configured/);
  assert.equal(last.result.provenance, 'unavailable');
});

test('reset drops a run: the late result is ignored and the backend is told to cancel', async () => {
  let release;
  const { flow, states, cancelled } = harness({ poll: () => new Promise(resolve => { release = () => resolve(progress('completed', result())); }) });
  flow.ask([fire], 'live');
  await wait(20);
  flow.reset();
  assert.equal(flow.state().status, 'idle');
  assert.deepEqual(cancelled, ['dinv-1']);
  release?.();
  await wait(30);
  assert.equal(states.at(-1).status, 'idle');
  assert.equal(flow.ask([fire], 'live'), true); // the gate was released
  flow.reset();
});

test('a start response that arrives after reset is cancelled on the backend and never shown', async () => {
  let resolveStart;
  const { flow, states, cancelled } = harness({ start: () => new Promise(resolve => { resolveStart = resolve; }) });
  flow.ask([fire], 'live');
  flow.reset();
  resolveStart('dinv-late');
  await wait(30);
  assert.deepEqual(cancelled, ['dinv-late']);
  assert.equal(states.at(-1).status, 'idle');
});

test('Cancel stops polling and shows idle', async () => {
  let polls = 0;
  const { flow, cancelled } = harness({ poll: async () => { polls += 1; return progress('running'); } });
  flow.ask([fire], 'live');
  await wait(30);
  flow.cancel();
  const seen = polls;
  await wait(40);
  assert.equal(polls, seen);
  assert.deepEqual(cancelled, ['dinv-1']);
  assert.equal(flow.state().status, 'idle');
});

test('a start failure and repeated poll failures surface as a failed run', async () => {
  const startFails = harness({ start: async () => { throw new ApiError('Too many analyses are running. Try again shortly.', 429); } });
  startFails.flow.ask([fire], 'live');
  await wait(20);
  assert.equal(startFails.states.at(-1).status, 'failed');
  assert.match(startFails.states.at(-1).error, /Too many analyses/);
  const pollFails = harness({ poll: async () => { throw new Error('network'); } });
  pollFails.flow.ask([fire], 'live');
  await wait(60);
  assert.equal(pollFails.states.at(-1).status, 'failed');
});

test('the client gives up after its deadline and cancels the run', async () => {
  let clock = 0;
  const { flow, states, cancelled } = harness({ now: () => clock, deadlineMs: 100, poll: async () => { clock += 60; return progress('running'); } });
  flow.ask([fire], 'live');
  await wait(60);
  assert.equal(states.at(-1).status, 'failed');
  assert.match(states.at(-1).error, /did not finish in time/);
  assert.deepEqual(cancelled, ['dinv-1']);
});

test('an agent result is never presented as checked when the checker best is invalid', () => {
  const view = resultView(result({ checked_best_is_valid: false }));
  assert.equal(view.tone, 'note');
  assert.match(view.decided, /No checked plan/);
  assert.equal(view.agreement, '');
});
