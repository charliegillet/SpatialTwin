import assert from 'node:assert/strict';
import test from 'node:test';
import { ApiError } from '../api/client.ts';
import {
  claimReasonCopy, followupError, isParentFinishing, parseLaneView, parseTeamProgress, parseTeamStart, parseTraceEvent, teamLaneErrorCopy, teamReadError, teamStartError, traceUrl,
  TEAM_LANE_ERRORS,
} from '../api/agentTeam.ts';

const startBody = () => ({
  investigation_id: 'dinv-1', deadline_at: 'x', deadline_at_ms: 2000,
  lanes: {
    strategist: { investigation_id: 'dinv-1.strategist', deadline_seconds: 45, deadline_at_ms: 1000 },
    robustness: { investigation_id: 'dinv-1.robustness', deadline_seconds: 150, deadline_at_ms: 2000 },
  },
  trace_url: '/api/venues/building-v2/investigations/dinv-1/trace',
});
const laneBody = (lane, over = {}) => ({ investigation_id: `dinv-1.${lane}`, lane, status: 'completed', provenance: 'local', recommended_door_states: { D9: 'open' }, verification: { verified: 1, total: 1, source: 'local', mismatches: [] }, ...over });
const progressBody = (over = {}) => ({
  investigation_id: 'dinv-1', status: 'completed', team_status: 'finished', deadline_at_ms: 2000,
  lanes: { strategist: laneBody('strategist'), robustness: { investigation_id: 'dinv-1.robustness', lane: 'robustness', status: 'running' } },
  trace_url: '/t', provenance_ignored: true, ...over,
});

test('start parser accepts the documented response and rejects broken ones', () => {
  const start = parseTeamStart(startBody());
  assert.equal(start.investigation_id, 'dinv-1');
  assert.equal(start.lanes.robustness.deadline_at_ms, 2000);
  assert.equal(start.parent_investigation_id, null);
  assert.equal(parseTeamStart({ ...startBody(), parent_investigation_id: 'dinv-0', scenario: 'stuck_closed:D3' }).scenario, 'stuck_closed:D3');
  for (const broken of [null, {}, { ...startBody(), investigation_id: '' }, { ...startBody(), lanes: {} }, { ...startBody(), trace_url: 3 },
    { ...startBody(), lanes: { strategist: { investigation_id: 'x' } } }, { ...startBody(), lanes: { oracle: startBody().lanes.strategist } }, { ...startBody(), deadline_at_ms: 'soon' }]) {
    assert.throws(() => parseTeamStart(broken), ApiError);
  }
});

test('progress parser keeps running lane stubs and follows the lane views', () => {
  const progress = parseTeamProgress(progressBody());
  assert.equal(progress.team_status, 'finished');
  assert.equal(progress.lanes.strategist.status, 'completed');
  assert.equal(progress.lanes.robustness.status, 'running');
  assert.equal(parseTeamProgress(progressBody({ lanes: {} })).lanes.strategist, undefined);
  assert.throws(() => parseTeamProgress(progressBody({ team_status: 'weird' })), ApiError);
  assert.throws(() => parseTeamProgress(progressBody({ lanes: null })), ApiError);
  assert.throws(() => parseTeamProgress(progressBody({ lanes: { strategist: { status: 'completed' } } })), ApiError);
});

test('lane views parse a nested fallback and reject a broken verification', () => {
  const view = parseLaneView(laneBody('robustness', { status: 'failed', provenance: 'live', effective: 'local_fallback', fallback: laneBody('robustness') }));
  assert.equal(view.fallback.provenance, 'local');
  assert.equal(parseLaneView({ investigation_id: 'a', status: 'running' }, 'strategist').lane, 'strategist');
  assert.throws(() => parseLaneView(laneBody('strategist', { verification: { verified: 1 } })), ApiError);
  assert.throws(() => parseLaneView({ investigation_id: 'a', status: 'running' }), ApiError);
});

test('trace frames parse per event name; unknown names and bad JSON are skipped', () => {
  const frame = parseTraceEvent('step', JSON.stringify({ seq: 7, event: 'step', lane: 'robustness', elapsed_ms: 12.5, index: 2, step_type: 'code_execution_call', text: 'print(1)' }));
  assert.equal(frame.seq, 7);
  assert.equal(frame.lane, 'robustness');
  assert.equal(frame.data.step_type, 'code_execution_call');
  assert.equal(parseTraceEvent('deadline', JSON.stringify({ seq: 1, lane: null })).lane, null);
  assert.equal(parseTraceEvent('step', '{not json'), null);
  assert.equal(parseTraceEvent('mystery', JSON.stringify({ seq: 1 })), null);
  assert.equal(parseTraceEvent('step', JSON.stringify({ lane: 'robustness' })), null);
  assert.equal(parseTraceEvent('step', JSON.stringify({ seq: 3, lane: 'not-a-lane' })).lane, null);
});

test('every documented error code has judge-readable copy', () => {
  assert.match(teamStartError(429, ''), /already working/);
  assert.match(teamStartError(403, ''), /disabled/);
  assert.match(teamStartError(404, 'unknown_venue'), /not available/);
  assert.match(teamStartError(422, 'outside_building'), /./);
  assert.match(teamStartError(422, 'duplicate_lane'), /twice/);
  assert.equal(teamStartError(500, ''), '');
  assert.match(followupError(404, 'unknown_investigation'), /no longer available/);
  assert.match(followupError(409, 'parent_running'), /still working/);
  assert.match(followupError(409, 'parent_finishing'), /wrapping up/);
  assert.match(followupError(422, 'scenario_unrecognized'), /stuck_closed:D3/);
  assert.match(followupError(429, ''), /already working/);
  assert.match(followupError(403, ''), /disabled/);
  assert.match(teamReadError(404, 'unknown_investigation'), /no longer available/);
  for (const code of ['investigation_deadline', 'submission_missing', 'followup_parent_unavailable', 'provider_rate_limited']) assert.ok(TEAM_LANE_ERRORS[code]);
  assert.match(TEAM_LANE_ERRORS.investigation_deadline, /deadline/);
  assert.equal(teamLaneErrorCopy(['mystery', 'submission_missing']), TEAM_LANE_ERRORS.submission_missing);
  assert.equal(teamLaneErrorCopy(['mystery']), 'The agent run did not complete.');
  assert.equal(teamLaneErrorCopy([]), '');
  assert.match(claimReasonCopy('crossings_mismatch'), /different number/);
  assert.match(claimReasonCopy('brand_new_reason'), /could not reproduce/);
  assert.equal(claimReasonCopy(null), '');
});

test('trace url appends the replay cursor only when there is one', () => {
  assert.equal(traceUrl('/t'), '/t');
  assert.equal(traceUrl('/t', 0), '/t');
  assert.equal(traceUrl('/t', 12), '/t?after=12');
  assert.equal(traceUrl('/t?x=1', 12), '/t?x=1&after=12');
});

test('only a 409 parent_finishing is retryable', () => {
  assert.equal(isParentFinishing(new ApiError('m', 409, 'parent_finishing')), true);
  assert.equal(isParentFinishing(new ApiError('m', 409, 'parent_running')), false);
  assert.equal(isParentFinishing(new ApiError('m', 500, 'parent_finishing')), false);
  assert.equal(isParentFinishing(new Error('x')), false);
});
