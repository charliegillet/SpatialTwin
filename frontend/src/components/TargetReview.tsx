import type { Ref } from 'react';
import { Check, LoaderCircle, X } from 'lucide-react';

export interface TargetOption { id: string; title: string; }
interface Props {
  reviewRef: Ref<HTMLElement>;
  targets: TargetOption[];
  target: string;
  blocked: boolean;
  busy: boolean;
  disabled: boolean;
  onChange: (target: string) => void;
  onApply: () => void;
  onClose: () => void;
}

/** Manual scenario change for the target picked on the model. Nothing changes until Apply. */
export function TargetReview({ reviewRef, targets, target, blocked, busy, disabled, onChange, onApply, onClose }: Props) {
  return <section ref={reviewRef} className="stage-review" aria-label="Review scenario change">
    <select aria-label="Scenario target" value={target} onChange={event => onChange(event.target.value)}>{targets.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>
    <button type="button" className="btn btn-primary" disabled={disabled} onClick={onApply}>{busy ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}{blocked ? 'Restore' : 'Block'}</button>
    <button type="button" className="btn btn-icon" aria-label="Cancel scenario change" onClick={onClose}><X size={16} aria-hidden="true" /></button>
  </section>;
}
