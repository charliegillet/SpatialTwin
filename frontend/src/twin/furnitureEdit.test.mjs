import assert from 'node:assert/strict';
import test from 'node:test';
import { addPiece, furnitureOf, furniturePayload, MAX_PIECES, movePiece, removePiece, updatePiece, withFurniture } from './furnitureEdit.ts';
import { prepareVideo, videoMime } from '../api/real2sim.ts';

const venue = {
  venue_id: 'flat-abc123', extent: [10, 6],
  zones: [{ id: 'LIVING', polygon: [[0, 0], [6, 0], [6, 6], [0, 6]] }, { id: 'KITCHEN', polygon: [[6, 0], [10, 0], [10, 6], [6, 6]] }],
  doors: [], exits: [],
  appearance: { zones: { LIVING: { floor_material: 'wood' } }, furniture: [
    { id: 'F1', zone: 'LIVING', label: 'Sofa', category: 'sofa', position: [2, 2], width: 2, depth: 0.9, height: 0.8, yaw_deg: 0, color: '#4d5a7a' },
  ] },
};

test('a new piece lands in the middle of its room with a typical size and a fresh id', () => {
  const { furniture, id } = addPiece(venue, furnitureOf(venue), 'KITCHEN', 'table');
  assert.equal(id, 'F2');
  assert.deepEqual(furniture[1].position, [8, 3]);
  assert.deepEqual([furniture[1].width, furniture[1].depth, furniture[1].height], [1.2, 0.8, 0.75]);
  assert.equal(addPiece(venue, furniture, 'ATTIC', 'bed').id, null);
  const full = Array.from({ length: MAX_PIECES }, (_, i) => ({ ...furniture[0], id: `F${i + 1}` }));
  assert.equal(addPiece(venue, full, 'LIVING', 'bin').id, null);
});

test('moving a piece keeps it in the building and moves it to the room it lands in', () => {
  const moved = movePiece(venue, furnitureOf(venue), 'F1', [8.123, 99]);
  assert.deepEqual(moved[0].position, [8.12, 6]);
  assert.equal(moved[0].zone, 'KITCHEN');
});

test('form edits clamp sizes, wrap the rotation and never blank the label', () => {
  const [piece] = updatePiece(furnitureOf(venue), 'F1', { width: 50, height: -1, yaw_deg: 270, label: '' });
  assert.equal(piece.width, 10);
  assert.equal(piece.height, 0.05);
  assert.equal(piece.yaw_deg, -90);
  assert.equal(piece.label, 'Sofa');
});

test('the payload drops ids, rounds numbers, and the drawn venue keeps its room looks', () => {
  const list = removePiece(addPiece(venue, furnitureOf(venue), 'LIVING', 'plant').furniture, 'F1');
  assert.deepEqual(furniturePayload(list).map(piece => [piece.id, piece.label]), [[undefined, 'Plant']]);
  const drawn = withFurniture(venue, list);
  assert.equal(drawn.zones, venue.zones);
  assert.deepEqual(drawn.appearance.zones, venue.appearance.zones);
});

test('videos are recognised by type or extension and refused when too big or of another kind', () => {
  assert.equal(videoMime('walk.MOV', ''), 'video/quicktime');
  assert.equal(videoMime('clip', 'video/webm'), 'video/webm');
  assert.equal(videoMime('plan.png', 'image/png'), null);
  assert.throws(() => prepareVideo({ name: 'plan.png', type: 'image/png', size: 10 }), /MP4, WebM or MOV/);
  assert.throws(() => prepareVideo({ name: 'walk.mp4', type: 'video/mp4', size: 300 * 1024 * 1024 }), /256 MB/);
  assert.equal(prepareVideo({ name: 'walk.mp4', type: '', size: 10 }).mime_type, 'video/mp4');
});
