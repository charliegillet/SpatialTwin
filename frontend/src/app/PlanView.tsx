// 2D plan, y-up (ruling R15). Graph metres in, SVG out. Used for Capture (SfM path), Review (editing) and the Twin legend.
import { useRef, useState, type PointerEvent as RPointerEvent } from 'react'
import type { GhostPoint } from '../apiTypes'
import type { VenueGraph } from '../types'

type Rect = [number, number, number, number]
interface Props {
  graph: VenueGraph | null
  path?: GhostPoint[]
  flashes?: GhostPoint[]
  hazards?: string[]
  selected?: string | null
  errorIds?: Set<string>
  editable?: boolean
  onRectCommit?: (zoneId: string, rect: Rect) => void
  onSelect?: (elementId: string) => void
  onSeek?: (t: number) => void
  label?: string
}

const STATE_COLOR: Record<string, string> = { open: 'var(--open)', closed: 'var(--closed)', locked: 'var(--locked)', unknown: 'var(--unknown)' }
const snap = (v: number) => Math.round(v * 20) / 20

function bounds(graph: VenueGraph | null, path: GhostPoint[]) {
  const xs: number[] = [], ys: number[] = []
  for (const z of graph?.zones ?? []) { xs.push(z.rect[0], z.rect[0] + z.rect[2]); ys.push(z.rect[1], z.rect[1] + z.rect[3]) }
  for (const p of path) { xs.push(p.x); ys.push(p.y) }
  if (!xs.length) return { x0: 0, y0: 0, x1: 10, y1: 6 }
  return { x0: Math.min(...xs) - 1, y0: Math.min(...ys) - 1, x1: Math.max(...xs) + 1, y1: Math.max(...ys) + 1 }
}

export function PlanView({ graph, path = [], flashes = [], hazards = [], selected, errorIds, editable, onRectCommit, onSelect, onSeek, label }: Props) {
  const svg = useRef<SVGSVGElement>(null)
  const [drag, setDrag] = useState<{ id: string; mode: 'move' | 'resize'; start: [number, number]; rect: Rect; cur: Rect } | null>(null)
  const b = bounds(graph, path)
  const w = b.x1 - b.x0, h = b.y1 - b.y0

  const toGraph = (e: RPointerEvent): [number, number] => {
    const el = svg.current!
    const pt = el.createSVGPoint()
    pt.x = e.clientX; pt.y = e.clientY
    const p = pt.matrixTransform(el.getScreenCTM()!.inverse())
    return [p.x, -p.y]
  }
  const begin = (e: RPointerEvent, id: string, mode: 'move' | 'resize', rect: Rect) => {
    if (!editable) return
    e.stopPropagation()
    ;(e.target as Element).setPointerCapture(e.pointerId)
    setDrag({ id, mode, start: toGraph(e), rect, cur: rect })
  }
  const move = (e: RPointerEvent) => {
    if (!drag) return
    const [gx, gy] = toGraph(e)
    const dx = gx - drag.start[0], dy = gy - drag.start[1]
    const [x, y, rw, rh] = drag.rect
    const cur: Rect = drag.mode === 'move'
      ? [snap(x + dx), snap(y + dy), rw, rh]
      : [x, y, Math.max(0.5, snap(rw + dx)), Math.max(0.5, snap(rh + dy))]
    setDrag({ ...drag, cur })
  }
  const end = () => {
    if (!drag) return
    const changed = drag.cur.some((v, i) => v !== drag.rect[i])
    if (changed) onRectCommit?.(drag.id, drag.cur)
    else onSelect?.(drag.id)
    setDrag(null)
  }

  const fs = Math.max(0.35, Math.min(w, h) / 28)
  return (
    <figure className="plan">
      <svg ref={svg} viewBox={`${b.x0} ${-b.y1} ${w} ${h}`} role="img" aria-label={label ?? 'Plan view'}
        onPointerMove={move} onPointerUp={end} onPointerCancel={() => setDrag(null)}>
        {graph?.zones.map((z) => {
          const r = drag?.id === z.id ? drag.cur : z.rect
          const err = errorIds?.has(z.id)
          return (
            <g key={z.id} className={`zone${selected === z.id ? ' sel' : ''}${err ? ' err' : ''}`}>
              <rect x={r[0]} y={-(r[1] + r[3])} width={r[2]} height={r[3]}
                onPointerDown={(e) => (editable ? begin(e, z.id, 'move', z.rect) : onSelect?.(z.id))} />
              <text className="zone-label" x={r[0] + r[2] / 2} y={-(r[1] + r[3] / 2)} fontSize={fs} textAnchor="middle">
                <tspan x={r[0] + r[2] / 2}>{z.id}</tspan>
                <tspan x={r[0] + r[2] / 2} dy={fs * 1.1} fontSize={fs * 0.8}>{z.name}</tspan>
              </text>
              {editable && (
                <circle className="handle" cx={r[0] + r[2]} cy={-(r[1] + r[3])} r={fs * 0.55}
                  onPointerDown={(e) => begin(e, z.id, 'resize', z.rect)}>
                  <title>Drag to resize {z.id}</title>
                </circle>
              )}
            </g>
          )
        })}
        {path.length > 1 && (
          <polyline className="ghost-path" points={path.map((p) => `${p.x},${-p.y}`).join(' ')} strokeWidth={fs * 0.25} />
        )}
        {graph?.doors.map((d) => (
          <g key={d.id} className={`door${selected === d.id ? ' sel' : ''}${errorIds?.has(d.id) ? ' err' : ''}`}
            onPointerDown={(e) => { e.stopPropagation(); onSelect?.(d.id) }}>
            {hazards.includes(d.id) && <circle className="hazard-ring" cx={d.position[0]} cy={-d.position[1]} r={fs * 1.6} />}
            <circle cx={d.position[0]} cy={-d.position[1]} r={fs * 0.7} fill={STATE_COLOR[d.state] ?? STATE_COLOR.unknown} />
            <text x={d.position[0] + fs * 0.9} y={-d.position[1] - fs * 0.6} fontSize={fs * 0.9}>{d.id}{d.kind === 'exit' ? ' exit' : ''}</text>
          </g>
        ))}
        {flashes.map((f, i) => (
          <circle key={i} className="flash" cx={f.x} cy={-f.y} r={fs * 0.75}
            onPointerDown={(e) => { e.stopPropagation(); onSeek?.(f.t_s) }}>
            <title>Illegal crossing at t={f.t_s.toFixed(1)} s, click to see the video</title>
          </circle>
        ))}
      </svg>
      {label && <figcaption>{label}</figcaption>}
    </figure>
  )
}
