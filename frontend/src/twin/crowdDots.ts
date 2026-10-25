// Crowd dots are driven 1:1 by the solver's zone_occupancy; nothing is animated on its own.
import type { FlowRun } from '../apiTypes'

export function formatHero(reached: number, total: number, horizon_s = 120): string {
  return `${reached} of ${total} reach a modeled exit in ${horizon_s} s`
}

export const stepCount = (run: FlowRun) => run.zone_occupancy.length
const clampStep = (run: FlowRun, k: number) => Math.max(0, Math.min(stepCount(run) - 1, Math.round(k)))

export function dotsForStep(run: FlowRun, k: number): { zoneId: string; count: number }[] {
  const occ = run.zone_occupancy[clampStep(run, k)] ?? {}
  return Object.entries(occ).map(([zoneId, count]) => ({ zoneId, count }))
}

export interface StepCounter { t_s: number; inZones: number; inTransit: number; reached: number; total: number }
export function counterForStep(run: FlowRun, k: number): StepCounter {
  const i = clampStep(run, k)
  const inZones = dotsForStep(run, i).reduce((s, d) => s + d.count, 0)
  return {
    t_s: i * run.params.dt_s,
    inZones,
    inTransit: run.transit_by_step[i] ?? 0,
    reached: run.reached_by_step[i] ?? 0,
    total: run.total,
  }
}

/** Signed people through door d during step k (a->b positive). */
export const doorFlowAt = (run: FlowRun, doorId: string, k: number) => run.door_flows[doorId]?.[Math.round(k)] ?? 0
export const doorFlowTotal = (run: FlowRun, doorId: string) =>
  (run.door_flows[doorId] ?? []).reduce((s, f) => s + Math.abs(f), 0)

/** Deterministic grid of `count` points strictly inside rect [x, y, w, h] (graph metres). */
export function dotLayout(rect: [number, number, number, number], count: number): [number, number][] {
  if (count <= 0) return []
  const [x, y, w, h] = rect
  const cols = Math.max(1, Math.round(Math.sqrt((count * w) / h)))
  const rows = Math.ceil(count / cols)
  const out: [number, number][] = []
  for (let i = 0; i < count; i++) {
    const c = i % cols, r = Math.floor(i / cols)
    out.push([x + ((c + 0.5) * w) / cols, y + ((r + 0.5) * h) / rows])
  }
  return out
}

/** Zones with people at step k that the twin has no rect for (their dots can't be drawn). */
export function droppedZones(zoneIds: Iterable<string>, run: FlowRun, k: number): string[] {
  const known = new Set(zoneIds)
  return dotsForStep(run, k).filter((d) => d.count > 0 && !known.has(d.zoneId)).map((d) => d.zoneId)
}

/** Explicit flag when the counter doesn't reconcile: people not conserved, or the horizon differs from the headline. */
export function counterMismatch(run: FlowRun, k: number): string | null {
  const c = counterForStep(run, k)
  if (c.inZones + c.inTransit + c.reached !== c.total) {
    return `counter mismatch: ${c.inZones} + ${c.inTransit} + ${c.reached} ≠ ${c.total}`
  }
  const last = stepCount(run) - 1
  if (Math.round(k) >= last && c.reached !== run.reached_exit) {
    return `counter mismatch: ${c.reached} at exits vs headline ${run.reached_exit}`
  }
  return null
}
