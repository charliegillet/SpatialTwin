// Session API client. Every response is shape-checked before it can reach the UI,
// and results that do not belong to the current graph revision / scenario are dropped.
// Currency fails closed: without the snapshot's revision fields nothing is current.
import type {
  FlowRun, Finding, Hazard, Investigation, InterventionResult, Report, Snapshot, VideoMode,
} from './apiTypes'
import type { VenueGraph } from './types'
import {
  ApiShapeError, any, arr, bool, int, lit, nullable, num, obj, opt, rec, str, tuple, validate, type Check,
} from './shape'

export { ApiShapeError }

// ---------- shapes (backend/walktwin/api.py SessionSnapshot) ----------
const evidence = obj({ start_s: num, end_s: num, note: str })
const measure = obj({ low_m: num, high_m: num, basis: str })
const anchor = obj({ door_id: str, measured_width_m: num })
const xy = tuple(num, num)
const xyz = tuple(num, num, num)
export const graphShape: Check = obj({
  schema_version: str, video_sha256: str, anchor: nullable(anchor),
  zones: arr(obj({ id: str, name: str, rect: tuple(num, num, num, num), occupants: int, furniture_seen: bool, evidence: arr(evidence) })),
  doors: arr(obj({ id: str, a: str, b: str, kind: str, state: str, clear_width: measure, position: xy, evidence: arr(evidence) })),
  keyframes: arr(obj({ t_s: num, zone_id: str, x: num, y: num, heading_deg: num })),
})
const finding = obj({ code: str, severity: lit('error', 'warning'), element_id: nullable(str), message: str })
const receipt = obj({ interaction_id: str, provider_model: nullable(str), status: str, usage: any, elapsed_ms: num, processing_calls: int })
const params = obj({ dt_s: num, horizon_s: num, specific_flow_p_per_m_s: num, boundary_layer_m: num, walk_speed_m_s: num })
const flowRun = obj({
  run_id: str, graph_revision: str, scenario_hash: str, params, total: int, reached_exit: int,
  remaining_by_zone: rec(int), in_transit_end: int, door_flows: rec(arr(int)),
  zone_occupancy: arr(rec(int)), transit_by_step: arr(int), reached_by_step: arr(int),
})
const geometry = obj({
  alignment_hash: str,
  illegal_crossings: arr(obj({ t_s: num, x: num, y: num, edge: str })),
  wall_support: num, unexplained_points: num, edge_chamfer_px: nullable(num), edge_within_5px: nullable(num), heldout_t_s: arr(num),
})
const iteration = obj({
  index: int, graph_revision: str, discrepancy_count: int, applied: arr(int), rejected: arr(tuple(int, str)),
  findings: arr(finding), geometry: nullable(geometry),
  renders: arr(obj({ t_s: nullable(num), path: str, kind: lit('perspective', 'top'), url: opt(str) })),
  receipt: nullable(receipt), stop_reason: nullable(str), rejected_geometry: opt(nullable(geometry)),
  kind: opt(lit('baseline', 'round', 'accepted')),
  critique: opt(nullable(obj({
    status: str,
    discrepancies: arr(obj({ t_s: num, element_id: nullable(str), description: str })),
    ops: arr(obj({ op: str, cite_t_s: num, reason: str, id: opt(str), door: opt(obj({ id: str })), zone: opt(obj({ id: str })) })),
    interaction_id: nullable(str), receipt: nullable(receipt), error: opt(nullable(str)),
    dropped_ops: opt(arr(tuple(int, str))),
  }))),
})
const result = obj({
  intervention_id: str, run_id: str, reached_exit: int, total: int, delta_vs_current: int, check_ok: bool, limiting_doors: arr(str),
})
const investigation = obj({
  investigation_id: str, graph_revision: str, scenario_hash: str,
  status: lit('completed', 'failed', 'timeout', 'incomplete', 'cancelled'),
  interaction_id: nullable(str), environment_id: nullable(str),
  ledger: arr(obj({ call_id: str, kind: lit('client_function', 'sandbox_step'), name: str, args: rec(any), result: nullable(rec(any)), executed_at: str })),
  sandbox_runs: int, results: arr(result),
  recommendation: nullable(obj({
    intervention_id: nullable(str), claimed_reached_exit: nullable(int), rationale: str, caveats: arr(str),
    sweep_summary: opt(arr(obj({ intervention_id: str, claimed_reached_exit: int, label: lit('sandbox, unverified') }))),
    copy_flags: opt(arr(str)),
  })),
  best: nullable(result), disagreement: nullable(str), hook_denials: int, receipt: nullable(receipt), error: opt(nullable(str)),
  network_mode: opt(nullable(str)),
})
const snapshotShape = obj({
  id: str, created_at: str,
  video: obj({ sha256: str, duration_s: num, width: int, height: int, url: str }),
  anchor: nullable(anchor), anchor_hint: nullable(str), anchor_width_m: nullable(num),
  pending_anchor: opt(nullable(anchor)),
  jobs: rec(obj({
    kind: str, status: lit('queued', 'running', 'done', 'failed'), error: nullable(str),
    started_at: nullable(str), finished_at: nullable(str), meta: rec(any),
  })),
  sfm: nullable(obj({
    status: str, registered_fraction: nullable(num), elapsed_ms: nullable(num), error: nullable(str),
    frame_count: int, point_count: int,
  })),
  alignment: nullable(obj({
    scale: num, yaw_rad: num, tx: num, ty: num, floor_normal: xyz, floor_offset: num, residual_m: num, eye_height_m: num, hash: str,
  })),
  alignment_error: nullable(str), geometry_unavailable_reason: nullable(str),
  ghost_path: arr(obj({ t_s: num, x: num, y: num })),
  sfm_preview: opt(nullable(obj({ points: arr(obj({ t_s: num, u: num, v: num })), note: str }))),
  extraction: nullable(obj({
    status: lit('completed', 'failed', 'timeout', 'invalid'), graph: nullable(graphShape), findings: arr(finding),
    receipt: nullable(receipt), mode: lit('static', 'static_hifps', 'agentic'), agentic_observed: nullable(bool),
    video_uri: nullable(str), error: nullable(str), interaction_id: opt(nullable(str)),
  })),
  draft_graph: nullable(graphShape), draft_revision: opt(nullable(str)), findings: arr(finding),
  accepted_graph: nullable(graphShape), accepted_revision: opt(nullable(str)), graph_revision: opt(nullable(str)),
  scenario: obj({ hazards: arr(obj({ door_id: str, kind: lit('fire'), from_s: num })), interventions: arr(str) }),
  scenario_hash: opt(nullable(str)),
  current_run: nullable(flowRun),
  current_check: nullable(obj({ ok: bool, run_id: str, violations: arr(str) })),
  iterations: arr(iteration),
  investigations: arr(investigation),
  ready_investigation_id: nullable(str),
  allowed_interventions: arr(str),
  approvals: arr(obj({ intervention_id: str, investigation_id: str, graph_revision: str, scenario_hash: str, run_id: str, note_path: str, approved_at: str })),
})
const reportShape = obj({
  session_id: str, graph_revision: str, scenario_hash: str, run_id: str,
  verdict: lit('verified_within_model', 'failed', 'incomplete'),
  requirements: arr(obj({
    id: str, statement: str, method: lit('measured', 'checker', 'model_reported', 'outside_model'),
    status: lit('pass', 'fail', 'cannot_measure', 'not_run'), value: nullable(str), evidence: str,
  })),
  rules: arr(obj({
    rule_id: str, element_id: str, statement: str, threshold_m: num, measured: nullable(measure),
    status: lit('pass', 'fail', 'cannot_measure'), reason: nullable(str), citation: str,
  })),
  hand_checks: arr(str), declared_parameters: rec(any), provenance: arr(str), security_note: opt(nullable(str)),
})

export function parseSnapshot(raw: unknown): Snapshot {
  const s = validate<Snapshot>(snapshotShape, raw)
  if (s.current_check && s.current_run && s.current_check.run_id !== s.current_run.run_id) {
    throw new ApiShapeError('current_check.run_id', `run_id ${s.current_run.run_id} (check belongs to another run)`)
  }
  if (s.current_check && !s.current_run) throw new ApiShapeError('current_check', 'null without a run')
  return s
}
export const parseReport = (raw: unknown): Report => validate<Report>(reportShape, raw)

// ---------- derived state (fail closed: no guessing from other fields) ----------
export const currentRevision = (s: Snapshot): string | null => s.graph_revision ?? null
export const currentScenarioHash = (s: Snapshot): string | null => s.scenario_hash ?? null
export const draftRevision = (s: Snapshot): string | null => s.draft_revision ?? null

/** True only when the result was computed for the current graph revision (and scenario, if it carries one). */
export function isCurrent(r: { graph_revision: string; scenario_hash?: string }, s: Snapshot): boolean {
  const rev = currentRevision(s)
  if (!rev || r.graph_revision !== rev) return false
  if (r.scenario_hash === undefined) return true
  const sh = currentScenarioHash(s)
  return !!sh && r.scenario_hash === sh
}

export const runningJobs = (s: Snapshot) =>
  Object.entries(s.jobs).filter(([, j]) => j.status === 'queued' || j.status === 'running').map(([k]) => k)
export const currentRun = (s: Snapshot): FlowRun | null => (s.current_run && isCurrent(s.current_run, s) ? s.current_run : null)
/** The check is shown as "checked" only for the current run, when it passed. */
export const checkedRun = (s: Snapshot): FlowRun | null => {
  const run = currentRun(s)
  return run && s.current_check?.ok && s.current_check.run_id === run.run_id ? run : null
}

/** One finding per (code, element_id); the first occurrence wins. */
export function dedupeFindings(fs: Finding[]): Finding[] {
  const seen = new Set<string>()
  return fs.filter((f) => {
    const k = `${f.code}\u0000${f.element_id ?? ''}`
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

export function acceptBlockers(s: Snapshot, extraErrors: Finding[] = []): string[] {
  const out: string[] = []
  if (!s.draft_graph) out.push('No draft twin yet')
  else if (!draftRevision(s)) out.push('Revision unknown; reload')
  const errors = dedupeFindings([...s.findings, ...extraErrors]).filter((f) => f.severity === 'error').length
  if (errors) out.push(`${errors} error finding${errors > 1 ? 's' : ''} to fix`)
  for (const j of runningJobs(s)) out.push(`Waiting for ${j.split(':')[0]}`)
  return out
}

/** Investigations tagged with the current revision and scenario (any status). */
export const readyInvestigations = (s: Snapshot): Investigation[] => s.investigations.filter((i) => isCurrent(i, s))
/** Investigation jobs still running for the current revision and scenario. */
export function investigationsInProgress(s: Snapshot): string[] {
  const rev = currentRevision(s), sh = currentScenarioHash(s)
  if (!rev || !sh) return []
  return Object.entries(s.jobs)
    .filter(([, j]) => j.kind === 'investigate' && (j.status === 'queued' || j.status === 'running')
      && j.meta.graph_revision === rev && j.meta.scenario_hash === sh)
    .map(([k]) => k)
}

/** The checked `best` that may be approved, or null. */
export function approvable(inv: Investigation, s: Snapshot): InterventionResult | null {
  const b = inv.best
  if (inv.status !== 'completed' || !b || !b.check_ok || b.delta_vs_current <= 0 || !isCurrent(inv, s)) return null
  if (!inv.results.some((r) => r.intervention_id === b.intervention_id && r.check_ok)) return null
  if (!s.allowed_interventions.includes(b.intervention_id)) return null
  if (s.approvals.some((a) => a.investigation_id === inv.investigation_id && a.intervention_id === b.intervention_id)) return null
  return b
}

/** Claimed vs checker figure for the recommended change, compared locally. */
export function localDisagreement(inv: Investigation): string | null {
  const rec = inv.recommendation
  if (!rec?.intervention_id || rec.claimed_reached_exit == null) return null
  const r = inv.results.find((x) => x.intervention_id === rec.intervention_id)
  if (!r) return `Agent claimed ${rec.claimed_reached_exit} for ${rec.intervention_id}; the checker never evaluated it`
  return r.reached_exit !== rec.claimed_reached_exit
    ? `Agent claimed ${rec.claimed_reached_exit} for ${rec.intervention_id}; checker computed ${r.reached_exit}` : null
}

/**
 * Sequence stamps from useSession: okAt = last successful reload, errorAt = last failed
 * reload, mutatedAt = last mutation that returned (either way). The snapshot on screen is
 * stale when anything happened after the last successful reload.
 */
export interface Freshness { okAt: number; errorAt: number; mutatedAt: number }
export const snapshotIsStale = (f: Freshness): boolean => f.okAt === 0 || f.errorAt > f.okAt || f.mutatedAt > f.okAt

/**
 * Whether to show the stale banner (gating uses snapshotIsStale immediately): only once a
 * reload has actually failed, or the reload after mutation `slowFor` has taken over 2 s.
 */
export const staleBannerVisible = (f: Freshness, slowFor: number): boolean =>
  f.okAt > 0 && (f.errorAt > f.okAt || (f.mutatedAt > f.okAt && slowFor === f.mutatedAt))

// ---------- HTTP ----------
export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    const code = typeof (body as { error?: unknown } | null)?.error === 'string' ? (body as { error: string }).error : null
    super(status === 409 && code === 'job_running' ? 'That job is already running.'
      : status === 409 && code === 'sfm_running' ? 'Your walk is still being reconstructed (SfM). Refine once it finishes.'
      : status === 422 && code === 'anchor_server_owned' ? 'The anchor is set with "Use as anchor", not by editing the graph.'
      : status === 409 ? `Stale ${code === 'stale_investigation' ? 'investigation' : 'revision'}: something changed first. Reloaded the latest state.`
        : `Request failed (${status}${code ? `: ${code}` : ''})`)
    this.status = status
    this.body = body
  }
  get findings(): Finding[] {
    const b = this.body as { findings?: unknown } | null
    try { return validate<Finding[]>(arr(finding), b?.findings) } catch { return [] }
  }
}

async function call(path: string, init?: RequestInit, as: 'json' | 'text' = 'json'): Promise<unknown> {
  const res = await fetch(path, init)
  const text = await res.text()
  let body: unknown = text
  if (as === 'json' || !res.ok) {
    try { body = text ? JSON.parse(text) : null } catch { body = text }
  }
  if (!res.ok) throw new ApiError(res.status, body)
  return body
}
const post = (path: string, body: unknown, method = 'POST') =>
  call(path, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })

const base = (id: string) => `/api/sessions/${encodeURIComponent(id)}`
export const videoUrl = (id: string) => `${base(id)}/video`
export const frameUrl = (id: string, t: number) => `${base(id)}/frame?t=${t.toFixed(2)}`
export const reportHtmlUrl = (id: string) => `${base(id)}/report.html`

export const api = {
  async createSession(video: File, anchorDoorHint?: string, anchorWidthM?: number): Promise<string> {
    const fd = new FormData()
    fd.append('video', video)
    if (anchorDoorHint) fd.append('anchor_door_hint', anchorDoorHint)
    if (anchorWidthM && anchorWidthM > 0) fd.append('anchor_width_m', String(anchorWidthM))
    return validate<{ id: string }>(obj({ id: str }), await call('/api/sessions', { method: 'POST', body: fd })).id
  },
  snapshot: async (id: string) => parseSnapshot(await call(base(id))),
  /** `expected_revision` is the current draft revision (null before the first draft). */
  extract: (id: string, mode: VideoMode, expected_revision: string | null) =>
    post(`${base(id)}/extract`, { mode, expected_revision }),
  /** D2: the server owns the anchor; this never edits the draft graph. */
  anchor: (id: string, expected_revision: string, door_id: string, measured_width_m: number) =>
    post(`${base(id)}/anchor`, { expected_revision, door_id, measured_width_m }),
  refine: (id: string, expected_revision: string) => post(`${base(id)}/refine`, { expected_revision }),
  putGraph: async (id: string, expected_revision: string, graph: VenueGraph) =>
    validate<{ revision: string; findings: Finding[] }>(obj({ revision: str, findings: arr(finding) }),
      await post(`${base(id)}/graph`, { expected_revision, graph }, 'PUT')),
  accept: (id: string, expected_revision: string) => post(`${base(id)}/accept`, { expected_revision }),
  setHazards: (id: string, expected_revision: string, hazards: Hazard[]) =>
    post(`${base(id)}/scenario`, { expected_revision, hazards }),
  investigate: (id: string, expected_revision: string, expected_scenario: string) =>
    post(`${base(id)}/investigate`, { expected_revision, expected_scenario }),
  approve: (id: string, b: { expected_revision: string; expected_scenario: string; investigation_id: string; intervention_id: string }) =>
    post(`${base(id)}/approve`, b),
  report: async (id: string) => parseReport(await call(`${base(id)}/report`)),
  /** The drafted note to security for approval `index` (markdown text). */
  note: async (id: string, index: number) => {
    const t = await call(`${base(id)}/approvals/${index}/note`, undefined, 'text')
    if (typeof t !== 'string') throw new ApiShapeError('note', 'text')
    return t
  },
}
