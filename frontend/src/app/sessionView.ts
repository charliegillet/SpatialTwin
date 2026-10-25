// Pure view data for the session: start time and saved-run badge, the server-owned anchor,
// the hero figure rule, approved openings, agent word flags, the SfM preview and ADA wording.
import type { FlowRun, Recommendation, RuleResult, SfmPreview, Snapshot } from '../apiTypes'
import type { Anchor, VenueGraph } from '../types'
import { formatHero } from '../twin/crowdDots'

/** D6, shown in the Twin's declared row. */
export const DECLARED_ROUTING = 'system-optimal (earliest arrival); real crowds tend to use the way they came in'

/** The server writes "+0000" offsets; normalise to "+00:00" before parsing. */
export function parseCreatedAt(iso: string): number | null {
  const t = Date.parse(iso.replace(/([+-]\d{2})(\d{2})$/, '$1:$2'))
  return Number.isFinite(t) ? t : null
}
const hhmm = (t: number) => {
  const d = new Date(t)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

export function sessionStarted(createdAt: string): string {
  const t = parseCreatedAt(createdAt)
  return t == null ? 'Session start time unknown' : `Session started ${hhmm(t)}`
}

export const SAVED_RUN_AFTER_MS = 30 * 60_000
/** "saved run · started HH:MM" once the session started more than 30 min before `now`. */
export function savedRunBadge(createdAt: string, now: number): string | null {
  const t = parseCreatedAt(createdAt)
  return t != null && now - t > SAVED_RUN_AFTER_MS ? `saved run · started ${hhmm(t)}` : null
}

/** D2: the server-owned anchor. Old snapshots only carry `anchor` (the same server field). */
export const pendingAnchor = (s: Snapshot): Anchor | null =>
  s.pending_anchor !== undefined ? s.pending_anchor : s.anchor

export interface AnchorStatus {
  door_id: string
  width_m: number
  /** pending: applies at Accept · applied: the accepted door's basis is anchor_measured · not_applied: accepted without it */
  state: 'pending' | 'applied' | 'not_applied'
  text: string
}

export function anchorStatus(s: Snapshot): AnchorStatus | null {
  const a = pendingAnchor(s) ?? s.accepted_graph?.anchor ?? null
  if (!a) return null
  const w = `${a.door_id} = ${a.measured_width_m.toFixed(3)} m`
  const door = s.accepted_graph?.doors.find((d) => d.id === a.door_id)
  if (door?.clear_width.basis === 'anchor_measured') return { door_id: a.door_id, width_m: a.measured_width_m, state: 'applied', text: `${w} · applied (tape-measured)` }
  if (s.accepted_graph && !pendingAnchor(s)) {
    return { door_id: a.door_id, width_m: a.measured_width_m, state: 'not_applied', text: `${w} · not applied to the accepted graph (widths stay model-reported)` }
  }
  return { door_id: a.door_id, width_m: a.measured_width_m, state: 'pending', text: `${w} tape-measured · applied at Accept` }
}

export interface HeroState {
  /** the headline, only for a checked run */
  figure: string | null
  tag: string
  checked: boolean
}

/** M9: the hero shows a figure only for the current run's passing check, never on a stale copy. */
export function heroState(s: Snapshot, run: FlowRun, stale: boolean): HeroState {
  const check = s.current_check
  if (stale) return { figure: null, tag: 'reload needed: figure withheld', checked: false }
  if (!check || check.run_id !== run.run_id) return { figure: null, tag: 'not checked: figure withheld', checked: false }
  if (!check.ok) return { figure: null, tag: 'check failed: figure withheld', checked: false }
  return { figure: `${formatHero(run.reached_exit, run.total, run.params.horizon_s)} · checked`, tag: 'checker verified', checked: true }
}

export interface Opening { intervention_id: string; door_id: string; approved: boolean }

/** M4: the scenario's OPEN:<door> interventions, and whether one of your approvals added them. */
export function approvedOpenings(s: Snapshot): Opening[] {
  return s.scenario.interventions.filter((i) => i.startsWith('OPEN:')).map((i) => ({
    intervention_id: i, door_id: i.slice(5), approved: s.approvals.some((a) => a.intervention_id === i),
  }))
}

/** The graph as the solver runs it: opened doors drawn open. The accepted graph is not changed. */
export function withOpenings(g: VenueGraph, openings: Opening[]): VenueGraph {
  if (!openings.length) return g
  const ids = new Set(openings.map((o) => o.door_id))
  return { ...g, doors: g.doors.map((d) => (ids.has(d.id) ? { ...d, state: 'open' } : d)) }
}

/** D5: the server's flags for the agent's own words, deduplicated (case-insensitive). */
export function agentFlags(rec: Pick<Recommendation, 'copy_flags'> | null): string[] {
  const seen = new Set<string>()
  return (rec?.copy_flags ?? []).filter((w) => {
    const k = w.toLowerCase()
    if (seen.has(k)) return false
    seen.add(k)
    return true
  })
}

export interface PreviewPlot { viewBox: string; points: string; start: [number, number]; end: [number, number]; stroke: number }

/** D4 inset geometry: u to the right, v (walking direction) up. SVG y is -v. */
export function previewPlot(p: SfmPreview | null | undefined): PreviewPlot | null {
  const pts = p?.points ?? []
  if (pts.length < 2) return null
  const xs = pts.map((q) => q.u), ys = pts.map((q) => -q.v)
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys)
  const span = Math.max(x1 - x0, y1 - y0, 1e-6)
  const pad = span * 0.08
  const r = (v: number) => Math.round(v * 1000) / 1000 + 0 // + 0 turns -0 into 0
  return {
    viewBox: `${r(x0 - pad)} ${r(y0 - pad)} ${r(x1 - x0 + 2 * pad)} ${r(y1 - y0 + 2 * pad)}`,
    points: pts.map((q) => `${r(q.u)},${r(-q.v)}`).join(' '),
    start: [r(xs[0]), r(ys[0])], end: [r(xs.at(-1)!), r(ys.at(-1)!)],
    stroke: r(span / 60),
  }
}

const STATUS: Record<string, string> = { pass: 'pass', fail: 'fail', cannot_measure: 'cannot measure' }

/** "measured" only for a tape-measured width; everything else is the model's estimate. */
export function adaResultText(r: RuleResult): string {
  const rule = r.rule_id.replace('ADA-', 'ADA §')
  const range = r.measured?.basis === 'anchor_measured' ? 'within measured range' : "within the model's estimated range (model-reported)"
  const base = r.status === 'pass' ? `meets ${rule} ${range}` : r.status === 'fail' ? `does not meet ${rule} ${range}` : STATUS[r.status] ?? r.status
  return r.reason ? `${base}: ${r.reason}` : base
}
