import { describe, expect, it } from 'vitest'
import fixture from '../__fixtures__/snapshot.json'
import { parseSnapshot } from '../api'
import { counterForStep, dotLayout, dotsForStep, formatHero } from './crowdDots'

const run = parseSnapshot(fixture).current_run!

describe('formatHero', () => {
  it('uses the exact hero wording', () => {
    expect(formatHero(60, 120)).toBe('60 of 120 reach a modeled exit in 120 s')
  })
})

describe('dotsForStep', () => {
  it('totals sum(zone_occupancy[k]) for every k of the fixture run', () => {
    expect(run.zone_occupancy.length).toBeGreaterThan(1)
    run.zone_occupancy.forEach((occ, k) => {
      const dots = dotsForStep(run, k)
      const total = dots.reduce((s, d) => s + d.count, 0)
      expect(total).toBe(Object.values(occ).reduce((s, n) => s + n, 0))
      for (const d of dots) expect(d.count).toBe(occ[d.zoneId])
    })
  })
})

describe('counterForStep', () => {
  it('reconciles to the hero number at the horizon and conserves people', () => {
    run.zone_occupancy.forEach((_, k) => {
      const c = counterForStep(run, k)
      expect(c.inZones + c.inTransit + c.reached).toBe(run.total)
    })
    const last = counterForStep(run, run.zone_occupancy.length - 1)
    expect(last.reached).toBe(run.reached_exit)
  })
})

describe('dotLayout', () => {
  it('places exactly count dots inside the zone rect', () => {
    const pts = dotLayout([3, 0, 12, 8], 120)
    expect(pts).toHaveLength(120)
    for (const [x, y] of pts) {
      expect(x).toBeGreaterThan(3); expect(x).toBeLessThan(15)
      expect(y).toBeGreaterThan(0); expect(y).toBeLessThan(8)
    }
    expect(dotLayout([0, 0, 1, 1], 0)).toEqual([])
  })
})
