import * as THREE from 'three'

/** Single source of truth for the graph -> three.js mapping: (x, y) -> (x, height, -y). */
export function graphToScene(x: number, y: number, height = 0): THREE.Vector3 {
  return new THREE.Vector3(x, height, -y)
}
