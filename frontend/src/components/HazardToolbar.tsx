import { Biohazard, Camera, CloudFog, Droplets, Flame, Minus, Plus, Radiation, Trash2, Undo2, X, type LucideIcon } from 'lucide-react';
import { SMOKE_MAX, SMOKE_MIN } from '../ai/hazardTools';
import { HAZARD_INFO, HAZARD_ORDER, hazardHint, hazardLabel } from '../twin/hazardModel';
import type { HazardType, PlacedHazard } from '../twin/types';

const ICON: Record<HazardType, LucideIcon> = { FIRE: Flame, SMOKE: CloudFog, GAS: Radiation, CHEMICAL: Biohazard, WATER: Droplets };

interface Props {
  armed: HazardType | null;
  onArm: (type: HazardType | null) => void;
  smokeSeconds: number;
  onSmokeStep: (direction: 1 | -1) => void;
  hazards: PlacedHazard[];
  zoneNames: Record<string, string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onRemove: (id: string) => void;
  canUndo: boolean;
  onUndo: () => void;
  onClear: () => void;
  notice: string | null;
}

/** Simulation hazards: tap a type to arm it, then tap the floor; or drag a type onto the floor. */
export function HazardToolbar({ armed, onArm, smokeSeconds, onSmokeStep, hazards, zoneNames, selectedId, onSelect, onRemove, canUndo, onUndo, onClear, notice }: Props) {
  const hint = armed ? `${hazardHint(armed, armed === 'SMOKE' ? smokeSeconds : undefined)}. Tap the floor.` : 'Pick a hazard, then tap the floor.';
  return <section className="hazard-palette twin-toolbar" aria-label="Hazards">
    <div className="twin-types" role="group" aria-label="Hazard type">
      {HAZARD_ORDER.map(type => {
        const Icon = ICON[type];
        return <button key={type} type="button" className="twin-type" style={{ ['--kind' as string]: HAZARD_INFO[type].color }} aria-pressed={armed === type}
          draggable onDragStart={event => { event.dataTransfer.setData('text/plain', `hazard:${type}`); event.dataTransfer.effectAllowed = 'copy'; onArm(type); }}
          onClick={() => onArm(armed === type ? null : type)} title={hazardHint(type, type === 'SMOKE' ? smokeSeconds : undefined)}>
          <Icon size={16} aria-hidden="true" /><span>{hazardLabel(type)}</span>
        </button>;
      })}
    </div>
    {(armed === 'SMOKE' || hazards.find(item => item.id === selectedId)?.type === 'SMOKE') && <div className="smoke-stepper" role="group" aria-label="Smoke untenable time">
      <span id="twin-smoke-label">Untenable at</span>
      <button type="button" className="btn btn-icon" aria-label="Earlier by 2 seconds" onClick={() => onSmokeStep(-1)} disabled={smokeSeconds <= SMOKE_MIN}><Minus size={14} aria-hidden="true" /></button>
      <output aria-labelledby="twin-smoke-label" className="smoke-value">{smokeSeconds} s</output>
      <button type="button" className="btn btn-icon" aria-label="Later by 2 seconds" onClick={() => onSmokeStep(1)} disabled={smokeSeconds >= SMOKE_MAX}><Plus size={14} aria-hidden="true" /></button>
    </div>}
    <p className="hazard-hint">{hint}</p>
    {notice && <p className="hazard-notice" role="status">{notice}</p>}
    {hazards.length > 0 && <ul className="twin-placed" aria-label="Placed hazards">
      {hazards.map(item => <li key={item.id} style={{ ['--kind' as string]: HAZARD_INFO[item.type].color }}>
        <button type="button" className="twin-chip" aria-pressed={selectedId === item.id} onClick={() => onSelect(selectedId === item.id ? null : item.id)}>
          {item.source === 'camera' && <Camera size={12} aria-label="From camera" />}{hazardLabel(item.type)}<small>{zoneNames[item.zone_id] ?? item.zone_id}{item.type === 'SMOKE' && item.untenable_s !== null ? ` · ${item.untenable_s} s` : ''}</small>
        </button>
        <button type="button" className="twin-chip-x" onClick={() => onRemove(item.id)} aria-label={`Remove ${hazardLabel(item.type)} in ${zoneNames[item.zone_id] ?? item.zone_id}`}><X size={13} aria-hidden="true" /></button>
      </li>)}
    </ul>}
    <div className="twin-actions">
      <button type="button" className="btn" onClick={onUndo} disabled={!canUndo}><Undo2 size={14} aria-hidden="true" />Undo</button>
      <button type="button" className="btn" onClick={onClear} disabled={hazards.length === 0}><Trash2 size={14} aria-hidden="true" />Clear all</button>
    </div>
  </section>;
}
