// I2: replay the red flashes of any measured row (the baseline included) for "before -> after".
import type { GeometryChoice } from './loopView'

export function FlashPicker({ choices, shown, onPick }: {
  choices: GeometryChoice[]; shown: GeometryChoice | null; onPick: (key: string) => void
}) {
  if (choices.length < 2) return null
  return (
    <div className="flash-picker">
      <label>Red flashes from{' '}
        <select value={shown?.key ?? ''} onChange={(e) => onPick(e.target.value)}>
          {!shown && <option value="">choose a round</option>}
          {choices.map((c) => (
            <option key={c.key} value={c.key}>
              {c.label}: {c.geometry.illegal_crossings.length} crossing{c.geometry.illegal_crossings.length === 1 ? '' : 's'}{c.current ? ' (this revision)' : ''}
            </option>
          ))}
        </select>
      </label>
      {shown?.otherFrame && <span className="muted small"> Measured before the anchor rescale: positions are in the earlier frame.</span>}
    </div>
  )
}
