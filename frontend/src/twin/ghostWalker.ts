// Ghost walker: the judge's own SfM camera path, in graph coordinates.
import type { GeometryScore, GhostPoint, Snapshot } from '../apiTypes'

/** The SfM path as frozen by the backend alignment (empty without SfM), in time order. */
export function ghostPath(s: Pick<Snapshot, 'ghost_path'>): GhostPoint[] {
  return [...s.ghost_path].sort((a, b) => a.t_s - b.t_s)
}

/** One red flash per illegal wall crossing. */
export function ghostFlashes(score: GeometryScore): GhostPoint[] {
  return score.illegal_crossings.map((c) => ({ t_s: c.t_s, x: c.x, y: c.y }))
}

/** Linear interpolation along the path at time t, clamped at the ends. */
export function positionAt(path: GhostPoint[], t: number): { x: number; y: number } | null {
  if (!path.length) return null
  if (t <= path[0].t_s) return { x: path[0].x, y: path[0].y }
  const last = path[path.length - 1]
  if (t >= last.t_s) return { x: last.x, y: last.y }
  let lo = 0, hi = path.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (path[mid].t_s <= t) lo = mid
    else hi = mid
  }
  const a = path[lo], b = path[hi]
  const u = b.t_s === a.t_s ? 0 : (t - a.t_s) / (b.t_s - a.t_s)
  return { x: a.x + u * (b.x - a.x), y: a.y + u * (b.y - a.y) }
}

/**
 * The measured geometry for exactly this graph revision: the last iteration whose
 * graph_revision matches. Null when this revision was never measured (or is unknown).
 */
export function latestGeometry(s: Pick<Snapshot, 'iterations'>, revision: string | null): GeometryScore | null {
  if (!revision) return null
  for (let i = s.iterations.length - 1; i >= 0; i--) {
    const it = s.iterations[i]
    if (it.graph_revision === revision && it.geometry) return it.geometry
  }
  return null
}
