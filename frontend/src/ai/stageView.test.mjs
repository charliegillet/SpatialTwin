import assert from 'node:assert/strict';
import test from 'node:test';
import { checkedChip, crossingChip, effectiveVideoMode, gainText, gateChip, hardwareChip, provenanceChip, uploadLogLine, uploadSourceLabel, videoModeOptions, VIDEO_DEADLINE_SECONDS } from './stageView.ts';

test('gate chip names the reported state and separates observed from unconfirmed open', () => {
  assert.equal(gateChip('CLOSED', true).label, 'P3 closed');
  assert.equal(gateChip('OPEN', true).label, 'P3 open · observed');
  assert.equal(gateChip('OPEN', false).label, 'P3 open · unconfirmed');
  assert.equal(gateChip('TRANSIT', true).label, 'P3 moving');
  assert.equal(gateChip('UNKNOWN', false).label, 'P3 unknown');
  assert.equal(gateChip(undefined, false).label, 'P3 unknown');
});

test('checked and hardware chips', () => {
  assert.equal(checkedChip(true, true).label, 'Checked');
  assert.equal(checkedChip(true, false).label, 'Unverified');
  assert.equal(checkedChip(false, false).label, 'Connecting');
  assert.equal(hardwareChip('simulator').label, 'Simulator');
  assert.equal(hardwareChip('physical_serial').label, 'Board connected');
  assert.equal(hardwareChip(undefined).label, 'No board');
});

test('crossing chip', () => {
  assert.equal(crossingChip({ completed_crossings: 60, initial_population: 120, horizon_seconds: 40 }), '60 / 120 crossed · 40 s');
  assert.equal(crossingChip(null), null);
});

test('provenance chip never promotes an unreceipted live result', () => {
  assert.equal(provenanceChip(null), null);
  assert.equal(provenanceChip({ status: 'completed', provenance: 'live', provider_interaction_id: 'x' })?.label, 'Live Gemini');
  assert.equal(provenanceChip({ status: 'completed', provenance: 'live' })?.label, 'Unavailable');
  assert.equal(provenanceChip({ status: 'completed', provenance: 'fixture' })?.label, 'Fixture');
  assert.equal(provenanceChip({ status: 'completed', provenance: 'local' })?.label, 'Local solver');
  assert.equal(provenanceChip({ status: 'failed', provenance: 'live', provider_interaction_id: 'x' })?.label, 'Unavailable');
});

test('gain text', () => {
  assert.equal(gainText(57), '+57 crossings');
  assert.equal(gainText(0), 'No gain');
  assert.equal(gainText(-3), '−3 crossings');
  assert.equal(gainText(null), '');
});

test('uploads are not labelled as camera stills', () => {
  assert.equal(uploadSourceLabel('image'), 'Uploaded image');
  assert.equal(uploadLogLine('video', 'low'), 'Uploaded clip sent for analysis · low thinking.');
  assert.doesNotMatch(uploadLogLine('image', 'low'), /camera/i);
});

test('video mode defaults to the single enabled capability', () => {
  assert.deepEqual(videoModeOptions({ video_static: false, video_agentic: true }), ['agentic']);
  assert.equal(effectiveVideoMode(['agentic'], 'static'), 'agentic');
  assert.equal(effectiveVideoMode(['static'], 'agentic'), 'static');
  assert.equal(effectiveVideoMode(['static', 'agentic'], 'agentic'), 'agentic');
  assert.deepEqual(videoModeOptions(null), []);
  assert.equal(VIDEO_DEADLINE_SECONDS, 60);
});
