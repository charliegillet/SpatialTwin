import test from 'node:test';
import assert from 'node:assert/strict';
import { canApplyGrounding, canApproveInvestigation, canCompareInvestigation, groundingLabel, investigationLabel, sameContext } from './policy.ts';
import { cancelInvestigation, clearBlockage, fetchInvestigationProgress, interpretGrounding, investigateScenario, operatorApproveGate } from '../api/client.ts';
import { captureEvidence, progressDescription } from './evidence.ts';

const context = {
  state_epoch: 'server-process-1',
  geometry_revision: 'geometry-1', scenario_revision: 2, physical_revision: 3,
  parameters_revision: 'params-1', solver_version: 'solver-1', context_hash: 'server-hash',
};
const grounding = () => ({
  proposal_id: 'saved-proposal', provenance: 'live', status: 'completed', provider_interaction_id: 'provider-1', errors: [], token_usage: {}, latency_ms: 20,
  proposal: { version: '1', capture_id: 'capture-1', source_context: { ...context }, status: 'matched', candidate_ids: ['portal:P2'], selected_entity_type: 'portal', selected_entity_id: 'P2', operation: 'SET_UNAVAILABLE', evidence: 'Printed pad P2.' },
});
const candidate = (alternative_id, completed_crossings) => ({
  alternative_id, base_context: { ...context }, status: 'PARTIAL_WITHIN_HORIZON', initial_population: 120,
  completed_crossings, remaining_population: 120 - completed_crossings, horizon_seconds: 40, time_step_seconds: 2,
  validator_report: { is_valid: true },
});
const investigation = () => ({
  provenance: 'live', status: 'completed', provider_interaction_id: 'managed-1', base_context: { ...context },
  recommended_alternative: 'OPEN_P3',
  candidate_envelopes: [candidate('KEEP_CURRENT', 60), candidate('OPEN_P3', 90)],
});

test('full context, including server hash, is required; stale parameters or solver fail closed', () => {
  assert.equal(sameContext(context, { ...context }), true);
  assert.equal(sameContext(context, { ...context, context_hash: undefined }), false);
  assert.equal(sameContext(context, { ...context, state_epoch: 'restarted-process' }), false);
  for (const field of Object.keys(context)) {
    assert.equal(sameContext(context, { ...context, [field]: 'different' }), false, field);
  }
});

test('configuration alone never creates a live source label', () => {
  assert.equal(groundingLabel(null), 'No model result');
  assert.equal(investigationLabel(null), 'No analysis yet');
  assert.equal(groundingLabel({ ...grounding(), provider_interaction_id: null }), 'Provider unverified');
  assert.equal(investigationLabel({ ...investigation(), provider_interaction_id: null }), 'Provider unverified');
  assert.equal(groundingLabel(grounding()), 'Live Gemini result');
  assert.equal(investigationLabel(investigation()), 'Live Gemini analysis');
});

test('explicit fixtures and local computation remain visibly distinct from Gemini', () => {
  const fixture = { ...grounding(), provenance: 'fixture', provider_interaction_id: null };
  assert.equal(groundingLabel(fixture), 'Fixture · no Gemini call');
  assert.equal(canApplyGrounding(fixture, context), true);
  const local = { ...investigation(), provenance: 'local', provider_interaction_id: null };
  assert.equal(investigationLabel(local), 'Local solver · no Gemini call');
  assert.equal(canCompareInvestigation(local, context), true);
  assert.match(investigationLabel({ ...investigation(), replayed: true }), /^Replayed saved run · Gemini/);
});

test('failed, timed-out, cancelled, incomplete and unverified outputs cannot apply or compare', () => {
  for (const status of ['failed', 'timed_out', 'cancelled', 'incomplete', 'in_progress', 'unavailable']) {
    assert.equal(canApplyGrounding({ ...grounding(), status }, context), false, status);
    assert.equal(canCompareInvestigation({ ...investigation(), status }, context), false, status);
    assert.doesNotMatch(groundingLabel({ ...grounding(), status }), /^Live/);
    assert.doesNotMatch(investigationLabel({ ...investigation(), status }), /^Live/);
  }
  assert.equal(canApplyGrounding({ ...grounding(), provenance: 'unavailable' }, context), false);
  assert.equal(canCompareInvestigation({ ...investigation(), provenance: undefined }, context), false);
});

test('apply requires saved review record, known typed target, candidate membership and current context', () => {
  assert.equal(canApplyGrounding(grounding(), context), true);
  assert.equal(canApplyGrounding({ ...grounding(), proposal_id: null }, context), false);
  assert.equal(canApplyGrounding({ ...grounding(), provider_interaction_id: null }, context), false);
  assert.equal(canApplyGrounding(grounding(), { ...context, scenario_revision: 99 }), false);
  for (const change of [
    { status: 'ambiguous' }, { status: 'no_match' }, { selected_entity_id: 'D99' },
    { selected_entity_type: 'boundary' }, { candidate_ids: [] },
    { candidate_ids: ['portal:P2', 'invented:D99'] }, { operation: 'OPEN_ALL_EXITS' },
    { candidate_ids: ['portal:P2', 'portal:P2'] }, { box_2d: [-15, 2000] }, { box_2d: [100, 20, 50, 300] },
  ]) {
    const result = grounding();
    result.proposal = { ...result.proposal, ...change };
    assert.equal(canApplyGrounding(result, context), false, JSON.stringify(change));
  }
});

test('capture API preserves original metadata and keeps fixture controls explicit', async t => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  let sent;
  globalThis.fetch = async (url, init) => {
    sent = { url, body: JSON.parse(init.body) };
    return new Response(JSON.stringify(grounding()), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  const capture = { capture_id: 'camera-capture-1', timestamp_iso: '2026-10-24T08:12:34.123Z', source_context: context, dimensions: [1280, 720], source_kind: 'tabletop_camera', mode: 'live', image_base64: 'test-image', thinking_level: 'high' };
  await interpretGrounding('facility-demo', capture);
  assert.equal(sent.url, '/api/scenarios/facility-demo/grounding');
  assert.deepEqual(sent.body, capture);
  assert.equal('force_target' in sent.body, false);
  assert.equal('fixture_target' in sent.body, false);
  const fixture = { capture_id: 'fixture-1', timestamp_iso: capture.timestamp_iso, source_context: context, dimensions: [600, 275], source_kind: 'fixture', mode: 'fixture', fixture_target: 'P1', thinking_level: 'low' };
  await interpretGrounding('facility-demo', fixture);
  assert.deepEqual(sent.body, fixture);
  assert.equal('image_base64' in sent.body, false);
});

test('investigation and manual mutation APIs send the complete reviewed context', async t => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const sent = [];
  globalThis.fetch = async (url, init) => {
    sent.push({ url, body: JSON.parse(init.body) });
    return new Response('{}', { status: 200, headers: { 'content-type': 'application/json' } });
  };
  await investigateScenario('facility-demo', context, 'local', 'local-request-1');
  await investigateScenario('facility-demo', context, 'live', 'live-request-2');
  assert.equal(sent[0].body.mode, 'local');
  assert.equal(sent[1].body.mode, 'live');
  assert.notEqual(sent[0].body.investigation_id, sent[1].body.investigation_id);
  assert.equal(sent[0].body.investigation_id, 'local-request-1');
  assert.equal(sent[1].body.investigation_id, 'live-request-2');
  assert.equal(sent[0].body.deadline_seconds, 60);
  assert.deepEqual(sent[0].body.expected_context, context);
  await clearBlockage('facility-demo', context, 'boundary', 'B2');
  assert.deepEqual(sent[2].body.expected_context, context);
  assert.equal(sent[2].body.expected_scenario_revision, context.scenario_revision);
  assert.equal(sent[2].body.source, 'manual_override');
  await operatorApproveGate(context, 'reviewed-investigation-1', 'reviewed-reserve-run');
  assert.equal(sent[3].url, '/api/hardware/operator-approve');
  assert.deepEqual(sent[3].body.expected_context, context);
  assert.equal(sent[3].body.investigation_id, 'reviewed-investigation-1');
  assert.equal(sent[3].body.candidate_run_id, 'reviewed-reserve-run');
  assert.ok(sent[3].body.idempotency_key);
});

test('physical approval requires a positive checked improvement and OPEN_P3 recommendation', () => {
  assert.equal(canApproveInvestigation(investigation(), context), true);
  for (const gain of [0, -1]) {
    const result = investigation();
    result.candidate_envelopes[1] = candidate('OPEN_P3', 60 + gain);
    assert.equal(canCompareInvestigation(result, context), true);
    assert.equal(canApproveInvestigation(result, context), false);
  }
  assert.equal(canApproveInvestigation({ ...investigation(), recommended_alternative: 'KEEP_CURRENT' }, context), false);
  assert.equal(canApproveInvestigation({ ...investigation(), recommended_alternative: null }, context), false);
  assert.equal(canApproveInvestigation({ ...investigation(), status: 'cancelled' }, context), false);
});

test('progress polling tolerates startup404 and preserves abort control; cancel targets the original context', async t => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  const requests = [];
  const controller = new AbortController();
  globalThis.fetch = async (url, init = {}) => {
    requests.push({ url, init });
    return requests.length === 1 ? new Response('{}', { status: 404 })
      : new Response(JSON.stringify({ status: 'cancellation_requested' }), { status: 200, headers: { 'content-type': 'application/json' } });
  };
  assert.deepEqual(await fetchInvestigationProgress('facility-demo', 'owned-request-1', controller.signal), { investigation_id: 'owned-request-1', status: 'not_found', provider_progress: [] });
  assert.equal(requests[0].init.signal, controller.signal);
  await cancelInvestigation('facility-demo', 'owned-request-1', context);
  assert.equal(requests[1].url, '/api/scenarios/facility-demo/investigations/owned-request-1/cancel');
  assert.deepEqual(JSON.parse(requests[1].init.body), { expected_context: context });
  assert.equal(requests[1].init.method, 'POST');
});

test('capture evidence retains original image, dimensions and timestamp with a matching SHA256', async () => {
  const input = { capture_id: 'capture-hash', timestamp_iso: '2026-10-24T08:12:34.123Z', source_context: context, dimensions: [1280, 720], source_kind: 'tabletop_camera', mode: 'live', image_base64: btoa('abc'), thinking_level: 'low' };
  const evidence = await captureEvidence(input);
  assert.deepEqual({ ...evidence, image_sha256: undefined }, { ...input, image_sha256: undefined });
  assert.equal(evidence.image_sha256, 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
  const fixture = { ...input, source_kind: 'fixture', mode: 'fixture', image_base64: undefined };
  assert.equal((await captureEvidence(fixture)).image_sha256, undefined);
});

test('provider progress descriptions expose lifecycle metadata without thought text or arbitrary tool names', () => {
  assert.equal(progressDescription({ phase: 'provider_response', status: 'requires_action', thought: 'private text' }), 'Gemini response · requires action');
  assert.match(progressDescription({ phase: 'local_tool_complete', function_name: 'get_checked_comparison' }), /get_checked_comparison/);
  assert.equal(progressDescription({ phase: 'local_tool_complete', function_name: 'arbitrary_shell', thought: 'private text' }), 'Read-only tool update');
});

test('failed HTTP interpretation stays a failure instead of returning a fixture', async t => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Stale full context; refresh and review again' }), { status: 409, headers: { 'content-type': 'application/json' } });
  await assert.rejects(() => interpretGrounding('facility-demo', {}), /Stale full context/);
});

test('comparison requires checked candidates under equal conditions, preserving every occupant', () => {
  assert.equal(canCompareInvestigation(investigation(), context), true);
  for (const change of [
    { initial_population: 119 }, { remaining_population: -1 }, { completed_crossings: Number.NaN },
    { horizon_seconds: 39 }, { time_step_seconds: 1 }, { status: 'FAILED' },
    { validator_report: { is_valid: false } }, { base_context: { ...context, physical_revision: 99 } },
  ]) {
    const result = investigation();
    result.candidate_envelopes[1] = { ...result.candidate_envelopes[1], ...change };
    assert.equal(canCompareInvestigation(result, context), false, JSON.stringify(change));
  }
  assert.equal(canCompareInvestigation({ ...investigation(), candidate_envelopes: [candidate('KEEP_CURRENT', 60)] }, context), false);
});
