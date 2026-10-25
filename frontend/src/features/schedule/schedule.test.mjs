import test from 'node:test';
import assert from 'node:assert/strict';
import { clampFrameIndex, getCheckedSchedule, SCHEDULE_CHECKS } from './schedule.ts';

function snapshot() {
  const context = { state_epoch: 'epoch-1', geometry_revision: 'geometry-1', scenario_revision: 1, physical_revision: 1, parameters_revision: 'params-1', solver_version: 'solver-2', context_hash: 'hash-1' };
  const frame = (step, event, west, east, transit, b1, b2) => ({ step, time_seconds: step * 2, event_occupancy: event, west_occupancy: west, east_occupancy: east, reserve_occupancy: 0, in_transit_occupancy: transit, b1_cumulative: b1, b2_cumulative: b2, total_completed: b1 + b2 });
  return {
    context, blocked_portals: [], blocked_boundaries: [], physical_gate_state: 'CLOSED', timestamp_iso: '2026-10-24T00:00:00Z',
    current_plan: {
      run_id: 'run-1', candidate_hash: 'candidate-1', base_context: { ...context }, alternative_id: 'KEEP_CURRENT', status: 'PARTIAL_WITHIN_HORIZON',
      initial_population: 12, completed_crossings: 10, remaining_population: 2, horizon_seconds: 6, time_step_seconds: 2,
      boundary_breakdown: { B1: 5, B2: 5 }, zone_occupancy: { EVENT: 2, WEST: 0, EAST: 0, RESERVE: 0 },
      validator_report: { is_valid: true, checks_run: [...SCHEDULE_CHECKS], reasons: [], conservation_verified: true, unassigned_accounted: true, capacities_respected: true, quota_respected: true },
      timeline: [frame(0, 12, 0, 0, 0, 0, 0), frame(1, 6, 1, 1, 2, 1, 1), frame(2, 2, 1, 1, 2, 3, 3), frame(3, 2, 0, 0, 0, 5, 5)],
    },
  };
}

test('a checked aggregate schedule retains holding, transit and completed occupants in every frame', () => {
  const state = snapshot();
  const result = getCheckedSchedule(state, true);
  assert.equal(result.available, true);
  assert.equal(result.frames[1].in_transit_occupancy, 2);
  assert.equal(result.frames[1].event_occupancy + result.frames[1].west_occupancy + result.frames[1].east_occupancy + result.frames[1].in_transit_occupancy + result.frames[1].total_completed, 12);
  result.frames[0].event_occupancy = 0;
  assert.equal(state.current_plan.timeline[0].event_occupancy, 12, 'inspection must not mutate accepted input');
});

test('legacy aggregate results are unavailable rather than fabricated into playback frames', () => {
  const state = snapshot();
  state.current_plan.validator_report.checks_run = ['population_conservation'];
  state.current_plan.timeline = [];
  const result = getCheckedSchedule(state, true);
  assert.equal(result.available, false);
  assert.equal(result.kind, 'legacy');
  assert.match(result.message, /Recompute using the updated backend/);
});

test('every named schedule check is required even when the report says valid', () => {
  for (const check of SCHEDULE_CHECKS) {
    const state = snapshot();
    state.current_plan.validator_report.checks_run = state.current_plan.validator_report.checks_run.filter(item => item !== check);
    assert.equal(getCheckedSchedule(state, true).available, false, check);
  }
});

test('disconnected, changed context and unconfirmed physical state fail closed', () => {
  assert.equal(getCheckedSchedule(snapshot(), false).available, false);
  for (const field of ['context_hash', 'state_epoch', 'scenario_revision', 'physical_revision', 'parameters_revision', 'solver_version']) {
    const state = snapshot();
    state.current_plan.base_context[field] = 'different';
    assert.equal(getCheckedSchedule(state, true).available, false, field);
  }
  for (const stateName of ['UNKNOWN', 'TRANSIT', 'FAULT']) {
    const state = snapshot(); state.physical_gate_state = stateName;
    assert.equal(getCheckedSchedule(state, true).available, false, stateName);
  }
});

test('lost transit, negative or fractional occupants and non-finite values invalidate the whole schedule', () => {
  for (const [field, value] of [['in_transit_occupancy', undefined], ['in_transit_occupancy', 0], ['west_occupancy', -1], ['event_occupancy', 6.5], ['total_completed', Infinity], ['east_occupancy', NaN]]) {
    const state = snapshot(); state.current_plan.timeline[1][field] = value;
    assert.equal(getCheckedSchedule(state, true).available, false, `${field}=${value}`);
  }
});

test('out-of-order, duplicate, missing and off-grid frames are not playable', () => {
  const mutations = [
    state => { state.current_plan.timeline.reverse(); },
    state => { state.current_plan.timeline[2] = { ...state.current_plan.timeline[1] }; },
    state => { state.current_plan.timeline.splice(1, 1); },
    state => { state.current_plan.timeline[1].time_seconds = 3; },
    state => { state.current_plan.time_step_seconds = 4; },
  ];
  for (const mutate of mutations) { const state = snapshot(); mutate(state); assert.equal(getCheckedSchedule(state, true).available, false); }
});

test('a decreasing boundary ledger is rejected even if every frame conserves population', () => {
  const state = snapshot();
  Object.assign(state.current_plan.timeline[2], { event_occupancy: 6, west_occupancy: 1, east_occupancy: 1, in_transit_occupancy: 2, b1_cumulative: 0, b2_cumulative: 2, total_completed: 2 });
  assert.equal(getCheckedSchedule(state, true).available, false);
});

test('a final count, boundary or holding mismatch invalidates earlier otherwise-valid frames too', () => {
  const mutations = [
    state => { state.current_plan.completed_crossings = 9; state.current_plan.remaining_population = 3; },
    state => { state.current_plan.boundary_breakdown = { B1: 4, B2: 6 }; },
    state => { state.current_plan.zone_occupancy = { EVENT: 0, WEST: 2, EAST: 0, RESERVE: 0 }; },
    state => { Object.assign(state.current_plan.timeline[3], { event_occupancy: 1, in_transit_occupancy: 1 }); },
  ];
  for (const mutate of mutations) { const state = snapshot(); mutate(state); assert.equal(getCheckedSchedule(state, true).available, false); }
});

test('all-boundaries-unavailable and zero population are real inspectable schedules', () => {
  for (const population of [12, 0]) {
    const state = snapshot(); const plan = state.current_plan;
    plan.initial_population = population; plan.completed_crossings = 0; plan.remaining_population = population;
    plan.status = population === 0 ? 'COMPLETE_WITHIN_MODEL' : 'NO_FEASIBLE_EXIT';
    plan.boundary_breakdown = { B1: 0, B2: 0 }; plan.zone_occupancy = { EVENT: population, WEST: 0, EAST: 0, RESERVE: 0 };
    plan.timeline.forEach(frame => Object.assign(frame, { event_occupancy: population, west_occupancy: 0, east_occupancy: 0, in_transit_occupancy: 0, b1_cumulative: 0, b2_cumulative: 0, total_completed: 0 }));
    assert.equal(getCheckedSchedule(state, true).available, true);
  }
});

test('run, candidate and server context identities each reset the playback key', () => {
  const original = getCheckedSchedule(snapshot(), true).key;
  for (const mutate of [
    state => { state.current_plan.run_id = 'run-2'; },
    state => { state.current_plan.candidate_hash = 'candidate-2'; },
    state => { state.context.state_epoch = 'epoch-2'; state.current_plan.base_context.state_epoch = 'epoch-2'; },
    state => { state.context.parameters_revision = 'params-2'; state.current_plan.base_context.parameters_revision = 'params-2'; },
  ]) { const state = snapshot(); mutate(state); assert.notEqual(getCheckedSchedule(state, true).key, original); }
});

test('direct time selection clamps to stored integer frames', () => {
  assert.equal(clampFrameIndex(-5, 4), 0);
  assert.equal(clampFrameIndex(2.8, 4), 2);
  assert.equal(clampFrameIndex(100, 4), 3);
  assert.equal(clampFrameIndex(NaN, 4), 0);
});
