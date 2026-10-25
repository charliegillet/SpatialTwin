import { Check, Circle } from 'lucide-react';
import { resetChecklist, type ResetFacts } from '../ai/resetFlow';

/** Four facts that must hold before the next judge. Each turns green when it is observed, not when requested. */
export function ResetChecklist({ facts, message, physical }: { facts: ResetFacts; message?: string | null; physical: boolean }) {
  const items = resetChecklist(facts, physical);
  return <div className="reset-checklist" role="status" aria-label="Ready for the next judge">
    <ul>{items.map(item => <li key={item.id} className={item.ok ? 'is-ok' : ''}>{item.ok ? <Check size={13} aria-hidden="true" /> : <Circle size={13} aria-hidden="true" />}<span>{item.label}</span><span className="sr-only">{item.ok ? 'ready' : 'waiting'}</span></li>)}</ul>
    {message && <p>{message}</p>}
  </div>;
}
