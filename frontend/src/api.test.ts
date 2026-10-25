import { describe, expect, it } from 'vitest'
import fixture from './__fixtures__/snapshot.json'
import {
  ApiShapeError, acceptBlockers, approvable, checkedRun, currentRevision, currentRun, currentScenarioHash,
  draftRevision, investigationsInProgress, isCurrent, localDisagreement, parseReport, parseSnapshot,
  readyInvestigations, snapshotIsStale,
} from './api'
import type { Snapshot } from './apiTypes'

// The fixture is generated from the real API by tests/test_frontend_fixture.py.
const raw = () => JSON.parse(JSON.stringify(fixture)) as Record<string, any>
const readyIndex = (r: Record<string, any>) =>
  r.investigations.findIndex((i: any) => i.investigation_id === r.ready_investigation_id)
const ready = (s: Snapshot) => s.investigations.find((i) => i.investigation_id === s.ready_investigation_id)!

describe('parseSnapshot', () => {
  it('accepts the real-API fixture session', () => {
    const s = parseSnapshot(raw())
    expect(s.id).toBe(fixture.id)
    expect(s.ghost_path.length).toBeGreaterThan(10)
    expect(s.iterations).toHaveLength(2)
    expect(s.iterations[0].renders.every((r) => r.url?.startsWith(`/api/sessions/${s.id}/renders/`))).toBe(true)
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
    const r2b = raw(); r2b.current_run.reached_by_step[3] = 1.5
    expect(() => parseSnapshot(r2b)).toThrow(ApiShapeError)
    const r3 = raw(); r3.jobs.sfm.status = 'exploded'
    expect(() => parseSnapshot(r3)).toThrow(ApiShapeError)
    expect(() => parseSnapshot(null)).toThrow(ApiShapeError)
  })
  it('fails closed without revision fields: nothing renders as current', () => {
    const r = raw()
    delete r.graph_revision; delete r.scenario_hash; delete r.draft_revision; delete r.accepted_revision
    const s = parseSnapshot(r)
    expect(currentRevision(s)).toBeNull()
    expect(currentScenarioHash(s)).toBeNull()
    expect(draftRevision(s)).toBeNull()
    expect(currentRun(s)).toBeNull()
    expect(checkedRun(s)).toBeNull()
    expect(readyInvestigations(s)).toEqual([])
    expect(s.investigations.some((i) => isCurrent(i, s))).toBe(false)
    expect(s.investigations.map((i) => approvable(i, s))).toEqual(s.investigations.map(() => null))
    expect(acceptBlockers(s)).toContain('Revision unknown; reload')
  })
  it('fails closed with only the scenario hash missing', () => {
    const r = raw(); delete r.scenario_hash
    const s = parseSnapshot(r)
    expect(currentRun(s)).toBeNull()
    expect(readyInvestigations(s)).toEqual([])
  })
})

describe('isCurrent', () => {
  it('is true for results on the current revision and scenario', () => {
    const s = parseSnapshot(raw())
    expect(isCurrent(ready(s), s)).toBe(true)
    expect(isCurrent(s.current_run!, s)).toBe(true)
    expect(readyInvestigations(s).map((i) => i.investigation_id)).toEqual([s.ready_investigation_id])
  })
  it('is false after the revision changes', () => {
    const before = parseSnapshot(raw())
    const r = raw(); r.graph_revision = 'g-ffffffffffffffff'
    const after = parseSnapshot(r)
    expect(isCurrent(ready(before), after)).toBe(false)
  })
  it('is false after a hazard change moves the scenario hash', () => {
    const r = raw(); r.scenario_hash = 's-ffffffffffff'
    const s = parseSnapshot(r)
    expect(s.investigations.some((i) => isCurrent(i, s))).toBe(false)
  })
})

describe('gating', () => {
  it('blocks Accept while the draft has error findings, including 422 ones', () => {
    const ok = parseSnapshot(raw())
    expect(acceptBlockers(ok)).toEqual([])
    const r = raw()
    r.findings = [{ code: 'NO_EXIT', severity: 'error', element_id: null, message: 'no exit' }]
    expect(acceptBlockers(parseSnapshot(r)).length).toBeGreaterThan(0)
    const w = raw()
    w.findings = [{ code: 'UNREACHABLE_ZONE', severity: 'warning', element_id: 'Z4', message: 'x' }]
    expect(acceptBlockers(parseSnapshot(w))).toEqual([])
    expect(acceptBlockers(ok, [{ code: 'ZONE_OVERLAP', severity: 'error', element_id: 'Z1', message: 'x' }]).length).toBe(1)
  })
  it('blocks Accept while a job is running', () => {
    const r = raw(); r.jobs.refine.status = 'running'
    expect(acceptBlockers(parseSnapshot(r))).toContain('Waiting for refine')
  })
  it('enables Approve only for a completed, checked best on the current state', () => {
    const s = parseSnapshot(raw())
    expect(approvable(ready(s), s)?.intervention_id).toBe('OPEN:D5')
    const variants: ((r: Record<string, any>, i: number) => void)[] = [
      (r, i) => { r.investigations[i].best.check_ok = false },
      (r, i) => { r.investigations[i].best = null },
      (r, i) => { r.investigations[i].status = 'incomplete' },
      (r) => { r.scenario_hash = 's-ffffffffffff' },
      (r) => { r.allowed_interventions = [] },
      (r, i) => { r.approvals = [{ intervention_id: 'OPEN:D5', investigation_id: r.investigations[i].investigation_id, graph_revision: r.graph_revision, scenario_hash: r.scenario_hash, run_id: 'r-1', note_path: 'n', approved_at: 't' }] },
    ]
    for (const mutate of variants) {
      const r = raw(); const i = readyIndex(r); mutate(r, i)
      const s2 = parseSnapshot(r)
      expect(approvable(s2.investigations[i], s2)).toBeNull()
    }
  })
})

describe('investigations', () => {
  it('flags a claimed-vs-checker disagreement locally', () => {
    const s = parseSnapshot(raw())
    const inv = ready(s)
    expect(localDisagreement(inv)).toMatch(/claimed \d+ for OPEN:D5; checker computed \d+/)
    const same = { ...inv, recommendation: { ...inv.recommendation!, claimed_reached_exit: inv.best!.reached_exit } }
    expect(localDisagreement(same)).toBeNull()
  })
  it('finds in-progress investigation jobs for the current state only', () => {
    const r = raw()
    r.jobs['investigate:x'] = { kind: 'investigate', status: 'running', error: null, started_at: null, finished_at: null, meta: { graph_revision: r.graph_revision, scenario_hash: r.scenario_hash } }
    r.jobs['investigate:y'] = { kind: 'investigate', status: 'running', error: null, started_at: null, finished_at: null, meta: { graph_revision: r.graph_revision, scenario_hash: 's-other' } }
    expect(investigationsInProgress(parseSnapshot(r))).toEqual(['investigate:x'])
  })
})

describe('snapshotIsStale', () => {
  it('is stale until the first load, after a failed reload, and after an unreloaded mutation', () => {
    expect(snapshotIsStale({ okAt: 0, errorAt: 0, mutatedAt: 0 })).toBe(true)
    expect(snapshotIsStale({ okAt: 1, errorAt: 0, mutatedAt: 0 })).toBe(false)
    expect(snapshotIsStale({ okAt: 1, errorAt: 2, mutatedAt: 0 })).toBe(true)
    expect(snapshotIsStale({ okAt: 2, errorAt: 3, mutatedAt: 1 })).toBe(true) // mutation, then the reload failed
    expect(snapshotIsStale({ okAt: 3, errorAt: 0, mutatedAt: 2 })).toBe(false)
    expect(snapshotIsStale({ okAt: 1, errorAt: 0, mutatedAt: 2 })).toBe(true)
    expect(snapshotIsStale({ okAt: 4, errorAt: 3, mutatedAt: 2 })).toBe(false) // a later reload succeeded
  })
})

describe('parseReport', () => {
  it('validates a report and rejects a bad verdict', () => {
    const rep = {
      session_id: 'fx', graph_revision: 'g-1', scenario_hash: 's-1', run_id: 'r-1', verdict: 'verified_within_model',
      requirements: [{ id: 'R1', statement: 'population conserved', method: 'measured', status: 'pass', value: '130', evidence: 'run' }],
      rules: [{ rule_id: 'ADA-404.2.3', element_id: 'D4', statement: 'door clear width', threshold_m: 0.914, measured: null, status: 'cannot_measure', reason: 'doorway depth unknown', citation: '2010 ADA Standards §404.2.3' }],
      hand_checks: ['Check threshold height at D3'], declared_parameters: { dt_s: 2 }, provenance: ['Argon proposed'], security_note: '',
    }
    expect(parseReport(rep).requirements).toHaveLength(1)
    expect(() => parseReport({ ...rep, verdict: 'great' })).toThrow(ApiShapeError)
  })
})
