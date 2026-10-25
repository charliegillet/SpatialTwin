import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  clampIndex, indexForTime, intensity, lastIndex, playbackView, stepDelayMs, timeForIndex, PLAYBACK_CAPTION,
} from './playback.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));
const plan = {
  chosen: {
    timeline: [
      { step: 0, time_seconds: 0, occupancy: { HALL: 80, LOBBY: 20 }, exits_cumulative: { E1: 0, E3: 0 }, in_transit: 0, total_completed: 0 },
      { step: 1, time_seconds: 2, occupancy: { HALL: 60, LOBBY: 12 }, exits_cumulative: { E1: 0, E3: 5 }, in_transit: 12, total_completed: 5 },
      { step: 2, time_seconds: 4, occupancy: { HALL: 0, LOBBY: 0 }, exits_cumulative: { E1: 0, E3: 38 }, in_transit: 0, total_completed: 38 },
    ],
  },
};

test('index and time map one to one, discretely', () => {
  assert.equal(lastIndex(plan), 2);
  assert.equal(timeForIndex(plan, 1), 2);
  assert.equal(indexForTime(plan, 3.9), 1);
  assert.equal(indexForTime(plan, 4), 2);
  assert.equal(indexForTime(plan, -1), 0);
  assert.equal(clampIndex(plan, 99), 2);
  assert.equal(clampIndex(plan, -3), 0);
  assert.equal(clampIndex(plan, 1.4), 1);
  assert.equal(clampIndex(plan, NaN), 0);
});

test('intensity is count over max(1, reference), clamped', () => {
  assert.equal(intensity(0, 0), 0);
  assert.equal(intensity(5, 0), 1);
  assert.equal(intensity(10, 20), 0.5);
  assert.equal(intensity(30, 20), 1);
});

test('labels, counts, transit text come straight from the frame', () => {
  const v = playbackView(venue, plan, 1);
  const hall = v.zones.find((z) => z.id === 'HALL');
  assert.equal(hall.label, 'Hall 60');
  assert.ok(Math.abs(hall.intensity - 60 / 80) < 1e-9);
  assert.equal(v.exits.find((e) => e.id === 'E3').label, 'E3 · 5');
  assert.equal(v.transit, '12 between rooms');
  assert.equal(v.timeLabel, 't = 2 s');
  assert.equal(v.atEnd, false);
  const end = playbackView(venue, plan, 5);
  assert.equal(end.atEnd, true);
  assert.equal(end.transit, null);
  assert.equal(end.exits.find((e) => e.id === 'E3').count, 38);
  assert.equal(end.zones.find((z) => z.id === 'ROOM_A').count, 0);
});

test('null or empty timeline yields no view; caption is fixed', () => {
  assert.equal(playbackView(venue, null, 0), null);
  assert.equal(playbackView(venue, { chosen: { timeline: [] } }, 0), null);
  assert.equal(PLAYBACK_CAPTION, 'Modeled occupancy · not positions');
  assert.ok(stepDelayMs(plan) > 0);
});

test('real fixture: conservation of frames shows final crossings', () => {
  const real = JSON.parse(readFileSync(new URL('./fixtures/door-plan-fire-lobby.json', import.meta.url), 'utf8'));
  const v = playbackView(venue, real, 999);
  assert.equal(v.atEnd, true);
  assert.equal(v.completed, real.chosen.timeline.at(-1).total_completed);
});
