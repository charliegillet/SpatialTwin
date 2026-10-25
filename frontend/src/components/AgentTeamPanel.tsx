import { useState, type FormEvent } from 'react';
import { Bot, LoaderCircle, Send, X } from 'lucide-react';
import { isActive } from '../twin/agentTeamFlow';
import { MODELED_NOTE, connectionLabel, laneCard, teamFooter, teamLanes } from '../twin/agentTeamView';
import type { AgentTeamController } from '../twin/useAgentTeam';
import { AgentTeamLane } from './AgentTeamLane';
import './AgentTeam.css';

const ASK_LABEL = 'Ask the agent team';

/** "Ask the agent team": a Strategist and a Robustness managed agent (or the local solver) work in parallel; the local checker re-runs every number they claim. */
export function AgentTeamPanel({ team }: { team: AgentTeamController }) {
  const { run, follow, now, unavailable, analysisMode } = team;
  const active = isActive(run);
  const lanes = teamLanes(run);
  const [text, setText] = useState('');
  const footer = teamFooter(run);
  const idle = run.status === 'idle';
  const connection = connectionLabel(run);
  // One status line, rewritten only when a lane changes state: the only live region, so a stream of trace lines never interrupts a screen reader.
  const statusLine = lanes.map(lane => { const card = laneCard(run, lane, now); return `${card.title}: ${card.chip.text}`; }).join(' · ');
  const followBusy = isActive(follow);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim() || team.followUnavailable) return;
    team.askFollowUp(text);
    setText('');
  };

  return <section className="agent-team" aria-label="Agent team" aria-busy={active}>
    <div className="agent-team-actions">
      <button type="button" className="btn btn-primary" disabled={Boolean(unavailable)} title={unavailable ?? 'Two managed agents investigate door states; the checker re-runs their claims'} onClick={team.ask}>
        {active ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Bot size={14} aria-hidden="true" />}{ASK_LABEL} · {analysisMode === 'live' ? 'Live Gemini' : 'Local solver'}
      </button>
      {(active || followBusy) && <button type="button" className="btn" onClick={team.cancel}><X size={14} aria-hidden="true" />Cancel</button>}
    </div>
    {unavailable && !active && <p className="twin-quiet">{unavailable}.</p>}
    {team.auto && idle && !unavailable && <p className="twin-quiet" role="status">The team starts by itself in a moment for these hazards.</p>}
    {!idle && <p className="agent-status" role="status">{run.status === 'starting' ? 'Starting the team…' : run.status === 'cancelled' ? 'Cancelled.' : statusLine}</p>}
    {run.notice && <p className="twin-quiet">{run.notice}</p>}
    {connection && <p className="twin-quiet">{connection}</p>}
    {run.status === 'failed' && <p className="door-advisory" role="alert">{run.error}</p>}

    {lanes.length > 0 && <div className="agent-lanes">{lanes.map(lane => <AgentTeamLane key={lane} card={laneCard(run, lane, now)} />)}</div>}

    {!idle && run.status !== 'starting' && <footer className="agent-footer">
      {footer.claims && <p className={footer.mismatches ? 'is-mismatch' : 'is-ok'}><strong>{footer.claims}</strong>{footer.mismatches > 0 && ` · ${footer.mismatches} did not reproduce`}</p>}
      {footer.selfCheck && <p className="twin-quiet">{footer.selfCheck}</p>}
      <p><strong>{footer.note}</strong></p>
      <p className="twin-quiet">{MODELED_NOTE}</p>
    </footer>}

    {!idle && <div className="agent-followup">
      <form onSubmit={submit}>
        <label htmlFor="agent-followup-input">Ask a follow-up in the same sandbox</label>
        <div className="agent-followup-row">
          <input id="agent-followup-input" type="text" value={text} placeholder="What if D3 jams?" maxLength={80} autoComplete="off" disabled={Boolean(team.followUnavailable)}
            onChange={event => setText(event.target.value)} />
          <button type="submit" className="btn" disabled={Boolean(team.followUnavailable) || !text.trim()}><Send size={14} aria-hidden="true" />Ask</button>
        </div>
      </form>
      {team.followUnavailable ? <p className="twin-quiet">{team.followUnavailable}.</p> : team.suggestions.length > 0 && <ul className="agent-suggestions" aria-label="Suggested follow-ups">
        {team.suggestions.map(item => <li key={item.scenario}><button type="button" className="btn btn-quiet" onClick={() => team.askFollowUp(item.scenario)}>{item.label}</button></li>)}
      </ul>}
      {team.followError && <p className="door-advisory" role="alert">{team.followError}</p>}
      {follow.status !== 'idle' && <div className="agent-followup-result">
        {follow.notice && <p className="twin-quiet">{follow.notice}</p>}
        {follow.status === 'failed' && <p className="door-advisory" role="alert">{follow.error}</p>}
        {follow.order.includes('followup') && <AgentTeamLane card={laneCard(follow, 'followup', now)} />}
      </div>}
    </div>}
  </section>;
}
