import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { cameraCardsLabel, selectFrame, addCorner, calibrationKey, calibratedLine, chipView, clearCalibration, clickToImagePoint, confirmedToPlaced, CORNER_ORDER, cornersComplete, emptyCorners, errorCopy, isStaleCalibration, loadCalibration, nextCorner, READ_ERROR_COPY, readFailure, REJECTED_COPY, saveCalibration, toCalibrationRequest, undoCorner, usableIds } from './camera.ts';
import { addCameraHazards, emptyPlacement, MAX_HAZARDS, placeHazard, toHazardInputs, undoPlacement } from './placement.ts';

const venue = JSON.parse(readFileSync(new URL('./fixtures/building-v2.json', import.meta.url), 'utf8'));
const size = [1920, 1080];
const memory = () => { const map = new Map(); return { getItem: k => map.get(k) ?? null, setItem: (k, v) => map.set(k, v), removeItem: k => map.delete(k), map }; };

test('corners go TL, TR, BR, BL; undo and reset step back', () => {
  let state = emptyCorners();
  assert.equal(nextCorner(state), 'TL');
  for (const [i, id] of CORNER_ORDER.entries()) {
    assert.equal(nextCorner(state), id);
    state = addCorner(state, [100 * (i + 1), 50 * (i + 1)], size);
  }
  assert.equal(cornersComplete(state), true);
  assert.equal(nextCorner(state), null);
  assert.equal(addCorner(state, [1, 1], size), state);
  const request = toCalibrationRequest(state, size);
  assert.deepEqual(request.corners_px.TL, [100, 50]);
  assert.deepEqual(request.corners_px.BL, [400, 200]);
  assert.deepEqual(request.image_size, size);
  state = undoCorner(state);
  assert.equal(nextCorner(state), 'BL');
  assert.equal(toCalibrationRequest(state, size), null);
  assert.equal(undoCorner(emptyCorners()).points.length, 0);
});

test('clicks outside the still are ignored and clicks scale to image pixels', () => {
  assert.deepEqual(addCorner(emptyCorners(), [-1, 5], size), emptyCorners());
  assert.deepEqual(addCorner(emptyCorners(), [2000, 5], size), emptyCorners());
  assert.deepEqual(clickToImagePoint({ x: 250, y: 150 }, { left: 50, top: 50, width: 400, height: 225 }, size), [960, 480]);
});

test('calibration is stored per camera and resolution and survives a broken store', () => {
  const store = memory();
  const key = calibrationKey('cam-1', size);
  assert.notEqual(key, calibrationKey('cam-1', [1280, 720]));
  assert.notEqual(key, calibrationKey('cam-2', size));
  assert.equal(loadCalibration(store, key), null);
  saveCalibration(store, key, { calibration_id: 'c1', image_size: size, reprojection_error_m: 0.012 });
  assert.equal(loadCalibration(store, key).calibration_id, 'c1');
  clearCalibration(store, key);
  assert.equal(loadCalibration(store, key), null);
  store.setItem(key, '{not json');
  assert.equal(loadCalibration(store, key), null);
  const throwing = { getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }, removeItem() { throw new Error('blocked'); } };
  assert.equal(loadCalibration(throwing, key), null);
  saveCalibration(throwing, key, { calibration_id: 'c', image_size: size, reprojection_error_m: 0 });
  clearCalibration(throwing, key);
  assert.equal(loadCalibration(null, key), null);
});

test('an unknown_calibration 422 means forget and recalibrate', () => {
  assert.equal(isStaleCalibration({ status: 422, detail: 'unknown_calibration' }), true);
  assert.equal(isStaleCalibration({ status: 422, detail: 'calibration_image_size_mismatch' }), true);
  assert.equal(isStaleCalibration({ status: 429, detail: 'camera_read_busy' }), false);
  assert.equal(isStaleCalibration(new Error('x')), false);
  assert.equal(calibratedLine(), 'Calibrated · 4 corners');
});

const candidate = (over = {}) => ({
  candidate_id: 'c1', type: 'FIRE', point: [500, 500], box_2d: [400, 200, 600, 400], label_text: 'FIRE', evidence: 'red card',
  confidence: 'high', low_confidence_reason: null, floor: { x: 20, y: 4 }, zone_id: 'LOBBY', usable: true, rejected_reason: null, confirmed: false, ...over,
});
const read = { provenance: 'live', latency_ms: 7400 };

test('a usable card reads "FIRE · Lobby · Live Gemini · 7 s"', () => {
  const chip = chipView(candidate(), read, venue);
  assert.equal(chip.label, 'FIRE · Lobby · Live Gemini · 7 s');
  assert.equal(chip.tone, 'ok');
  assert.equal(chip.usable, true);
  assert.deepEqual(chip.box, { left: 20, top: 40, width: 20, height: 20 });
  assert.equal(chip.note, null);
});

test('an uploaded image is named in the chip, never passed off as the live camera', () => {
  assert.equal(chipView(candidate(), read, venue, new Set(), 'image').label, 'FIRE \u00b7 Lobby \u00b7 Live Gemini \u00b7 7 s \u00b7 Uploaded image');
  assert.doesNotMatch(chipView(candidate(), read, venue).label, /Uploaded/);
});

test('low confidence is amber with its reason', () => {
  const chip = chipView(candidate({ confidence: 'low', low_confidence_reason: 'card is partly covered' }), read, venue);
  assert.equal(chip.tone, 'warn');
  assert.equal(chip.note, 'Check card · card is partly covered');
  assert.equal(chipView(candidate({ confidence: 'low' }), read, venue).note, 'Check card');
});

test('every rejection has copy and greys the chip', () => {
  for (const reason of ['no_calibration', 'outside_building', 'crosses_building_edge']) {
    const chip = chipView(candidate({ usable: false, rejected_reason: reason, zone_id: null, floor: null }), read, venue);
    assert.equal(chip.tone, 'muted');
    assert.equal(chip.usable, false);
    assert.equal(chip.note, REJECTED_COPY[reason]);
    assert.match(chip.label, /off plan/);
  }
  assert.equal(REJECTED_COPY.no_calibration, 'Calibrate the sheet first');
  assert.equal(REJECTED_COPY.outside_building, 'Card is outside the plan');
  assert.equal(REJECTED_COPY.crosses_building_edge, 'Card crosses the plan edge');
});

test('provenance names the source: fixture and unavailable never read as live', () => {
  assert.match(chipView(candidate(), { provenance: 'fixture', latency_ms: 20 }, venue).label, /Fixture · 0 s$/);
  assert.match(chipView(candidate(), { provenance: 'unavailable', latency_ms: 0 }, venue).label, /Unavailable/);
});

test('failed reads map to short copy', () => {
  assert.equal(readFailure({ status: 'completed', errors: [] }), null);
  assert.equal(readFailure({ status: 'unavailable', errors: ['configuration_missing'] }), 'Gemini is not configured on this laptop');
  for (const code of ['provider_timeout', 'provider_rate_limited', 'stale_capture', 'camera_read_busy']) {
    assert.equal(readFailure({ status: 'failed', errors: [code] }), READ_ERROR_COPY[code]);
  }
  assert.equal(readFailure({ status: 'timed_out', errors: [] }), 'Gemini took too long. Read again.');
  assert.equal(readFailure({ status: 'failed', errors: ['calibration:missing_corner'] }), 'The read failed. Read again.');
  assert.equal(errorCopy('unknown_calibration'), 'Calibration expired. Calibrate the sheet again.');
  assert.equal(errorCopy('candidate_not_usable:outside_building'), 'That card cannot be used');
  assert.equal(errorCopy('whatever'), 'The camera read did not complete');
});

test('usable ids skip rejected, confirmed and locally confirmed cards', () => {
  const cards = [candidate(), candidate({ candidate_id: 'c2', usable: false, rejected_reason: 'outside_building' }), candidate({ candidate_id: 'c3', confirmed: true }), candidate({ candidate_id: 'c4' })];
  assert.deepEqual(usableIds({ candidates: cards }), ['c1', 'c4']);
  assert.deepEqual(usableIds({ candidates: cards }, new Set(['c1'])), ['c4']);
});

const confirmed = { read_id: 'read-1', provenance: 'live', hazards: [{ id: 'cam-1', type: 'FIRE', position: { x: 20.123456, y: 4.5 }, zone_id: 'LOBBY', source: 'camera', untenable_s: null, proposal_id: 'read-1' }] };

test('confirmed hazards keep id, position, zone and proposal_id exactly', () => {
  const [placed] = confirmedToPlaced(confirmed);
  assert.deepEqual(placed, { id: 'cam-1', type: 'FIRE', x: 20.123456, y: 4.5, zone_id: 'LOBBY', untenable_s: null, source: 'camera', proposal_id: 'read-1' });
  const [input] = toHazardInputs([placed]);
  assert.deepEqual(input, { id: 'cam-1', type: 'FIRE', position: { x: 20.123456, y: 4.5 }, zone_id: 'LOBBY', source: 'camera', proposal_id: 'read-1' });
});

test('camera hazards join the placement, undo removes them together, the cap of six holds', () => {
  const state = placeHazard(emptyPlacement(), venue, 'WATER', { x: 10, y: 10 }).state;
  const result = addCameraHazards(state, confirmedToPlaced(confirmed));
  assert.equal(result.added, 1);
  assert.deepEqual(result.state.hazards.map(item => item.source), ['simulated', 'camera']);
  assert.equal(undoPlacement(result.state).hazards.length, 1);
  assert.equal(addCameraHazards(result.state, confirmedToPlaced(confirmed)).added, 0);
  const many = Array.from({ length: 9 }, (_, i) => ({ ...confirmedToPlaced(confirmed)[0], id: `cam-${i}` }));
  const capped = addCameraHazards(emptyPlacement(), many);
  assert.equal(capped.state.hazards.length, MAX_HAZARDS);
  assert.equal(capped.skipped, 3);
});

test('selectFrame follows the selected source, never whichever has data', () => {
  assert.equal(selectFrame('image', 'live', 'upload'), 'upload');
  assert.equal(selectFrame('image', 'live', null), null);
  assert.equal(selectFrame('camera', 'live', 'upload'), 'live');
});

test('corners_too_close has its own copy', () => {
  assert.equal(errorCopy('corners_too_close'), 'Corners too close together. Click the four printed markers.');
});

test('cameraCardsLabel names the card provenance', () => {
  const cam = [{ source: 'camera' }];
  const plan = camera_provenance => ({ hazards: [{ source: 'camera', camera_provenance }] });
  assert.equal(cameraCardsLabel([{ source: 'simulated' }], null, 'live'), null);
  assert.equal(cameraCardsLabel(cam, null, null), 'Camera cards confirmed');
  assert.equal(cameraCardsLabel(cam, null, 'fixture'), 'Camera cards confirmed · Fixture card');
  assert.equal(cameraCardsLabel(cam, plan('live'), 'fixture'), 'Camera cards confirmed · Live Gemini card');
  assert.equal(cameraCardsLabel(cam, { hazards: [{ source: 'camera', camera_provenance: 'live' }, { source: 'camera', camera_provenance: 'fixture' }] }, null), 'Camera cards confirmed · Fixture and live cards');
});
