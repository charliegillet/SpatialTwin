import { useState } from 'react';
import { LoaderCircle, Plus, Save, Trash2, X } from 'lucide-react';
import { FURNITURE_KINDS, MAX_PIECES, addPiece, removePiece, updatePiece, type FurnitureKind } from '../twin/furnitureEdit.ts';
import type { VenueFurniture, VenueV2 } from '../twin/types.ts';

interface Props {
  venue: VenueV2;
  furniture: VenueFurniture[];
  onChange: (furniture: VenueFurniture[]) => void;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  error: string | null;
}

const num = (text: string) => (text.trim() === '' ? undefined : Number(text));

/** Optional furniture editing on a draft (looks only): add, select, resize, rotate, recolour, relabel and delete pieces
 *  one room at a time; pieces are moved by dragging them in the 3D view. Accept never requires this. */
export function FurnitureEditor({ venue, furniture, onChange, selectedId, onSelect, onSave, onCancel, saving, error }: Props) {
  const selected = furniture.find(piece => piece.id === selectedId) ?? null;
  const [roomPick, setRoomPick] = useState(venue.zones[0]?.id ?? '');
  const room = selected?.zone ?? roomPick;
  const [kind, setKind] = useState<FurnitureKind>('table');
  const inRoom = furniture.filter(piece => piece.zone === room);
  const zoneName = (id: string) => venue.zones.find(zone => zone.id === id)?.name ?? id;
  const set = (patch: Parameters<typeof updatePiece>[2]) => { if (selected?.id) onChange(updatePiece(furniture, selected.id, patch)); };
  const add = () => {
    const next = addPiece(venue, furniture, room, kind);
    if (next.id) { onChange(next.furniture); onSelect(next.id); }
  };

  return <div className="r2s-furniture" aria-label="Edit furniture">
    <h3 className="r2s-h3">Furniture</h3>
    <p className="twin-quiet">Drag a piece in the 3D view to move it. Furniture is for looks only; it never changes the routes.</p>
    <label className="r2s-field">Room
      <select value={room} onChange={event => { setRoomPick(event.target.value); onSelect(null); }}>
        {venue.zones.map(zone => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
      </select>
    </label>
    <ul className="r2s-pieces" aria-label={`Furniture in ${zoneName(room)}`}>
      {inRoom.length === 0 && <li className="twin-quiet">No furniture in this room yet.</li>}
      {inRoom.map(piece => <li key={piece.id}>
        <button type="button" className={`r2s-piece${piece.id === selectedId ? ' is-on' : ''}`} aria-pressed={piece.id === selectedId} onClick={() => onSelect(piece.id ?? null)}>
          <span className="r2s-swatch" style={{ background: piece.color || 'transparent' }} aria-hidden="true" />{piece.label}
        </button>
      </li>)}
    </ul>
    <div className="r2s-add">
      <select aria-label="Kind of furniture to add" value={kind} onChange={event => setKind(event.target.value as FurnitureKind)}>
        {FURNITURE_KINDS.map(item => <option key={item} value={item}>{item}</option>)}
      </select>
      <button type="button" className="btn" onClick={add} disabled={!room || furniture.length >= MAX_PIECES}><Plus size={14} aria-hidden="true" />Add</button>
    </div>
    {selected && <fieldset className="r2s-piece-form">
      <legend>{selected.label}</legend>
      <label className="r2s-field">Name<input type="text" maxLength={40} value={selected.label} onChange={event => set({ label: event.target.value })} /></label>
      <label className="r2s-field">Kind
        <select value={selected.category} onChange={event => set({ category: event.target.value })}>
          {!(FURNITURE_KINDS as readonly string[]).includes(selected.category) && <option value={selected.category}>{selected.category}</option>}
          {FURNITURE_KINDS.map(item => <option key={item} value={item}>{item}</option>)}
        </select>
      </label>
      <div className="r2s-fields r2s-fields-3">
        <label className="r2s-field">Width, m<input type="number" min={0.05} max={10} step={0.1} value={selected.width} onChange={event => set({ width: num(event.target.value) })} /></label>
        <label className="r2s-field">Depth, m<input type="number" min={0.05} max={10} step={0.1} value={selected.depth} onChange={event => set({ depth: num(event.target.value) })} /></label>
        <label className="r2s-field">Height, m<input type="number" min={0.05} max={4} step={0.1} value={selected.height} onChange={event => set({ height: num(event.target.value) })} /></label>
      </div>
      <div className="r2s-fields">
        <label className="r2s-field">Rotation, °<input type="number" step={15} value={selected.yaw_deg} onChange={event => set({ yaw_deg: num(event.target.value) })} /></label>
        <label className="r2s-field">Colour<input type="color" value={selected.color || '#9aa3ad'} onChange={event => set({ color: event.target.value })} /></label>
      </div>
      <button type="button" className="btn btn-quiet" onClick={() => { onChange(removePiece(furniture, selected.id!)); onSelect(null); }}><Trash2 size={14} aria-hidden="true" />Delete</button>
    </fieldset>}
    {error && <p className="door-advisory" role="alert">{error}</p>}
    <div className="r2s-edit-actions">
      <button type="button" className="btn btn-primary" onClick={onSave} disabled={saving}>
        {saving ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Save size={14} aria-hidden="true" />}Save furniture
      </button>
      <button type="button" className="btn" onClick={onCancel} disabled={saving}><X size={14} aria-hidden="true" />Cancel</button>
    </div>
  </div>;
}
