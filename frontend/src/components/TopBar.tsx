import { useEffect, useRef, useState, type Ref } from 'react';
import { Expand, LoaderCircle, OctagonX, PanelRight, Settings2, Shrink, UserRoundPlus } from 'lucide-react';
import type { Chip } from '../ai/stageView';
import type { OperatorOutcome } from '../ai/operator';

interface Props {
  hardware: Chip;
  checked: Chip;
  connection: 'connecting' | 'connected' | 'reconnecting';
  presenting: boolean;
  presenterRef: Ref<HTMLButtonElement>;
  onTogglePresenting: () => void;
  onStop: () => Promise<OperatorOutcome>;
  onOpenDetails: () => void;
  onToggleMenu: () => void;
  menuOpen: boolean;
  menuRef: Ref<HTMLButtonElement>;
  onResetJudge: () => void;
  isResetting: boolean;
  canReset: boolean;
}

export function TopBar({ hardware, checked, connection, presenting, presenterRef, onTogglePresenting, onStop, onOpenDetails, onToggleMenu, menuOpen, menuRef, onResetJudge, isResetting, canReset }: Props) {
  const [stopping, setStopping] = useState(false);
  const [outcome, setOutcome] = useState<OperatorOutcome | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);
  const stop = async () => {
    if (stopping) return;
    clearTimeout(timer.current);
    setStopping(true); setOutcome(null);
    let result: OperatorOutcome;
    try { result = await onStop(); }
    catch (failure) { result = { ok: false, message: failure instanceof Error ? failure.message : 'Stop not confirmed.' }; }
    setStopping(false); setOutcome(result);
    timer.current = setTimeout(() => setOutcome(null), 10_000);
  };
  return <header className="topbar">
    <a className="wordmark" href="#workspace-main" aria-label="SpatialTwin">SpatialTwin<span className="wordmark-dot" aria-hidden="true" /></a>
    <div className="topbar-chips" role="status" aria-label="System status">
      {connection !== 'connected' && <span className="chip chip-warn">{connection === 'connecting' ? 'Connecting…' : 'Reconnecting…'}</span>}
      <span className={`chip chip-${hardware.tone}`}>{hardware.label}</span>
      <span className={`chip chip-${checked.tone}`}>{checked.label}</span>
    </div>
    {outcome && <span className={`topbar-toast${outcome.ok ? '' : ' is-error'}`} role={outcome.ok ? 'status' : 'alert'} title={outcome.message}>{outcome.message}</span>}
    <div className="topbar-actions">
      <button type="button" className="btn" onClick={onResetJudge} disabled={!canReset || isResetting} title="Cancel any run, clear hazards, close P3 and wait for the endpoint"><UserRoundPlus size={15} aria-hidden="true" /><span className="btn-label">{isResetting ? 'Resetting…' : 'Next judge'}</span></button>
      <button type="button" ref={presenterRef} className="btn btn-ghost" onClick={onTogglePresenting} aria-pressed={presenting} aria-label={presenting ? 'Exit presenter mode' : 'Present'}>{presenting ? <Shrink size={15} aria-hidden="true" /> : <Expand size={15} aria-hidden="true" />}<span className="btn-label">{presenting ? 'Exit' : 'Present'}</span></button>
      <button type="button" className="btn btn-stop" onClick={() => void stop()} disabled={stopping} aria-label="Stop outputs">{stopping ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <OctagonX size={15} aria-hidden="true" />}<span className="btn-label">Stop</span></button>
      <button type="button" ref={menuRef} className="btn btn-icon" onClick={onToggleMenu} aria-expanded={menuOpen} aria-controls="presenter-menu" aria-label="Presenter menu" title="Presenter menu"><Settings2 size={16} aria-hidden="true" /></button>
      <button type="button" className="btn" onClick={onOpenDetails} aria-haspopup="dialog"><PanelRight size={15} aria-hidden="true" /><span className="btn-label">Details</span></button>
    </div>
  </header>;
}
