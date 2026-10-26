import assert from 'node:assert/strict';
import test from 'node:test';
import { FAILSAFE_OFF, parseFailSafe, parseIncidentEvent, parseIncidentState } from '../api/incident.ts';
import { approvalSummary, executingNote, failsafeAnnounceKey, failsafeDisplay, initialIncidentState, reduceIncidentEvent } from './incidentFlow.ts';
import { twinHero, withFallback } from './twinHero.ts';
import { announceFailsafe, createAudioPlayer, voiceNote } from './announce.ts';

const gate = id => ({ gate_id: id, state: 'CLOSED', open_switch: false, closed_switch: true, epoch: 1, target: null, fault: null,
  last_command_id: null, last_ack: null, observed: 'closed', applied: 'closed', detail: '' });
const plan = (over = {}) => ({
  plan_id: 'dp-1', plan_revision: 4, candidate_hash: 'h4', label: 'primary', note: null, reason: 'hazards updated', valid: true,
  initial_population: 125, completed_crossings: 105, baseline_completed: 93, count_label: 'modeled crossings',
  door_states: { D4: 'open', D9: 'closed' }, doors: [], stuck_doors: [], held_doors: [], advisories: [], announcement: 'a', ...over,
});
const NOW = Date.parse('2026-10-26T12:00:00.000Z');
const armed = (over = {}) => ({ ...FAILSAFE_OFF, armed: true, status: 'counting_down', plan_revision: 4,
  deadline_at: new Date(NOW + 9_200).toISOString(), seconds_left: 9.2, would_hold: ['D4'], note: '', ...over });
const incident = (over = {}) => ({
  venue_id: 'building-v2', plan_revision: 4, hazards: [], plan: plan(), plan_error: null,
  controller: { label: 'Simulated device', boot_id: 'b', heartbeat: 'ok', transit_seconds: 1.75, gates: [gate('D4'), gate('D9')] },
  stuck_doors: [], approvals: [], approval_in_progress: false, failsafe: armed(), last_event_id: 3, ...over,
});
const approval = (over = {}) => ({ approval_id: 'apv-1', plan_revision: 4, candidate_hash: 'h4', door_states: {}, status: 'applied',
  commands: {}, results: {}, reason: null, fallback_plan_revision: null, actor: 'fail_safe', ...over });

test('a server without the fail-safe, or a broken field, reads as off and never as armed', () => {
  assert.deepEqual(parseFailSafe(undefined), FAILSAFE_OFF);
  assert.equal(parseFailSafe({ armed: 'yes' }).armed, false);
  const view = parseFailSafe({ armed: true, window_seconds: 30, status: 'counting_down', plan_revision: 4, deadline_at: 'x',
    held_doors: { D4: ['HALL', 3] }, would_hold: ['D4'], last_action: { approval_id: 'apv-1', plan_revision: 4, summary: 's', at: 't' } });
  assert.equal(view.window_seconds, 30);
  assert.deepEqual(view.held_doors, { D4: ['HALL'] });
  assert.equal(view.last_action.approval_id, 'apv-1');
  assert.equal(parseFailSafe({ armed: true, status: 'bogus' }).status, 'standing_by');
  const state = parseIncidentState({ ...incident({ failsafe: undefined }), approvals: [{ ...approval(), actor: undefined }] });
  assert.equal(state.failsafe.armed, false);
  assert.equal(state.approvals[0].actor, 'operator', 'an approval without an actor is a person’s');
  assert.deepEqual(state.plan.held_doors, []);
});

test('failsafe events replace the view and keep the console line', () => {
  const start = { ...initialIncidentState(), incident: incident({ failsafe: FAILSAFE_OFF }), lastSeq: 3 };
  const event = parseIncidentEvent('failsafe', JSON.stringify({ seq: 4, ts: 't', plan_revision: 4, line: 'FAILSAFE armed: ...', failsafe: armed() }));
  const next = reduceIncidentEvent(start, event, NOW);
  assert.equal(next.incident.failsafe.armed, true);
  assert.equal(next.log.at(-1).text, 'FAILSAFE armed: ...');
  assert.equal(next.log.at(-1).tone, 'warn');
});

test('the countdown shows seconds left and which doors it will keep shut', () => {
  const view = failsafeDisplay(incident(), NOW);
  assert.equal(view.tone, 'counting');
  assert.equal(view.secondsLeft, 10);
  assert.equal(view.headline, 'No approval yet · the fail-safe acts in 10 s');
  assert.match(view.detail, /keep D4 closed: it opens into a room with a hazard/);
  assert.ok(view.fraction > 0.3 && view.fraction < 0.4);
  assert.equal(failsafeDisplay(incident({ failsafe: armed({ would_hold: [] }) }), NOW).detail, 'It will approve r4 as it is.');
  assert.equal(failsafeDisplay(incident(), NOW + 20_000).headline, 'No approval · the fail-safe is acting');
});

test('a countdown for an older plan, or a plan a person approved, is not shown as one', () => {
  assert.equal(failsafeDisplay(incident({ failsafe: armed({ plan_revision: 3 }) }), NOW).tone, 'armed');
  const person = failsafeDisplay(incident({ approvals: [approval({ actor: 'operator' })] }), NOW);
  assert.equal(person.tone, 'approved');
  const acted = failsafeDisplay(incident({ approvals: [approval()], failsafe: armed({ status: 'acted', last_action: { summary: 'held D4 closed' } }) }), NOW);
  assert.equal(acted.tone, 'acted');
  assert.equal(acted.detail, 'held D4 closed');
  assert.equal(failsafeDisplay(incident({ failsafe: FAILSAFE_OFF }), NOW).tone, 'off');
  assert.equal(failsafeDisplay(null, NOW).armed, false);
});

test('the executed plan says why it differs from the stateless one', () => {
  assert.equal(executingNote(plan()), null);
  assert.equal(executingNote(plan({ held_doors: ['D4'], plan_revision: 5 })),
    'Fail-safe plan r5: the doors now follow it (D4 held closed by the fail-safe: it opens into a room with a hazard).');
  assert.equal(executingNote(plan({ label: 'fallback', stuck_doors: ['D9'] })), 'Fallback plan r4: the doors now follow it (D9 stuck closed).');
  assert.match(executingNote(plan({ label: 'fallback', stuck_doors: ['D9'], held_doors: ['D4'] })), /^Fallback plan r4: .*D9 stuck closed; D4 held closed/);
});

test('the fail-safe speaks once, only when the drawn plan is the one it approved', () => {
  const plain = incident({ approvals: [approval()] });
  assert.equal(failsafeAnnounceKey(plain, 'h4', true), 'apv-1', 'the drawn plan has the approved candidate hash');
  assert.equal(failsafeAnnounceKey(plain, 'h-other', true), null, 'the screen draws another plan (hazards moved, or the held plan is still loading)');
  assert.equal(failsafeAnnounceKey(plain, 'h4', false), null, 'this screen’s hazards are not synced yet');
  assert.equal(failsafeAnnounceKey(plain, null, true), null, 'still solving');
  const held = incident({ plan: plan({ held_doors: ['D4'], plan_revision: 5, candidate_hash: 'h5' }), approvals: [approval({ plan_revision: 5, approval_id: 'apv-2', candidate_hash: 'h5' })] });
  assert.equal(failsafeAnnounceKey(held, 'h4', true), null, 'the stateless plan is drawn until the held one arrives');
  assert.equal(failsafeAnnounceKey(held, 'h5', true), 'apv-2');
  assert.equal(failsafeAnnounceKey(incident({ approvals: [approval({ actor: 'operator' })] }), 'h4', true), null, 'a person approved: they press Announce');
  assert.equal(failsafeAnnounceKey(incident({ approvals: [approval()], failsafe: FAILSAFE_OFF }), 'h4', true), null);
  assert.equal(failsafeAnnounceKey(incident({ approvals: [approval({ status: 'failed' })] }), 'h4', true), null);
});

test('the countdown names gates in doubt, and the screen-reader status does not tick', () => {
  const view = failsafeDisplay(incident({ failsafe: armed({ would_hold: [], in_doubt: ['D9'] }) }), NOW);
  assert.equal(view.detail, 'It will treat D9 as stuck closed: position unknown.');
  assert.equal(failsafeDisplay(incident(), NOW).status, failsafeDisplay(incident(), NOW + 3_000).status);
  assert.notEqual(failsafeDisplay(incident(), NOW).headline, failsafeDisplay(incident(), NOW + 3_000).headline);
});

test('approval lines and the hero name the fail-safe', () => {
  assert.equal(approvalSummary(approval({ commands: { D9: 'OPEN' }, status: 'actuating' })), 'Fail-safe · Actuating r4: D9 open — waiting for endpoint switches');
  assert.equal(approvalSummary(approval({ actor: 'operator' })), 'Applied r4: nothing needed to move');
  const stateless = {
    plan_id: 'p', venue_id: 'building-v2', geometry_revision: 'g', hazards: [{ id: 'h0', type: 'FIRE', zone_id: 'HALL' }], doors: [], exits: [], zones: [], routes: [],
    chosen: { completed_crossings: 105, initial_population: 125, horizon_seconds: 120, validator_report: { is_valid: true } }, baseline: { completed_crossings: 93 },
    no_hazard_completed: 125, alternatives: [], lights: { px: '', segments: [], held: [] }, advisories: [], announcement: '', model_assumptions: [], timings_ms: 1,
  };
  const hero = twinHero({ plan: stateless, pending: false });
  const shown = withFallback(hero, { valid: true, completed: 93, population: 125, stuck: [], held: ['D4'] }, stateless);
  assert.equal(shown.digits, '93');
  assert.equal(shown.delta.text, 'fail-safe · D4 held closed · −12 vs the plan');
});

// ---- the fail-safe's voice ---------------------------------------------------------------------------------------

test('the fail-safe view carries its voice and whether Gemini TTS is configured', () => {
  const view = parseFailSafe({ ...armed(), voice: 'gemini', voice_available: true, voice_model: 'gemini-3.8-flash-tts',
    last_action: { approval_id: 'apv-1', plan_revision: 4, summary: 's', at: 't', voice: 'gemini', voice_status: 'ready', voice_model: 'gemini-3.8-flash-tts' } });
  assert.equal(view.voice, 'gemini');
  assert.equal(view.voice_model, 'gemini-3.8-flash-tts');
  assert.equal(view.last_action.voice_status, 'ready');
  assert.equal(parseFailSafe({ ...armed(), voice: 'robot' }).voice, 'browser');
  const off = parseFailSafe({ armed: false, voice_available: true, voice_model: 'gemini-3.8-flash-tts' });
  assert.equal(off.armed, false);
  assert.equal(off.voice_available, true, 'the card can offer Gemini TTS before arming');
});

const blob = { size: 3 };
const player = (fail = null) => {
  const played = [];
  return { played, play: async item => { if (fail) throw fail; played.push(item); }, stop: () => undefined };
};

test('armed with Gemini TTS it plays the server clip and never also speaks with the browser', async () => {
  const spoken = [];
  const p = player();
  const outcome = await announceFailsafe({ voice: 'gemini', text: 'words', player: p,
    fetchVoice: async () => ({ blob, model: 'gemini-3.8-flash-tts' }), speakBrowser: text => { spoken.push(text); return true; } });
  assert.deepEqual(outcome, { by: 'gemini', model: 'gemini-3.8-flash-tts' });
  assert.deepEqual(p.played, [blob]);
  assert.deepEqual(spoken, []);
  assert.equal(voiceNote(outcome), 'Fail-safe voice · Gemini TTS (gemini-3.8-flash-tts)');
});

test('any Gemini voice failure falls back to the browser voice and says why', async () => {
  const spoken = [];
  const speakBrowser = text => { spoken.push(text); return true; };
  const failed = Object.assign(new Error('provider_timeout'), { code: 'provider_timeout' });
  const fromServer = await announceFailsafe({ voice: 'gemini', text: 'words', player: player(), fetchVoice: async () => { throw failed; }, speakBrowser });
  assert.deepEqual(fromServer, { by: 'browser', reason: 'provider_timeout' });
  assert.equal(voiceNote(fromServer), 'Fail-safe voice · browser speech (Gemini TTS: provider timeout)');
  const blocked = await announceFailsafe({ voice: 'gemini', text: 'words', player: player(new DOMException('blocked', 'NotAllowedError')),
    fetchVoice: async () => ({ blob, model: null }), speakBrowser });
  assert.deepEqual(blocked, { by: 'browser', reason: 'NotAllowedError' });
  const browserOnly = await announceFailsafe({ voice: 'browser', text: 'words', player: player(), fetchVoice: async () => { throw new Error('never'); }, speakBrowser });
  assert.deepEqual(browserOnly, { by: 'browser', reason: null });
  assert.deepEqual(spoken, ['words', 'words', 'words']);
  const silent = await announceFailsafe({ voice: 'browser', text: 'words', player: null, fetchVoice: async () => ({ blob, model: null }), speakBrowser: () => false });
  assert.equal(silent.by, 'none');
  assert.match(voiceNote(silent), /blocked audio/);
});

test('the audio player plays one clip at a time and frees each object URL', async () => {
  const events = [];
  const make = url => ({ play: async () => { events.push(`play ${url}`); }, pause: () => events.push(`pause ${url}`) });
  let n = 0;
  const urls = { create: () => `blob:${++n}`, revoke: url => events.push(`revoke ${url}`) };
  const p = createAudioPlayer(make, urls);
  await p.play(blob);
  await p.play(blob);
  p.stop();
  p.stop();
  assert.deepEqual(events, ['play blob:1', 'pause blob:1', 'revoke blob:1', 'play blob:2', 'pause blob:2', 'revoke blob:2']);
});
