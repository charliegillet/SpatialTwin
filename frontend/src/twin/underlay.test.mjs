// Map underlay: parse the server's placement strictly, draw only under the same geometry, crop to the building.
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_UNDERLAY_OPACITY, NO_PHOTO_VENUES, featherMask, floorOpacity, parseUnderlay, underlayMargin, underlayMatches,
  underlayPlacement,
} from './underlay.ts';

const VENUE = 'ferry-building-level-2';
// The shape GET /api/venues/{id}/underlay returns (numbers from the home test fixture: 12 m over 800 px).
const raw = (extra = {}) => ({
  available: true, venue_id: VENUE, geometry_revision: 'geom-abc', reason: null,
  image_url: `/api/venues/${VENUE}/underlay.jpg?v=0123456789abcdef`,
  corners_m: [[-1.5, 13.5], [13.5, 13.5], [13.5, -1.5], [-1.5, -1.5]],
  width_px: 1000, height_px: 1000, mime_type: 'image/png', provenance: 'live',
  provenance_label: 'Source photo · read by Gemini 4 Argon', ...extra,
});

test('a placed photo parses with its corners, size and provenance', () => {
  const answer = parseUnderlay(raw(), VENUE);
  assert.equal(answer.available, true);
  assert.deepEqual(answer.underlay.corners, [[-1.5, 13.5], [13.5, 13.5], [13.5, -1.5], [-1.5, -1.5]]);
  assert.equal(answer.underlay.provenanceLabel, 'Source photo · read by Gemini 4 Argon');
  assert.equal(answer.underlay.geometryRevision, 'geom-abc');
});

test('not available keeps the server reason; anything malformed is not drawn', () => {
  assert.deepEqual(parseUnderlay({ available: false, venue_id: VENUE, reason: 'underlay_misaligned' }, VENUE),
    { available: false, reason: 'underlay_misaligned' });
  const bad = [
    raw({ venue_id: 'other-venue' }),
    raw({ corners_m: [[0, 1], [1, 1], [1, 0]] }),
    raw({ corners_m: [[0, 1], [1, 1.2], [1, 0], [0, 0]] }),          // not axis-aligned
    raw({ corners_m: [[1, 1], [0, 1], [0, 0], [1, 0]] }),            // mirrored
    raw({ image_url: 'https://elsewhere.example/x.jpg' }),
    raw({ image_url: `/api/venues/${VENUE}/underlay//evil` }),
    raw({ image_url: '/api/venues/other-venue/underlay.jpg' }),
    raw({ provenance_label: '' }),
    raw({ width_px: 0 }),
    raw({ geometry_revision: null }),
    null, 'nope', [],
  ];
  for (const item of bad) assert.equal(parseUnderlay(item, VENUE).available, false, JSON.stringify(item));
});

test('the photo is drawn only under the geometry it was placed against', () => {
  const { underlay } = parseUnderlay(raw(), VENUE);
  assert.equal(underlayMatches(underlay, { venue_id: VENUE, geometry_revision: 'geom-abc' }), true);
  assert.equal(underlayMatches(underlay, { venue_id: VENUE, geometry_revision: 'geom-new' }), false);
  assert.equal(underlayMatches(underlay, { venue_id: 'building-v2', geometry_revision: 'geom-abc' }), false);
  assert.equal(underlayMatches(null, { venue_id: VENUE, geometry_revision: 'geom-abc' }), false);
});

test('the built-in venue is never asked for a photo; the photo starts on', () => {
  assert.ok(NO_PHOTO_VENUES.has('building-v2'));
  assert.ok(DEFAULT_UNDERLAY_OPACITY > 0 && DEFAULT_UNDERLAY_OPACITY <= 1);
});

test('placement crops to the building plus a margin and maps metres to texture coordinates', () => {
  const { underlay } = parseUnderlay(raw(), VENUE);
  // A 12 x 12 m building in a 15 x 15 m image (1.5 m of paper all round): the margin is clipped to the image.
  const p = underlayPlacement(underlay, [12, 12], 3);
  assert.deepEqual([p.x0, p.y0, p.x1, p.y1], [-1.5, -1.5, 13.5, 13.5]);
  assert.deepEqual([p.u0, p.v0, p.u1, p.v1], [0, 0, 1, 1]);
  // Large image: the crop keeps 1 m round the building; (0, 0) m is 1.5 m from the image's west and south edges.
  const big = parseUnderlay(raw({ corners_m: [[-20, 40], [30, 40], [30, -10], [-20, -10]] }), VENUE).underlay;
  const q = underlayPlacement(big, [12, 12], 1);
  assert.deepEqual([q.x0, q.y0, q.x1, q.y1], [-1, -1, 13, 13]);
  assert.ok(Math.abs(q.u0 - 19 / 50) < 1e-12 && Math.abs(q.u1 - 33 / 50) < 1e-12);
  assert.ok(Math.abs(q.v0 - 9 / 50) < 1e-12 && Math.abs(q.v1 - 23 / 50) < 1e-12);
  assert.ok(q.featherU > 0 && q.featherU <= 0.45 && q.featherV > 0 && q.featherV <= 0.45);
});

test('a photo that does not cover the building at all is not placed', () => {
  const far = parseUnderlay(raw({ corners_m: [[100, 140], [130, 140], [130, 110], [100, 110]] }), VENUE).underlay;
  assert.equal(underlayPlacement(far, [12, 12], 3), null);
});

test('margin grows with the building but stays between 3 and 8 m', () => {
  assert.equal(underlayMargin([12, 8]), 3);
  assert.ok(Math.abs(underlayMargin([26.1, 54.2]) - 5.42) < 1e-9);
  assert.equal(underlayMargin([200, 90]), 8);
});

test('the feather mask is opaque in the middle and fades to nothing at every edge', () => {
  const size = 32;
  const mask = featherMask(size, 0.2, 0.2);
  const at = (row, col) => mask[row * size + col];
  assert.equal(at(16, 16), 255);
  for (const [row, col] of [[0, 16], [31, 16], [16, 0], [16, 31]]) assert.ok(at(row, col) < 20, `${row},${col}`);
  assert.ok(at(3, 16) < at(6, 16));
  assert.deepEqual(featherMask(4, 0, 0), new Uint8Array(16).fill(255));
});

test('floors turn see-through as the photo comes up, never fully transparent', () => {
  assert.equal(floorOpacity(0), 1);
  assert.ok(floorOpacity(0.6) < 0.5 && floorOpacity(0.6) > 0.2);
  assert.equal(floorOpacity(1), 0.15);
  assert.equal(floorOpacity(5), 0.15);
  assert.equal(floorOpacity(-1), 1);
});
