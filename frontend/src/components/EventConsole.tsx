import { useEffect, useRef, useState } from 'react';
import { ArrowDown, Check, Pause, Play, Terminal, Trash2 } from 'lucide-react';
export interface WorkspaceEvent { id: number; at: string; source: 'system' | 'scenario' | 'planner' | 'vision' | 'analysis' | 'device'; message: string; level: 'info' | 'success' | 'warning'; }
interface Props { events: WorkspaceEvent[]; connected: boolean; onClear: () => void; }
export function EventConsole({ events, connected, onClear }: Props) {
  const [filter, setFilter] = useState('all');
  const [paused, setPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const filtered = events.filter(event => filter === 'all' || (filter === 'model' ? event.source === 'planner' || event.source === 'scenario' : event.source === 'vision' || event.source === 'analysis'));
  const newestEventId = events[events.length - 1]?.id;
  useEffect(() => { if (!paused && scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight; }, [newestEventId, filter, paused]);
  return <section className="event-console" aria-labelledby="console-title">
    <header className="panel-header"><div><Terminal size={15} /><h2 id="console-title">Activity stream</h2><span className="console-live"><i className={connected ? 'is-connected' : ''} />{connected ? 'Connected' : 'Reconnecting'}</span></div><div className="console-tools"><button className="icon-button" onClick={() => setPaused(!paused)} aria-label={paused ? 'Resume auto-scroll' : 'Pause auto-scroll'} title={paused ? 'Resume auto-scroll' : 'Pause auto-scroll'}>{paused ? <Play size={13} /> : <Pause size={13} />}</button><button className="icon-button" onClick={onClear} aria-label="Clear activity stream" title="Clear activity stream"><Trash2 size={13} /></button></div></header>
    <div className="console-toolbar"><div className="console-filters" aria-label="Activity filters">{['all', 'model', 'ai'].map(item => <button key={item} onClick={() => setFilter(item)} className={filter === item ? 'is-active' : ''} aria-pressed={filter === item}>{item === 'all' ? 'All events' : item === 'model' ? 'Model' : 'AI'}{item === 'all' && <span>{events.length}</span>}</button>)}</div><span><span className="console-prompt">&gt;_</span> LOCAL SESSION</span></div>
    <div className="console-output" ref={scrollRef} role="log" aria-label="Recorded application events"><div className="console-session-heading"><span>SPATIALTWIN / EVENT LEDGER</span><span>ACTUAL APPLICATION EVENTS</span></div>
      {filtered.length ? filtered.map(event => <div key={event.id} className={`console-event console-event-${event.level}`}><time dateTime={event.at}>{new Date(event.at).toLocaleTimeString('en-GB', { hour12: false })}</time><span className={`console-source console-source-${event.source}`}>{event.source}</span><span className="console-message">{event.message}</span>{event.level === 'success' && <Check size={11} />}</div>) : <div className="console-empty"><Terminal size={21} strokeWidth={1} /><p>{events.length ? 'No events match this filter.' : 'Your next action starts the story.'}</p><span>Scenario changes, model results and device events appear here.</span></div>}
      {!paused && <div className="console-cursor"><span>›</span><i /></div>}
    </div><footer className="console-footer"><span><i />{paused ? 'Auto-scroll paused · events still recorded' : 'Listening for application events'}</span><button onClick={() => { setPaused(false); scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' }); }}>{filtered.length} {filtered.length === 1 ? 'event' : 'events'}<ArrowDown size={10} /></button></footer>
  </section>;
}
