import test from 'node:test';
import assert from 'node:assert/strict';
import {
  addObjectToScene,
  buildSegmentedWallPieces,
  conditionalGapPassProbability,
  createInitialHistory,
  discardUnsavedEdits,
  pushSceneEdit,
  redoSceneEdit,
  undoSceneEdit,
  updateObjectInScene,
} from './editorState.ts';

const sampleScene = {
  schema_version: '1.0',
  scene_id: 'scene-test-1',
  scene_revision: 1,
  name: 'Sample Room',
  units: 'm',
  up_axis: 'Y',
  geometry_source: 'model_estimate',
  floor: [
    [-2, -1.5],
    [2, -1.5],
    [2, 1.5],
    [-2, 1.5],
  ],
  walls: [
    { id: 'wall-1', start: [-2, -1.5], end: [2, -1.5], height_m: 2.7, thickness_m: 0.12 },
    { id: 'wall-2', start: [2, -1.5], end: [2, 1.5], height_m: 2.7, thickness_m: 0.12 },
    { id: 'wall-3', start: [2, 1.5], end: [-2, 1.5], height_m: 2.7, thickness_m: 0.12 },
    { id: 'wall-4', start: [-2, 1.5], end: [-2, -1.5], height_m: 2.7, thickness_m: 0.12 },
  ],
  openings: [
    { id: 'door-1', wall_id: 'wall-1', kind: 'door', offset_m: 1.0, width_m: 0.9, height_m: 2.1, sill_m: 0 },
    { id: 'win-1', wall_id: 'wall-2', kind: 'window', offset_m: 0.5, width_m: 1.2, height_m: 1.1, sill_m: 0.9 },
  ],
  objects: [
    {
      id: 'table-1',
      label: 'Main Table',
      category: 'table',
      center: [0, 0],
      width_m: 1.4,
      depth_m: 0.8,
      height_m: 0.75,
      yaw_deg: 0,
      movable: true,
      resize_allowed: true,
      uncertainty_radius_m: 0.1,
    },
  ],
};

test('history undo, redo, and discard work deterministically', () => {
  let state = createInitialHistory(sampleScene);
  assert.equal(state.dirty, false);

  const edited = updateObjectInScene(state.present, 'table-1', (o) => ({ ...o, center: [0.5, -0.25] }));
  state = pushSceneEdit(state, edited);
  assert.equal(state.dirty, true);
  assert.deepEqual(state.present.objects[0].center, [0.5, -0.25]);
  assert.equal(state.present.objects[0].provenance.source, 'user_edit');

  state = undoSceneEdit(state);
  assert.equal(state.dirty, false);
  assert.deepEqual(state.present.objects[0].center, [0, 0]);

  state = redoSceneEdit(state);
  assert.equal(state.dirty, true);
  assert.deepEqual(state.present.objects[0].center, [0.5, -0.25]);

  state = discardUnsavedEdits(state);
  assert.equal(state.dirty, false);
  assert.deepEqual(state.present.objects[0].center, [0, 0]);
});

test('buildSegmentedWallPieces splits walls around doors and windows', () => {
  const pieces = buildSegmentedWallPieces(sampleScene);
  const wall1Pieces = pieces.filter((p) => p.wallId === 'wall-1');
  const wall2Pieces = pieces.filter((p) => p.wallId === 'wall-2');

  // wall-1 has 1 door (left solid + lintel + right solid = 3 pieces)
  assert.equal(wall1Pieces.length, 3);
  assert.ok(wall1Pieces.some((p) => p.kind === 'lintel'));

  // wall-2 has 1 window with sill > 0 (left solid + sill + lintel + right solid = 4 pieces)
  assert.equal(wall2Pieces.length, 4);
  assert.ok(wall2Pieces.some((p) => p.kind === 'sill'));
  assert.ok(wall2Pieces.some((p) => p.kind === 'lintel'));
});

test('addObjectToScene and conditionalGapPassProbability behave accurately', () => {
  const { scene: next, newId } = addObjectToScene(sampleScene, 'chair');
  assert.equal(next.objects.length, 2);
  assert.ok(newId.startsWith('obj-'));

  assert.equal(conditionalGapPassProbability(0.8, 0.9, 0), 1.0);
  assert.equal(conditionalGapPassProbability(0.8, 0.7, 0), 0.0);
  const pMid = conditionalGapPassProbability(0.8, 0.8, 0.1);
  assert.ok(Math.abs(pMid - 0.5) < 1e-5);
});
