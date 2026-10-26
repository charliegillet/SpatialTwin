import assert from 'node:assert/strict';
import test from 'node:test';
import { HOME_VENUE_KEY, nextJudgeVenue, readHomeVenue, writeHomeVenue } from './homeVenue.ts';

const memory = () => { const data = new Map(); return { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value) }; };

test('Next judge returns to the demo venue, not the built-in building', () => {
  const known = ['building-v2', 'ferry-building-level-2', 'judge-sketch-1'];
  assert.equal(nextJudgeVenue('ferry-building-level-2', 'building-v2', known), 'ferry-building-level-2', 'the presenter pick wins');
  assert.equal(nextJudgeVenue(null, 'ferry-building-level-2', known), 'ferry-building-level-2', 'else the venue active when the screen opened');
  assert.equal(nextJudgeVenue('gone-venue', 'ferry-building-level-2', known), 'ferry-building-level-2', 'a home that no longer exists is skipped');
  assert.equal(nextJudgeVenue(null, null, known), 'building-v2');
});

test('the home venue is kept in this browser and survives a broken storage', () => {
  const store = memory();
  assert.equal(readHomeVenue(store), null);
  writeHomeVenue('ferry-building-level-2', store);
  assert.equal(store.getItem(HOME_VENUE_KEY), 'ferry-building-level-2');
  assert.equal(readHomeVenue(store), 'ferry-building-level-2');
  const broken = { getItem() { throw new Error('denied'); }, setItem() { throw new Error('denied'); } };
  assert.equal(readHomeVenue(broken), null);
  assert.doesNotThrow(() => writeHomeVenue('x', broken));
});
