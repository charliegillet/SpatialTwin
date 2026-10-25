import { useEffect, useId, useRef, type ReactNode, type RefObject } from 'react';
import { Check, LoaderCircle, RotateCcw, X } from 'lucide-react';
import type { InvestigationMode } from '../types';
import type { PreflightItem, ResetFacts } from '../ai/resetFlow';
import { ResetChecklist } from './ResetChecklist';
import { MODE_LABEL, MODE_LOCKED, visibleModes } from '../twin/modes';
import type { TwinMode, VenueSummary } from '../twin/types';

interface Props {
  open: boolean;
  onClose: () => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  /** Receives the element the board panel renders its source, target and thinking controls into. */
  boardSlot: (element: HTMLDivElement | null) => void;
  mode: InvestigationMode;
  onModeChange: (mode: InvestigationMode) => void;
  modeLocked: boolean;
  apiConfigured: boolean;
  localEnabled: boolean;
  physical: boolean;
  operatorToken: string;
  onOperatorToken: (token: string) => void;
  preflight: PreflightItem[];
  facts: ResetFacts;
  resetMessage: string | null;
  isResetting: boolean;
  canReset: boolean;
  onReset: () => void;
  onClearHazards: () => void;
  clearMessage: string | null;
  twinMode: TwinMode;
  onTwinMode: (mode: TwinMode) => void;
  /** Locked while an analysis or investigation runs. */
  twinLocked: boolean;
  /** Camera twin only: freeze a frame and click the sheet's corner markers. */
  onCalibrate: () => void;
  /** Rehearsal without a camera: an image of the sheet replaces the live frame, and every read says so. */
  imageFile: File | null;
  onImageFile: (file: File | null) => void;
  /** Built-in and accepted venues; Simulation plans on the active one. */
  venues: VenueSummary[];
  venueId: string;
  onVenue: (venueId: string) => void;
  children?: ReactNode;
}

/** Everything a presenter sets before a judge arrives. The stage itself shows only the live view, Read the board and the proposal. */
export function PresenterMenu({ open, onClose, triggerRef, boardSlot, mode, onModeChange, modeLocked, apiConfigured, localEnabled, physical, operatorToken, onOperatorToken, preflight, facts, resetMessage, isResetting, canReset, onReset, onClearHazards, clearMessage, twinMode, onTwinMode, twinLocked, onCalibrate, imageFile, onImageFile, venues, venueId, onVenue }: Props) {
  const uid = useId();
  const panel = useRef<HTMLElement>(null);
  const opened = useRef(false);
  useEffect(() => {
    if (open) { opened.current = true; panel.current?.querySelector<HTMLElement>('button, select, input')?.focus({ preventScroll: true }); }
    else if (opened.current) { opened.current = false; triggerRef.current?.focus({ preventScroll: true }); }
  }, [open, triggerRef]);
  const allGreen = preflight.every(item => item.ok);
  return <section ref={panel} id="presenter-menu" className="presenter-menu" role="dialog" aria-label="Presenter menu" aria-modal="false" hidden={!open}
    onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); onClose(); } }}>
    <header><h2>Presenter</h2><button type="button" className="btn btn-icon" onClick={onClose} aria-label="Close presenter menu"><X size={16} aria-hidden="true" /></button></header>

    <div className="pm-group">
      <h3 id={`${uid}-twin`}>Twin</h3>
      <div className="seg" role="group" aria-labelledby={`${uid}-twin`}>
        {visibleModes().map(item => <button key={item} type="button" aria-pressed={twinMode === item} disabled={twinLocked} onClick={() => onTwinMode(item)}>{MODE_LABEL[item]}</button>)}
      </div>
      {(twinMode === 'sim' || twinMode === 'build') && venues.length > 1 && <label className="clip-mode">Venue<select aria-label="Venue" value={venueId} disabled={twinLocked} onChange={event => onVenue(event.target.value)}>
        {venues.map(item => <option key={item.venue_id} value={item.venue_id}>{item.builtin ? item.name : `${item.name} · ${item.zones} rooms`}</option>)}
      </select></label>}
      {twinMode === 'camera' && <>
        <button type="button" className="btn pm-reset" onClick={onCalibrate}>Calibrate sheet</button>
        <label className="btn pm-reset pm-file">{imageFile ? `Image: ${imageFile.name.slice(0, 24)}` : 'Use an uploaded image'}<input type="file" accept="image/*" aria-label="Image of the sheet" onChange={event => { const file = event.target.files?.[0]; if (file) onImageFile(file); event.target.value = ''; }} /></label>
        {imageFile && <button type="button" className="btn pm-reset" onClick={() => onImageFile(null)}>Use the live camera</button>}
      </>}
      {twinLocked && <p className="pm-note">{MODE_LOCKED}</p>}
    </div>

    <div className="pm-group">
      <h3 id={`${uid}-analysis`}>Analysis</h3>
      <div className="seg" role="group" aria-labelledby={`${uid}-analysis`}>
        <button type="button" aria-pressed={mode === 'live'} disabled={modeLocked} onClick={() => onModeChange('live')}>Live Gemini</button>
        <button type="button" aria-pressed={mode === 'local'} disabled={modeLocked} onClick={() => onModeChange('local')}>Local solver</button>
      </div>
      <p className="pm-note">{mode === 'live' ? (apiConfigured ? 'Managed agent run, 40–57 s.' : 'Gemini is not configured.') : (localEnabled ? 'Instant. No Gemini call.' : 'Local solver is disabled.')}</p>
    </div>

    <div className="pm-group">
      <h3>Board source</h3>
      <div ref={boardSlot} className="pm-board" />
    </div>

    {physical && <div className="pm-group">
      <h3><label htmlFor={`${uid}-token`}>Operator token</label></h3>
      <input id={`${uid}-token`} type="password" autoComplete="off" spellCheck={false} value={operatorToken} onChange={event => onOperatorToken(event.target.value)} placeholder="Held in memory only" />
    </div>}

    <div className="pm-group">
      <h3>Preflight <span className={`chip chip-${allGreen ? 'ok' : 'warn'}`}>{allGreen ? 'All green' : 'Needs attention'}</span></h3>
      <ul className="pm-preflight">{preflight.map(item => <li key={item.id} className={item.ok ? 'is-ok' : 'is-bad'}>{item.ok ? <Check size={13} aria-hidden="true" /> : <span className="pm-dot" aria-hidden="true" />}<strong>{item.label}</strong><span>{item.detail}</span></li>)}</ul>
    </div>

    <div className="pm-group">
      <button type="button" className="btn btn-primary pm-reset" onClick={onReset} disabled={!canReset || isResetting}>{isResetting ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <RotateCcw size={14} aria-hidden="true" />}{isResetting ? 'Resetting…' : 'Reset for next judge'}</button>
      <button type="button" className="btn pm-reset" onClick={onClearHazards} disabled={!canReset || isResetting}>Clear hazards</button>
      {clearMessage && <p className="pm-note" role="status">{clearMessage}</p>}
      <ResetChecklist facts={facts} message={resetMessage} physical={physical} />
    </div>
  </section>;
}
