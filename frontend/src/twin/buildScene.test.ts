import * as THREE from 'three'
import { describe, expect, it } from 'vitest'
import type { VenueGraph } from '../types'
import fixture from './__fixtures__/office_graph.json'
import { buildScene } from './buildScene'
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
  it('colours locked doors 0x8b1a1a and open doors green', () => {
    const s = buildScene(graph, { hazards: [] })
    const m = (id: string) => ((s.getObjectByName(`door:${id}`) as THREE.Mesh).material as THREE.MeshStandardMaterial).color.getHex()
    expect(m('D5')).toBe(0x8b1a1a)
    expect(m('D1')).not.toBe(0x8b1a1a)
  })
  it('leaves a gap in the wall at a door', () => {
    const s = buildScene(graph, { hazards: [] })
    // D1 at (3,4), width 1.7: no wall box on Z1 west edge covers z=4
    const covers = named(s, 'wall:Z1:2').some((o) => {
      const b = new THREE.Box3().setFromObject(o)
      return b.min.z < 4 && b.max.z > 4
    })
    expect(covers).toBe(false)
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
    expect(dir.z).toBeCloseTo(1)
  })
  it('topDownCamera bounds contain every zone rect', () => {
    const c = topDownCamera(graph)
    for (const z of graph.zones) {
      const [x, y, w, h] = z.rect
      for (const [px, py] of [[x, y], [x + w, y + h]]) {
        const p = new THREE.Vector3(px, 0, py).project(c)
        expect(Math.abs(p.x)).toBeLessThanOrEqual(1)
        expect(Math.abs(p.y)).toBeLessThanOrEqual(1)
      }
    }
  })
})
