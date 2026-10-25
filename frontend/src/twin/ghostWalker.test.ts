import { describe, expect, it } from 'vitest'
import fixture from '../__fixtures__/snapshot.json'
import { parseSnapshot } from '../api'
import { ghostFlashes, ghostPath, positionAt } from './ghostWalker'

const snap = parseSnapshot(fixture)

describe('ghostPath', () => {
  it('reads the frozen alignment path from the snapshot, in time order', () => {
    const p = ghostPath(snap)
    expect(p).toHaveLength(fixture.ghost_path.length)
    for (let i = 1; i < p.length; i++) expect(p[i].t_s).toBeGreaterThanOrEqual(p[i - 1].t_s)
    expect(p[0]).toEqual(fixture.ghost_path[0])
  })
  it('is empty without SfM', () => {
    expect(ghostPath({ ...snap, ghost_path: [] })).toEqual([])
  })
})

describe('ghostFlashes', () => {
  it('has one flash per illegal crossing', () => {
    for (const it of snap.iterations) {
      const g = it.geometry!
      const f = ghostFlashes(g)
      expect(f).toHaveLength(g.illegal_crossings.length)
      expect(f[0]).toEqual({ t_s: g.illegal_crossings[0].t_s, x: g.illegal_crossings[0].x, y: g.illegal_crossings[0].y })
    }
  })
})

describe('positionAt', () => {
  it('interpolates between samples and clamps at the ends', () => {
    const p = [{ t_s: 0, x: 0, y: 0 }, { t_s: 2, x: 2, y: 4 }]
    expect(positionAt(p, 1)).toEqual({ x: 1, y: 2 })
    expect(positionAt(p, -5)).toEqual({ x: 0, y: 0 })
    expect(positionAt(p, 9)).toEqual({ x: 2, y: 4 })
    expect(positionAt([], 1)).toBeNull()
  })
})
