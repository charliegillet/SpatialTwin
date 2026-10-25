import type { ReactNode } from 'react';
import type { Chip } from '../ai/stageView';

interface Props { hero: ReactNode; gate: Chip; provenance: Chip | null; blocked: string[]; }

/** Overlay on the model: the hero number, then gate state, AI provenance and blocked targets. */
export function StageChips({ hero, gate, provenance, blocked }: Props) {
  return <div className="stage-chips" aria-label="Model status">
    {hero}
    <div className="stage-chip-row">
      <span className={`chip chip-${gate.tone}`}>{gate.label}</span>
      {blocked.map(id => <span key={id} className="chip chip-hazard">{id} closed</span>)}
      {provenance && <span className={`chip chip-${provenance.tone}`}>{provenance.label}</span>}
    </div>
  </div>;
}
