import * as THREE from 'three'

/**
 * Graph (x, y) on the floor plan -> three.js world, Y up (ruling R15: right-handed,
 * plan view is y-up). Placeholder with the same signature and behaviour as the
 * shared helper landing on another lane; the merge replaces this file.
 */
export function graphToScene(x: number, y: number, height = 0): THREE.Vector3 {
  return new THREE.Vector3(x, height, -y)
}
