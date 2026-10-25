import assert from 'node:assert/strict';
import test from 'node:test';
import { deltaText, heroView, nextResultMemory } from './heroView.ts';

const base = { connected: true, physicalUncertain: false, planCurrent: true, completed: 117, population: 120, horizon: 40 };

test('hero shows the checked count with its label', () => {
  const hero = heroView(base);
  assert.equal(hero.ready, true);
  assert.equal(hero.digits, '117');
  assert.equal(hero.label, 'of 120 reach an exit in 40 s');
  assert.equal(hero.delta, null);
  assert.doesNotMatch(hero.spoken, /inside|casualt/i);
});

test('delta compares with the previous result and names its sign', () => {
  assert.deepEqual(heroView({ ...base, previous: 60 }).delta, { text: '+57', tone: 'gain', versus: 60 });
  assert.deepEqual(heroView({ ...base, completed: 60, previous: 120 }).delta, { text: '−60', tone: 'loss', versus: 120 });
  assert.equal(heroView({ ...base, previous: 117 }).delta, null);
  assert.equal(deltaText(-3), '−3');
});

test('an unchecked result shows a dash and one reason', () => {
  for (const input of [{ ...base, planCurrent: false }, { ...base, connected: false }, { ...base, physicalUncertain: true }, { ...base, completed: null }]) {
    const hero = heroView(input);
    assert.equal(hero.ready, false);
    assert.equal(hero.digits, '—');
    assert.ok(hero.reason && hero.reason.length < 60);
    assert.equal(hero.delta, null);
  }
});

test('result memory keeps the last different count', () => {
  let memory = { current: null, previous: null };
  memory = nextResultMemory(memory, 120);
  memory = nextResultMemory(memory, 60);
  assert.deepEqual(memory, { current: 60, previous: 120 });
  assert.equal(nextResultMemory(memory, 60), memory);
  assert.equal(nextResultMemory(memory, null), memory);
});
