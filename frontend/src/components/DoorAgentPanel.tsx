import { useEffect, useState } from 'react';
import { Bot, LoaderCircle, X } from 'lucide-react';
import { askLabel, elapsedLabel, phaseLine, resultView } from '../twin/doorAgent';
import type { DoorAgentController } from '../twin/useDoorAgent';

/** "Ask the agent": a managed Gemini agent (or the local solver) investigates door states through read-only checker tools. The checker decides. */
export function DoorAgentPanel({ agent }: { agent: DoorAgentController }) {
  const { state, analysisMode, unavailable } = agent;
  const running = state.status === 'running';
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [running]);
  const view = state.result ? resultView(state.result) : null;
  return <section className="door-agent" aria-label="Door agent" aria-busy={running}>
    <div className="door-agent-actions">
      <button type="button" className="btn" disabled={Boolean(unavailable)} title={unavailable ?? 'Investigate door states through read-only checker tools'} onClick={agent.ask}>
        {running ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Bot size={14} aria-hidden="true" />}{askLabel(analysisMode)}
      </button>
      {running && <button type="button" className="btn" onClick={agent.cancel}><X size={14} aria-hidden="true" />Cancel</button>}
    </div>
    {running && <p className="twin-quiet" role="status">Working · {elapsedLabel(now - (state.startedAt ?? now))}{state.events.length ? ` · ${phaseLine(state.events)}` : ''}</p>}
    {state.status === 'failed' && <p className="door-advisory" role="alert">{state.error}</p>}
    {view && <div className={`door-agent-result is-${view.tone}`} role="status">
      <span className="door-agent-chip">{view.chip}</span>
      {view.explanation && <p className="door-agent-said"><small>{view.attribution}</small>{view.explanation}</p>}
      {view.decided && <p className="door-agent-decided"><strong>{view.decided}</strong></p>}
      {view.agreement && <p className="door-agent-agreement">{view.agreement}</p>}
      {view.tools.length > 0 && <details><summary>{view.tools.length} checker call{view.tools.length === 1 ? '' : 's'}</summary><ul>{view.tools.map((line, index) => <li key={index}>{line}</li>)}</ul></details>}
      <p className="twin-quiet">{view.disclaimer}</p>
    </div>}
  </section>;
}
