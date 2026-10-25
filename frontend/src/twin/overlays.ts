// three.js overlays on the twin. Inputs are graph coordinates; every placement goes through graphToScene.
import * as THREE from 'three'
import type { FlowRun, GhostPoint } from '../apiTypes'
import type { VenueGraph } from '../types'
import { doorFlowAt, dotLayout, dotsForStep } from './crowdDots'
import { graphToScene } from './graphToScene'

export function disposeGroup(g: THREE.Object3D) {
  g.traverse((o) => {
    const m = o as THREE.Mesh
    m.geometry?.dispose()
    const mat = m.material as THREE.Material | THREE.Material[] | undefined
    if (Array.isArray(mat)) mat.forEach((x) => x.dispose())
    else mat?.dispose()
  })
  g.clear()
}

const centroid = (graph: VenueGraph, id: string): [number, number] | null => {
  const z = graph.zones.find((q) => q.id === id)
  return z ? [z.rect[0] + z.rect[2] / 2, z.rect[1] + z.rect[3] / 2] : null
}

/** Invisible tall boxes at each door so clicks land easily. Named pick:<doorId>. */
export function pickTargets(graph: VenueGraph): THREE.Group {
  const g = new THREE.Group()
  for (const d of graph.doors) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(1.1, 2.2, 1.1), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }))
    m.name = `pick:${d.id}`
    m.position.copy(graphToScene(d.position[0], d.position[1], 1.1))
    g.add(m)
  }
  return g
}

/** One dot per person, per zone, exactly zone_occupancy[k]. */
export function crowdDots(graph: VenueGraph, run: FlowRun, k: number): THREE.InstancedMesh {
  const dots = dotsForStep(run, k)
  const n = dots.reduce((s, d) => s + d.count, 0)
  const mesh = new THREE.InstancedMesh(new THREE.SphereGeometry(0.11, 10, 8), new THREE.MeshStandardMaterial({ color: 0x40c4ff, emissive: 0x0a3a55 }), Math.max(1, n))
  mesh.name = 'crowd'
  const m = new THREE.Matrix4()
  let i = 0
  for (const d of dots) {
    const z = graph.zones.find((q) => q.id === d.zoneId)
    if (!z) continue
    const inset: [number, number, number, number] = [z.rect[0] + 0.2, z.rect[1] + 0.2, Math.max(0.1, z.rect[2] - 0.4), Math.max(0.1, z.rect[3] - 0.4)]
    for (const [x, y] of dotLayout(inset, d.count)) {
      m.setPosition(graphToScene(x, y, 0.15))
      mesh.setMatrixAt(i++, m)
    }
  }
  mesh.count = i
  mesh.instanceMatrix.needsUpdate = true
  return mesh
}

/** Arrows at doors whose shaft thickness scales with people through the door during step k. */
export function flowArrows(graph: VenueGraph, run: FlowRun, k: number): THREE.Group {
  const g = new THREE.Group()
  g.name = 'flows'
  const up = new THREE.Vector3(0, 1, 0)
  const origin = graphToScene(0, 0)
  for (const d of graph.doors) {
    const f = doorFlowAt(run, d.id, k)
    if (!f) continue
    const a = centroid(graph, d.a)
    const b = d.b === 'OUTSIDE' ? null : centroid(graph, d.b)
    if (!a) continue
    // a->b direction; for an exit, from the room centroid out through the door
    const dx = (b ? b[0] : d.position[0]) - a[0], dy = (b ? b[1] : d.position[1]) - a[1]
    const len = Math.hypot(dx, dy) || 1
    const sign = f > 0 ? 1 : -1
    const dir = graphToScene((sign * dx) / len, (sign * dy) / len).sub(origin).normalize()
    const r = 0.04 + 0.05 * Math.min(6, Math.abs(f))
    const mat = new THREE.MeshStandardMaterial({ color: 0xffd54a, emissive: 0x4a3a00 })
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(r, r, 0.9, 12), mat)
    const head = new THREE.Mesh(new THREE.ConeGeometry(r * 2.2, 0.45, 14), mat)
    shaft.position.y = 0.45
    head.position.y = 0.9 + 0.22
    const arrow = new THREE.Group()
    arrow.add(shaft, head)
    arrow.name = `flow:${d.id}`
    arrow.quaternion.setFromUnitVectors(up, dir)
    arrow.position.copy(graphToScene(d.position[0], d.position[1], 0.35)).addScaledVector(dir, -0.55)
    g.add(arrow)
  }
  return g
}

export function ghostTrail(path: GhostPoint[]): THREE.Line {
  const geo = new THREE.BufferGeometry().setFromPoints(path.map((p) => graphToScene(p.x, p.y, 0.04)))
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color: 0xb388ff }))
  line.name = 'ghost-trail'
  return line
}

export function ghostBody(): THREE.Group {
  const g = new THREE.Group()
  g.name = 'ghost'
  const mat = new THREE.MeshStandardMaterial({ color: 0xe6dcff, emissive: 0x5a3ea8, transparent: true, opacity: 0.85 })
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 1.2, 16), mat)
  body.position.y = 0.6
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.17, 16, 12), mat)
  head.position.y = 1.4
  g.add(body, head)
  return g
}

export function flashMarkers(flashes: GhostPoint[]): THREE.Group {
  const g = new THREE.Group()
  g.name = 'flashes'
  flashes.forEach((f, i) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.28, 16, 12), new THREE.MeshStandardMaterial({ color: 0xff3b3b, emissive: 0xff0000, emissiveIntensity: 0.4 }))
    m.name = `flash:${i}`
    m.position.copy(graphToScene(f.x, f.y, 1.0))
    m.userData.t_s = f.t_s
    g.add(m)
  })
  return g
}
