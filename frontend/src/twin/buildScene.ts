import * as THREE from 'three'
import type { Door, VenueGraph, Zone } from '../types'

export const WALL_HEIGHT_M = 2.7
const WALL_THICK = 0.12
const EPS = 0.05

export const DOOR_COLORS: Record<string, number> = {
  open: 0x2e9e4f,
  closed: 0x8a8a8a,
  locked: 0x8b1a1a,
  unknown: 0xe0a020,
}

export interface BuildOpts {
  hazards: string[]
  doorFlows?: Record<string, number>
}

const midWidth = (d: Door) => (d.clear_width.low_m + d.clear_width.high_m) / 2

function wallBox(
  group: THREE.Object3D, mat: THREE.Material, name: string,
  x0: number, y0: number, x1: number, y1: number,
) {
  const len = Math.hypot(x1 - x0, y1 - y0)
  if (len < 1e-3) return
  const horizontal = Math.abs(y1 - y0) < 1e-9
  const geo = new THREE.BoxGeometry(horizontal ? len : WALL_THICK, WALL_HEIGHT_M, horizontal ? WALL_THICK : len)
  const m = new THREE.Mesh(geo, mat)
  m.name = name
  m.position.set((x0 + x1) / 2, WALL_HEIGHT_M / 2, (y0 + y1) / 2)
  group.add(m)
}

function zoneWalls(zone: Zone, doors: Door[], group: THREE.Object3D, mat: THREE.Material) {
  const [x, y, w, h] = zone.rect
  // each edge: fixed coord, varying axis start/end, and which door coordinate decides membership
  const edges = [
    { horiz: true, fixed: y, a: x, b: x + w, near: (d: Door) => Math.abs(d.position[1] - y) < EPS, along: (d: Door) => d.position[0] },
    { horiz: true, fixed: y + h, a: x, b: x + w, near: (d: Door) => Math.abs(d.position[1] - (y + h)) < EPS, along: (d: Door) => d.position[0] },
    { horiz: false, fixed: x, a: y, b: y + h, near: (d: Door) => Math.abs(d.position[0] - x) < EPS, along: (d: Door) => d.position[1] },
    { horiz: false, fixed: x + w, a: y, b: y + h, near: (d: Door) => Math.abs(d.position[0] - (x + w)) < EPS, along: (d: Door) => d.position[1] },
  ]
  edges.forEach((e, ei) => {
    const gaps = doors
      .filter((d) => (d.a === zone.id || d.b === zone.id) && e.near(d) && e.along(d) >= e.a - EPS && e.along(d) <= e.b + EPS)
      .map((d) => [e.along(d) - midWidth(d) / 2, e.along(d) + midWidth(d) / 2] as [number, number])
      .sort((p, q) => p[0] - q[0])
    let cur = e.a
    let seg = 0
    const emit = (s: number, t: number) => {
      const name = `wall:${zone.id}:${ei}:${seg++}`
      if (e.horiz) wallBox(group, mat, name, s, e.fixed, t, e.fixed)
      else wallBox(group, mat, name, e.fixed, s, e.fixed, t)
    }
    for (const [g0, g1] of gaps) {
      emit(cur, Math.max(cur, g0))
      cur = Math.max(cur, g1)
    }
    emit(cur, e.b)
  })
}

/** Pure scene construction: no DOM, no renderer. Graph (x,y) -> three (x,0,y). */
export function buildScene(graph: VenueGraph, opts: BuildOpts): THREE.Scene {
  const scene = new THREE.Scene()
  scene.background = new THREE.Color(0xdfe6ee)
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8890a0, 1.4))
  const sun = new THREE.DirectionalLight(0xffffff, 1.2)
  sun.position.set(10, 20, 5)
  scene.add(sun)

  const wallMat = new THREE.MeshStandardMaterial({ color: 0xf2f2f0 })
  const floorColors = [0xc9b79c, 0xb7c4b0, 0xb0bcc9, 0xc9b0c0]
  graph.zones.forEach((z, i) => {
    const [x, y, w, h] = z.rect
    const floor = new THREE.Mesh(
      new THREE.BoxGeometry(w, 0.05, h),
      new THREE.MeshStandardMaterial({ color: floorColors[i % floorColors.length] }),
    )
    floor.name = `zone:${z.id}`
    floor.position.set(x + w / 2, -0.025, y + h / 2)
    scene.add(floor)
    zoneWalls(z, graph.doors, scene, wallMat)
  })

  const doorById = new Map<string, Door>()
  for (const d of graph.doors) {
    doorById.set(d.id, d)
    const wdt = midWidth(d)
    const color = DOOR_COLORS[d.state] ?? DOOR_COLORS.unknown
    // orient frame along the wall: wall is vertical in plan if door sits on an x-edge of a zone
    const onXEdge = graph.zones.some((z) => (d.a === z.id || d.b === z.id) &&
      (Math.abs(d.position[0] - z.rect[0]) < EPS || Math.abs(d.position[0] - (z.rect[0] + z.rect[2])) < EPS) &&
      d.position[1] >= z.rect[1] - EPS && d.position[1] <= z.rect[1] + z.rect[3] + EPS)
    const mat = new THREE.MeshStandardMaterial({ color })
    const frame = new THREE.Mesh(
      new THREE.BoxGeometry(onXEdge ? 0.2 : wdt, 0.12, onXEdge ? wdt : 0.2), mat)
    frame.name = `door:${d.id}`
    frame.position.set(d.position[0], 2.1, d.position[1])
    scene.add(frame)

    if (d.b === 'OUTSIDE' || d.kind === 'exit') {
      const sign = new THREE.Mesh(
        new THREE.BoxGeometry(0.5, 0.25, 0.1),
        new THREE.MeshStandardMaterial({ color: 0x1fbf5f, emissive: 0x1fbf5f, emissiveIntensity: 0.8 }))
      sign.name = `exit:${d.id}`
      sign.position.set(d.position[0], 2.4, d.position[1])
      scene.add(sign)
    }
  }

  for (const id of opts.hazards) {
    const d = doorById.get(id)
    if (!d) continue
    const hz = new THREE.Mesh(
      new THREE.BoxGeometry(0.8, 0.8, 0.8),
      new THREE.MeshStandardMaterial({ color: 0xff2020, emissive: 0xff0000, emissiveIntensity: 1.0 }))
    hz.name = `hazard:${id}`
    hz.position.set(d.position[0], 0.4, d.position[1])
    scene.add(hz)
  }

  // optional flow markers: thin bar whose height scales with flow
  for (const [id, flow] of Object.entries(opts.doorFlows ?? {})) {
    const d = doorById.get(id)
    if (!d) continue
    const bar = new THREE.Mesh(
      new THREE.BoxGeometry(0.2, Math.max(0.05, flow), 0.2),
      new THREE.MeshStandardMaterial({ color: 0x2060ff }))
    bar.name = `flow:${id}`
    bar.position.set(d.position[0], Math.max(0.05, flow) / 2, d.position[1])
    scene.add(bar)
  }
  return scene
}
