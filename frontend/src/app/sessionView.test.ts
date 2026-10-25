import { describe, expect, it } from 'vitest'
import fixture from '../__fixtures__/snapshot.json'
import { parseSnapshot } from '../api'
import type { RuleResult, Snapshot } from '../apiTypes'
import {
  DECLARED_ROUTING, adaResultText, agentFlags, anchorStatus, approvedOpenings, heroState, parseCreatedAt, pendingAnchor,
  previewPlot, savedRunBadge, sessionStarted, withOpenings,
} from './sessionView'

const raw = () => JSON.parse(JSON.stringify(fixture)) as Record<string, any>
const snap = (edit?: (r: Record<string, any>) => void): Snapshot => {
  const r = raw()
  edit?.(r)
  return parseSnapshot(r)
}
const hhmm = (iso: string) => {
  const d = new Date(iso)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

describe('validators stay tolerant of the D1-D6 fields', () => {
  it('accepts the fixture with and without the new optional fields', () => {
    expect(snap().sfm_preview?.points.length).toBeGreaterThan(3)
    const old = snap((r) => {
      delete r.sfm_preview; delete r.pending_anchor
      for (const it of r.iterations) { delete it.kind; delete it.critique }
      for (const i of r.investigations) delete i.recommendation?.copy_flags
    })
    expect(old.iterations[0].kind).toBeUndefined()
  })
  it('still rejects a malformed new field', () => {
    expect(() => snap((r) => { r.iterations[0].kind = 'warmup' })).toThrow()
    expect(() => snap((r) => { r.sfm_preview = { points: [{ t_s: 0, u: 'x', v: 0 }], note: '' } })).toThrow()
    expect(() => snap((r) => { r.pending_anchor = { door_id: 'D1' } })).toThrow()
  })
})

describe('session start and the saved-run badge (I8)', () => {
  const at = '2026-10-25T18:39:00+0000'
  const t = Date.parse('2026-10-25T18:39:00Z')
  it('parses the server timestamp (+0000 offsets included)', () => {
    expect(parseCreatedAt(at)).toBe(t)
    expect(parseCreatedAt('2026-10-25T18:39:00+00:00')).toBe(t)
    expect(parseCreatedAt('not a time')).toBeNull()
  })
  it('shows the start time', () => {
    expect(sessionStarted(at)).toBe(`Session started ${hhmm('2026-10-25T18:39:00Z')}`)
    expect(sessionStarted('garbage')).toBe('Session start time unknown')
  })
  it('badges a run started more than 30 min ago', () => {
    expect(savedRunBadge(at, t + 30 * 60_000)).toBeNull()
    expect(savedRunBadge(at, t + 31 * 60_000)).toBe(`saved run · started ${hhmm('2026-10-25T18:39:00Z')}`)
    expect(savedRunBadge(at, t + 60_000)).toBeNull()
    expect(savedRunBadge('garbage', t + 99 * 60_000)).toBeNull()
  })
})

describe('server-owned anchor (C2, D2)', () => {
  it('reads pending_anchor, falling back to anchor on old data', () => {
    expect(pendingAnchor(snap())).toMatchObject({ door_id: 'D1', measured_width_m: 1.75 })
    expect(pendingAnchor(snap((r) => { r.pending_anchor = null }))).toBeNull()
    expect(pendingAnchor(snap((r) => { r.pending_anchor = { door_id: 'D4', measured_width_m: 0.91 } }))?.door_id).toBe('D4')
    expect(pendingAnchor(snap((r) => { delete r.pending_anchor; r.anchor = { door_id: 'D1', measured_width_m: 1.7 } }))?.door_id).toBe('D1')
  })
  it('is pending before accept', () => {
    const s = snap((r) => { r.pending_anchor = { door_id: 'D4', measured_width_m: 0.91 }; r.accepted_graph = null })
    expect(anchorStatus(s)).toEqual({ door_id: 'D4', width_m: 0.91, state: 'pending', text: 'D4 = 0.910 m tape-measured · applied at Accept' })
  })
  it('says applied (tape-measured) only when the accepted door basis is anchor_measured', () => {
    const notApplied = snap((r) => { r.pending_anchor = { door_id: 'D4', measured_width_m: 0.91 } })
    expect(anchorStatus(notApplied)!.state).toBe('pending')
    expect(anchorStatus(notApplied)!.text).not.toMatch(/applied \(tape-measured\)/)
    const applied = snap((r) => {
      r.pending_anchor = { door_id: 'D4', measured_width_m: 0.91 }
      const d = r.accepted_graph.doors.find((x: any) => x.id === 'D4')
      d.clear_width = { low_m: 0.91, high_m: 0.91, basis: 'anchor_measured' }
    })
    expect(anchorStatus(applied)).toMatchObject({ state: 'applied', text: 'D4 = 0.910 m · applied (tape-measured)' })
  })
  it('reports an anchor the accepted graph did not take as not applied', () => {
    const s = snap((r) => { r.pending_anchor = null; r.accepted_graph.anchor = { door_id: 'D4', measured_width_m: 0.91 } })
    expect(anchorStatus(s)).toMatchObject({ state: 'not_applied' })
    expect(anchorStatus(s)!.text).toMatch(/not applied/)
  })
  it('is applied in the generated session: the tape-measured door took the accepted graph', () => {
    expect(anchorStatus(snap())).toMatchObject({ door_id: 'D1', state: 'applied' })
  })
  it('is null without any anchor', () => {
    expect(anchorStatus(snap((r) => { r.pending_anchor = null; r.accepted_graph.anchor = null }))).toBeNull()
  })
})

describe('hero figure (M9)', () => {
  const s = snap()
  const run = s.current_run!
  it('shows the figure for a checked run', () => {
    expect(heroState(s, run, false)).toMatchObject({ figure: '73 of 130 reach a modeled exit in 120 s · checked', tag: 'checker verified', checked: true })
  })
  it('withholds the figure when the check failed', () => {
    const f = snap((r) => { r.current_check.ok = false; r.current_check.violations = ['conservation'] })
    expect(heroState(f, f.current_run!, false)).toEqual({ figure: null, tag: 'check failed: figure withheld', checked: false })
  })
  it('withholds it without a check, or on a stale copy', () => {
    const n = snap((r) => { r.current_check = null })
    expect(heroState(n, n.current_run!, false).figure).toBeNull()
    expect(heroState(n, n.current_run!, false).tag).toBe('not checked: figure withheld')
    expect(heroState(s, run, true)).toMatchObject({ figure: null, tag: 'reload needed: figure withheld' })
  })
})

describe('approved interventions on the twin (M4)', () => {
  const approved = snap((r) => {
    r.scenario.interventions = ['OPEN:D5']
    r.approvals = [{ intervention_id: 'OPEN:D5', investigation_id: 'inv-x', graph_revision: r.accepted_revision, scenario_hash: r.scenario_hash, run_id: r.current_run.run_id, note_path: 'n', approved_at: '2026-10-25T18:45:00+0000' }]
  })
  it('lists the scenario openings and whether you approved them', () => {
    expect(approvedOpenings(approved)).toEqual([{ intervention_id: 'OPEN:D5', door_id: 'D5', approved: true }])
    expect(approvedOpenings(snap())).toEqual([])
  })
  it('draws those doors open without touching the accepted graph', () => {
    const g = approved.accepted_graph!
    const shown = withOpenings(g, approvedOpenings(approved))
    expect(shown.doors.find((d) => d.id === 'D5')!.state).toBe('open')
    expect(g.doors.find((d) => d.id === 'D5')!.state).toBe('locked')
    expect(withOpenings(g, [])).toBe(g)
  })
})

describe('agent words (D5)', () => {
  it('passes the server flags through, deduplicated', () => {
    expect(agentFlags({ copy_flags: ['safe', 'Safe', 'evacuated'] })).toEqual(['safe', 'evacuated'])
    expect(agentFlags({})).toEqual([])
    expect(agentFlags(null)).toEqual([])
  })
})

describe('declared routing (D6)', () => {
  it('is the exact declared parameter', () => {
    expect(DECLARED_ROUTING).toBe('system-optimal (earliest arrival); real crowds tend to use the way they came in')
  })
})

describe('SfM preview inset (D4)', () => {
  it('plots u right, v up, inside a padded viewBox', () => {
    const p = previewPlot({ points: [{ t_s: 0, u: 0, v: 0 }, { t_s: 1, u: 1, v: 2 }, { t_s: 2, u: -1, v: 4 }], note: 'unaligned, SfM units' })!
    expect(p.points).toBe('0,0 1,-2 -1,-4')
    const [x, y, w, h] = p.viewBox.split(' ').map(Number)
    expect(x).toBeLessThan(-1); expect(y).toBeLessThan(-4)
    expect(x + w).toBeGreaterThan(1); expect(y + h).toBeGreaterThan(0)
    expect(p.start).toEqual([0, 0]); expect(p.end).toEqual([-1, -4])
  })
  it('is null with fewer than 2 points', () => {
    expect(previewPlot(null)).toBeNull()
    expect(previewPlot({ points: [{ t_s: 0, u: 0, v: 0 }], note: '' })).toBeNull()
  })
})

describe('ADA wording (honest labels)', () => {
  const rule = (basis: string, status: RuleResult['status']): RuleResult => ({
    rule_id: 'ADA-404.2.3', element_id: 'D4', statement: '', threshold_m: 0.815,
    measured: { low_m: 0.9, high_m: 1.0, basis }, status, reason: null, citation: '',
  })
  it('says "measured" only for a tape-measured width', () => {
    expect(adaResultText(rule('anchor_measured', 'pass'))).toBe('meets ADA §404.2.3 within measured range')
    expect(adaResultText(rule('estimated', 'pass'))).toBe("meets ADA §404.2.3 within the model's estimated range (model-reported)")
    expect(adaResultText(rule('estimated', 'fail'))).toBe("does not meet ADA §404.2.3 within the model's estimated range (model-reported)")
    expect(adaResultText({ ...rule('estimated', 'cannot_measure'), reason: 'no width' })).toBe('cannot measure: no width')
  })
})
