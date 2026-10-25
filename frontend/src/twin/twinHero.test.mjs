import assert from 'node:assert/strict';
import test from 'node:test';
import { alternativeRows, deltaFor, doorRows, planLogLine, plannerOpened, twinChips, twinHero, unsafeExits } from './twinHero.ts';
import { makePlan } from './planFixture.mjs';

test('the hero reads population and horizon from the response', () => {
  const hero = twinHero({ plan: makePlan(), pending: false });
  assert.equal(hero.digits, '91');
  assert.equal(hero.label, 'of 125 reach an exit in 40 s');
  assert.equal(hero.tag, 'building-v2 model');
  assert.equal(hero.ready, true);
  const other = makePlan({ chosen: { ...makePlan().chosen, initial_population: 80, horizon_seconds: 60 } });
  assert.equal(twinHero({ plan: other, pending: false }).label, 'of 80 reach an exit in 60 s');
});

test('the delta names the doors the planner opened', () => {
  const plan = makePlan();
  assert.deepEqual(plannerOpened(plan), ['D4', 'D9']);
  assert.deepEqual(deltaFor(plan), { text: '+34 by opening D4 and D9', tone: 'gain' });
  const one = makePlan({ doors: plan.doors.filter(door => door.id !== 'D4') });
  assert.equal(deltaFor(one).text, '+34 by opening D9');
});

test('no hazards shows the no-hazard figure and no delta', () => {
  const plan = makePlan({ hazards: [], doors: [], chosen: { ...makePlan().chosen, completed_crossings: 125 }, baseline: { completed_crossings: 125, run_id: 'b' } });
  const hero = twinHero({ plan, pending: false });
  assert.equal(hero.digits, '125');
  assert.equal(hero.delta, null);
});

test('no delta when the plan equals the default doors', () => {
  const plan = makePlan({ baseline: { completed_crossings: 91, run_id: 'b' } });
  assert.equal(deltaFor(plan), null);
});

test('pending keeps the earlier figure but marks it stale; no plan shows a dash', () => {
  const stale = twinHero({ plan: makePlan(), pending: true });
  assert.equal(stale.digits, '91');
  assert.equal(stale.ready, false);
  assert.equal(stale.delta, null);
  const none = twinHero({ plan: null, pending: true });
  assert.equal(none.digits, '—');
  assert.equal(twinHero({ plan: null, pending: false, error: 'Up to 6 hazards' }).reason, 'Up to 6 hazards');
});

test('wording never claims survival', () => {
  const hero = twinHero({ plan: makePlan(), pending: false });
  const text = JSON.stringify(hero) + planLogLine(makePlan(), { LOBBY: 'Lobby' }, 12);
  assert.doesNotMatch(text, /surviv|saved|rescued|lives/i);
});

test('chips are honest about the source', () => {
  assert.deepEqual(twinChips(makePlan(), false), ['Local solver', 'Hypothetical']);
  assert.deepEqual(twinChips(makePlan(), true), ['Local solver', 'Hypothetical', 'Fixture venue']);
  assert.deepEqual(twinChips(null, false), []);
});

test('door rows list only touched doors with the backend reason', () => {
  const rows = doorRows(makePlan());
  assert.deepEqual(rows.map(row => [row.id, row.verb]), [['D1', 'closed to entry'], ['D4', 'opened'], ['D9', 'opened']]);
  assert.equal(rows[0].reason, 'fire in Lobby');
  const gas = makePlan({ doors: [{ ...makePlan().doors[2], state: 'closed', locked: true, reason: 'gas in Hall', decided_by: 'gas_lock' }] });
  assert.deepEqual(doorRows(gas).map(row => [row.id, row.verb, row.tone]), [['D4', 'locked', 'locked']]);
});

test('unsafe exits and alternatives come straight from the plan', () => {
  assert.deepEqual(unsafeExits(makePlan()).map(exit => exit.id), ['E1']);
  const rows = alternativeRows(makePlan());
  assert.deepEqual(rows.map(row => [row.rank, row.doors, row.crossings, row.chosen]), [[1, 'D4 open · D9 open', 91, true], [2, 'defaults', 57, false]]);
});

test('the log line names hazards, doors, crossings and time', () => {
  const line = planLogLine(makePlan(), { LOBBY: 'Lobby' }, 12);
  assert.match(line, /^FIRE Lobby → D1 closed to entry, D4 D9 opened → 91 of 125 · 12 ms/);
});

test('door rows with the same verb and reason read as one group', async () => {
  const { groupDoorRows } = await import('./twinHero.ts');
  const rows = [{ id: 'D1', verb: 'closed to entry', reason: 'r', tone: 'closed' }, { id: 'D5', verb: 'closed to entry', reason: 'r', tone: 'closed' }, { id: 'D9', verb: 'opened', reason: 'x', tone: 'open' }];
  assert.deepEqual(groupDoorRows(rows).map(group => group.ids), [['D1', 'D5'], ['D9']]);
});

test('an open door that only denies entry says so and is not shown as changed', async () => {
  const { doorVerb } = await import('./twinHero.ts');
  assert.deepEqual(doorVerb({ ...makePlan().doors[1], entry_denied_into: ['HALL'] }), { verb: 'stays open \u00b7 no entry', tone: 'locked' });
});

test('a per-door gain is read from the backend reason only when present', async () => {
  const { gainFrom } = await import('./twinHero.ts');
  assert.equal(gainFrom('opened: +29 modeled crossings'), '+29');
  assert.equal(gainFrom('Fire in Lobby: closed to entry into Lobby; egress until untenable at 6 s'), null);
});

import { NO_CHECKED_PLAN, planChecked } from './twinHero.ts';
const invalid = () => { const plan = makePlan(); plan.chosen.validator_report = { is_valid: false, checks_run: [], reasons: ['x'] }; plan.alternatives[1].is_valid = false; return plan; };

test('an unchecked plan withholds the hero figure and delta', () => {
  const plan = invalid();
  assert.equal(planChecked(plan), false);
  const hero = twinHero({ plan, pending: false });
  assert.equal(hero.withheld, true);
  assert.equal(hero.digits, '—');
  assert.equal(hero.delta, null);
  assert.equal(hero.reason, NO_CHECKED_PLAN);
  assert.doesNotMatch(hero.spoken, /91/);
  assert.equal(twinHero({ plan: makePlan(), pending: false }).withheld, false);
});

test('failing alternatives are labelled failed check', () => {
  const rows = alternativeRows(invalid());
  assert.equal(rows[1].valid, false);
});
