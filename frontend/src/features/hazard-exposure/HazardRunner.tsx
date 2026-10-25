import { FlaskConical, LoaderCircle, Plus, X } from 'lucide-react';
import { hazardElements } from '../../ai/hazardView';
import './HazardRunner.css';

export interface HazardRow { element_id: string; close_at_s: string; }
interface Props {
  rows: HazardRow[];
  onRows: (update: (rows: HazardRow[]) => HazardRow[]) => void;
  onRun: () => void;
  canRun: boolean;
  isSimulating: boolean;
  error: string | null;
}

export function HazardRunner({ rows, onRows, onRun, canRun, isSimulating, error }: Props) {
  return <section className="hazard-runner" aria-label="Run a hazard forecast">
    <h2>Forecast closures</h2>
    <p className="hazard-runner-note">Closures at known times. Forecast, not reactive replanning.</p>
    {rows.map((row, index) => <div className="hazard-runner-row" key={index}>
      <select aria-label={`Closure element ${index + 1}`} value={row.element_id} onChange={event => onRows(items => items.map((item, at) => at === index ? { ...item, element_id: event.target.value } : item))}>{hazardElements.map(id => <option key={id} value={id}>{id}</option>)}</select>
      <input aria-label={`Close at seconds ${index + 1}`} inputMode="numeric" value={row.close_at_s} onChange={event => onRows(items => items.map((item, at) => at === index ? { ...item, close_at_s: event.target.value } : item))} placeholder="seconds" />
      <button type="button" className="btn btn-icon" onClick={() => onRows(items => items.filter((_, at) => at !== index))} aria-label={`Remove closure ${index + 1}`}><X size={14} aria-hidden="true" /></button>
    </div>)}
    <div className="hazard-runner-actions">
      <button type="button" className="btn" onClick={() => onRows(items => [...items, { element_id: 'portal:P2', close_at_s: '12' }])} disabled={rows.length >= 6}><Plus size={14} aria-hidden="true" />Add closure</button>
      <button type="button" className="btn btn-primary" onClick={onRun} disabled={!canRun || isSimulating}>{isSimulating ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <FlaskConical size={14} aria-hidden="true" />}Run forecast</button>
    </div>
    {error && <p className="hazard-runner-error" role="alert">{error}</p>}
  </section>;
}
