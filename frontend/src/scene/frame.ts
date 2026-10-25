// Camera framing: fit the footprint (plus label margin) inside a screen rectangle by projecting its corners.
import * as THREE from 'three';
import type { Point2 } from '../twin/types.ts';

export interface Framing {
  position: THREE.Vector3;
  target: THREE.Vector3;
  distance: number;
}

/**
 * @param margin   NDC margin kept free on every side (0.08 -> 8 percent of half-size)
 * @param topBand  fraction of the canvas height (0..1) left free at the top for overlays
 */
export function frameFootprint(
  extent: Point2, fovDeg: number, aspect: number, polar: number, margin = 0.08, topBand = 0,
): Framing {
  const pad = 2.2; // exit labels sit about 1.5 m outside the walls
  const centre = new THREE.Vector3(extent[0] / 2, 0, -extent[1] / 2);
  const corners: THREE.Vector3[] = [];
  for (const x of [-pad, extent[0] + pad]) {
    for (const z of [pad, -(extent[1] + pad)]) {
      for (const y of [0, 2.2]) corners.push(new THREE.Vector3(x, y, z));
    }
  }
  const cam = new THREE.PerspectiveCamera(fovDeg, aspect, 0.1, 500);
  const place = (distance: number, target: THREE.Vector3) => {
    cam.position.set(target.x, distance * Math.cos(polar), target.z + distance * Math.sin(polar));
    cam.lookAt(target);
    cam.updateMatrixWorld(true);
    cam.updateProjectionMatrix();
  };
  const bounds = () => {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const c of corners) {
      const p = c.clone().project(cam);
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y); maxY = Math.max(maxY, p.y);
    }
    return { minX, maxX, minY, maxY };
  };
  // Usable NDC window: full width, and everything below the top band.
  const lo = -1 + margin;
  const hi = 1 - margin - 2 * topBand;
  const winW = 2 * (1 - margin);
  const winH = hi - lo;

  let a = 8;
  let b = 400;
  for (let i = 0; i < 40; i++) {
    const mid = (a + b) / 2;
    place(mid, centre);
    const bb = bounds();
    if (bb.maxX - bb.minX <= winW && bb.maxY - bb.minY <= winH) b = mid; else a = mid;
  }
  const distance = b;

  // Shift the target so the footprint's centre lands in the middle of the usable window.
  place(distance, centre);
  const bb = bounds();
  const dx = (bb.minX + bb.maxX) / 2 - 0;
  const dy = (bb.minY + bb.maxY) / 2 - (lo + hi) / 2;
  const half = distance * Math.tan((fovDeg * Math.PI) / 360);
  const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0);
  const up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
  const target = centre.clone().addScaledVector(right, dx * half * aspect).addScaledVector(up, dy * half);
  place(distance, target);
  return { position: cam.position.clone(), target, distance };
}
