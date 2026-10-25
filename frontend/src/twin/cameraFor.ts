import * as THREE from 'three'
import type { Keyframe, VenueGraph } from '../types'

export const EYE_HEIGHT_M = 1.6

/**
 * Graph (x, y) on the floor maps to three.js (x, 0, y), Y up.
 * heading_deg 0 looks along +y in graph space (three +z); angles increase
 * clockwise when the graph is viewed from above (y up), so 90 looks along +x.
 * Direction in three space = (sin h, 0, cos h).
 * Note: because (x,y)->(x,0,y) is a reflection of the right-handed floor plan,
 * on-screen the perspective view turns left as heading grows.
 */
export function cameraFor(k: Keyframe): THREE.PerspectiveCamera {
  const cam = new THREE.PerspectiveCamera(65, 1280 / 720, 0.05, 200)
  cam.position.set(k.x, EYE_HEIGHT_M, k.y)
  const h = (k.heading_deg * Math.PI) / 180
  cam.lookAt(k.x + Math.sin(h), EYE_HEIGHT_M, k.y + Math.cos(h))
  cam.updateMatrixWorld(true)
  return cam
}

/** Orthographic plan view fitting all zones with a 1 m margin (16:9 frame). */
export function topDownCamera(graph: VenueGraph): THREE.OrthographicCamera {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (const z of graph.zones) {
    const [x, y, w, h] = z.rect
    minX = Math.min(minX, x); minY = Math.min(minY, y)
    maxX = Math.max(maxX, x + w); maxY = Math.max(maxY, y + h)
  }
  if (!Number.isFinite(minX)) { minX = minY = 0; maxX = maxY = 1 }
  minX -= 1; minY -= 1; maxX += 1; maxY += 1
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2
  let halfW = (maxX - minX) / 2, halfH = (maxY - minY) / 2
  const aspect = 1280 / 720
  if (halfW / halfH < aspect) halfW = halfH * aspect
  else halfH = halfW / aspect
  const cam = new THREE.OrthographicCamera(-halfW, halfW, halfH, -halfH, 0.1, 100)
  cam.position.set(cx, 50, cy)
  cam.up.set(0, 0, -1) // screen right = +x, screen down = +y (image convention)
  cam.lookAt(cx, 0, cy)
  cam.updateMatrixWorld(true)
  return cam
}
