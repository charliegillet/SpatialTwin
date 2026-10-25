import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanHazardEvents, toHazardView } from './hazardView.ts';

const response = (alternative_id, overrides = {}) => ({
  tool: 'simulate_hazard_schedule', alternative_id, is_valid: true, reasons: [], status: 'COMPLETE_WITHIN_MODEL',
  completed_crossings: 40, remaining_population: 0, baseline_completed_crossings: 30,
  modeled_exposure_people_seconds: 120, exposure_label: 'x', ...overrides,
});

test('event rows are cleaned, de-duplicated and capped', () => {
  const rows = [
    { element_id: 'portal:P1', close_at_s: '20' }, { element_id: 'portal:P1', close_at_s: '30' },
    { element_id: 'portal:P2', close_at_s: '' }, { element_id: 'boundary:B2', close_at_s: '-5' },
    { element_id: 'boundary:B2', close_at_s: '1.5' }, { element_id: 'boundary:B2', close_at_s: '60' },
  ];
  assert.deepEqual(cleanHazardEvents(rows), [{ element_id: 'portal:P1', close_at_s: 20 }, { element_id: 'boundary:B2', close_at_s: 60 }]);
});

test('responses map to one table and the verdict needs every alternative valid', () => {
  const events = [{ element_id: 'portal:P1', close_at_s: 20 }];
  const ok = toHazardView(events, [response('KEEP_CURRENT'), response('OPEN_P3')]);
  assert.equal(ok.check.status, 'passed');
  assert.deepEqual(ok.alternatives[1], { alternative_id: 'OPEN_P3', completed_crossings: 40, exposure_people_seconds: 120 });
  const bad = toHazardView(events, [response('KEEP_CURRENT'), response('OPEN_P3', { is_valid: false, reasons: ['conservation_failed'] })]);
  assert.equal(bad.check.status, 'failed');
  assert.deepEqual(bad.check.reasons, ['conservation_failed']);
  assert.equal(toHazardView(events, []).check.status, 'failed');
});
