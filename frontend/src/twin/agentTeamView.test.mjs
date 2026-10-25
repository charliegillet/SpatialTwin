import assert from 'node:assert/strict';
import test from 'node:test';
import { applyStart, beginRun, idleRun, reduceTrace } from './agentTeamFlow.ts';
import {
  CHECKER_NOTE, LIVE_CHIP, LOCAL_CHIP, argsSummary, claimRows, claimsLine, compactCount, connectionLabel, elapsedLabel, formatUsd, laneCard, teamFooter, teamLanes, tokenTotal, traceRows,
} from './agentTeamView.ts';

const NOW = 5_000_000;
const startOf = () => ({
  investigation_id: 'dinv-1', deadline_at_ms: NOW + 150_000, trace_url: '/t',
  lanes: { strategist: { investigation_id: 's', deadline_seconds: 45, deadline_at_ms: NOW + 45_000 }, robustness: { investigation_id: 'r', deadline_seconds: 150, deadline_at_ms: NOW + 150_000 } },
});
const running = (mode = 'live') => applyStart(beginRun({ mode, hazardsKey: 'k', now: NOW, lanes: ['strategist', 'robustness'] }), startOf(), NOW);
let seq = 0;
const ev = (event, lane, data = {}) => { seq++; return { seq, event, lane, elapsed_ms: seq, data: { seq, event, lane, ...data } }; };
const check = (over = {}) => ({ index: 0, scenario: 'baseline', applies_to: 'recommended', claimed_completed_crossings: 18, local_completed_crossings: 18, local_is_valid: true, reproduced: true, reason: null, ...over });
const live = (lane, over = {}) => ({ investigation_id: lane, lane, status: 'completed', provenance: 'live', recommended_door_states: { D9: 'open', D4: 'closed' }, fallback_if_jammed: { D9: 'closed' }, errors: [], ...over });

test('claim rows show agent claimed vs checker verified, with mismatches flagged and sandbox numbers labelled as estimates', () => {
  const verification = { verified: 1, total: 2, source: 'sandbox', mismatches: [], checks: [
    check({ scenario: 'baseline' }),
    check({ index: 1, scenario: 'stuck_closed:D3', applies_to: 'fallback', claimed_completed_crossings: 17, local_completed_crossings: 14, reproduced: false, reason: 'crossings_mismatch' }),
  ] };
  const rows = claimRows(verification);
  assert.equal(rows.length, 2);
  assert.deepEqual([rows[0].claimed, rows[0].verified, rows[0].reproduced, rows[0].reason], ['18', '18', true, '']);
  assert.deepEqual([rows[1].claimed, rows[1].verified, rows[1].reproduced], ['17', '14', false]);
  assert.match(rows[1].reason, /different number of crossings/);
  assert.equal(rows[1].appliesTo, 'if the door jams');
  assert.ok(rows.every(row => row.sandboxEstimate));
  assert.equal(claimsLine(verification), '1 of 2 sandbox claims reproduced by the local checker');
});

test('without a full check list only the named mismatches become rows; the line still counts every claim', () => {
  const verification = { verified: 3, total: 4, source: 'agent', mismatches: [check({ scenario: 'jam:D2@0.50', reproduced: false, claimed_completed_crossings: 20, local_completed_crossings: 15, reason: 'crossings_mismatch' })] };
  const rows = claimRows(verification);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].sandboxEstimate, false);
  assert.equal(claimsLine(verification), '3 of 4 claims reproduced by the local checker');
  assert.deepEqual(claimRows(null), []);
  assert.equal(claimsLine({ verified: 0, total: 0, source: 'agent', mismatches: [] }), null);
});

test('a local self-check is never worded as agent evidence', () => {
  assert.match(claimsLine({ verified: 12, total: 12, source: 'local', mismatches: [] }), /Not agent evidence/);
  const run = reduceTrace(running('local'), ev('verification', 'robustness', { verified: 12, total: 12, source: 'local', mismatches: [] }), NOW);
  const footer = teamFooter(run);
  assert.equal(footer.claims, null);
  assert.match(footer.selfCheck, /No agent claims to verify/);
  assert.equal(footer.note, CHECKER_NOTE);
});

test('footer totals agent and sandbox claims across lanes and counts what did not reproduce', () => {
  let run = running();
  run = reduceTrace(run, ev('verification', 'strategist', { verified: 2, total: 2, source: 'agent', mismatches: [] }), NOW);
  run = reduceTrace(run, ev('verification', 'robustness', { verified: 7, total: 9, source: 'sandbox', mismatches: [check({ reproduced: false })] }), NOW);
  const footer = teamFooter(run);
  assert.equal(footer.claims, '9 of 11 claims reproduced by the local checker');
  assert.equal(footer.mismatches, 2);
  assert.equal(footer.selfCheck, null);
});

test('provenance chips: live confirmed by the server, local, and a requested-but-unconfirmed live run', () => {
  let run = running('live');
  assert.equal(laneCard(run, 'strategist', NOW).provenance.text, 'Live run requested');
  run = reduceTrace(run, ev('result', 'strategist', live('strategist')), NOW);
  const card = laneCard(run, 'strategist', NOW);
  assert.equal(card.provenance.text, LIVE_CHIP);
  assert.equal(card.provenance.tone, 'live');
  assert.deepEqual(card.doors, [{ id: 'D4', state: 'closed' }, { id: 'D9', state: 'open' }]);
  assert.equal(laneCard(running('local'), 'strategist', NOW).provenance.text, LOCAL_CHIP);
});

test('a failed live lane with a local fallback shows both: the fallback chip with the reason, and the live failure', () => {
  let run = running();
  run = reduceTrace(run, ev('fallback', 'robustness', { reason: { status: 'failed', errors: ['provider_timeout'] } }), NOW);
  const mid = laneCard(run, 'robustness', NOW);
  assert.equal(mid.chip.text, 'Falling back to local');
  assert.equal(mid.provenance.tone, 'fallback');
  run = reduceTrace(run, ev('result', 'robustness', live('robustness', { provenance: 'local', robustness_headline: 'D9 open holds 8 of 16.', fallback_for: { status: 'failed', errors: ['provider_timeout'] } })), NOW);
  const card = laneCard(run, 'robustness', NOW);
  assert.equal(card.provenance.text, 'Local fallback');
  assert.match(card.provenance.reason, /did not answer in time/);
  assert.match(card.liveFailure, /Live lane failed.*did not answer/);
  assert.equal(card.chip.text, 'Done · local fallback');
  assert.equal(card.summary, 'D9 open holds 8 of 16.');
  assert.equal(card.tokens, 'No model tokens');
});

test('a live lane that failed without a fallback keeps its failure on screen', () => {
  const run = reduceTrace(running(), ev('result', 'strategist', live('strategist', { status: 'failed', errors: ['submission_missing'] })), NOW);
  const card = laneCard(run, 'strategist', NOW);
  assert.equal(card.chip.tone, 'bad');
  assert.match(card.liveFailure, /without submitting/);
});

test('countdown shows while a lane runs and disappears when it ends; token and cost chips', () => {
  let run = running();
  run = reduceTrace(run, ev('lane', 'strategist', { status: 'started' }), NOW);
  assert.equal(laneCard(run, 'strategist', NOW + 3000).countdown, '0:42 left');
  assert.equal(laneCard(run, 'robustness', NOW + 3000).countdown, '2:27 left');
  run = reduceTrace(run, ev('usage', 'strategist', { token_usage: { total_tokens: 12400 }, token_budget: 40000, cost_estimate: { usd: 0.0345, input_tokens: 9000, output_tokens: 3400 } }), NOW);
  const card = laneCard(run, 'strategist', NOW + 3000);
  assert.equal(card.tokens, '12k / 40k tokens');
  assert.equal(card.cost, '≈ $0.035 est.');
  run = reduceTrace(run, ev('result', 'strategist', live('strategist', { latency_ms: 21400 })), NOW);
  const done = laneCard(run, 'strategist', NOW + 30000);
  assert.equal(done.countdown, null);
  assert.equal(done.elapsed, '21 s');
});

test('lane order and idle runs', () => {
  assert.deepEqual(teamLanes(running()), ['strategist', 'robustness']);
  assert.deepEqual(teamLanes(idleRun()), []);
  assert.equal(connectionLabel(running()), null);
  assert.match(connectionLabel({ ...running(), connection: 'polling' }), /polling/);
  assert.match(connectionLabel({ ...running(), connection: 'offline' }), /retrying/);
});

test('trace rows: code collapses to its first line, calls show short args, results summarise', () => {
  const rows = traceRows([
    { key: 'a', kind: 'code', atMs: 1, text: 'import json\nprint(1)\nprint(2)' },
    { key: 'b', kind: 'code', atMs: 2, text: 'x = 1' },
    { key: 'c', kind: 'call', atMs: 3, name: 'compare_door_states', text: '{"states":[{"D9":"open"}],"note":"a very long note that keeps going and going past the limit"}' },
    { key: 'd', kind: 'result', atMs: 4, text: '' },
    { key: 'e', kind: 'tool', atMs: 5, name: 'plan_doors', text: 'executed · 15 ms' },
  ]);
  assert.equal(rows[0].head, 'import json');
  assert.equal(rows[0].body, 'import json\nprint(1)\nprint(2)');
  assert.equal(rows[1].body, null);
  assert.equal(rows[2].label, 'call compare_door_states');
  assert.ok(rows[2].head.length <= 90);
  assert.match(rows[2].head, /^states=/);
  assert.equal(rows[3].head, '(no output)');
  assert.equal(rows[4].label, 'checker plan_doors');
});

test('formatters', () => {
  assert.equal(argsSummary('{"door":"D3","n":2}'), 'door="D3", n=2');
  assert.equal(argsSummary('{"door":'), '{"door":');
  assert.equal(argsSummary(''), '');
  assert.equal(compactCount(950), '950');
  assert.equal(compactCount(1250), '1.3k');
  assert.equal(compactCount(150000), '150k');
  assert.equal(tokenTotal({ total_tokens: 5 }), 5);
  assert.equal(tokenTotal({ input_tokens: 3, output_tokens: 4 }), 7);
  assert.equal(tokenTotal({}, { usd: 1, input_tokens: 10, output_tokens: 5 }), 15);
  assert.equal(tokenTotal(undefined, null), null);
  assert.equal(formatUsd(0.0004), '<$0.001');
  assert.equal(formatUsd(0.034), '$0.034');
  assert.equal(formatUsd(2.5), '$2.50');
  assert.equal(elapsedLabel(61_000), '1 min 1 s');
});
