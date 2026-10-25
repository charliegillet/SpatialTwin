// Session API client. Every response is shape-checked before it can reach the UI,
// and results that do not belong to the current graph revision / scenario are dropped.
import type {
  FlowRun, Finding, Hazard, Investigation, InterventionResult, Report, Snapshot, VideoMode,
} from './apiTypes'
import type { VenueGraph } from './types'
import {
  ApiShapeError, any, arr, bool, int, lit, nullable, num, obj, opt, rec, str, tuple, validate, type Check,
} from './shape'

export { ApiShapeError }

// ---------- shapes ----------
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
  receipt: nullable(receipt), stop_reason: nullable(str),
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
  recommendation: nullable(obj({ intervention_id: nullable(str), claimed_reached_exit: nullable(int), rationale: str, caveats: arr(str) })),
  best: nullable(result), disagreement: nullable(str), hook_denials: int, receipt: nullable(receipt),
})
const snapshotShape = obj({
  id: str,
  video: obj({ path: str, sha256: str, duration_s: num, width: int, height: int }),
  anchor: nullable(anchor),
  sfm: nullable(obj({
    status: lit('completed', 'failed'), frames: arr(obj({ t_s: num, center: xyz, R: any, K: any })),
    points: arr(xyz), registered_fraction: num, elapsed_ms: num, error: nullable(str),
  })),
  alignment: nullable(obj({
    scale: num, yaw_rad: num, tx: num, ty: num, floor_normal: xyz, floor_offset: num, residual_m: num, eye_height_m: num, hash: str,
  })),
  draft_graph: nullable(graphShape), accepted_graph: nullable(graphShape),
  scenario: obj({ hazards: arr(obj({ door_id: str, kind: lit('fire'), from_s: num })), interventions: arr(str) }),
  current_run: nullable(flowRun),
  current_check: nullable(obj({ ok: bool, run_id: str, violations: arr(str) })),
  iterations: arr(iteration),
  extraction: nullable(obj({
    status: lit('completed', 'failed', 'timeout', 'invalid'), graph: nullable(graphShape), findings: arr(finding),
    receipt: nullable(receipt), mode: lit('static', 'static_hifps', 'agentic'), agentic_observed: nullable(bool),
    video_uri: nullable(str), error: nullable(str),
  })),
  investigations: arr(investigation),
  approvals: arr(obj({ intervention_id: str, investigation_id: str, graph_revision: str, scenario_hash: str, run_id: str, note_path: str, approved_at: str })),
  jobs: rec(obj({ kind: str, status: lit('queued', 'running', 'done', 'failed'), error: nullable(str) })),
  ghost_path: arr(obj({ t_s: num, x: num, y: num })),
  graph_revision: opt(nullable(str)), draft_revision: opt(nullable(str)), scenario_hash: opt(nullable(str)),
  findings: opt(arr(finding)), allowed_interventions: opt(arr(str)),
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

// ---------- derived state ----------
export const currentRevision = (s: Snapshot): string | null => s.graph_revision ?? s.current_run?.graph_revision ?? null
export const currentScenarioHash = (s: Snapshot): string | null => s.scenario_hash ?? s.current_run?.scenario_hash ?? null
export const draftRevision = (s: Snapshot): string | null =>
  s.draft_revision ?? s.iterations.at(-1)?.graph_revision ?? (s.accepted_graph ? currentRevision(s) : null)

/** True only when the result was computed for the current graph revision (and scenario, if it carries one). */
export function isCurrent(r: { graph_revision: string; scenario_hash?: string }, s: Snapshot): boolean {
  const rev = currentRevision(s)
  if (!rev || r.graph_revision !== rev) return false
  if (r.scenario_hash !== undefined) return r.scenario_hash === currentScenarioHash(s)
  return true
}

export const findingsOf = (s: Snapshot): Finding[] =>
  s.findings ?? s.iterations.at(-1)?.findings ?? s.extraction?.findings ?? []
export const runningJobs = (s: Snapshot) =>
  Object.entries(s.jobs).filter(([, j]) => j.status === 'queued' || j.status === 'running').map(([k]) => k)
export const currentRun = (s: Snapshot): FlowRun | null => (s.current_run && isCurrent(s.current_run, s) ? s.current_run : null)

export function acceptBlockers(s: Snapshot): string[] {
  const out: string[] = []
  if (!s.draft_graph) out.push('No draft twin yet')
  else if (!draftRevision(s)) out.push('Draft revision unknown; reload')
  const errors = findingsOf(s).filter((f) => f.severity === 'error').length
  if (errors) out.push(`${errors} error finding${errors > 1 ? 's' : ''} to fix`)
  for (const j of runningJobs(s)) out.push(`Waiting for ${j}`)
  return out
}

export const readyInvestigations = (s: Snapshot): Investigation[] => s.investigations.filter((i) => isCurrent(i, s))

/** The checked `best` that may be approved, or null. */
export function approvable(inv: Investigation, s: Snapshot): InterventionResult | null {
  const b = inv.best
  if (!b || !b.check_ok || b.delta_vs_current <= 0 || !isCurrent(inv, s)) return null
  if (!inv.results.some((r) => r.intervention_id === b.intervention_id && r.check_ok)) return null
  if (s.allowed_interventions && !s.allowed_interventions.includes(b.intervention_id)) return null
  if (s.approvals.some((a) => a.investigation_id === inv.investigation_id && a.intervention_id === b.intervention_id)) return null
  return b
}

// ---------- HTTP ----------
export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(status === 409 ? 'Stale revision: someone changed this first. Reloaded the latest state.' : `Request failed (${status})`)
    this.status = status
    this.body = body
  }
  get findings(): Finding[] {
    const b = this.body as { findings?: unknown; detail?: { findings?: unknown } } | null
    const f = b?.findings ?? b?.detail?.findings
    try { return validate<Finding[]>(arr(finding), f) } catch { return [] }
  }
}

async function call(path: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(path, init)
  const text = await res.text()
  let body: unknown = null
  try { body = text ? JSON.parse(text) : null } catch { body = text }
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
  extract: (id: string, mode: VideoMode) => post(`${base(id)}/extract`, { mode }),
  refine: (id: string, expected_revision: string) => post(`${base(id)}/refine`, { expected_revision }),
  putGraph: async (id: string, expected_revision: string, graph: VenueGraph) =>
    validate<{ revision?: string }>(obj({ revision: opt(str) }), (await post(`${base(id)}/graph`, { expected_revision, graph }, 'PUT')) ?? {}),
  accept: (id: string, expected_revision: string) => post(`${base(id)}/accept`, { expected_revision }),
  setHazards: (id: string, expected_revision: string, hazards: Hazard[]) =>
    post(`${base(id)}/scenario`, { expected_revision, hazards }),
  investigate: (id: string, expected_revision: string, expected_scenario: string) =>
    post(`${base(id)}/investigate`, { expected_revision, expected_scenario }),
  approve: (id: string, b: { expected_revision: string; expected_scenario: string; investigation_id: string; intervention_id: string }) =>
    post(`${base(id)}/approve`, b),
  report: async (id: string) => parseReport(await call(`${base(id)}/report`)),
}
