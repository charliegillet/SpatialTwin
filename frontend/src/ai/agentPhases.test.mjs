import assert from 'node:assert/strict';
import test from 'node:test';
import { agentLines, collapsePhases, phaseLine, shortInteractionId } from './agentPhases.ts';

const events = [
  { phase: 'provider_request', elapsed_ms: 0 },
  { phase: 'provider_response', status: 'in_progress', elapsed_ms: 3000 },
  { phase: 'provider_response', status: 'in_progress', elapsed_ms: 4000 },
  { phase: 'provider_response', status: 'running', elapsed_ms: 15000 },
  { phase: 'provider_response', status: 'requires_action', elapsed_ms: 32000 },
  { phase: 'local_tool_complete', function_name: 'evaluate_allowed_alternative', elapsed_ms: 32100 },
  { phase: 'provider_response', status: 'completed', elapsed_ms: 51000 },
];
const entry = (name, ms, status = 'executed') => ({ call_id: name + ms, function_name: name, arguments: { alternative_id: 'OPEN_P3' }, status, execution_time_ms: ms });

test('polling receipts collapse to one entry per phase', () => {
  assert.deepEqual(collapsePhases(events).map(phase => phase.label), ['submitted', 'running', 'tool requested', 'checked locally', 'finished']);
  assert.equal(collapsePhases(events)[1].atMs, 3000);
});

test('phase line reads as a timeline with the local check in ms', () => {
  assert.equal(phaseLine(events, [entry('evaluate_allowed_alternative', 14)]), 'submitted 0 s · running 3 s · tool requested 32 s · checked locally 14 ms · finished 51 s');
});

test('a run never exceeds eight lines', () => {
  const ledger = Array.from({ length: 12 }, (_, i) => entry('evaluate_allowed_alternative', i + 1));
  const lines = agentLines({ events, ledger, interactionId: 'v1_abcdefghijklmnop' });
  assert.ok(1 + lines.tools.length + (lines.id ? 1 : 0) <= 8);
  assert.match(lines.tools.at(-1), /more calls/);
  assert.equal(lines.id, 'v1_abcde…');
});

test('unknown tools are not named', () => {
  const lines = agentLines({ events: [], ledger: [entry('rm_rf', 3)], interactionId: null });
  assert.match(lines.tools[0], /^rejected tool request/);
  assert.equal(lines.id, null);
  assert.equal(shortInteractionId('abc'), 'abc');
});
