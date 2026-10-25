// Pure view data for the geometry loop (D1): baseline / round / accepted rows, ops,
// discrepancies, provider errors and the measured before -> after delta.
import type { GeometryScore, Iteration, IterationKind, PatchOp, Snapshot } from '../apiTypes'

/** D1: old data has no kind; it means "round". */
export const iterKind = (it: Pick<Iteration, 'kind'>): IterationKind => it.kind ?? 'round'

/**
 * A label per iteration, in list order. Every refine appends its own baseline, so with more
 * than one loop in the session the labels carry the loop number ("Loop 2 · Round 1").
 */
export function iterationLabels(its: Pick<Iteration, 'kind' | 'index'>[]): string[] {
  const loops = its.filter((it) => iterKind(it) === 'baseline').length
  let loop = 0
  return its.map((it) => {
    const k = iterKind(it)
    if (k === 'baseline') loop++
    const prefix = loops > 1 && k !== 'accepted' ? `Loop ${Math.max(loop, 1)} · ` : ''
    if (k === 'baseline') return `${prefix}Before the loop`
    if (k === 'accepted') return 'Accepted graph'
    return `${prefix}Round ${it.index}`
  })
}

export type OpStatus = 'applied' | 'rejected' | 'reverted' | 'not applied'
export interface OpRow {
  i: number
  type: string
  target: string | null
  cite_t_s: number
  reason: string
  /** the op's other fields, as plain text ("state=open") */
  detail: string
  status: OpStatus
  why: string | null
}

const OP_KEYS = new Set(['op', 'id', 'cite_t_s', 'reason', 'door', 'zone'])

export function opTarget(op: PatchOp): string | null {
  if (typeof op.id === 'string') return op.id
  if (op.door && typeof op.door.id === 'string') return op.door.id
  if (op.zone && typeof op.zone.id === 'string') return op.zone.id
  return null
}

function fmtValue(v: unknown): string {
  if (v && typeof v === 'object' && !Array.isArray(v)) {
    const m = v as { low_m?: unknown; high_m?: unknown; basis?: unknown }
    if (typeof m.low_m === 'number' && typeof m.high_m === 'number') {
      return `${m.low_m}–${m.high_m} m${typeof m.basis === 'string' ? ` (${m.basis})` : ''}`
    }
  }
  return typeof v === 'string' ? v : JSON.stringify(v)
}

export function opDetail(op: PatchOp): string {
  const parts = Object.entries(op).filter(([k, v]) => !OP_KEYS.has(k) && v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${fmtValue(v)}`)
  if (op.door) parts.unshift(`door ${String(op.door.a ?? '?')}↔${String(op.door.b ?? '?')}`)
  if (op.zone) parts.unshift(`zone ${String(op.zone.name ?? '')}`.trim())
  return parts.join(' · ')
}

/** Every op Argon proposed this round, with what the patcher did with it. */
export function opRows(it: Pick<Iteration, 'applied' | 'rejected' | 'critique'>): OpRow[] {
  const ops = it.critique?.ops ?? []
  return ops.map((op, i) => {
    const rej = it.rejected.find(([j]) => j === i)
    const status: OpStatus = rej ? (rej[1] === 'measured_regression' ? 'reverted' : 'rejected')
      : it.applied.includes(i) ? 'applied' : 'not applied'
    return {
      i, type: op.op, target: opTarget(op), cite_t_s: op.cite_t_s, reason: op.reason, detail: opDetail(op), status,
      why: rej ? (rej[1] === 'measured_regression' ? 'measured regression: the whole round was reverted' : rej[1]) : null,
    }
  })
}

/** Rejections for op indices the critique does not list (old data without `critique`). */
export function orphanRejections(it: Pick<Iteration, 'rejected' | 'critique'>): [number, string][] {
  const n = it.critique?.ops.length ?? 0
  return it.rejected.filter(([i]) => i >= n)
}

/** Why this round has no usable critique: a provider failure, timeout or invalid output. */
export function critiqueProblem(it: Pick<Iteration, 'critique' | 'stop_reason'>): string | null {
  const c = it.critique
  if (c && c.status !== 'completed') return `Argon critique ${c.status}${c.error ? `: ${c.error}` : ''}`
  if (c?.error) return `Argon critique error: ${c.error}`
  if (it.stop_reason === 'provider_failed') return 'Provider failed; no critique for this round'
  return null
}

export interface LoopDelta {
  before: GeometryScore
  after: GeometryScore
  afterLabel: string
}

/**
 * Measured before -> after for the latest loop: its baseline against the last measured
 * row after it (a round, or the accepted rescore). Null without a measured baseline.
 */
export function loopDelta(s: Pick<Snapshot, 'iterations'>): LoopDelta | null {
  const its = s.iterations
  const labels = iterationLabels(its)
  let b = -1
  for (let i = its.length - 1; i >= 0; i--) if (iterKind(its[i]) === 'baseline') { b = i; break }
  if (b < 0 || !its[b].geometry) return null
  for (let i = its.length - 1; i > b; i--) {
    const g = its[i].geometry
    if (g) return { before: its[b].geometry!, after: g, afterLabel: labels[i] }
  }
  return null
}

export interface GeometryChoice {
  key: string
  label: string
  geometry: GeometryScore
  /** measured on the given revision */
  current: boolean
  /** measured under another alignment than the session's current one (e.g. before an anchor rescale) */
  otherFrame: boolean
}

/** Every measured iteration (baseline included), so Twin and Review can replay past flashes. */
export function geometryChoices(s: Pick<Snapshot, 'iterations' | 'alignment'>, revision: string | null): GeometryChoice[] {
  const labels = iterationLabels(s.iterations)
  const out: GeometryChoice[] = []
  s.iterations.forEach((it, i) => {
    if (!it.geometry) return
    out.push({
      key: String(i), label: labels[i], geometry: it.geometry,
      current: !!revision && it.graph_revision === revision,
      otherFrame: !!s.alignment && it.geometry.alignment_hash !== s.alignment.hash,
    })
  })
  return out
}

/** The selected choice, else the last one measured on this revision, else null. */
export function pickGeometry(choices: GeometryChoice[], selected: string | null): GeometryChoice | null {
  return choices.find((c) => c.key === selected) ?? choices.filter((c) => c.current).at(-1) ?? null
}
