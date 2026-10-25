import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Armchair, Camera, CheckCircle2, LoaderCircle, RotateCcw, Video } from 'lucide-react';
import { ApiError } from '../api/client.ts';
import { MAX_CONTROLLABLE_DOORS, overlayUrl, saveFurniture, topdownUrl } from '../api/real2sim.ts';
import type { AcceptResponse, SourceKind } from '../api/real2sim.ts';
import { furnitureOf, furniturePayload, movePiece, withFurniture } from '../twin/furnitureEdit.ts';
import type { FurnitureEditBridge, Point2, VenueFurniture, VenueV2 } from '../twin/types.ts';
import { FurnitureEditor } from './FurnitureEditor.tsx';
import { elapsedLabel } from '../twin/doorAgent.ts';
import { isRunning, type Real2SimState } from '../twin/real2simFlow.ts';
import {
  acceptDisabledReason, countsLine, progressSteps, readBuildingWidth, readHeadcount, receiptView, reconcileSelection, roundLine, thoughtSegments, toggleDoor,
} from '../twin/real2simView.ts';
import { useReal2Sim, type Real2SimController } from '../twin/useReal2Sim.ts';
import { Real2SimEvidence } from './Real2SimEvidence.tsx';
import './Real2Sim.css';

const KINDS: { kind: SourceKind; label: string }[] = [
  { kind: 'photo', label: 'Photo of a posted map' },
  { kind: 'sketch', label: 'Sketch' },
  { kind: 'pdf', label: 'PDF' },
  { kind: 'video', label: 'Video walkthrough' },
];

const PICK: Record<SourceKind, { accept: string; label: string; aria: string }> = {
  photo: { accept: 'image/jpeg,image/png,image/*', label: 'Take or upload a photo', aria: 'Take or upload a photo' },
  sketch: { accept: 'image/jpeg,image/png,image/*', label: 'Take or upload a photo', aria: 'Take or upload a photo' },
  pdf: { accept: 'application/pdf', label: 'Upload a PDF', aria: 'Upload a floor-plan PDF' },
  video: { accept: 'video/mp4,video/webm,video/quicktime,.mp4,.mov,.webm', label: 'Record or upload a video', aria: 'Record or upload a walkthrough video (up to 2 minutes)' },
};

/** Build stage: a photo, sketch or PDF of a floor plan, or a video walkthrough, becomes a checked venue draft the operator accepts.
 *  Argon proposes; the local compiler and graph checks decide; the operator accepts. `onAccepted` is the only output. */
export function Real2SimPanel({ onAccepted, onPreview }: { onAccepted?: (venueId: string, accepted: AcceptResponse) => void; onPreview?: (venue: VenueV2 | null, edit?: FurnitureEditBridge) => void }) {
  const r2s = useReal2Sim(onAccepted);
  const { state } = r2s;
  // The stage shows the draft's preview compile until it is accepted (then the accepted venue is the active one).
  const preview = state.view && !state.view.accepted ? state.view.preview : null;
  const furniture = useFurnitureEdit(r2s, preview);
  useEffect(() => { onPreview?.(furniture.shown, furniture.bridge); }, [furniture.shown, furniture.bridge, onPreview]);
  useEffect(() => () => onPreview?.(null), [onPreview]);
  const running = isRunning(state.stage);
  const picking = state.stage === 'idle' || state.stage === 'failed';
  return <section className="r2s" aria-label="Build a venue from a drawing" aria-busy={running}>
    <header className="r2s-head">
      <h2 className="r2s-title">Build from a drawing</h2>
      <p className="twin-quiet">Gemini 4 Argon reads it. Local checks decide. You accept.</p>
    </header>
    {state.stage === 'failed' && <div className="r2s-failed" role="alert">
      <p>{state.error}</p>
      {r2s.saved && r2s.saved.length > 0 && <p className="twin-quiet">Every reading here is a live Gemini 4 Argon call. If one fails, a labelled saved run is in the fallback list below; it never stands in for a live reading.</p>}
    </div>}
    {picking && <SourcePicker r2s={r2s} />}
    {state.provenanceLabel && !picking && <p className={`r2s-provenance is-${state.provenance ?? 'live'}`}>{state.provenanceLabel}</p>}
    {(running || state.thoughts.length > 0) && <Progress state={state} />}
    {(state.stage === 'ready' || state.stage === 'accepting' || state.stage === 'accepted') && <Review r2s={r2s} furniture={furniture} />}
    {state.stage !== 'idle' && !picking && <button type="button" className="btn r2s-start-over" onClick={r2s.reset}><RotateCcw size={14} aria-hidden="true" />Start over</button>}
    {state.stage === 'failed' && <button type="button" className="btn r2s-start-over" onClick={r2s.reset}><RotateCcw size={14} aria-hidden="true" />Clear</button>}
  </section>;
}

function SourcePicker({ r2s }: { r2s: Real2SimController }) {
  const [kind, setKind] = useState<SourceKind>('photo');
  const input = useRef<HTMLInputElement>(null);
  const pick = PICK[kind];
  const Icon = kind === 'video' ? Video : Camera;
  return <div className="r2s-source">
    <fieldset className="r2s-kinds">
      <legend>What are you showing it?</legend>
      {KINDS.map(item => <label key={item.kind} className={`r2s-kind${kind === item.kind ? ' is-on' : ''}`}>
        <input type="radio" name="r2s-kind" value={item.kind} checked={kind === item.kind} onChange={() => setKind(item.kind)} />{item.label}
      </label>)}
    </fieldset>
    {/* Picking a file starts the reading at once; the kind radios come first so the choice is made before the live call. */}
    <input ref={input} className="r2s-file" type="file" accept={pick.accept} {...(kind === 'pdf' || kind === 'video' ? {} : { capture: 'environment' as const })}
      aria-label={pick.aria} tabIndex={-1}
      onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) r2s.startFile(file, kind); }} />
    <button type="button" className="btn btn-primary r2s-pick" onClick={() => input.current?.click()}>
      <Icon size={16} aria-hidden="true" />{pick.label}
    </button>
    <SavedRuns r2s={r2s} />
  </div>;
}

function SavedRuns({ r2s }: { r2s: Real2SimController }) {
  const { saved, savedEnabled, savedError } = r2s;
  if (saved === null) return <p className="twin-quiet" role="status">Loading saved runs…</p>;
  // Live reading is the path; saved runs are a labelled fallback for when a live reading is slow or fails.
  return <details className="r2s-saved">
    <summary className="r2s-h3">Fallback: saved runs (recorded, not live)</summary>
    {savedError && <p className="door-advisory" role="alert">{savedError} <button type="button" className="btn btn-quiet" onClick={r2s.reloadSaved}>Retry</button></p>}
    {!savedEnabled && <p className="twin-quiet">Saved runs are switched off on this server.</p>}
    {savedEnabled && saved.length === 0 && !savedError && <p className="twin-quiet">No saved runs are available.</p>}
    <ul className="r2s-saved-list">
      {saved.map(run => <li key={run.fixture_id}>
        <button type="button" className="r2s-run" onClick={() => r2s.startSaved(run.fixture_id)}>
          <span className="r2s-run-title">{run.title}</span>
          <span className="r2s-run-meta">{run.source_kind}{countsLine(run.counts) ? ` · ${countsLine(run.counts)}` : ''}</span>
          <span className={`r2s-run-prov is-${run.provenance}`}>{run.provenance_label}</span>
        </button>
      </li>)}
    </ul>
  </details>;
}

function useElapsed(state: Real2SimState): number {
  const [now, setNow] = useState(() => Date.now());
  const running = isRunning(state.stage);
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const end = running ? now : state.finishedAt ?? now;
  return state.startedAt === null ? 0 : end - state.startedAt;
}

function Progress({ state }: { state: Real2SimState }) {
  const elapsed = useElapsed(state);
  const running = isRunning(state.stage);
  const steps = progressSteps(state.stage, state.rounds.length > 0);
  const counts = countsLine(state.counts);
  const log = useRef<HTMLOListElement>(null);
  useEffect(() => { const el = log.current; if (el) el.scrollTop = el.scrollHeight; }, [state.thoughts.length]);
  return <div className="r2s-progress">
    <ol className="r2s-steps" aria-label="Progress">
      {steps.map(step => <li key={step.key} className={`is-${step.state}`} aria-current={step.state === 'active' ? 'step' : undefined}>
        {step.state === 'active' && <LoaderCircle size={12} className="spin" aria-hidden="true" />}{step.label}
      </li>)}
    </ol>
    <p className="twin-quiet r2s-line" role="status">
      {running ? `Working · ${elapsedLabel(elapsed)}` : `Took ${elapsedLabel(elapsed)}`}
      {counts ? ` · ${counts}` : ''}
      {state.transport === 'polling' && running ? ' · live stream lost, checking every 1.5 s' : ''}
    </p>
    {state.rounds.length > 0 && <ul className="r2s-rounds">{state.rounds.map(round => <li key={round.round}>{roundLine(round)}</li>)}</ul>}
    <div className="r2s-thoughts">
      <h3 className="r2s-h3" id="r2s-thoughts-h">Argon&rsquo;s reasoning</h3>
      {/* Model text, rendered as text nodes only; bold headings come from splitting, never from HTML. */}
      <ol ref={log} className="r2s-thought-list" aria-labelledby="r2s-thoughts-h" aria-live="polite" aria-relevant="additions" tabIndex={0}>
        {state.thoughts.length === 0 && <li className="twin-quiet">{running ? 'Waiting for Argon to think. Short drawings may show none.' : 'No reasoning summaries were recorded.'}</li>}
        {state.thoughts.map(thought => <li key={thought.id}>
          {thoughtSegments(thought.text).map((part, index) => part.bold ? <strong key={index}>{part.text}</strong> : <span key={index}>{part.text}</span>)}
          {thought.recorded && <small className="r2s-recorded"> recorded</small>}
        </li>)}
      </ol>
    </div>
  </div>;
}

/** The optional furniture edit on a ready draft: a working copy drawn on the stage until it is saved or dropped. */
interface FurnitureEdit {
  editing: VenueFurniture[] | null;
  shown: VenueV2 | null;
  bridge: FurnitureEditBridge | undefined;
  selectedId: string | null;
  saving: boolean;
  error: string | null;
  start: () => void;
  change: (next: VenueFurniture[]) => void;
  select: (id: string | null) => void;
  save: () => void;
  cancel: () => void;
}

function useFurnitureEdit(r2s: Real2SimController, preview: VenueV2 | null): FurnitureEdit {
  const { state } = r2s;
  const [editing, setEditing] = useState<VenueFurniture[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A new draft, Start over or Accept drops an unsaved edit.
  useEffect(() => { setEditing(null); setSelectedId(null); setError(null); }, [state.draftId, state.epoch]);
  useEffect(() => { if (state.stage !== 'ready') { setEditing(null); setSelectedId(null); } }, [state.stage]);
  const previewRef = useRef(preview);
  previewRef.current = preview;
  const onMove = useCallback((id: string, position: Point2) => {
    const base = previewRef.current;
    if (base) setEditing(current => current && movePiece(base, current, id, position));
  }, []);
  const shown = useMemo(() => (preview && editing ? withFurniture(preview, editing) : preview), [preview, editing]);
  const bridge = useMemo(() => (editing ? { selectedId, onSelect: setSelectedId, onMove } : undefined), [editing !== null, selectedId, onMove]); // eslint-disable-line react-hooks/exhaustive-deps
  const save = () => {
    if (!editing || !state.draftId || state.revision === null) return;
    setSaving(true); setError(null);
    saveFurniture(state.draftId, state.revision, furniturePayload(editing))
      .then(() => r2s.refresh())
      .then(() => { setEditing(null); setSelectedId(null); })
      .catch(failure => setError(failure instanceof ApiError ? failure.message : 'The furniture could not be saved. Try again.'))
      .finally(() => setSaving(false));
  };
  return {
    editing, shown, bridge, selectedId, saving, error,
    start: () => { if (preview) { setEditing(furnitureOf(preview)); setError(null); } },
    change: setEditing, select: setSelectedId, save,
    cancel: () => { setEditing(null); setSelectedId(null); setError(null); },
  };
}

function Review({ r2s, furniture }: { r2s: Real2SimController; furniture: FurnitureEdit }) {
  const { state } = r2s;
  const view = state.view;
  if (!view) return null;
  const receipt = receiptView(view);
  const accepted = state.stage === 'accepted' && state.accepted;
  const editable = !accepted && state.stage === 'ready' && view.preview !== null;
  let action;
  if (accepted) action = <AcceptedNote accepted={state.accepted as AcceptResponse} />;
  else if (furniture.editing && view.preview) action = <FurnitureEditor venue={view.preview} furniture={furniture.editing} onChange={furniture.change}
    selectedId={furniture.selectedId} onSelect={furniture.select} onSave={furniture.save} onCancel={furniture.cancel} saving={furniture.saving} error={furniture.error} />;
  else action = <>
    {editable && <div className="r2s-review-actions">
      <button type="button" className="btn" onClick={furniture.start}><Armchair size={14} aria-hidden="true" />Edit furniture</button>
      <span className="twin-quiet">Optional. You can accept straight away.</span>
    </div>}
    <AcceptForm r2s={r2s} />
  </>;
  return <div className="r2s-review">
    <p className={`r2s-receipt is-${receipt.tone}`}>
      <span className="r2s-chip">{receipt.provenance}</span>
      {[receipt.model, receipt.latency, receipt.tokens, receipt.thinking].filter(Boolean).map(text => <span key={text} className="r2s-chip">{text}</span>)}
    </p>
    <Real2SimEvidence view={view} overlaySrc={view.overlay_available ? overlayUrl(view.draft_id, view.revision) : null} topdownSrc={view.topdown_available ? topdownUrl(view.draft_id, view.revision) : null} />
    {action}
  </div>;
}

function AcceptedNote({ accepted }: { accepted: AcceptResponse }) {
  return <div className="r2s-accepted" role="status">
    <p><CheckCircle2 size={16} aria-hidden="true" /> Accepted. <code>{accepted.venue_id}</code>{accepted.active_revision !== null ? ' is now the active venue.' : ' was stored.'}</p>
    {accepted.warnings.length > 0 && <ul className="r2s-list">{accepted.warnings.map((issue, index) => <li key={index}>{issue.message}</li>)}</ul>}
    {accepted.defaults.length > 0 && <details><summary>{accepted.defaults.length} declared default{accepted.defaults.length === 1 ? '' : 's'}</summary><ul className="r2s-list">{accepted.defaults.map((text, index) => <li key={index}>{text}</li>)}</ul></details>}
  </div>;
}

function AcceptForm({ r2s }: { r2s: Real2SimController }) {
  const { state } = r2s;
  const view = state.view!;
  const max = view.max_controllable_doors || MAX_CONTROLLABLE_DOORS;
  const [selected, setSelected] = useState<string[]>([]);
  const [headcount, setHeadcount] = useState('');
  const [width, setWidth] = useState('');
  // A conflict refresh can change the candidate list; selections that no longer exist are dropped.
  const chosen = reconcileSelection(selected, view.controllable_door_candidates, max);
  const headcountRead = readHeadcount(headcount);
  const widthRead = readBuildingWidth(width);
  const reason = acceptDisabledReason({
    stage: state.stage, blockers: view.accept_blockers,
    headcountError: headcountRead.ok ? undefined : headcountRead.message, widthError: widthRead.ok ? undefined : widthRead.message,
  });
  const submit = () => {
    if (reason || !headcountRead.ok || !widthRead.ok) return;
    r2s.accept({ controllableDoors: chosen, headcount: headcountRead.value, buildingWidthM: widthRead.value, makeActive: true });
  };
  return <form className="r2s-accept" onSubmit={event => { event.preventDefault(); submit(); }} aria-label="Accept this building">
    {view.controllable_door_candidates.length > 0 && <fieldset className="r2s-doors">
      <legend>Controllable doors <span className="twin-quiet">(up to {max}; the rest stay fixed)</span></legend>
      {view.controllable_door_candidates.map(door => {
        const on = chosen.includes(door.key);
        const rooms = door.room_names.length === 2 ? `${door.room_names[0]} ↔ ${door.room_names[1]}` : door.between.join(' ↔ ');
        return <label key={door.key} className={`r2s-door${on ? ' is-on' : ''}`}>
          <input type="checkbox" checked={on} disabled={!on && chosen.length >= max} onChange={() => setSelected(toggleDoor(chosen, door.key, max))}
            aria-label={`Motorized door ${door.key}: ${door.room_names.length === 2 ? `${door.room_names[0]} to ${door.room_names[1]}` : door.between.join(' to ')}`} />
          <span>{rooms}<small> door {door.key}{door.symbol ? ` · ${door.symbol}` : ''}</small></span>
        </label>;
      })}
    </fieldset>}
    <div className="r2s-fields">
      <label className="r2s-field">Headcount (optional)
        <input type="text" inputMode="numeric" autoComplete="off" value={headcount} onChange={event => setHeadcount(event.target.value)} aria-invalid={!headcountRead.ok} placeholder="e.g. 40" />
      </label>
      <label className="r2s-field">Building width, m (optional)
        <input type="text" inputMode="decimal" autoComplete="off" value={width} onChange={event => setWidth(event.target.value)} aria-invalid={!widthRead.ok} placeholder="e.g. 24" />
      </label>
    </div>
    {state.acceptNotice && <p className="door-advisory" role="status">{state.acceptNotice}</p>}
    {state.acceptError && <p className="door-advisory" role="alert">{state.acceptError}</p>}
    <button type="submit" className="btn btn-primary r2s-accept-btn" disabled={Boolean(reason)} aria-describedby={reason ? 'r2s-accept-why' : undefined}>
      {state.stage === 'accepting' ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <CheckCircle2 size={14} aria-hidden="true" />}Accept this building
    </button>
    {reason && state.stage !== 'accepting' && <p id="r2s-accept-why" className="twin-quiet r2s-why">{reason}</p>}
    <p className="twin-quiet">Accepting stores the venue and makes it the active one. Nothing changes before that.</p>
  </form>;
}
