// Headless/in-app single-view renderer. Params: ?graph=<url>&t=<t_s> | &view=top, &hazards=D1,D2
import * as THREE from 'three'
import type { VenueGraph } from './types'
import { buildScene } from './twin/buildScene'
import { cameraFor, topDownCamera } from './twin/cameraFor'

declare global {
  interface Window { __renderReady?: boolean; __renderError?: string }
}

async function main() {
  const q = new URLSearchParams(location.search)
  const url = q.get('graph')
  if (!url) throw new Error('missing ?graph=')
  const graph = (await (await fetch(url)).json()) as VenueGraph
  const hazards = (q.get('hazards') ?? '').split(',').filter(Boolean)
  const scene = buildScene(graph, { hazards })

  let camera: THREE.Camera
  if (q.get('view') === 'top') {
    camera = topDownCamera(graph)
  } else {
    const t = Number(q.get('t') ?? graph.keyframes[0]?.t_s ?? 0)
    if (!graph.keyframes.length) throw new Error('graph has no keyframes')
    // keyframe nearest in time
    const k = graph.keyframes.reduce((a, b) => (Math.abs(b.t_s - t) < Math.abs(a.t_s - t) ? b : a))
    camera = cameraFor(k)
  }

  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
  renderer.setPixelRatio(1)
  renderer.setSize(1280, 720)
  document.body.appendChild(renderer.domElement)
  renderer.render(scene, camera)
  window.__renderReady = true
}

main().catch((e) => {
  window.__renderError = String(e)
  console.error(e)
})
