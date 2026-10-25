import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import type { VenueGraph } from '../types'
import fixture from './__fixtures__/office_graph.json'
import { buildScene } from './buildScene'
import { graphToScene } from './graphToScene'
import { cameraFor, topDownCamera } from './cameraFor'

const graph = fixture as unknown as VenueGraph
const named = (s: THREE.Scene, p: string) => {
  const out: THREE.Object3D[] = []
  s.traverse((o) => { if (o.name.startsWith(p)) out.push(o) })
  return out
}

describe('buildScene', () => {
  it('builds zones, doors and exits', () => {
    const s = buildScene(graph, { hazards: [] })
    expect(named(s, 'zone:')).toHaveLength(4)
    expect(named(s, 'door:')).toHaveLength(6)
    expect(named(s, 'exit:')).toHaveLength(3) // fixture exits: D2, D4, D5
    expect(named(s, 'hazard:')).toHaveLength(0)
  })
  it('adds hazard boxes', () => {
    const s = buildScene(graph, { hazards: ['D2'] })
    expect(named(s, 'hazard:D2')).toHaveLength(1)
  })
  it('colours doors by state', () => {
    const g = structuredClone(graph)
    g.doors[1].state = 'closed'
    g.doors[2].state = 'unknown'
    const s = buildScene(g, { hazards: [] })
    const m = (id: string) => ((s.getObjectByName(`door:${id}`) as THREE.Mesh).material as THREE.MeshStandardMaterial).color.getHex()
    expect(m('D5')).toBe(0x8b1a1a)
    expect(m('D1')).toBe(0x2e9e4f)
    expect(m('D2')).toBe(0x8a8a8a)
    expect(m('D3')).toBe(0xe0a020)
  })
  it('marks doors opened by your approval (M4)', () => {
    const s = buildScene(graph, { hazards: [], approved: ['D5', 'D99'] })
    expect(named(s, 'approved:')).toHaveLength(1)
    expect(s.getObjectByName('approved:D5')).toBeTruthy()
    expect(named(buildScene(graph, { hazards: [] }), 'approved:')).toHaveLength(0)
  })
  it('leaves gaps in walls at doors', () => {
    const s = buildScene(graph, { hazards: [] })
    // D1 at graph (3,4), mid width 1.7: Z1 west edge (index 2) splits at y 3.15 and 4.85
    const segs = named(s, 'wall:Z1:2').map((o) => new THREE.Box3().setFromObject(o))
    expect(segs).toHaveLength(2)
    const ys = segs.map((b) => [-b.max.z, -b.min.z]).sort((p, q) => p[0] - q[0])
    expect(ys[0][1]).toBeCloseTo(3.15, 2)
    expect(ys[1][0]).toBeCloseTo(4.85, 2)
    // D5 at graph (9,0), mid width 1.05: Z1 south edge (index 0) splits at x 8.475 and 9.525
    const hs = named(s, 'wall:Z1:0').map((o) => new THREE.Box3().setFromObject(o))
    expect(hs).toHaveLength(2)
    const xs = hs.map((b) => [b.min.x, b.max.x]).sort((p, q) => p[0] - q[0])
    expect(xs[0][1]).toBeCloseTo(8.475, 2)
    expect(xs[1][0]).toBeCloseTo(9.525, 2)
  })
})

describe('cameras', () => {
  it('cameraFor sets eye height, fov and heading', () => {
    const c = cameraFor({ t_s: 0, zone_id: 'Z1', x: 5, y: 2, heading_deg: 90 })
    expect(c.position.y).toBeCloseTo(1.6)
    expect(c.fov).toBe(65)
    const dir = new THREE.Vector3(); c.getWorldDirection(dir)
    expect(dir.x).toBeCloseTo(1); expect(dir.z).toBeCloseTo(0)
    const c0 = cameraFor({ t_s: 0, zone_id: 'Z1', x: 5, y: 2, heading_deg: 0 })
    c0.getWorldDirection(dir)
    expect(dir.z).toBeCloseTo(-1)
  })
  it('topDownCamera bounds contain every zone rect with 1 m margin', () => {
    const c = topDownCamera(graph)
    // fixture extent: x 0..18, y 0..11
    const ndc = (x: number, y: number) => new THREE.Vector3(x, 0, -y).project(c)
    for (const [x, y] of [[0, 0], [18, 11]]) {
      const p = ndc(x, y)
      expect(Math.abs(p.x)).toBeLessThanOrEqual(1)
      expect(Math.abs(p.y)).toBeLessThanOrEqual(1)
    }
    // margin: 1 m beyond the extent still fits, 1 m further is not required to
    const half = (c.right - c.left) / 2, halfH = (c.top - c.bottom) / 2
    expect(half).toBeGreaterThanOrEqual(10)
    expect(halfH).toBeGreaterThanOrEqual(6.5)
    expect(Math.min(half, halfH * 1280 / 720) * 2).toBeGreaterThanOrEqual(20 - 1e-9)
    // tight on the limiting axis: 20 m wide (18 + 2 m margin)
    expect(c.right - c.left).toBeCloseTo(Math.max(20, 13 * 1280 / 720), 6)
  })
  it('topDownCamera shows graph +x right and +y up', () => {
    const c = topDownCamera(graph)
    const mid = new THREE.Vector3(9, 0, -5.5).project(c)
    const px = new THREE.Vector3(14, 0, -5.5).project(c)
    const py = new THREE.Vector3(9, 0, -10.5).project(c)
    expect(px.x).toBeGreaterThan(mid.x)
    expect(py.y).toBeGreaterThan(mid.y)
  })
  it('facing +y puts +x on screen-right', () => {
    const c = cameraFor({ t_s: 0, zone_id: 'Z1', x: 5, y: 2, heading_deg: 0 })
    expect(new THREE.Vector3(6, 1.6, -3).project(c).x).toBeGreaterThan(0)
    const c90 = cameraFor({ t_s: 0, zone_id: 'Z1', x: 5, y: 2, heading_deg: 90 })
    expect(new THREE.Vector3(6, 1.6, -1).project(c90).x).toBeGreaterThan(0)
  })
})

describe('graphToScene', () => {
  it('maps (x, y, h) to (x, h, -y)', () => {
    expect(graphToScene(3, 4, 1.6).toArray()).toEqual([3, 1.6, -4])
    expect(graphToScene(3, 4).toArray()).toEqual([3, 0, -4])
  })
})
