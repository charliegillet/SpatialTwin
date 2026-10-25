import test from 'node:test';
import assert from 'node:assert/strict';
import { buildReviewHtml, nextStepCopy, reviewJson, reviewPayload } from './review.ts';

const context = {
  state_epoch: 'epoch-1', geometry_revision: 'geom-1', scenario_revision: 2, physical_revision: 2,
  parameters_revision: 'params-v1', solver_version: 'solver-1', context_hash: 'hash-1',
};
const snapshot = (overrides = {}) => ({
  context: { ...context }, blocked_portals: ['P2'], blocked_boundaries: [], physical_gate_state: 'CLOSED',
  current_plan: { run_id: 'run-1', candidate_hash: 'cand-1', base_context: { ...context } },
  timestamp_iso: '2026-10-24T10:00:00Z', ...overrides,
});
const plan = field => ({ source: 'checked_plan', ref: 'run-1', field });
const state = field => ({ source: 'reported_state', ref: 'hash-1', field });
const record = (watcher_id, kind, severity, summary, evidence, extra = {}) => ({ record_id: `${watcher_id}:${kind}`, watcher_id, kind, severity, summary, evidence, ...extra });
const requirement = (requirement_id, status, method = 'measured', extra = {}) => ({
  requirement_id, category: 'conservation', scope: 'plan', statement: `${requirement_id} statement`, method, status,
  measured: `${requirement_id} measured`, expected: 'expected', evidence: [plan('initial_population')], ...extra,
});

function payload() {
  const records = [
    record('zone:EVENT', 'RESIDUAL_HOLDING', 'alert', '60 synthetic occupants still holding in Main Event Hall at 40s.', [plan('timeline[20].event_occupancy')], { value: 60, at_seconds: 40 }),
    record('passage:P2', 'PASSAGE_UNAVAILABLE', 'alert', 'P2 is unavailable in the accepted scenario.', [state('blocked_portals')]),
    record('boundary:B1', 'BOUNDARY_AT_QUOTA', 'advisory', 'B1 serviced 60 of its 60 finite-horizon quota.', [plan('boundary_breakdown.B1')], { value: 60, limit: 60 }),
    record('reserve:P3', 'RESERVE_OBSERVED', 'info', 'P3 reported CLOSED by endpoint telemetry (epoch 1).', [state('physical_gate_state')]),
    record('reserve:P3', 'SIMULATED_ENDPOINT', 'info', 'Simulator endpoint. This is not a physical gate observation.', [state('hardware_mode')]),
  ];
  const requirements = [
    requirement('population_conserved', 'pass'), requirement('frames_conserve_population', 'pass'),
    requirement('flow_witness_edges', 'checker_attested', 'checker'), requirement('comparison_equal_conditions', 'not_run', 'measured', { evidence: [] }),
    requirement('outside:survival', 'cannot_measure', 'outside_model'), requirement('outside:venue_survey', 'cannot_measure', 'outside_model'),
  ];
  return {
    provenance: 'local_review', generated_at_iso: '2026-10-24T10:00:01Z', base_context: { ...context }, run_id: 'run-1',
    candidate_hash: 'cand-1', hardware_mode: 'simulator', notice: 'Local simulated escalation record. No message was sent.',
    watch: {
      version: 'zone-watch-v1', base_context: { ...context }, run_id: 'run-1', candidate_hash: 'cand-1', records,
      watchers: [
        { watcher_id: 'zone:EVENT', label: 'Main Event Hall', scope: 'zone', severity: 'alert', record_ids: ['zone:EVENT:RESIDUAL_HOLDING'] },
        { watcher_id: 'passage:P2', label: 'P2 passage', scope: 'passage', severity: 'alert', record_ids: ['passage:P2:PASSAGE_UNAVAILABLE'] },
        { watcher_id: 'boundary:B1', label: 'B1 boundary', scope: 'boundary', severity: 'advisory', record_ids: ['boundary:B1:BOUNDARY_AT_QUOTA'] },
        { watcher_id: 'reserve:P3', label: 'P3 reserve gate', scope: 'reserve', severity: 'info', record_ids: ['reserve:P3:RESERVE_OBSERVED', 'reserve:P3:SIMULATED_ENDPOINT'] },
      ],
      escalation: 'escalated', escalation_reasons: ['zone:EVENT:RESIDUAL_HOLDING', 'passage:P2:PASSAGE_UNAVAILABLE'],
      next_step: 'compare_alternatives', delivery: 'local_record_only', notice: 'Local simulated escalation record. No message was sent.',
    },
    verification: {
      version: 'verification-v1', base_context: { ...context }, run_id: 'run-1', candidate_hash: 'cand-1', verdict: 'verified_within_model',
      summary: { passed: 2, failed: 0, checker_attested: 1, cannot_measure: 2, not_run: 1 }, requirements,
      scope_note: 'Counts describe modeled floor-transfer boundary crossings of synthetic occupants; not survival.',
    },
    escalation_record: {
      record_id: 'esc-0123', created_at_iso: '2026-10-24T10:00:01Z', context_hash: 'hash-1', run_id: 'run-1', escalation: 'escalated',
      reasons: ['zone:EVENT:RESIDUAL_HOLDING', 'passage:P2:PASSAGE_UNAVAILABLE'], next_step: 'compare_alternatives',
      delivery: 'local_record_only', notice: 'Local simulated escalation record. No message was sent.',
    },
  };
}

function rejected(data, view = snapshot(), current = true) {
  const reviewed = reviewPayload(data, view, current);
  assert.equal(reviewed.available, false);
  assert.ok(!('payload' in reviewed));
  return reviewed.message;
}

test('a consistent local review of the current run is shown with its escalation and next step', () => {
  const reviewed = reviewPayload(payload(), snapshot(), true);
  assert.equal(reviewed.available, true);
  assert.equal(reviewed.payload.watch.escalation, 'escalated');
  assert.match(nextStepCopy(reviewed.payload.watch.next_step), /zero is a valid result/);
});

test('lost connection, a changed context or another run hides every record', () => {
  assert.match(rejected(payload(), snapshot(), false), /hidden/);
  assert.match(rejected(payload(), snapshot({ context: { ...context, context_hash: 'hash-2', scenario_revision: 3 } })), /scenario changed/);
  assert.match(rejected(payload(), snapshot({ current_plan: { run_id: 'run-2', candidate_hash: 'cand-1' } })), /different run/);
  assert.match(rejected(payload(), snapshot({ current_plan: null })), /No checked run/);
  assert.match(rejected({ ...payload(), provenance: 'live' }), /not a local review/);
});

test('an understated escalation, watcher severity or orphan record is rejected', () => {
  const nominal = payload(); nominal.watch.escalation = 'nominal'; nominal.escalation_record = null;
  rejected(nominal);
  const understated = payload(); understated.watch.watchers[0].severity = 'info';
  rejected(understated);
  const orphan = payload(); orphan.watch.watchers[2].record_ids = [];
  rejected(orphan);
  const borrowed = payload(); borrowed.watch.watchers[3].record_ids.push('zone:EVENT:RESIDUAL_HOLDING');
  rejected(borrowed);
  const reordered = payload(); reordered.watch.escalation_reasons.reverse();
  rejected(reordered);
});

test('evidence must point at the reviewed run and numeric fields must be integers', () => {
  const foreign = payload(); foreign.watch.records[0].evidence = [{ source: 'checked_plan', ref: 'run-0', field: 'timeline' }];
  rejected(foreign);
  const fractional = payload(); fractional.watch.records[0].value = 59.5;
  rejected(fractional);
  const unknownSource = payload(); unknownSource.verification.requirements[0].evidence = [{ source: 'model_prose', ref: 'x', field: 'y' }];
  rejected(unknownSource);
});

test('the next step must match escalation and an unconfirmed reserve must wait for an endpoint', () => {
  const transit = snapshot({ physical_gate_state: 'TRANSIT' });
  assert.match(rejected(payload(), transit), /watch records/);
  const waiting = payload(); waiting.watch.next_step = 'await_endpoint'; waiting.escalation_record.next_step = 'await_endpoint';
  assert.equal(reviewPayload(waiting, transit, true).available, true);
  rejected(waiting);
  const advisory = payload();
  advisory.watch.records = advisory.watch.records.filter(item => item.severity !== 'alert');
  advisory.watch.watchers = advisory.watch.watchers.slice(2);
  advisory.watch.escalation = 'advisory'; advisory.watch.escalation_reasons = ['boundary:B1:BOUNDARY_AT_QUOTA']; advisory.escalation_record = null;
  rejected(advisory);
  advisory.watch.next_step = 'none';
  assert.equal(reviewPayload(advisory, snapshot(), true).available, true);
});

test('verification counts, verdict and scope limits must agree with the requirements', () => {
  const miscounted = payload(); miscounted.verification.summary.passed = 3;
  rejected(miscounted);
  const optimistic = payload(); optimistic.verification.requirements[0].status = 'fail'; optimistic.verification.summary.passed = 1; optimistic.verification.summary.failed = 1;
  rejected(optimistic);
  optimistic.verification.verdict = 'not_verified';
  assert.equal(reviewPayload(optimistic, snapshot(), true).available, true);
  const unlimited = payload();
  unlimited.verification.requirements = unlimited.verification.requirements.filter(item => item.status !== 'cannot_measure');
  unlimited.verification.summary.cannot_measure = 0;
  assert.match(rejected(unlimited), /verification report/);
  const guessed = payload(); guessed.verification.requirements[4].status = 'pass';
  guessed.verification.summary.passed = 3; guessed.verification.summary.cannot_measure = 1;
  rejected(guessed);
});

test('an escalation record is required, local-only and matching exactly when escalated', () => {
  const missing = payload(); missing.escalation_record = null;
  assert.match(rejected(missing), /escalation record/);
  const sent = payload(); sent.escalation_record.delivery = 'sms';
  rejected(sent);
  const otherRun = payload(); otherRun.escalation_record.run_id = 'run-0';
  rejected(otherRun);
  const advisory = payload();
  advisory.watch.records = advisory.watch.records.filter(item => item.severity !== 'alert');
  advisory.watch.watchers = advisory.watch.watchers.slice(2);
  advisory.watch.escalation = 'advisory'; advisory.watch.escalation_reasons = ['boundary:B1:BOUNDARY_AT_QUOTA']; advisory.watch.next_step = 'none';
  assert.match(rejected(advisory), /non-escalated/);
});

test('the printable report escapes content, carries scope limits and loads nothing external', () => {
  assert.equal(/<script\b|<link\b|<img\b|\b(?:src|href)\s*=\s*["']|https?:\/\//i.test(buildReviewHtml(payload())), false);
  const data = payload();
  data.watch.records[0].summary = '</td><script>alert(1)</script><img src="https://evil.test/x">';
  const html = buildReviewHtml(data, '2026-10-24T11:00:00Z');
  assert.equal(/<script\b|<link\b|<img\b|\b(?:src|href)\s*=\s*["']/i.test(html), false);
  assert.ok(html.includes('&lt;script&gt;') && html.includes('&lt;img src=&quot;'));
  assert.ok(html.includes("default-src 'none'"));
  for (const expected of ['run-1', 'hash-1', 'esc-0123', 'Outside the model', 'outside:survival statement', 'Escalated · local record', 'No message', '2026-10-24T11:00:00Z'])
    assert.ok(html.includes(expected), expected);
  const json = JSON.parse(reviewJson(data, '2026-10-24T11:00:00Z'));
  assert.equal(json.exported_at, '2026-10-24T11:00:00Z');
  assert.equal(json.review.run_id, 'run-1');
});
