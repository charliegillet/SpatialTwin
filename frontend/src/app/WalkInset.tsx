// D4: the SfM camera path before alignment, as soon as SfM completes. Not in twin coordinates.
import type { Snapshot } from '../apiTypes'
import { previewPlot } from './sessionView'

export function WalkInset({ snap }: { snap: Snapshot }) {
  const p = previewPlot(snap.sfm_preview)
  if (!p) return null
  return (
    <figure className="walk-inset">
      <svg viewBox={p.viewBox} role="img" aria-label={`Your walk (unaligned, SfM units): ${snap.sfm_preview!.points.length} camera positions`}>
        <polyline points={p.points} fill="none" stroke="var(--ghost, #40c4ff)" strokeWidth={p.stroke} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={p.start[0]} cy={p.start[1]} r={p.stroke * 2.5} className="walk-start" />
        <circle cx={p.end[0]} cy={p.end[1]} r={p.stroke * 2.5} className="walk-end" />
      </svg>
      <figcaption>Your walk (unaligned, SfM units)</figcaption>
    </figure>
  )
}
