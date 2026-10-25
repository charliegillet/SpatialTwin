import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/snapshot.json'
import {
  ApiShapeError, acceptBlockers, approvable, currentRevision, currentScenarioHash,
  draftRevision, isCurrent, parseReport, parseSnapshot,
} from './api'

const raw = () => JSON.parse(JSON.stringify(fixture)) as Record<string, any>

describe('parseSnapshot', () => {
  it('accepts the fixture session', () => {
    const s = parseSnapshot(raw())
    expect(s.id).toBe('fx-session')
    expect(s.ghost_path.length).toBeGreaterThan(10)
    expect(s.iterations).toHaveLength(2)
  })
  it('rejects a snapshot whose current_check.run_id !== current_run.run_id', () => {
    const r = raw()
    r.current_check.run_id = 'r-000000000000'
    expect(() => parseSnapshot(r)).toThrow(ApiShapeError)
  })
  it('rejects malformed shapes', () => {
    const r = raw(); r.ghost_path = 'nope'
    expect(() => parseSnapshot(r)).toThrow(ApiShapeError)
    const r2 = raw(); r2.current_run.zone_occupancy = [{ Z1: 'x' }]
    expect(() => parseSnapshot(r2)).toThrow(ApiShapeError)
    const r3 = raw(); r3.jobs.sfm.status = 'exploded'
    expect(() => parseSnapshot(r3)).toThrow(ApiShapeError)
    expect(() => parseSnapshot(null)).toThrow(ApiShapeError)
  })
  it('falls back to the run for revision and scenario hash when not sent', () => {
    const r = raw()
    delete r.graph_revision; delete r.scenario_hash; delete r.draft_revision
    const s = parseSnapshot(r)
    expect(currentRevision(s)).toBe(fixture.current_run.graph_revision)
    expect(currentScenarioHash(s)).toBe(fixture.current_run.scenario_hash)
    expect(draftRevision(s)).toBe(fixture.iterations[1].graph_revision)
  })
})

describe('isCurrent', () => {
  it('is true for results on the current revision and scenario', () => {
    const s = parseSnapshot(raw())
    expect(isCurrent(s.investigations[0], s)).toBe(true)
    expect(isCurrent(s.current_run!, s)).toBe(true)
  })
  it('is false after the revision changes', () => {
    const before = parseSnapshot(raw())
    const r = raw(); r.graph_revision = 'g-ffffffffffffffff'
    const after = parseSnapshot(r)
    expect(isCurrent(before.investigations[0], after)).toBe(false)
  })
  it('is false after a hazard change moves the scenario hash', () => {
    const r = raw(); r.scenario_hash = 's-ffffffffffff'
    const s = parseSnapshot(r)
    expect(isCurrent(s.investigations[0], s)).toBe(false)
  })
})

describe('gating', () => {
  it('blocks Accept while the draft has error findings', () => {
    const ok = parseSnapshot(raw())
    expect(acceptBlockers(ok)).toEqual([])
    const r = raw()
    r.findings = [{ code: 'NO_EXIT', severity: 'error', element_id: null, message: 'no exit' }]
    expect(acceptBlockers(parseSnapshot(r)).length).toBeGreaterThan(0)
    const w = raw()
    w.findings = [{ code: 'UNREACHABLE_ZONE', severity: 'warning', element_id: 'Z4', message: 'x' }]
    expect(acceptBlockers(parseSnapshot(w))).toEqual([])
  })
  it('blocks Accept while a job is running', () => {
    const r = raw(); r.jobs.refine.status = 'running'
    expect(acceptBlockers(parseSnapshot(r)).length).toBeGreaterThan(0)
  })
  it('enables Approve only for a checked best on the current state', () => {
    const s = parseSnapshot(raw())
    expect(approvable(s.investigations[0], s)?.intervention_id).toBe('OPEN:D5')
    const r = raw(); r.investigations[0].best.check_ok = false
    const s2 = parseSnapshot(r)
    expect(approvable(s2.investigations[0], s2)).toBeNull()
    const r3 = raw(); r3.investigations[0].best = null
    const s3 = parseSnapshot(r3)
    expect(approvable(s3.investigations[0], s3)).toBeNull()
    const r4 = raw(); r4.scenario_hash = 's-ffffffffffff'
    const s4 = parseSnapshot(r4)
    expect(approvable(s4.investigations[0], s4)).toBeNull()
  })
})

describe('parseReport', () => {
  it('validates a report and rejects a bad verdict', () => {
    const rep = {
      session_id: 'fx', graph_revision: 'g-1', scenario_hash: 's-1', run_id: 'r-1', verdict: 'verified_within_model',
      requirements: [{ id: 'R1', statement: 'population conserved', method: 'measured', status: 'pass', value: '130', evidence: 'run' }],
      rules: [{ rule_id: 'ADA-404.2.3', element_id: 'D4', statement: 'door clear width', threshold_m: 0.914, measured: null, status: 'cannot_measure', reason: 'doorway depth unknown', citation: '2010 ADA Standards §404.2.3' }],
      hand_checks: ['Check threshold height at D3'], declared_parameters: { dt_s: 2 }, provenance: ['Argon proposed'],
    }
    expect(parseReport(rep).requirements).toHaveLength(1)
    expect(() => parseReport({ ...rep, verdict: 'great' })).toThrow(ApiShapeError)
  })
})
