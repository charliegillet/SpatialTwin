import { useEffect, useId, useMemo, useState } from 'react';
import { Activity, ChevronDown, ChevronLeft, ChevronRight, Pause, Play, RotateCcw, Table2 } from 'lucide-react';
import type { ScenarioSnapshot } from '../../types';
import { clampFrameIndex, getCheckedSchedule, HOLDING_ZONES } from './schedule';
import type { CheckedSchedule } from './schedule';
import './ScheduleExplorer.css';

export interface ScheduleExplorerProps {
  snapshot: ScenarioSnapshot | null;
  isCurrent: boolean;
}

const CHART = { width: 680, height: 160, left: 0, right: 0, top: 8, bottom: 8 };

function ScheduleChart({ schedule, selectedIndex }: { schedule: CheckedSchedule; selectedIndex: number }) {
  const frame = schedule.frames[selectedIndex];
  const plotWidth = CHART.width - CHART.left - CHART.right;
  const plotHeight = CHART.height - CHART.top - CHART.bottom;
  const x = (time: number) => CHART.left + time / schedule.horizonSeconds * plotWidth;
  const y = (count: number) => CHART.top + plotHeight - (schedule.population > 0 ? count / schedule.population : 0) * plotHeight;
  const path = schedule.frames.map((item, index) => index === 0
    ? `M ${x(item.time_seconds)} ${y(item.total_completed)}`
    : `H ${x(item.time_seconds)} V ${y(item.total_completed)}`).join(' ');
  const yTicks = [...new Set([0, Math.floor(schedule.population / 2), schedule.population])];
  const xTicks = [...new Set([0, Math.floor((schedule.frames.length - 1) / 2) * schedule.stepSeconds, schedule.horizonSeconds])];
  return <figure className="schedule-chart">
    <figcaption><span>Completed boundary crossings</span><span>Stored model frames</span></figcaption>
    <div className="schedule-chart-layout"><div className="schedule-chart-y-axis" aria-hidden="true">{yTicks.map(tick => <span key={tick} style={{ top: `${y(tick) / CHART.height * 100}%` }}>{tick}</span>)}</div><div className="schedule-chart-plot">
      <svg viewBox={`0 0 ${CHART.width} ${CHART.height}`} preserveAspectRatio="none" role="img" aria-label={`Cumulative modeled crossings over ${schedule.horizonSeconds} seconds. At ${frame.time_seconds} seconds, ${frame.total_completed} of ${schedule.population} synthetic occupants have crossed. The full data is available in the frame table.`}>
        {yTicks.map(tick => <line key={`y-${tick}`} x1={CHART.left} x2={CHART.width - CHART.right} y1={y(tick)} y2={y(tick)} className="schedule-chart-grid" />)}
        <path d={path} className="schedule-chart-series" />
        <line x1={x(frame.time_seconds)} x2={x(frame.time_seconds)} y1={CHART.top} y2={CHART.height - CHART.bottom} className="schedule-chart-cursor" />
        <circle cx={x(frame.time_seconds)} cy={y(frame.total_completed)} r="4" className="schedule-chart-point" />
      </svg>
      <div className="schedule-chart-x-axis" aria-hidden="true">{xTicks.map(tick => <span key={tick} style={{ left: `${tick / schedule.horizonSeconds * 100}%`, transform: `translateX(${tick === 0 ? '0' : tick === schedule.horizonSeconds ? '-100%' : '-50%'})` }}>{tick}s</span>)}</div>
    </div></div>
  </figure>;
}

export function ScheduleExplorer({ snapshot, isCurrent }: ScheduleExplorerProps) {
  const id = useId();
  const schedule = useMemo(() => getCheckedSchedule(snapshot, isCurrent), [snapshot, isCurrent]);
  const key = schedule.available ? schedule.key : `unavailable:${schedule.kind}`;
  const [position, setPosition] = useState({ key, index: 0 });
  const [playingKey, setPlayingKey] = useState<string | null>(null);
  const [pageVisible, setPageVisible] = useState(() => typeof document === 'undefined' || document.visibilityState !== 'hidden');
  const frameCount = schedule.available ? schedule.frames.length : 0;
  const index = position.key === key ? clampFrameIndex(position.index, frameCount) : 0;
  const isPlaying = schedule.available && pageVisible && playingKey === key;

  useEffect(() => {
    setPosition({ key, index: 0 });
    setPlayingKey(null);
  }, [key]);

  useEffect(() => {
    const onVisibilityChange = () => {
      const visible = document.visibilityState !== 'hidden';
      setPageVisible(visible);
      if (!visible) { setPlayingKey(null); setPosition({ key, index: 0 }); }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [key]);

  useEffect(() => {
    if (!isPlaying || frameCount < 2) return;
    const timer = window.setInterval(() => {
      setPosition(previous => ({ key, index: clampFrameIndex((previous.key === key ? previous.index : 0) + 1, frameCount) }));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [isPlaying, frameCount, key]);

  useEffect(() => {
    if (isPlaying && index === frameCount - 1) setPlayingKey(null);
  }, [isPlaying, index, frameCount]);

  const selectFrame = (next: number) => {
    setPlayingKey(null);
    setPosition({ key, index: clampFrameIndex(next, frameCount) });
  };
  const togglePlayback = () => {
    if (!schedule.available || frameCount < 2 || !pageVisible) return;
    if (isPlaying) { setPlayingKey(null); return; }
    if (index === frameCount - 1) setPosition({ key, index: 0 });
    setPlayingKey(key);
  };
  const frame = schedule.available ? schedule.frames[index] : null;

  return <section id="schedule-explorer" className="schedule-explorer" tabIndex={-1} aria-labelledby={`${id}-title`}>
    <header className="schedule-header"><div><Activity size={16} aria-hidden="true" /><h2 id={`${id}-title`}>Computed schedule</h2></div><span>Model schedule · synthetic population</span></header>
    {!schedule.available || !frame ? <div className="schedule-unavailable" role="status"><p>{schedule.available ? 'No model frames are available.' : schedule.message}</p><span>Playback inspects numerical results and never requests physical movement.</span></div> : <div className="schedule-content">
      <div className="schedule-frame-heading"><h3>At <span>{frame.time_seconds}s</span></h3><span>{index + 1} of {frameCount} computed frames</span></div>
      <dl className="schedule-totals">
        <div><dt>Completed crossings</dt><dd>{frame.total_completed}<span> / {schedule.population}</span></dd></div>
        <div><dt>Remaining in model</dt><dd>{schedule.population - frame.total_completed}</dd></div>
        <div><dt>Through B1</dt><dd>{frame.b1_cumulative}</dd></div>
        <div><dt>Through B2</dt><dd>{frame.b2_cumulative}</dd></div>
      </dl>
      <ScheduleChart schedule={schedule} selectedIndex={index} />
      <div className="schedule-controls">
        <div className="schedule-transport"><button type="button" onClick={() => selectFrame(0)} aria-label="Restart schedule at zero" title="Restart"><RotateCcw size={15} aria-hidden="true" /></button><button type="button" onClick={() => selectFrame(index - 1)} disabled={index === 0} aria-label="Previous computed frame" title="Previous frame"><ChevronLeft size={17} aria-hidden="true" /></button><button type="button" className="schedule-play" onClick={togglePlayback} aria-label={isPlaying ? 'Pause computed schedule' : 'Play computed schedule'} aria-pressed={isPlaying}>{isPlaying ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}<span>{isPlaying ? 'Pause' : 'Play'}</span></button><button type="button" onClick={() => selectFrame(index + 1)} disabled={index === frameCount - 1} aria-label="Next computed frame" title="Next frame"><ChevronRight size={17} aria-hidden="true" /></button></div>
        <div className="schedule-scrubber"><label className="schedule-sr-only" htmlFor={`${id}-time`}>Model time</label><input id={`${id}-time`} type="range" min={0} max={frameCount - 1} step={1} value={index} onChange={event => selectFrame(Number(event.target.value))} aria-valuetext={`${frame.time_seconds} seconds: ${frame.total_completed} completed, ${schedule.population - frame.total_completed} remaining`} /><output htmlFor={`${id}-time`}>{frame.time_seconds}s<span> / {schedule.horizonSeconds}s</span></output></div>
      </div>
      <div className="schedule-holding"><div><h3>Population in the model</h3><p>Holding states after arrivals and crossings, before departures.</p></div><dl>{HOLDING_ZONES.map(zone => <div key={zone.id}><dt>{zone.label}</dt><dd>{frame[zone.field]}</dd></div>)}<div><dt>In transfer</dt><dd>{frame.in_transit_occupancy}</dd></div></dl></div>
      <div className="schedule-notes"><span>{isPlaying ? 'Playing one stored frame per second.' : 'Use the slider or arrow keys to inspect stored frames.'}</span><span>Aggregate model output · no individual trajectories</span></div>
      <details className="schedule-table-details"><summary><Table2 size={14} aria-hidden="true" /><span>All computed frames</span><span>{frameCount} rows</span><ChevronDown className="schedule-table-chevron" size={14} aria-hidden="true" /></summary><div className="schedule-table-scroll" tabIndex={0} role="region" aria-label="Computed frame data, scroll horizontally for all columns"><table><caption>Every synthetic occupant is either holding, in transfer, or counted as a completed crossing.</caption><thead><tr><th scope="col">Time</th><th scope="col">Completed</th><th scope="col">Remaining</th><th scope="col">B1</th><th scope="col">B2</th>{HOLDING_ZONES.map(zone => <th scope="col" key={zone.id}>{zone.label}</th>)}<th scope="col">In transfer</th></tr></thead><tbody>{schedule.frames.map((item, itemIndex) => <tr key={item.step} data-selected={itemIndex === index || undefined}><th scope="row">{item.time_seconds}s</th><td>{item.total_completed}</td><td>{schedule.population - item.total_completed}</td><td>{item.b1_cumulative}</td><td>{item.b2_cumulative}</td>{HOLDING_ZONES.map(zone => <td key={zone.id}>{item[zone.field]}</td>)}<td>{item.in_transit_occupancy}</td></tr>)}</tbody></table></div></details>
      <p className="schedule-run-reference">Run <span>{schedule.runId}</span></p>
    </div>}
  </section>;
}

export default ScheduleExplorer;
