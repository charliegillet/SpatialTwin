import assert from 'node:assert/strict';
import test from 'node:test';
import {
  BASE64_CHUNK, PIPELINE_ERRORS, REAL2SIM_ERRORS, bytesToBase64, effectiveKind, fitSize, overlayUrl, parseAcceptResponse, parseDraftEvent, parseDraftView, parseSavedRuns,
  pipelineErrorMessage, real2simErrorMessage, sourceMime, topdownUrl,
} from '../api/real2sim.ts';
import { ApiError } from '../api/client.ts';
import {
  acceptDisabledReason, blockerLabel, countsLine, progressSteps, readBuildingWidth, readHeadcount, receiptView, reconcileSelection, roundLine, thoughtSegments, toggleDoor,
} from './real2simView.ts';
import { makeView } from './real2simFixture.ts';

const invalid = error => error instanceof ApiError && error.status === 502 && error.detail === 'invalid_response';

test('a well-formed draft view parses with every list present', () => {
  const view = parseDraftView(makeView());
  assert.equal(view.status, 'ready');
  assert.equal(view.controllable_door_candidates[0].room_names[1], 'Hall');
  assert.equal(view.checks.issues[0].severity, 'warning');
  assert.equal(view.receipts[0].token_usage.total_tokens, 23000);
});

test('malformed draft views are rejected as 502 invalid_response', () => {
  const good = makeView();
  for (const broken of [null, [], {}, { ...good, draft_id: 'nope' }, { ...good, revision: '3' }, { ...good, status: 'weird' }, { ...good, provenance: 'maybe' },
    { ...good, provenance_label: undefined }, { ...good, thoughts: null }, { ...good, unreadable: [1] }, { ...good, accept_blockers: 'x' }, { ...good, checks: { issues: [{}] } }, { ...good, rounds: [{}] }]) {
    assert.throws(() => parseDraftView(broken), invalid);
  }
});

test('saved runs keep the server provenance label verbatim and reject junk', () => {
  const raw = { fixtures_enabled: true, saved: [{ fixture_id: 'sketch-home', title: 'Home', source_kind: 'sketch', provenance: 'synthetic', provenance_label: 'Synthetic saved run: x', counts: { rooms: 6, doors: 6, exits: 3 }, note: 'n' }] };
  const parsed = parseSavedRuns(raw);
  assert.equal(parsed.saved[0].provenance_label, 'Synthetic saved run: x');
  assert.deepEqual(parsed.saved[0].counts, { rooms: 6, doors: 6, exits: 3 });
  assert.deepEqual(parseSavedRuns({ fixtures_enabled: false, saved: [] }).saved, []);
  for (const broken of [null, { saved: [] }, { fixtures_enabled: true, saved: [{ fixture_id: 'a' }] }, { fixtures_enabled: true, saved: [{ ...raw.saved[0], source_kind: 'video' }] }]) {
    assert.throws(() => parseSavedRuns(broken), invalid);
  }
});

test('accept responses are validated', () => {
  const ok = { venue_id: 'meridian-1-24a745', venue_revision: 1, draft_revision: 4, active_revision: 7, geometry_revision: 'geom-1', provenance: 'live', warnings: [], defaults: ['d'] };
  assert.equal(parseAcceptResponse(ok).active_revision, 7);
  assert.equal(parseAcceptResponse({ ...ok, active_revision: null }).active_revision, null);
  assert.throws(() => parseAcceptResponse({ ...ok, venue_id: 5 }), invalid);
  assert.throws(() => parseAcceptResponse(null), invalid);
});

test('SSE events parse; unknown or malformed ones are skipped, never thrown', () => {
  assert.deepEqual(parseDraftEvent('status', '{"status":"checking","phase":"check","revision":2,"provenance":"live"}'), { name: 'status', status: 'checking', phase: 'check', revision: 2, provenance: 'live' });
  assert.equal(parseDraftEvent('thought', '{"phase":"extract","index":0,"text":"**Walls** look thin","recorded":false}').thought.text, '**Walls** look thin');
  assert.deepEqual(parseDraftEvent('draft', '{"phase":"extract","draft":{},"unreadable":["a"],"dropped":[],"repaired":[],"counts":{"rooms":2,"doors":1,"exits":1}}').counts, { rooms: 2, doors: 1, exits: 1 });
  assert.equal(parseDraftEvent('checks', '{"issues":[],"errors":0,"warnings":0,"compile_error":null,"geometry_revision":"g"}').checks.errors, 0);
  assert.equal(parseDraftEvent('done', '{"revision":5,"errors":0,"warnings":1}').revision, 5);
  assert.equal(parseDraftEvent('error', '{"code":"provider_timeout","revision":3}').code, 'provider_timeout');
  assert.equal(parseDraftEvent('mystery', '{}'), null);
  assert.equal(parseDraftEvent('status', 'not json'), null);
  assert.equal(parseDraftEvent('status', '{"status":"bogus","revision":1}'), null);
  assert.equal(parseDraftEvent('thought', '{"text":5}'), null);
  assert.equal(parseDraftEvent('draft', '{"unreadable":[1]}'), null);
});

test('every documented error code has judge-readable copy', () => {
  const documented = ['fixtures_disabled', 'unknown_fixture', 'draft_id_conflict', 'source_too_large', 'unsupported_mime_type', 'source_required', 'invalid_source_encoding', 'source_mime_mismatch',
    'source_kind_mismatch', 'invalid_source_image', 'invalid_source_dimensions', 'invalid_fixture_id', 'invalid_fixture', 'real2sim_busy', 'configuration_missing', 'runtime_storage_unavailable',
    'unknown_draft', 'draft_not_ready', 'stale_draft_revision', 'draft_closed', 'too_many_controllable_doors', 'duplicate_controllable_door', 'unknown_controllable_door', 'invalid_venue_id',
    'compile_failed', 'compiler_failure', 'graph_check_errors'];
  for (const code of documented) assert.ok(REAL2SIM_ERRORS[code], code);
  const providerCodes = ['provider_model_mismatch', 'provider_receipt_missing', 'provider_status_not_completed', 'unexpected_provider_step', 'provider_stream_incomplete', 'invalid_provider_output',
    'draft_not_an_object', 'no_room_survived', 'provider_timeout', 'provider_rate_limited', 'provider_access_denied', 'provider_unavailable', 'provider_request_rejected', 'provider_stream_error',
    'provider_failure', 'local_processing_failure', 'pipeline_interrupted'];
  for (const code of providerCodes) assert.ok(PIPELINE_ERRORS[code], code);
  assert.equal(real2simErrorMessage(503, 'configuration_missing'), 'Gemini is not configured on this server. Use a saved run instead.');
  assert.match(real2simErrorMessage(429, 'real2sim_busy'), /Another reading is running/);
  assert.match(real2simErrorMessage(409, 'stale_draft_revision'), /changed/);
  assert.match(real2simErrorMessage(413, ''), /8 MB/);
  assert.equal(real2simErrorMessage(500, ''), '');
  assert.match(pipelineErrorMessage('never_heard_of_it'), /Try again/);
  assert.ok(Object.values({ ...REAL2SIM_ERRORS, ...PIPELINE_ERRORS }).every(text => text.length < 140 && !/[{}]/.test(text)));
});

test('base64 chunking handles large buffers without a stack error and round-trips', () => {
  assert.equal(BASE64_CHUNK % 3, 0);
  const size = 9 * 1024 * 1024 + 7;
  const bytes = new Uint8Array(size);
  for (let i = 0; i < size; i += 1) bytes[i] = (i * 31 + 7) & 255;
  const encoded = bytesToBase64(bytes);
  assert.equal(encoded, Buffer.from(bytes).toString('base64'));
  assert.equal(bytesToBase64(new Uint8Array(0)), '');
  assert.equal(bytesToBase64(new Uint8Array([1, 2, 3, 4])), 'AQIDBA==');
  // A single fromCharCode.apply over the whole buffer is what the chunking avoids.
  assert.throws(() => String.fromCharCode.apply(null, bytes), RangeError);
});

test('mime and kind rules follow the contract (pdf <=> application/pdf)', () => {
  assert.equal(sourceMime('x.bin', 'image/png'), 'image/png');
  assert.equal(sourceMime('IMG_1.JPG', ''), 'image/jpeg');
  assert.equal(sourceMime('plan.pdf', ''), 'application/pdf');
  assert.equal(sourceMime('x.gif', 'image/gif'), null);
  assert.equal(effectiveKind('application/pdf', 'photo'), 'pdf');
  assert.equal(effectiveKind('image/png', 'pdf'), 'photo');
  assert.equal(effectiveKind('image/png', 'sketch'), 'sketch');
  assert.deepEqual(fitSize(8000, 4000), { width: 4096, height: 2048, scale: 0.512 });
  assert.deepEqual(fitSize(1000, 500), { width: 1000, height: 500, scale: 1 });
  assert.match(overlayUrl('r2s-' + 'a'.repeat(24), 3), /\/overlay\.png\?rev=3$/);
  assert.match(topdownUrl('r2s-' + 'a'.repeat(24), 3), /\/topdown\.png\?rev=3$/);
});

test('thought text is split into plain segments, never markup', () => {
  assert.deepEqual(thoughtSegments('**Reading the walls** then <img src=x onerror=alert(1)> done'),
    [{ text: 'Reading the walls', bold: true }, { text: ' then <img src=x onerror=alert(1)> done', bold: false }]);
  assert.deepEqual(thoughtSegments('plain'), [{ text: 'plain', bold: false }]);
  assert.deepEqual(thoughtSegments('**open'), [{ text: '**open', bold: false }]);
  assert.deepEqual(thoughtSegments(''), []);
});

test('controllable doors: at most 3, toggle off, refresh keeps only live candidates', () => {
  let selected = [];
  for (const key of ['KD1', 'KD2', 'KD3', 'KD4']) selected = toggleDoor(selected, key);
  assert.deepEqual(selected, ['KD1', 'KD2', 'KD3']);
  assert.deepEqual(toggleDoor(selected, 'KD2'), ['KD1', 'KD3']);
  assert.deepEqual(reconcileSelection(['KD1', 'KD9'], [{ key: 'KD1' }, { key: 'KD2' }]), ['KD1']);
});

test('optional headcount and width are validated', () => {
  assert.deepEqual(readHeadcount(''), { ok: true, value: undefined });
  assert.deepEqual(readHeadcount(' 40 '), { ok: true, value: 40 });
  assert.equal(readHeadcount('5001').ok, false);
  assert.equal(readHeadcount('-1').ok, false);
  assert.equal(readHeadcount('4.5').ok, false);
  assert.deepEqual(readBuildingWidth('24,5'), { ok: true, value: 24.5 });
  assert.deepEqual(readBuildingWidth(''), { ok: true, value: undefined });
  for (const text of ['0', '501', 'abc', '-3']) assert.equal(readBuildingWidth(text).ok, false, text);
});

test('Accept is disabled with a reason while blockers exist or the draft is not ready', () => {
  const ok = { stage: 'ready', blockers: [] };
  assert.equal(acceptDisabledReason(ok), null);
  assert.equal(acceptDisabledReason({ ...ok, stage: 'extracting' }), 'The draft is not ready yet');
  assert.equal(acceptDisabledReason({ ...ok, stage: 'accepting' }), 'Accepting…');
  assert.match(acceptDisabledReason({ ...ok, blockers: ['room_unreachable', 'compile:no_exit_survived'] }), /cannot reach any exit. No exit could be placed/);
  assert.equal(acceptDisabledReason({ ...ok, headcountError: 'bad' }), 'bad');
  // Leaving every unreachable room out lifts only that blocker; anything else still blocks.
  assert.equal(acceptDisabledReason({ ...ok, blockers: ['room_unreachable'], unreachableResolved: true }), null);
  assert.match(acceptDisabledReason({ ...ok, blockers: ['room_unreachable', 'compile:no_exit_survived'], unreachableResolved: true }), /No exit could be placed/);
  assert.match(acceptDisabledReason({ ...ok, blockers: ['room_unreachable'], unreachableResolved: false }), /cannot reach any exit/);
  assert.equal(blockerLabel('status:extracting'), 'Still reading the drawing');
  assert.equal(blockerLabel('weird_code'), 'Check failed: weird code');
});

test('progress steps, receipt chip, round lines and counts read honestly', () => {
  assert.deepEqual(progressSteps('extracting', false).map(step => `${step.label}:${step.state}`), ['Reading:active', 'Checking:pending', 'Ready:pending']);
  assert.deepEqual(progressSteps('critiquing', true).map(step => `${step.label}:${step.state}`), ['Reading:done', 'Checking:done', 'Fixing (critique):active', 'Ready:pending']);
  assert.ok(progressSteps('ready', true).every(step => step.state === 'done'));
  assert.ok(progressSteps('failed', false).every(step => step.state === 'pending'));
  const live = receiptView(makeView());
  assert.deepEqual([live.provenance, live.model, live.latency, live.tokens, live.thinking], ['Live Gemini 4 Argon', 'gemini-4-argon', '29 s', '23,000 tokens', 'medium thinking']);
  const synthetic = receiptView(makeView({ provenance: 'synthetic', provenance_label: 'Synthetic saved run: x', receipts: [] }));
  assert.deepEqual([synthetic.provenance, synthetic.fullLabel, synthetic.model, synthetic.tone], ['Synthetic saved run', 'Synthetic saved run: x', null, 'saved']);
  const round = { round: 1, accepted: true, note: 'n', issues_before: { errors: 3, warnings: 1, compile_failed: false }, issues_after: { errors: 0, warnings: 1, compile_failed: false } };
  assert.equal(roundLine(round), 'round 1: 3 errors → 0 (correction kept)');
  assert.equal(countsLine({ rooms: 1, doors: 2, exits: 1 }), '1 room · 2 doors · 1 exit');
  assert.equal(countsLine(null), null);
});
