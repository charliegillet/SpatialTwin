import { useEffect, useRef, useState } from 'react';
import { ArrowDown, Check, Pause, Play, Terminal, Trash2 } from 'lucide-react';
import { getActivityView, pauseActivity, type ActivitySnapshot } from '../ai/interactions';
export interface WorkspaceEvent { id: number; at: string; source: 'system' | 'scenario' | 'planner' | 'vision' | 'analysis' | 'device'; message: string; level: 'info' | 'success' | 'warning'; }
interface Props { events: WorkspaceEvent[]; connected: boolean; onClear: () => void; }
export function EventConsole({ events, connected, onClear }: Props) {
  const [filter, setFilter] = useState('all');
  const [held, setHeld] = useState<ActivitySnapshot<WorkspaceEvent> | null>(null);
  const paused = held !== null;
  const scrollRef = useRef<HTMLDivElement>(null);
  const { events: visibleEvents, bufferedCount } = getActivityView(events, held);
  const filtered = visibleEvents.filter(event => filter === 'all' || (filter === 'model' ? event.source === 'planner' || event.source === 'scenario' : event.source === 'vision' || event.source === 'analysis'));
  const newestEventId = visibleEvents[visibleEvents.length - 1]?.id;
  useEffect(() => { if (!paused && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [newestEventId, filter, paused]);
  const resume = () => {
    setHeld(null);
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight,
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }));
  };
  const clear = () => { onClear(); if (paused) setHeld(pauseActivity([])); };
  return <section className="event-console" aria-labelledby="console-title">
    <header className="panel-header"><div><Terminal size={15} aria-hidden="true" /><h2 id="console-title">Activity stream</h2><span className="console-live"><i className={connected ? 'is-connected' : ''} />{connected ? 'Connected' : 'Reconnecting'}</span></div><div className="console-tools"><button className="icon-button" onClick={() => paused ? resume() : setHeld(pauseActivity(events))} aria-pressed={paused} aria-label={paused ? 'Resume activity stream' : 'Pause activity stream'} title={paused ? 'Resume activity stream' : 'Pause activity stream'}>{paused ? <Play size={13} aria-hidden="true" /> : <Pause size={13} aria-hidden="true" />}</button><button className="icon-button" onClick={clear} aria-label="Clear activity stream" title="Clear activity stream"><Trash2 size={13} aria-hidden="true" /></button></div></header>
    <div className="console-toolbar"><div className="console-filters" role="group" aria-label="Activity filters">{['all', 'model', 'ai'].map(item => <button key={item} onClick={() => setFilter(item)} className={filter === item ? 'is-active' : ''} aria-pressed={filter === item}>{item === 'all' ? 'All events' : item === 'model' ? 'Model' : 'AI'}{item === 'all' && <span>{visibleEvents.length}</span>}</button>)}</div><span><span className="console-prompt">&gt;_</span> LOCAL SESSION</span></div>
    <div className="console-output" ref={scrollRef} role="log" tabIndex={0} aria-label="Recorded application events" aria-live={paused ? 'off' : 'polite'} aria-relevant="additions" aria-atomic={false}><div className="console-session-heading"><span>SPATIALTWIN / EVENT LEDGER</span><span>ACTUAL APPLICATION EVENTS</span></div>
      {filtered.length ? filtered.map(event => <div key={event.id} className={`console-event console-event-${event.level}`}><time dateTime={event.at}>{new Date(event.at).toLocaleTimeString('en-GB', { hour12: false })}</time><span className={`console-source console-source-${event.source}`}>{event.source}</span><span className="console-message">{event.message}</span>{event.level === 'success' && <Check size={11} aria-hidden="true" />}</div>) : <div className="console-empty"><Terminal size={21} strokeWidth={1} aria-hidden="true" /><p>{paused ? 'Activity paused.' : visibleEvents.length ? 'No events match this filter.' : 'Your next action starts the story.'}</p><span>{paused ? 'New events continue buffering. Resume when you are ready.' : 'Scenario changes, model results and device events appear here.'}</span></div>}
      {!paused && <div className="console-cursor"><span>›</span><i /></div>}
    </div><footer className="console-footer"><span><i />{paused ? 'Paused · incoming events buffered' : 'Listening for application events'}</span><button onClick={resume}>{paused ? `${bufferedCount} new · Resume` : `${filtered.length} ${filtered.length === 1 ? 'event' : 'events'}`}<ArrowDown size={10} aria-hidden="true" /></button></footer>
  </section>;
}
