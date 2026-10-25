import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { X } from 'lucide-react';

export const SHEET_TABS = [
  { id: 'forecast', label: 'Forecast' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'schedule', label: 'Schedule' },
  { id: 'review', label: 'Review' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'upload', label: 'Upload' },
] as const;
export type SheetTab = typeof SHEET_TABS[number]['id'];

interface Props {
  open: boolean;
  tab: SheetTab;
  onTab: (tab: SheetTab) => void;
  onClose: () => void;
  panels: Record<SheetTab, ReactNode>;
}

/** Right-side sheet on a native modal dialog: focus is trapped, Escape closes, focus returns to the opener. */
export function DetailsSheet({ open, tab, onTab, onClose, panels }: Props) {
  const id = useId();
  const dialogRef = useRef<HTMLDialogElement>(null);
  // A panel mounts on its first visit and then stays, so its local state survives tab switches and reopening.
  const [visited, setVisited] = useState<Set<SheetTab>>(() => new Set([tab]));
  useEffect(() => { if (open) setVisited(current => current.has(tab) ? current : new Set(current).add(tab)); }, [open, tab]);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  const move = (event: KeyboardEvent<HTMLButtonElement>) => {
    const index = SHEET_TABS.findIndex(item => item.id === tab);
    const next = event.key === 'ArrowRight' ? index + 1 : event.key === 'ArrowLeft' ? index - 1 : event.key === 'Home' ? 0 : event.key === 'End' ? SHEET_TABS.length - 1 : null;
    if (next === null) return;
    event.preventDefault();
    const target = SHEET_TABS[(next + SHEET_TABS.length) % SHEET_TABS.length].id;
    onTab(target);
    document.getElementById(`${id}-${target}-tab`)?.focus();
  };
  return <dialog ref={dialogRef} className="sheet" aria-labelledby={`${id}-title`} onCancel={event => { event.preventDefault(); onClose(); }} onClose={onClose} onClick={event => { if (event.target === dialogRef.current) onClose(); }}>
    <div className="sheet-surface">
      <header className="sheet-header"><h2 id={`${id}-title`}>Details</h2><button type="button" className="btn btn-icon" onClick={onClose} aria-label="Close details"><X size={18} aria-hidden="true" /></button></header>
      <div className="sheet-tabs" role="tablist" aria-label="Details sections">{SHEET_TABS.map(item => <button key={item.id} type="button" role="tab" id={`${id}-${item.id}-tab`} aria-selected={tab === item.id} aria-controls={`${id}-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onClick={() => onTab(item.id)} onKeyDown={move}>{item.label}</button>)}</div>
      <div className="sheet-body">{SHEET_TABS.map(item => <div key={item.id} id={`${id}-${item.id}`} role="tabpanel" aria-labelledby={`${id}-${item.id}-tab`} className="sheet-panel" hidden={tab !== item.id}>{visited.has(item.id) && panels[item.id]}</div>)}</div>
    </div>
  </dialog>;
}
