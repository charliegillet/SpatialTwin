import { describe, expect, it } from 'vitest'
import fixture from '../__fixtures__/snapshot.json'
import { parseSnapshot } from '../api'
import type { Iteration } from '../apiTypes'
import {
  critiqueProblem, geometryChoices, iterKind, iterationLabels, loopDelta, opDetail, opRows, opTarget, orphanRejections, pickGeometry,
} from './loopView'

const snap = () => parseSnapshot(JSON.parse(JSON.stringify(fixture)))

describe('iteration kinds (D1)', () => {
  it('reads kind with "round" as the default for old data', () => {
    expect(iterKind({})).toBe('round')
    expect(iterKind({ kind: 'baseline' })).toBe('baseline')
  })
  it('labels baseline, rounds and the accepted rescore', () => {
    expect(iterationLabels(snap().iterations)).toEqual(['Before the loop', 'Round 1', 'Round 2', 'Accepted graph'])
  })
  it('numbers loops once a session has refined twice', () => {
    const its = [{ kind: 'baseline', index: 0 }, { kind: 'round', index: 1 }, { kind: 'baseline', index: 0 }, { kind: 'round', index: 1 }] as const
    expect(iterationLabels([...its])).toEqual(['Loop 1 · Before the loop', 'Loop 1 · Round 1', 'Loop 2 · Before the loop', 'Loop 2 · Round 1'])
  })
  it('keeps old rounds without kind labelled by index', () => {
    expect(iterationLabels([{ index: 1 }, { index: 2 }])).toEqual(['Round 1', 'Round 2'])
  })
})

describe('op rows (I4)', () => {
  it('lists every op with type, target, citation, reason and outcome', () => {
    const r1 = snap().iterations[1]
    expect(opRows(r1)).toEqual([
      expect.objectContaining({ i: 0, type: 'update_zone', target: 'Z4', cite_t_s: 24, status: 'applied', why: null, detail: 'furniture_seen=true' }),
      expect.objectContaining({ i: 1, type: 'update_door', target: 'D3', cite_t_s: 31, status: 'applied', detail: 'state=open' }),
      expect.objectContaining({ i: 2, type: 'update_door', target: 'D9', status: 'rejected', why: 'unknown id D9' }),
    ])
    expect(opRows(r1)[0].reason).toBe('Furniture visible in the green room at 0:24.')
  })
  it('marks a measured regression as a reverted round', () => {
    const rows = opRows(snap().iterations[2])
    expect(rows[1]).toMatchObject({ type: 'remove_door', target: 'D6', status: 'reverted' })
    expect(rows[1].why).toMatch(/whole round was reverted/)
    expect(rows[0].detail).toBe('clear_width=0.95–1 m (estimated)')
  })
  it('finds the target of add ops', () => {
    expect(opTarget({ op: 'add_door', cite_t_s: 1, reason: '', door: { id: 'D7', a: 'Z1', b: 'Z2' } })).toBe('D7')
    expect(opTarget({ op: 'add_zone', cite_t_s: 1, reason: '', zone: { id: 'Z9', name: 'Store' } })).toBe('Z9')
    expect(opDetail({ op: 'add_door', cite_t_s: 1, reason: '', door: { id: 'D7', a: 'Z1', b: 'OUTSIDE' } })).toBe('door Z1↔OUTSIDE')
  })
  it('has no rows without a critique, and keeps rejections it cannot match', () => {
    const it0 = { applied: [0], rejected: [[2, 'unknown id D9']] as [number, string][], critique: null }
    expect(opRows(it0)).toEqual([])
    expect(orphanRejections(it0)).toEqual([[2, 'unknown id D9']])
    expect(orphanRejections(snap().iterations[1])).toEqual([])
  })
})

describe('critique problems (I4)', () => {
  it('shows provider failures and errors, nothing for a completed critique', () => {
    const s = snap()
    expect(critiqueProblem(s.iterations[1])).toBeNull()
    expect(critiqueProblem({ critique: { ...s.iterations[1].critique!, status: 'timeout', error: 'deadline 240 s' }, stop_reason: null }))
      .toBe('Argon critique timeout: deadline 240 s')
    expect(critiqueProblem({ critique: null, stop_reason: 'provider_failed' })).toMatch(/Provider failed/)
  })
})

describe('before -> after (I2)', () => {
  it('compares the baseline with the last measured row after it', () => {
    const d = loopDelta(snap())!
    expect(d.before.illegal_crossings).toHaveLength(5)
    expect(d.after.illegal_crossings).toHaveLength(1)
    expect(d.afterLabel).toBe('Accepted graph')
  })
  it('is null without a measured baseline', () => {
    const s = snap()
    expect(loopDelta({ iterations: s.iterations.slice(1) })).toBeNull()
    const noGeo = s.iterations.map((it): Iteration => (iterKind(it) === 'baseline' ? { ...it, geometry: null } : it))
    expect(loopDelta({ iterations: noGeo })).toBeNull()
  })
})

describe('geometry choices for past flashes (I2)', () => {
  it('offers every measured row, baseline included, and defaults to this revision', () => {
    const s = snap()
    const cs = geometryChoices(s, s.accepted_revision!)
    expect(cs.map((c) => c.label)).toEqual(['Before the loop', 'Round 1', 'Round 2', 'Accepted graph'])
    // the anchor rescaled the accepted graph, so only the accepted row is this revision
    expect(cs.map((c) => c.current)).toEqual([false, false, false, true])
    expect(pickGeometry(cs, null)!.label).toBe('Accepted graph')
    expect(pickGeometry(cs, '0')!.geometry.illegal_crossings).toHaveLength(5)
    expect(pickGeometry(cs, 'gone')!.label).toBe('Accepted graph')
    expect(pickGeometry(geometryChoices(s, null), null)).toBeNull()
  })
  it('flags rows measured under another alignment: the anchor moved the frame', () => {
    const s = snap()
    // rounds were scored unanchored; only the accepted row used the anchored alignment
    expect(geometryChoices(s, null).map((c) => c.otherFrame)).toEqual([true, true, true, false])
    const unanchored = { ...s, alignment: { ...s.alignment!, hash: 'a-fixture' } }  // the unanchored fit's hash
    expect(geometryChoices(unanchored, null).map((c) => c.otherFrame)).toEqual([false, false, false, true])
  })
})
