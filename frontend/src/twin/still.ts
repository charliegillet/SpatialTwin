// Client-side still of the twin at the keyframe nearest t (used when the server render isn't servable).
import * as THREE from 'three'
import type { VenueGraph } from '../types'
import { buildScene } from './buildScene'
import { cameraFor } from './cameraFor'

let renderer: THREE.WebGLRenderer | null = null
const cache = new Map<string, string>()

export function renderStill(graph: VenueGraph, revision: string, t: number): string | null {
  const key = `${revision}@${t}`
  const hit = cache.get(key)
  if (hit) return hit
  if (!graph.keyframes.length) return null
  try {
    if (!renderer) {
      renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true, canvas: document.createElement('canvas') })
      renderer.setPixelRatio(1)
      renderer.setSize(640, 360, false)
    }
    const k = graph.keyframes.reduce((a, b) => (Math.abs(b.t_s - t) < Math.abs(a.t_s - t) ? b : a))
    const cam = cameraFor(k)
    renderer.render(buildScene(graph, { hazards: [] }), cam)
    const url = renderer.domElement.toDataURL('image/jpeg', 0.8)
    cache.set(key, url)
    return url
  } catch {
    return null
  }
}
