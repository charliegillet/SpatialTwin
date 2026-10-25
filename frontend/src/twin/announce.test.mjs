import assert from 'node:assert/strict';
import test from 'node:test';
import { announcementText, speak, speechAvailable, stopSpeaking } from './announce.ts';

const fakes = () => {
  const log = [];
  const synth = { speak: u => log.push(['speak', u.text]), cancel: () => log.push(['cancel']) };
  class Utterance { constructor(text) { this.text = text; } }
  return { synth, Utterance, log };
};

test('the text comes from the plan and is empty with no hazard', () => {
  assert.equal(announcementText({ announcement: '  Attention. Fire in the lobby.  ' }), 'Attention. Fire in the lobby.');
  assert.equal(announcementText({ announcement: '' }), '');
  assert.equal(announcementText(null), '');
  assert.equal(announcementText({}), '');
});

test('availability needs both the synthesiser and the utterance class', () => {
  const { synth, Utterance } = fakes();
  assert.equal(speechAvailable(synth, Utterance), true);
  assert.equal(speechAvailable(undefined, Utterance), false);
  assert.equal(speechAvailable(synth, undefined), false);
  assert.equal(speechAvailable({}, Utterance), false);
});

test('speaking cancels what is in progress first', () => {
  const { synth, Utterance, log } = fakes();
  assert.equal(speak(synth, Utterance, 'Attention.'), true);
  assert.deepEqual(log, [['cancel'], ['speak', 'Attention.']]);
});

test('nothing is spoken for empty text or without speech support', () => {
  const { synth, Utterance, log } = fakes();
  assert.equal(speak(synth, Utterance, ''), false);
  assert.equal(speak(undefined, Utterance, 'x'), false);
  assert.deepEqual(log, []);
});

test('stop cancels and never throws', () => {
  const { synth, log } = fakes();
  stopSpeaking(synth);
  assert.deepEqual(log, [['cancel']]);
  stopSpeaking(undefined);
  stopSpeaking({ cancel() { throw new Error('x'); } });
});

test('an unchecked plan has nothing to announce', () => {
  assert.equal(announcementText({ announcement: 'Fire.', chosen: { validator_report: { is_valid: false } } }), '');
  assert.equal(announcementText({ announcement: 'Fire.', chosen: { validator_report: { is_valid: true } } }), 'Fire.');
});
