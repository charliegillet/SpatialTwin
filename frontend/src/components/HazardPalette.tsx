import { Eraser, Flame, Minus, Plus, Wind } from 'lucide-react';
import { FIRE_HINT, SMOKE_MAX, SMOKE_MIN, smokeHint, stepSmokeSeconds, type HazardTool } from '../ai/hazardTools';

interface Props {
  tool: HazardTool | null;
  onTool: (tool: HazardTool | null) => void;
  smokeSeconds: number;
  onSmokeSeconds: (seconds: number) => void;
  /** Hotspots are locked while an analysis runs. */
  locked: boolean;
  notice: string | null;
  forecast: { text: string; pending: boolean } | null;
  forecastError: string | null;
}

const TOOLS: { id: HazardTool; label: string; hint: string; icon: typeof Flame }[] = [
  { id: 'fire', label: 'Fire', hint: FIRE_HINT, icon: Flame },
  { id: 'smoke', label: 'Smoke', hint: '', icon: Wind },
  { id: 'clear', label: 'Clear', hint: 'Removes a hazard', icon: Eraser },
];

/** Hazards for the twin: pick a tool, then tap P1, P2 or B2. Fire changes the scenario; smoke only forecasts. */
export function HazardPalette({ tool, onTool, smokeSeconds, onSmokeSeconds, locked, notice, forecast, forecastError }: Props) {
  const active = TOOLS.find(item => item.id === tool);
  const hintFor = (id: HazardTool) => id === 'smoke' ? smokeHint(smokeSeconds) : TOOLS.find(item => item.id === id)!.hint;
  return <section className="hazard-palette" aria-label="Hazards">
    <div className="seg" role="group" aria-label="Hazard tool">
      {TOOLS.map(item => <button key={item.id} type="button" aria-pressed={tool === item.id} onClick={() => onTool(tool === item.id ? null : item.id)} title={hintFor(item.id)}><item.icon size={14} aria-hidden="true" />{item.label}</button>)}
    </div>
    {tool === 'smoke' && <div className="smoke-stepper" role="group" aria-label="Smoke arrival time">
      <span id="smoke-time-label">Smoke closes it at</span>
      <button type="button" className="btn btn-icon" aria-label="Earlier by 2 seconds" onClick={() => onSmokeSeconds(stepSmokeSeconds(smokeSeconds, -1))} disabled={smokeSeconds <= SMOKE_MIN}><Minus size={14} aria-hidden="true" /></button>
      <output aria-labelledby="smoke-time-label" className="smoke-value">{smokeSeconds} s</output>
      <button type="button" className="btn btn-icon" aria-label="Later by 2 seconds" onClick={() => onSmokeSeconds(stepSmokeSeconds(smokeSeconds, 1))} disabled={smokeSeconds >= SMOKE_MAX}><Plus size={14} aria-hidden="true" /></button>
    </div>}
    <p className="hazard-hint">{locked ? 'Analysis running. Hotspots are locked.' : active ? `${hintFor(active.id)}. Tap P1, P2 or B2 on the model.` : 'Pick a hazard, then tap a pad.'}</p>
    {notice && <p className="hazard-notice" role="status">{notice}</p>}
    {forecastError && <p className="hazard-notice is-error" role="alert">{forecastError}</p>}
    {forecast && <p className="hazard-forecast" role="status" aria-busy={forecast.pending}><span className="chip chip-info">Forecast</span><span>{forecast.pending ? 'Forecasting…' : forecast.text}</span></p>}
  </section>;
}
