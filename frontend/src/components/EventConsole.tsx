import { useEffect, useRef, useState } from 'react';
import { Pause, Play, Trash2 } from 'lucide-react';
import { getActivityView, pauseActivity, type ActivitySnapshot } from '../ai/interactions';
import { TerminalPane } from './TerminalPane';
export interface WorkspaceEvent { id: number; at: string; source: 'system' | 'scenario' | 'planner' | 'vision' | 'analysis' | 'device'; message: string; level: 'info' | 'success' | 'warning'; }
interface Props { events: WorkspaceEvent[]; connected: boolean; onClear: () => void; }

const FILTERS = [{ id: 'all', label: 'All' }, { id: 'model', label: 'Model' }, { id: 'ai', label: 'AI' }];
const FOOTNOTE = 'Illustrative schematic · synthetic population · modeled crossings, not survival.';

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
  const pauseLabel = paused ? `Resume activity (${bufferedCount} new)` : 'Pause activity';
  return <TerminalPane id="activity" title="Activity" status={<><i className={`terminal-dot${connected ? ' is-on' : ''}`} aria-hidden="true" />{connected ? 'live' : 'reconnecting'}{paused && ` · paused · ${bufferedCount} new`}</>}
    actions={<>
      <div className="terminal-filters" role="group" aria-label="Activity filters">{FILTERS.map(item => <button key={item.id} type="button" onClick={() => setFilter(item.id)} aria-pressed={filter === item.id}>{item.label}</button>)}</div>
      <button type="button" className="terminal-icon" onClick={() => paused ? resume() : setHeld(pauseActivity(events))} aria-label={pauseLabel} title={pauseLabel}>{paused ? <Play size={14} aria-hidden="true" /> : <Pause size={14} aria-hidden="true" />}</button>
      <button type="button" className="terminal-icon" onClick={clear} aria-label="Clear activity" title="Clear activity"><Trash2 size={14} aria-hidden="true" /></button>
    </>}
    footer={FOOTNOTE}>
    <div className="terminal-body" ref={scrollRef} role="log" tabIndex={0} aria-label="Recorded application events" aria-live={paused ? 'off' : undefined} aria-relevant="additions">
      {filtered.length ? filtered.map(event => <div key={event.id} className={`t-line t-${event.level}`}><time dateTime={event.at}>{new Date(event.at).toLocaleTimeString('en-GB', { hour12: false })}</time><span className="t-src">{event.source}</span><span className="t-msg">{event.message}</span></div>) : <div className="t-empty">{paused ? 'Paused.' : visibleEvents.length ? 'No events match this filter.' : 'Waiting for events.'}</div>}
    </div>
  </TerminalPane>;
}
