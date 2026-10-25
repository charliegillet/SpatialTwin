import assert from 'node:assert/strict';
import test from 'node:test';
import { approvalLadder, comparisonLine, doneLine } from './decisionView.ts';
import { pendingMessage, preflightItems, resetChecklist, resetComplete, resetGateError } from './resetFlow.ts';

const states = steps => steps.map(step => step.state).join(',');

test('approval ladder advances from approval to the re-solve', () => {
  const base = { approved: false, acknowledged: false, gateState: 'CLOSED', endpointReported: true, resolved: null };
  assert.equal(states(approvalLadder(base)), 'pending,pending,pending,pending,pending');
  assert.equal(states(approvalLadder({ ...base, approved: true })), 'done,active,pending,pending,pending');
  assert.equal(states(approvalLadder({ ...base, approved: true, acknowledged: true })), 'done,done,active,pending,pending');
  assert.equal(states(approvalLadder({ ...base, approved: true, acknowledged: true, gateState: 'TRANSIT' })), 'done,done,done,active,pending');
  const done = approvalLadder({ approved: true, acknowledged: true, gateState: 'OPEN', endpointReported: true, resolved: 117 });
  assert.equal(states(done), 'done,done,done,done,done');
  assert.equal(done[4].label, 'Re-solved 117');
  assert.equal(done[1].label, 'Acknowledged · not arrival');
});

test('an unreported open switch does not count as observed', () => {
  const steps = approvalLadder({ approved: true, acknowledged: true, gateState: 'OPEN', endpointReported: false, resolved: 117 });
  assert.notEqual(steps[3].state, 'done');
});

test('decision wording', () => {
  assert.equal(comparisonLine(60, 117), 'Open P3: 60 → 117 · checked');
  assert.equal(doneLine(117), 'Done · re-solved 117');
});

test('reset checklist turns green only when all four facts hold', () => {
  const facts = { scenarioClear: true, gateClosedObserved: false, noRunActive: true, boardReady: true };
  assert.equal(resetChecklist(facts).length, 4);
  assert.equal(resetComplete(facts), false);
  assert.equal(resetComplete({ ...facts, gateClosedObserved: true }), true);
});

test('reset-gate errors are plain', () => {
  assert.match(resetGateError(409, 'investigation_running'), /analysis is still running/i);
  assert.match(resetGateError(502, 'device_not_acknowledged:serial_timeout'), /serial timeout/);
  assert.equal(resetGateError(500, ''), '');
});

test('preflight is honest about missing receipt age and token', () => {
  const input = { geminiConfigured: true, receiptAgeSeconds: 600, hardwareMode: 'physical_serial', gateState: 'CLOSED', endpointReported: true, physical: true, tokenHeld: true, cameraLive: true };
  assert.ok(preflightItems(input).every(item => item.ok));
  assert.equal(preflightItems({ ...input, receiptAgeSeconds: null })[0].ok, false);
  assert.equal(preflightItems({ ...input, tokenHeld: false }).find(item => item.id === 'token').ok, false);
  assert.equal(preflightItems({ ...input, physical: false, tokenHeld: false }).find(item => item.id === 'token').ok, true);
  assert.equal(preflightItems({ ...input, gateState: 'OPEN' }).find(item => item.id === 'p3').ok, false);
});

test('the reset message names only unmet items and disappears when all are met', () => {
  const facts = { scenarioClear: true, gateClosedObserved: false, noRunActive: true, boardReady: false };
  assert.equal(pendingMessage(facts), 'Waiting for: P3 closed · observed, Board view ready');
  assert.doesNotMatch(pendingMessage({ ...facts, gateClosedObserved: true }), /P3/);
  assert.equal(pendingMessage({ ...facts, gateClosedObserved: true, boardReady: true }), null);
});

test('physical hardware approves only on live evidence; the simulator accepts local', async () => {
  const { hasApprovableEvidence } = await import('./decisionView.ts');
  assert.equal(hasApprovableEvidence(true, 'live'), true);
  assert.equal(hasApprovableEvidence(true, 'local'), false);
  assert.equal(hasApprovableEvidence(true, undefined), false);
  assert.equal(hasApprovableEvidence(false, 'local'), true);
});

test('an approval counts only for the scenario revision it was made on', async () => {
  const { approvalIsCurrent } = await import('./decisionView.ts');
  assert.equal(approvalIsCurrent({ revision: 4 }, 4), true);
  assert.equal(approvalIsCurrent({ revision: 4 }, 5), false);
  assert.equal(approvalIsCurrent(null, 4), false);
});
