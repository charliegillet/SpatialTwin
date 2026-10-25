import test from 'node:test';
import assert from 'node:assert/strict';
import { canRunScenarioLab, labCases, predictionOutcome, reviewScenarioLab } from './policy.ts';

const context = {
  state_epoch: 'server-1', geometry_revision: 'geometry-1', scenario_revision: 2, physical_revision: 3,
  parameters_revision: 'parameters-1', solver_version: 'solver-1', context_hash: 'context-hash',
};
function candidate(alternative, completed, caseId = 'reference') {
  return {
    run_id: `${caseId}-${alternative}`, base_context: { ...context }, candidate_hash: `${caseId}-hash-${alternative}`,
    alternative_id: alternative, status: 'PARTIAL_WITHIN_HORIZON', initial_population: 120,
    completed_crossings: completed, remaining_population: 120 - completed,
    horizon_seconds: 40, time_step_seconds: 2, boundary_breakdown: { B1: completed, B2: 0 },
    zone_occupancy: { EVENT: 120 - completed }, bottlenecks: [], assumptions: [], timings_ms: 2,
    provenance: 'fixed_numerical_flow_solver_v1',
    validator_report: { is_valid: true, checks_run: ['conservation'], reasons: [], conservation_verified: true,
      unassigned_accounted: true, capacities_respected: true, quota_respected: true },
  };
}
const reference = () => candidate('KEEP_CURRENT', 100);
function result() {
  const counts = { baseline: [100, 110], p1_blocked: [80, 90], p2_blocked: [70, 100], b2_blocked: [50, 50] };
  return {
    base_context: { ...context }, generated_at_iso: '2026-10-24T10:00:00.000Z', hypothetical: true,
    provenance: 'local_scenario_lab', reserve_basis: 'reported', p3_physical_open: false, comparable: true, errors: [],
    cases: labCases.map(spec => ({ id: spec.id, title: spec.title, blocked_portals: [...spec.portals], blocked_boundaries: [...spec.boundaries],
      keep_current: candidate('KEEP_CURRENT', counts[spec.id][0], spec.id), open_p3: candidate('OPEN_P3', counts[spec.id][1], spec.id),
      net_gain: counts[spec.id][1] - counts[spec.id][0], comparable: true, reasons: [],
    })),
  };
}
const inspect = data => reviewScenarioLab(data, context, 'reported', reference(), false);
function unavailable(data) {
  const reviewed = inspect(data);
  assert.equal(reviewed.valid, false);
  assert.deepEqual(reviewed.leaders, []);
  assert.equal(reviewed.maxGain, null);
  assert.ok(reviewed.rows.every(row => !row.available && !('keep' in row) && !('open' in row) && !('gain' in row)));
  return reviewed;
}

test('complete four-case batch reveals checked counts and the largest blocked-case improvement', () => {
  const reviewed = inspect(result());
  assert.equal(reviewed.valid, true);
  assert.deepEqual(reviewed.rows.map(row => [row.id, row.keep, row.open, row.gain]), [
    ['baseline', 100, 110, 10], ['p1_blocked', 80, 90, 10], ['p2_blocked', 70, 100, 30], ['b2_blocked', 50, 50, 0],
  ]);
  assert.deepEqual(reviewed.leaders, ['p2_blocked']);
  assert.deepEqual(reviewed.parameters, { population: 120, horizon: 40, timestep: 2 });
  assert.match(predictionOutcome('p2_blocked', reviewed), /Your prediction: P2 — matched/);
  assert.match(predictionOutcome('p1_blocked', reviewed), /Your prediction: P1\./);
});

test('run availability requires a current checked reference and tolerates malformed snapshots', () => {
  assert.equal(canRunScenarioLab(reference(), context), true);
  assert.equal(canRunScenarioLab(null, context), false);
  assert.equal(canRunScenarioLab({ ...reference(), validator_report: undefined }, context), false);
  assert.equal(canRunScenarioLab(reference(), { ...context, state_epoch: 'restarted' }), false);
});

test('all full-context drift, including a restart epoch, hides every metric', () => {
  for (const field of Object.keys(context)) {
    const data = result();
    data.base_context[field] = 'changed';
    unavailable(data);
  }
  const data = result();
  data.cases[2].open_p3.base_context.state_epoch = 'restarted-server';
  unavailable(data);
  data.cases[2].open_p3.base_context = { ...context, context_hash: undefined };
  unavailable(data);
});

test('missing, duplicate, null and unknown cases cannot produce a partial winner', () => {
  for (const change of [
    data => { data.cases.pop(); },
    data => { data.cases[3] = data.cases[2]; },
    data => { data.cases[3] = null; },
    data => { data.cases[3].id = 'custom_case'; },
    data => { data.cases.push(data.cases[0]); },
  ]) { const data = result(); change(data); unavailable(data); }
});

test('each case must declare its exact canonical blockage, without inherited or invented closures', () => {
  for (const change of [
    data => { data.cases[0].blocked_portals = ['P2']; },
    data => { data.cases[1].blocked_portals = ['P1', 'P1']; },
    data => { data.cases[2].blocked_boundaries = ['B2']; },
    data => { data.cases[3].blocked_boundaries = ['B99']; },
    data => { data.cases[1].blocked_portals = undefined; },
  ]) { const data = result(); change(data); unavailable(data); }
});

test('incomplete, corrupt and unchecked alternatives fail closed without throwing', () => {
  for (const change of [
    item => { item.comparable = false; },
    item => { item.open_p3 = null; },
    item => { delete item.open_p3.validator_report; },
    item => { item.open_p3.validator_report.is_valid = 'true'; },
    item => { item.open_p3.validator_report.quota_respected = false; },
    item => { item.open_p3.validator_report.conservation_verified = false; },
    item => { item.open_p3.status = 'FAILED'; },
    item => { item.open_p3.alternative_id = 'KEEP_CURRENT'; },
    item => { item.keep_current.alternative_id = 'OPEN_P3'; },
    item => { item.open_p3.run_id = ''; },
    item => { item.open_p3.candidate_hash = ''; },
    item => { item.reasons = null; },
    item => { item.reasons = ['comparison has an unresolved issue']; },
  ]) { const data = result(); change(data.cases[2]); unavailable(data); }
});

test('all eight runs must match the current checked population, horizon and timestep', () => {
  for (const change of [
    candidate => { candidate.initial_population = 121; candidate.remaining_population += 1; },
    candidate => { candidate.horizon_seconds = 42; },
    candidate => { candidate.time_step_seconds = 4; },
    candidate => { candidate.completed_crossings += .5; candidate.remaining_population -= .5; },
    candidate => { candidate.completed_crossings = NaN; },
    candidate => { candidate.remaining_population = -1; },
    candidate => { candidate.completed_crossings += 1; },
  ]) { const data = result(); change(data.cases[1].open_p3); unavailable(data); }
  const data = result();
  data.cases.forEach(item => { for (const run of [item.keep_current, item.open_p3]) { run.initial_population = 119; run.remaining_population -= 1; } });
  unavailable(data);
  assert.equal(reviewScenarioLab(result(), context, 'reported', { ...reference(), validator_report: { is_valid: false } }, false).valid, false);
});

test('the gain must equal the checked difference; absent or fabricated improvement never displays', () => {
  for (const gain of [null, undefined, NaN, Infinity, 31, 30.5]) {
    const data = result(); data.cases[2].net_gain = gain; unavailable(data);
  }
});

test('zero and negative gains remain valid, with ties shown honestly and no forced winner', () => {
  const data = result();
  data.cases[1].open_p3 = candidate('OPEN_P3', 110, 'p1_blocked'); data.cases[1].net_gain = 30;
  let reviewed = inspect(data);
  assert.equal(reviewed.valid, true);
  assert.deepEqual(reviewed.leaders, ['p1_blocked', 'p2_blocked']);
  assert.match(predictionOutcome(null, reviewed), /tied: P1 and P2/);
  data.cases.forEach(item => { item.open_p3 = candidate('OPEN_P3', item.keep_current.completed_crossings - 1, item.id); item.net_gain = -1; });
  reviewed = inspect(data);
  assert.equal(reviewed.valid, true);
  assert.deepEqual(reviewed.leaders, []);
  assert.equal(reviewed.rows[1].gain, -1);
  assert.match(predictionOutcome('p2_blocked', reviewed), /^None of the blocked cases gains/);
  data.cases.forEach(item => { item.open_p3 = candidate('OPEN_P3', item.keep_current.completed_crossings, item.id); item.net_gain = 0; });
  assert.equal(inspect(data).valid, true);
  assert.deepEqual(inspect(data).leaders, []);
});

test('hypothetical provenance, basis and reported reserve state must agree with the request', () => {
  for (const change of [
    data => { data.hypothetical = false; },
    data => { data.provenance = 'live'; },
    data => { data.reserve_basis = 'closed_benchmark'; },
    data => { data.p3_physical_open = true; },
    data => { data.errors = ['failed case']; },
    data => { data.errors = undefined; },
    data => { data.comparable = false; },
    data => { data.generated_at_iso = 'invalid'; },
  ]) { const data = result(); change(data); unavailable(data); }
  const benchmark = { ...result(), reserve_basis: 'closed_benchmark', p3_physical_open: false };
  assert.equal(reviewScenarioLab(benchmark, context, 'closed_benchmark', reference(), true).valid, true);
  assert.equal(reviewScenarioLab({ ...benchmark, p3_physical_open: true }, context, 'closed_benchmark', reference(), true).valid, false);
  const reported = { ...result(), p3_physical_open: true };
  assert.equal(reviewScenarioLab(reported, context, 'reported', reference(), true).valid, false);
  reported.cases.forEach(item => { item.open_p3 = candidate('OPEN_P3', item.keep_current.completed_crossings, item.id); item.net_gain = 0; });
  assert.equal(reviewScenarioLab(reported, context, 'reported', reference(), true).valid, true);
  assert.equal(predictionOutcome('p2_blocked', unavailable(null)), '');
});
