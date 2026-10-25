import assert from 'node:assert/strict';
import test from 'node:test';
import { approvalSuccessMessage, investigationErrorMessage, needsOperatorToken, operatorErrorMessage, stopSuccessMessage } from './operator.ts';
import { MAX_NOT_FOUND_POLLS, createWorkflowEpoch, nextNotFoundCount, shouldKeepPolling } from './workflowEpoch.ts';

test('only physical serial hardware needs an operator token', () => {
  assert.equal(needsOperatorToken('physical_serial'), true);
  assert.equal(needsOperatorToken('simulator'), false);
  assert.equal(needsOperatorToken(undefined), false);
});

test('403 outcomes are distinct plain-words messages', () => {
  const a = operatorErrorMessage('approve', 403, 'operator_token_not_configured');
  const b = operatorErrorMessage('approve', 403, 'operator_token_rejected');
  const c = operatorErrorMessage('stop', 403, 'operator_config_invalid');
  assert.equal(new Set([a, b, c]).size, 3);
  assert.match(b, /rejected/);
  assert.doesNotMatch(a + b + c, /operator_/);
});

test('approve 502 says nothing was recorded and can be retried', () => {
  const message = operatorErrorMessage('approve', 502, 'device_not_acknowledged:timeout');
  assert.match(message, /did not acknowledge/);
  assert.match(message, /timeout/);
  assert.match(message, /Nothing was recorded; you can retry/);
});

test('stop 502 does not claim the outputs stopped', () => {
  const message = operatorErrorMessage('stop', 502, 'stop_not_acknowledged:serial_closed');
  assert.match(message, /still active/);
  assert.match(message, /serial closed/);
  assert.doesNotMatch(message, /retry\b.*recorded/);
});

test('unsafe reason text is dropped', () => {
  const message = operatorErrorMessage('approve', 502, 'device_not_acknowledged:<script>');
  assert.doesNotMatch(message, /script/);
});

test('409 and 429 and success wording', () => {
  assert.match(operatorErrorMessage('approve', 409, ''), /already recorded/);
  assert.match(investigationErrorMessage(429), /Too many analyses/);
  assert.equal(investigationErrorMessage(500), '');
  assert.match(approvalSuccessMessage(true), /not arrival/);
  assert.match(stopSuccessMessage(), /Acknowledgement is not proof/);
});

test('workflow epoch invalidates earlier requests', () => {
  const epoch = createWorkflowEpoch();
  const started = epoch.current();
  assert.equal(epoch.isCurrent(started), true);
  epoch.bump();
  assert.equal(epoch.isCurrent(started), false);
  assert.equal(epoch.isCurrent(epoch.current()), true);
});

test('progress polling stops after repeated not_found', () => {
  let count = 0;
  let polls = 0;
  while (true) {
    polls += 1;
    count = nextNotFoundCount('not_found', count);
    if (!shouldKeepPolling('not_found', count)) break;
  }
  assert.equal(polls, MAX_NOT_FOUND_POLLS);
  assert.equal(nextNotFoundCount('running', 5), 0);
  assert.equal(shouldKeepPolling('running', 0), true);
  assert.equal(shouldKeepPolling('completed', 0), false);
});
