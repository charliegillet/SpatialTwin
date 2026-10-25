import type { RoomSceneV1, RoomObject, Wall, Opening } from './contracts.generated';

export type SelectionTarget =
  | { kind: 'object'; id: string }
  | { kind: 'wall'; id: string }
  | { kind: 'opening'; id: string }
  | null;

export type ViewMode = 'orbit' | 'top';

export interface HistoryState {
  authoritative: RoomSceneV1 | null;
  present: RoomSceneV1 | null;
  past: RoomSceneV1[];
  future: RoomSceneV1[];
  dirty: boolean;
}

export function cloneScene(scene: RoomSceneV1): RoomSceneV1 {
  return JSON.parse(JSON.stringify(scene)) as RoomSceneV1;
}

export function createInitialHistory(scene: RoomSceneV1 | null = null): HistoryState {
  return {
    authoritative: scene ? cloneScene(scene) : null,
    present: scene ? cloneScene(scene) : null,
    past: [],
    future: [],
    dirty: false,
  };
}

export function loadAuthoritativeScene(state: HistoryState, scene: RoomSceneV1): HistoryState {
  const copy = cloneScene(scene);
  return {
    authoritative: copy,
    present: cloneScene(scene),
    past: [],
    future: [],
    dirty: false,
  };
}

export function pushSceneEdit(state: HistoryState, nextScene: RoomSceneV1): HistoryState {
  if (!state.present) {
    return createInitialHistory(nextScene);
  }
  const past = [...state.past.slice(-29), cloneScene(state.present)];
  return {
    authoritative: state.authoritative,
    present: cloneScene(nextScene),
    past,
    future: [],
    dirty: true,
  };
}

export function undoSceneEdit(state: HistoryState): HistoryState {
  if (!state.present || state.past.length === 0) return state;
  const previous = state.past[state.past.length - 1];
  const newPast = state.past.slice(0, -1);
  const newFuture = [cloneScene(state.present), ...state.future.slice(0, 29)];
  const dirty = JSON.stringify(previous) !== JSON.stringify(state.authoritative);
  return {
    authoritative: state.authoritative,
    present: cloneScene(previous),
    past: newPast,
    future: newFuture,
    dirty,
  };
}

export function redoSceneEdit(state: HistoryState): HistoryState {
  if (!state.present || state.future.length === 0) return state;
  const next = state.future[0];
  const newFuture = state.future.slice(1);
  const newPast = [...state.past.slice(-29), cloneScene(state.present)];
  const dirty = JSON.stringify(next) !== JSON.stringify(state.authoritative);
  return {
    authoritative: state.authoritative,
    present: cloneScene(next),
    past: newPast,
    future: newFuture,
    dirty,
  };
}

export function discardUnsavedEdits(state: HistoryState): HistoryState {
  if (!state.authoritative) return state;
  return {
    authoritative: cloneScene(state.authoritative),
    present: cloneScene(state.authoritative),
    past: [],
    future: [],
    dirty: false,
  };
}

export function wallLengthMeters(wall: Wall): number {
  const dx = (wall.end[0] ?? 0) - (wall.start[0] ?? 0);
  const dz = (wall.end[1] ?? 0) - (wall.start[1] ?? 0);
  return Math.hypot(dx, dz);
}

export function deriveWallsFromFloor(scene: RoomSceneV1): Wall[] {
  if (scene.walls && scene.walls.length >= 3) {
    return scene.walls;
  }
  const floor = scene.floor ?? [];
  return floor.map((pt, idx) => {
    const next = floor[(idx + 1) % floor.length];
    return {
      id: `wall-${idx + 1}`,
      start: [pt[0], pt[1]],
      end: [next[0], next[1]],
      height_m: 2.7,
      thickness_m: 0.12,
      provenance: {
        source: 'model_estimate',
        visibility: 'partial',
        evidence_frame_ids: [],
        note: 'Derived from floor polygon.',
      },
    };
  });
}

export interface WallSegmentPiece {
  key: string;
  wallId: string;
  center: [number, number, number];
  length: number;
  height: number;
  thickness: number;
  yawRad: number;
  kind: 'solid' | 'lintel' | 'sill';
}

/**
 * Splits each wall around its attached doors/windows/passages so openings are
 * genuinely open in 3D without needing CSG boolean meshes.
 * Backend convention: positive yaw around +Y means THREE rotation.y = yaw * pi / 180,
 * where local +X direction along wall from start -> end has angle atan2(-dz, dx).
 */
export function buildSegmentedWallPieces(scene: RoomSceneV1): WallSegmentPiece[] {
  const walls = deriveWallsFromFloor(scene);
  const openingsByWall = new Map<string, Opening[]>();
  for (const op of scene.openings ?? []) {
    const list = openingsByWall.get(op.wall_id) ?? [];
    list.push(op);
    openingsByWall.set(op.wall_id, list);
  }

  const pieces: WallSegmentPiece[] = [];

  for (const wall of walls) {
    const ax = wall.start[0];
    const az = wall.start[1];
    const bx = wall.end[0];
    const bz = wall.end[1];
    const dx = bx - ax;
    const dz = bz - az;
    const totalLen = Math.hypot(dx, dz);
    if (totalLen < 0.05) continue;

    const ux = dx / totalLen;
    const uz = dz / totalLen;
    // In Three.js Y-up, rotating a unit X box by rotation.y = theta maps (1,0,0) -> (cos(theta), 0, -sin(theta))
    const yawRad = Math.atan2(-dz, dx);
    const wallH = wall.height_m ?? 2.7;
    const wallT = wall.thickness_m ?? 0.12;

    const ops = (openingsByWall.get(wall.id) ?? [])
      .map((op) => {
        const start = Math.max(0, Math.min(totalLen, op.offset_m));
        const end = Math.max(start, Math.min(totalLen, op.offset_m + op.width_m));
        return { op, start, end };
      })
      .filter((item) => item.end - item.start > 0.05)
      .sort((a, b) => a.start - b.start);

    const addPiece = (
      s0: number,
      s1: number,
      yBottom: number,
      yTop: number,
      kind: 'solid' | 'lintel' | 'sill',
      suffix: string,
    ) => {
      const segLen = s1 - s0;
      const segH = yTop - yBottom;
      if (segLen <= 0.02 || segH <= 0.02) return;
      const midS = (s0 + s1) * 0.5;
      const cx = ax + ux * midS;
      const cz = az + uz * midS;
      const cy = yBottom + segH * 0.5;
      pieces.push({
        key: `${wall.id}-${suffix}`,
        wallId: wall.id,
        center: [cx, cy, cz],
        length: segLen,
        height: segH,
        thickness: wallT,
        yawRad,
        kind,
      });
    };

    let cursor = 0;
    ops.forEach((item, idx) => {
      const s0 = Math.max(cursor, item.start);
      const s1 = Math.max(s0, item.end);
      if (s0 > cursor + 0.02) {
        addPiece(cursor, s0, 0, wallH, 'solid', `pre-${idx}`);
      }
      const sill = item.op.kind === 'window' ? Math.max(0, item.op.sill_m ?? 0.9) : Math.max(0, item.op.sill_m ?? 0);
      const opH = Math.max(0.2, item.op.height_m ?? 2.1);
      const top = Math.min(wallH, sill + opH);

      if (sill > 0.02) {
        addPiece(s0, s1, 0, sill, 'sill', `sill-${item.op.id}`);
      }
      if (wallH - top > 0.02) {
        addPiece(s0, s1, top, wallH, 'lintel', `lintel-${item.op.id}`);
      }
      cursor = s1;
    });

    if (totalLen > cursor + 0.02) {
      addPiece(cursor, totalLen, 0, wallH, 'solid', 'tail');
    }
  }

  return pieces;
}

export function updateObjectInScene(
  scene: RoomSceneV1,
  objectId: string,
  updater: (obj: RoomObject) => RoomObject,
): RoomSceneV1 {
  const next = cloneScene(scene);
  next.objects = (next.objects ?? []).map((obj) => {
    if (obj.id !== objectId) return obj;
    const updated = updater(obj);
    return {
      ...updated,
      provenance: {
        ...(updated.provenance ?? {}),
        source: 'user_edit',
        visibility: updated.provenance?.visibility ?? 'observed',
        evidence_frame_ids: updated.provenance?.evidence_frame_ids ?? [],
        note: updated.provenance?.note || 'Edited in RoomLab 3D editor.',
      },
    };
  });
  return next;
}

export function addObjectToScene(scene: RoomSceneV1, category = 'table'): { scene: RoomSceneV1; newId: string } {
  const next = cloneScene(scene);
  const existingIds = new Set((next.objects ?? []).map((o) => o.id));
  let idx = (next.objects?.length ?? 0) + 1;
  while (existingIds.has(`obj-${idx}`)) idx += 1;
  const newId = `obj-${idx}`;

  const presets: Record<string, { label: string; w: number; d: number; h: number; movable: boolean }> = {
    table: { label: `Table ${idx}`, w: 1.4, d: 0.8, h: 0.75, movable: true },
    chair: { label: `Chair ${idx}`, w: 0.55, d: 0.55, h: 0.82, movable: true },
    sofa: { label: `Sofa ${idx}`, w: 1.9, d: 0.9, h: 0.85, movable: true },
    pillar: { label: `Column ${idx}`, w: 0.45, d: 0.45, h: 2.7, movable: false },
  };
  const spec = presets[category] ?? presets.table;

  const newObj: RoomObject = {
    id: newId,
    label: spec.label,
    category,
    center: [0, 0],
    width_m: spec.w,
    depth_m: spec.d,
    height_m: spec.h,
    yaw_deg: 0,
    movable: spec.movable,
    resize_allowed: true,
    uncertainty_radius_m: 0.05,
    provenance: {
      source: 'user_edit',
      visibility: 'observed',
      evidence_frame_ids: [],
      note: 'Added manually by user.',
    },
  };
  next.objects = [...(next.objects ?? []), newObj];
  return { scene: next, newId };
}

export function removeObjectFromScene(scene: RoomSceneV1, objectId: string): RoomSceneV1 {
  const next = cloneScene(scene);
  next.objects = (next.objects ?? []).filter((o) => o.id !== objectId);
  return next;
}

/**
 * Educational conditional Gaussian tail probability P(Gap >= requiredWidth)
 * using Abramowitz & Stegun erfc approximation (max error < 1.5e-7).
 */
export function erfcApprox(x: number): number {
  const z = Math.abs(x);
  const t = 1.0 / (1.0 + 0.5 * z);
  const r =
    t *
    Math.exp(
      -z * z -
        1.26551223 +
        t *
          (1.00002368 +
            t *
              (0.37409196 +
                t *
                  (0.09678418 +
                    t *
                      (-0.18628806 +
                        t *
                          (0.27886807 +
                            t *
                              (-1.13520398 +
                                t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))),
    );
  return x >= 0 ? r : 2.0 - r;
}

export function conditionalGapPassProbability(
  requiredGapM: number,
  assumedMeanGapM: number,
  assumedSigmaM: number,
): number {
  if (!Number.isFinite(requiredGapM) || !Number.isFinite(assumedMeanGapM) || !Number.isFinite(assumedSigmaM) || assumedSigmaM < 0) {
    return NaN;
  }
  if (assumedSigmaM === 0) {
    return assumedMeanGapM >= requiredGapM ? 1.0 : 0.0;
  }
  const arg = (requiredGapM - assumedMeanGapM) / (assumedSigmaM * Math.SQRT2);
  return Math.max(0, Math.min(1, 0.5 * erfcApprox(arg)));
}
