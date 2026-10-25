import { useEffect } from 'react';
import { ChevronDown, DoorClosed, DoorOpen, LockKeyhole, TriangleAlert, Volume2 } from 'lucide-react';
import { ANNOUNCE_LABEL, SPEECH_UNAVAILABLE, announcementText, speak, speechAvailable, stopSpeaking } from '../twin/announce';
import { FAILED_CHECK, NO_CHECKED_PLAN, alternativeRows, doorRows, gainFrom, groupDoorRows, planChecked, unsafeExits } from '../twin/twinHero';
import type { DoorPlanResponse } from '../twin/types';
import type { AgentTeamController } from '../twin/useAgentTeam';
import { AgentTeamPanel } from './AgentTeamPanel';

const SIMULATED = 'Simulated doors · a virtual door controller, no hardware';

/** The door decisions that changed, unsafe exits, advisories and the alternatives the planner compared. No approval: nothing physical moves. */
export function DoorPlanBar({ plan, pending, team }: { plan: DoorPlanResponse | null; pending: boolean; team?: AgentTeamController }) {
  const text = announcementText(plan);
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
  const Utterance = typeof window !== 'undefined' ? window.SpeechSynthesisUtterance : undefined;
  const canSpeak = speechAvailable(synth, Utterance);
  // A new plan, Clear, a mode switch or Next judge (unmount) silences a running announcement. Speech only ever starts from the button.
  useEffect(() => { stopSpeaking(synth); return () => stopSpeaking(synth); }, [text, synth]);
  if (!plan) return <section className="door-plan twin-card" aria-label="Door plan"><p className="twin-quiet">{pending ? 'Solving\u2026' : 'Waiting for the planner.'}</p><p className="twin-quiet">{SIMULATED}</p></section>;
  const rows = groupDoorRows(doorRows(plan));
  const unsafe = unsafeExits(plan);
  const alternatives = alternativeRows(plan);
  const checked = planChecked(plan);
  return <section className={`door-plan twin-card${pending ? ' is-pending' : ''}`} aria-label="Door plan" aria-busy={pending}>
    {rows.length === 0 && unsafe.length === 0 ? <p className="twin-quiet">No door changes. Every door stays at its default.</p> : <ul className="door-rows">
      {rows.map(row => {
        const gain = checked ? gainFrom(row.reason) : null;
        return <li key={row.ids.join()} className={`door-${row.tone}`}><details>
          <summary>{row.tone === 'open' ? <DoorOpen size={14} aria-hidden="true" /> : row.tone === 'locked' ? <LockKeyhole size={14} aria-hidden="true" /> : <DoorClosed size={14} aria-hidden="true" />}<strong>{row.ids.join(' ')}</strong><span>· {row.verb}{gain ? ` · ${gain}` : ''}</span></summary>
          <p>{row.reason}</p>
        </details></li>;
      })}
      {unsafe.map(exit => <li key={exit.id} className="door-closed"><details>
        <summary><TriangleAlert size={14} aria-hidden="true" /><strong>{exit.id}</strong><span>· unsafe</span></summary>
        <p>{exit.reason}</p>
      </details></li>)}
    </ul>}
    {!checked && <p className="door-advisory" role="alert">{NO_CHECKED_PLAN}</p>}
    {plan.hazards.some(item => item.source === 'camera') && <p className="twin-quiet">Includes confirmed camera cards. The plan is still local and hypothetical.</p>}
    {plan.advisories.map(text => <p key={text} className="door-advisory">{text}</p>)}
    {text && <div className="door-announce">
      <button type="button" className="btn" disabled={!canSpeak} title={canSpeak ? ANNOUNCE_LABEL : SPEECH_UNAVAILABLE} onClick={() => speak(synth, Utterance, text)}><Volume2 size={14} aria-hidden="true" />Announce<small>{ANNOUNCE_LABEL}</small></button>
      <p className="twin-quiet">{text}</p>
    </div>}
    <details className="door-alt">
      <summary>Alternatives<ChevronDown size={13} aria-hidden="true" /></summary>
      <table className="door-alternatives"><caption className="sr-only">Door states the planner compared</caption>
        <thead><tr><th scope="col">Rank</th><th scope="col">Doors</th><th scope="col">Crossings</th></tr></thead>
        <tbody>{alternatives.map(item => <tr key={`${item.rank}-${item.doors}`} className={item.chosen ? 'is-chosen' : undefined}>
          <td>{item.rank}</td><td>{item.doors}{item.valid ? '' : ` \u00b7 ${FAILED_CHECK}`}</td><td>{checked ? item.crossings : '\u2014'}</td></tr>)}</tbody></table>
    </details>
    {team && <AgentTeamPanel team={team} />}
    <p className="twin-quiet">Local solver · checker decided. {SIMULATED}</p>
  </section>;
}
