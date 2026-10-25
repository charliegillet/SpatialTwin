import * as THREE from "three";
import type { LocalVisualPart } from "./visualBounds.ts";
export function createPartGeometry(part: LocalVisualPart) {
  if (part.shape === "cylinder") {
    // Both horizontal radii must fit; independently clamped X/Z can differ.
    const r = Math.min(part.size[0], part.size[2]) / 2;
    return new THREE.CylinderGeometry(r, r, part.size[1], 20);
  }
  return new THREE.BoxGeometry(...part.size);
}
export const NO_RAYCAST: THREE.Mesh["raycast"] = () => {};
export function setPiecePicking(
  mesh: THREE.Mesh,
  visible: boolean,
  original: THREE.Mesh["raycast"],
) {
  mesh.visible = visible;
  mesh.raycast = visible ? original : NO_RAYCAST;
}
export function shellOutwardNormal(
  floor: number[][],
  start: number[],
  end: number[],
): [number, number] {
  const area = floor.reduce(
    (a, p, i) =>
      a +
      p[0] * floor[(i + 1) % floor.length][1] -
      floor[(i + 1) % floor.length][0] * p[1],
    0,
  );
  const dx = end[0] - start[0],
    dz = end[1] - start[1],
    len = Math.hypot(dx, dz) || 1,
    sign = area >= 0 ? 1 : -1;
  return [(sign * dz) / len, (-sign * dx) / len];
}
