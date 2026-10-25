import assert from 'node:assert/strict';
import test from 'node:test';
import {
  canSend, connectionNote, exitDisplay, hazardSummary, overviewDisplays, parseSignState, proposeErrorMessage, routedLabel,
  signDisplay, STALE_AFTER_MS,
} from './signView.ts';

const NOW = 1_800_000_000_000;

function state(overrides = {}) {
  return {
    simulated: true, venue_id: 'building-v2', venue_name: 'Building v2', status: 'incident', plan_revision: 4, plan_label: 'primary',
    exits: [
      { exit_id: 'E1', name: 'South exit', lamp: 'red_x', routed: 0 },
      { exit_id: 'E2', name: 'North stair exit', lamp: 'green_flash', routed: 40 },
      { exit_id: 'E3', name: 'Dock exit', lamp: 'green', routed: 0 },
      { exit_id: 'E4', name: 'West exit', lamp: 'red_static', routed: 0 },
    ],
    hazards: [{ type: 'FIRE', room: 'Lobby' }], count_label: 'modeled crossings', expires_at: null, server_time: '',
    ...overrides,
  };
}

const live = (s, exitId, extra = {}) => signDisplay({ state: s, exitId, connection: 'live', lastMessageAt: NOW, now: NOW, ...extra });

test('each lamp maps to its sign face', () => {
  const s = state();
  assert.deepEqual(['E1', 'E2', 'E3', 'E4'].map(id => [live(s, id).kind, live(s, id).tone, live(s, id).glyph]), [
    ['unsafe', 'red', 'cross'], ['go_flash', 'green', 'exit'], ['go', 'green', 'exit'], ['locked', 'red', 'no_entry'],
  ]);
  assert.equal(live(s, 'E1').headline, 'DO NOT USE');
  assert.equal(live(s, 'E1').detail, 'Hazard: Fire · Lobby');
  assert.equal(live(s, 'E4').headline, 'LOCKED · GAS');
  assert.equal(live(s, 'E2').exitLabel, 'E2 · North stair exit');
});

test('only a routed exit during an incident flashes, and never under reduced motion', () => {
  const s = state();
  assert.equal(live(s, 'E2').flashing, true);
  assert.equal(live(s, 'E2').detail, '40 modeled crossings routed here');
  assert.equal(live(s, 'E2', { reducedMotion: true }).flashing, false);
  assert.match(live(s, 'E2', { reducedMotion: true }).detail, /^Use this exit/);
  assert.equal(live(s, 'E3').flashing, false);
  const calm = state({ status: 'normal', hazards: [] });
  assert.equal(live(calm, 'E2').flashing, false);
  assert.equal(live(calm, 'E2').detail, 'No incident');
});

test('no plan yet shows a steady exit sign; unchecked and inactive never show a lamp', () => {
  const unlit = state({ status: 'normal', hazards: [], plan_revision: 1, exits: [{ exit_id: 'E1', name: 'South exit', lamp: null, routed: null }] });
  assert.deepEqual([live(unlit, 'E1').kind, live(unlit, 'E1').flashing], ['go', false]);
  const unchecked = state({ status: 'unchecked' });
  assert.deepEqual([live(unchecked, 'E2').kind, live(unchecked, 'E2').tone], ['unchecked', 'amber']);
  const inactive = state({ status: 'inactive' });
  assert.deepEqual([live(inactive, 'E2').kind, live(inactive, 'E2').tone], ['inactive', 'grey']);
});

test('a stale connection never keeps showing green; an expired link says so', () => {
  const s = state();
  const stale = live(s, 'E2', { now: NOW + STALE_AFTER_MS + 1 });
  assert.equal(stale.kind, 'stale');
  assert.equal(stale.tone, 'grey');
  assert.equal(live(s, 'E2', { now: NOW + STALE_AFTER_MS - 1 }).kind, 'go_flash');
  assert.equal(live(s, 'E2', { connection: 'expired' }).kind, 'expired');
  assert.equal(signDisplay({ state: null, exitId: 'E1', connection: 'connecting', lastMessageAt: null, now: NOW }).kind, 'connecting');
});

test('an unknown exit is reported, and a one-exit payload needs no exit id', () => {
  assert.equal(live(state(), 'E9').kind, 'missing');
  const one = state({ exits: [{ exit_id: 'E3', name: 'Dock exit', lamp: 'green', routed: 0 }] });
  assert.equal(live(one, null).exitLabel, 'E3 · Dock exit');
  assert.equal(live(state(), null).kind, 'missing');
});

test('fallback plans are labelled', () => {
  assert.match(live(state({ plan_label: 'fallback' }), 'E2').footnote, /fallback plan$/);
  assert.match(live(state(), 'E2').footnote, /^Simulated sign/);
});

test('the overview shows every exit, or the stale/expired state', () => {
  const input = { state: state(), exitId: null, connection: 'live', lastMessageAt: NOW, now: NOW };
  assert.deepEqual(overviewDisplays(input).map(d => d.kind), ['unsafe', 'go_flash', 'go', 'locked']);
  assert.ok(overviewDisplays({ ...input, now: NOW + STALE_AFTER_MS + 5 }).every(d => d.kind === 'stale'));
  assert.deepEqual(overviewDisplays({ ...input, connection: 'expired' }).map(d => d.kind), ['expired']);
});

test('parseSignState rejects off-contract payloads instead of drawing a wrong sign', () => {
  assert.equal(parseSignState(null), null);
  assert.equal(parseSignState({ venue_id: 'x', status: 'party', exits: [], hazards: [] }), null);
  assert.equal(parseSignState({ ...state(), exits: [{ exit_id: 'E1', name: 'x', lamp: 'blue', routed: 1 }] }), null);
  assert.equal(parseSignState({ ...state(), exits: [42] }), null);
  const parsed = parseSignState(state());
  assert.equal(parsed.exits[1].lamp, 'green_flash');
  assert.equal(parsed.plan_label, 'primary');
});

test('labels and helpers', () => {
  assert.equal(routedLabel(1), '1 modeled crossing');
  assert.equal(hazardSummary([{ type: 'FIRE', room: 'A' }, { type: 'GAS', room: 'B' }, { type: 'WATER', room: 'C' }]), 'Fire · A, Gas · B +1');
  assert.equal(connectionNote('live', NOW, NOW), null);
  assert.equal(connectionNote('reconnecting', NOW - 12_000, NOW), 'Reconnecting… last update 12 s ago');
  assert.match(proposeErrorMessage(429, 'rate_limited', 7), /7 s/);
  assert.match(proposeErrorMessage(403, null, null), /expired/);
  assert.match(proposeErrorMessage(409, 'venue_not_active', null), /not on the presenter screen/);
  assert.equal(canSend('FIRE', 'LOBBY', false, true), true);
  assert.equal(canSend('FIRE', null, false, true), false);
  assert.equal(canSend('FIRE', 'LOBBY', false, false), false);
  assert.equal(exitDisplay(state(), state().exits[0]).announce, 'E1 · South exit: DO NOT USE. Hazard: Fire · Lobby');
});
