import { useMemo, useRef, useState } from 'react';
import { useThree, type ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import type { FurnitureEditBridge, VenueV2 } from '../twin/types.ts';
import { GlowContext, ObjectModel, objectColor, objectKind } from './FurnitureModels.tsx';

const SELECTED_GLOW = { color: '#5cf28a', intensity: 0.45 };
const NO_GLOW = { color: '#000000', intensity: 0 };
const FLOOR = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
let lastDragEnd = 0;
/** The click that ends a drag lands on the floor; it must not read as "clicked empty floor, deselect". */
export const justDragged = () => performance.now() - lastDragEnd < 250;

/** Furniture from a video walkthrough, drawn for looks only (the planner never sees it). With `edit`, a piece is
 *  selected by clicking it and moved by dragging it across the floor; without it, furniture takes no pointer events
 *  of its own, so hazard drops and clicks reach the floor exactly as before. */
export default function Furniture({ venue, edit }: { venue: VenueV2; edit?: FurnitureEditBridge }) {
  const pieces = venue.appearance?.furniture ?? [];
  const [dragging, setDragging] = useState<string | null>(null);
  const offset = useRef<[number, number]>([0, 0]);
  const hit = useMemo(() => new THREE.Vector3(), []);
  // The orbit camera would turn with the drag; it pauses while a piece is held.
  const controls = useThree((state) => state.controls) as { enabled: boolean } | null;
  if (pieces.length === 0) return null;

  const floorPoint = (event: ThreeEvent<PointerEvent>): [number, number] | null =>
    event.ray.intersectPlane(FLOOR, hit) ? [hit.x, -hit.z] : null;

  const handlers = (id: string, position: [number, number]) => edit ? {
    onPointerDown: (event: ThreeEvent<PointerEvent>) => {
      event.stopPropagation();
      edit.onSelect(id);
      const point = floorPoint(event);
      if (!point) return;
      offset.current = [position[0] - point[0], position[1] - point[1]];
      (event.target as Element | null)?.setPointerCapture?.(event.pointerId);
      if (controls) controls.enabled = false;
      setDragging(id);
    },
    onPointerMove: (event: ThreeEvent<PointerEvent>) => {
      if (dragging !== id) return;
      event.stopPropagation();
      const point = floorPoint(event);
      if (point) edit.onMove(id, [point[0] + offset.current[0], point[1] + offset.current[1]]);
    },
    onPointerUp: (event: ThreeEvent<PointerEvent>) => {
      if (dragging !== id) return;
      event.stopPropagation();
      (event.target as Element | null)?.releasePointerCapture?.(event.pointerId);
      if (controls) controls.enabled = true;
      lastDragEnd = performance.now();
      setDragging(null);
    },
    onClick: (event: ThreeEvent<MouseEvent>) => event.stopPropagation(),
  } : {};

  return (
    <group>
      {pieces.map((piece, index) => {
        const id = piece.id ?? `F${index + 1}`;
        const kind = objectKind(piece);
        const selected = edit?.selectedId === id;
        return (
          <GlowContext.Provider key={id} value={selected ? SELECTED_GLOW : NO_GLOW}>
            <group position={[piece.position[0], 0.01, -piece.position[1]]} rotation={[0, (piece.yaw_deg * Math.PI) / 180, 0]}
              {...handlers(id, piece.position)}>
              <ObjectModel kind={kind} w={piece.width} d={piece.depth} h={piece.height} color={objectColor(piece, kind)} />
            </group>
          </GlowContext.Provider>
        );
      })}
    </group>
  );
}
