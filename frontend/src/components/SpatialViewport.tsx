import React, { useId, useRef, useState } from 'react';
import { ArrowUpRight, Box, Check, Layers2, Minus, Plus, RotateCcw, Scan } from 'lucide-react';
import { clampPan, forecastTargets, formatForecastClosure, panByKey, type ForecastClosure, type Pan } from '../features/spatial-view/spatialView';
import type { ScenarioSnapshot } from '../types';
import './SpatialViewport.css';

type SpatialTarget = 'portal:P1' | 'portal:P2' | 'boundary:B2';
interface SpatialViewportProps {
  snapshot: ScenarioSnapshot | null;
  selectedTarget: string | null;
  onSelectTarget: (target: SpatialTarget) => void;
  onInspectPlan?: () => void;
  forecast?: ForecastClosure[];
}
type Point = [number, number];
type Project = (x: number, y: number, height?: number) => Point;
type Wall = [number, number, number, number, number?];

// Coordinates follow the four modeled zones in venue/reviewed_venue.json,
// translated by (-50, -50). Screen projection is illustrative, never metric.
const ZONES = [
  { id: 'EVENT', title: 'Main event hall', x: 0, y: 0, width: 300, height: 200, label: [138, 92] },
  { id: 'WEST', title: 'West corridor', x: 0, y: 220, width: 120, height: 150, label: [48, 284] },
  { id: 'EAST', title: 'East corridor', x: 180, y: 220, width: 120, height: 150, label: [238, 288] },
  { id: 'RESERVE', title: 'Reserve', x: 130, y: 210, width: 40, height: 120, label: [150, 287] },
];

const WALLS: Wall[] = [
  [0, 0, 300, 0, 32], [0, 0, 0, 200, 32], [300, 0, 300, 200, 32],
  [0, 200, 35, 200], [85, 200, 125, 200], [175, 200, 215, 200], [265, 200, 300, 200],
  [0, 220, 35, 220], [85, 220, 120, 220], [0, 220, 0, 370], [120, 220, 120, 370],
  [0, 370, 38, 370, 14], [82, 370, 120, 370, 14],
  [180, 220, 215, 220], [265, 220, 300, 220], [300, 220, 300, 370],
  [180, 220, 180, 266], [180, 294, 180, 370],
  [180, 370, 218, 370, 14], [262, 370, 300, 370, 14],
  [130, 210, 130, 330, 17], [170, 210, 170, 266, 17], [170, 294, 170, 330, 17],
  [130, 330, 170, 330, 14],
];

const TARGETS: { id: SpatialTarget; short: string; title: string; x: number; y: number }[] = [
  { id: 'portal:P1', short: 'P1', title: 'West passage', x: 60, y: 210 },
  { id: 'portal:P2', short: 'P2', title: 'East passage', x: 240, y: 210 },
  { id: 'boundary:B2', short: 'B2', title: 'East boundary', x: 240, y: 374 },
];

function points(values: Point[]) { return values.map(value => value.join(',')).join(' '); }

function WallPrism({ wall, project, flat }: { wall: Wall; project: Project; flat: boolean }) {
  const [x1, y1, x2, y2, specifiedHeight = 24] = wall;
  const half = 2.8;
  const height = flat ? 0 : specifiedHeight;
  const horizontal = y1 === y2;
  const corners: Point[] = horizontal
    ? [[x1, y1 - half], [x2, y2 - half], [x2, y2 + half], [x1, y1 + half]]
    : [[x1 - half, y1], [x2 - half, y2], [x2 + half, y2], [x1 + half, y1]];
  const top = corners.map(([x, y]) => project(x, y, height));
  const base = corners.map(([x, y]) => project(x, y));
  return <g className="spatial-wall">
    {!flat && <>
      <polygon points={points([base[1], base[2], top[2], top[1]])} fill="#a0afaa" />
      <polygon points={points([base[2], base[3], top[3], top[2]])} fill="#b9c6bf" />
      <polygon points={points([base[0], base[3], top[3], top[0]])} fill="#ced8d0" />
    </>}
    <polygon points={points(top)} fill="#ecf0e5" stroke="#f9fbef" strokeWidth="0.7" />
    {!flat && <polyline points={points([top[0], top[1], top[2]])} fill="none" stroke="#ffffff" strokeOpacity=".72" strokeWidth="1" />}
  </g>;
}

export const SpatialViewport: React.FC<SpatialViewportProps> = ({ snapshot, selectedTarget, onSelectTarget, onInspectPlan, forecast }) => {
  // The model is drawn wide; on phone-width screens it is unreadable at 1x, so the default view is closer.
  const defaultZoom = () => (typeof window !== 'undefined' && window.matchMedia?.('(max-width: 520px)').matches ? 1.25 : 1);
  const [zoom, setZoom] = useState(defaultZoom);
  const [pan, setPan] = useState<Pan>({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ x: number; y: number; scale: number } | null>(null);
  const [flat, setFlat] = useState(false);
  const uid = useId().replace(/:/g, '');
  const plan = snapshot?.current_plan;
  const context = snapshot?.context;
  const checked = Boolean(plan && context && plan.validator_report?.is_valid
    && ['COMPLETE_WITHIN_MODEL', 'PARTIAL_WITHIN_HORIZON', 'NO_FEASIBLE_EXIT'].includes(plan.status)
    && plan.base_context.geometry_revision === context.geometry_revision
    && plan.base_context.scenario_revision === context.scenario_revision
    && plan.base_context.physical_revision === context.physical_revision
    && plan.base_context.parameters_revision === context.parameters_revision
    && plan.base_context.solver_version === context.solver_version
    && plan.alternative_id === 'KEEP_CURRENT');
  const gate = snapshot?.physical_gate_state ?? 'UNKNOWN';
  const hasEndpointReceipt = Boolean(snapshot?.last_hardware_boot_id && (snapshot.last_gate_epoch ?? 0) > 0);
  const reserveConfirmed = gate === 'OPEN' && checked && hasEndpointReceipt;
  const gateLabel = gate === 'OPEN' ? (reserveConfirmed ? 'OPEN · RECEIPT' : 'OPEN · REPORTED') : gate;
  const isBlocked = (id: SpatialTarget) => id === 'boundary:B2'
    ? Boolean(snapshot?.blocked_boundaries.includes('B2'))
    : Boolean(snapshot?.blocked_portals.includes(id.slice(7)));
  const p1Flow = checked && !isBlocked('portal:P1') && (plan?.boundary_breakdown.B1 ?? 0) > 0;
  const eastFlow = checked && !isBlocked('boundary:B2') && (plan?.boundary_breakdown.B2 ?? 0) > 0;
  const p2Flow = eastFlow && !isBlocked('portal:P2');
  const reserveFlow = reserveConfirmed && eastFlow && isBlocked('portal:P2');
  const blockedTargets = TARGETS.filter(target => isBlocked(target.id));
  const project: Project = flat
    ? (x, y) => [260 + x * 1.65, 54 + y * 1.38]
    : (x, y, height = 0) => [540 + (x - y) * 1.22, 146 + (x + y) * .58 - height];
  const polygon = (x: number, y: number, w: number, h: number, z = 0) => points([
    project(x, y, z), project(x + w, y, z), project(x + w, y + h, z), project(x, y + h, z),
  ]);
  const line = (path: Point[]) => path.map(([x, y], index) => `${index ? 'L' : 'M'} ${project(x, y).join(' ')}`).join(' ');
  const gatePosition = project(150, 205);
  const viewBox = flat ? '100 0 850 640' : '0 72 1060 520';
  const bounds = flat ? { width: 850, height: 640 } : { width: 1060, height: 520 };
  const forecastByTarget = new Map(forecastTargets(forecast).map(item => [item.target, item.close_at_s]));
  const changeZoom = (delta: number) => {
    const next = Math.max(.75, Math.min(1.65, Math.round((zoom + delta) * 100) / 100));
    setZoom(next); setPan(current => clampPan(current, next, bounds));
  };
  const resetView = () => { setZoom(defaultZoom()); setPan({ x: 0, y: 0 }); };
  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.pointerType === 'touch' || event.button !== 0) return;
    const ctm = event.currentTarget.getScreenCTM();
    if (!ctm || !ctm.a) return;
    drag.current = { x: event.clientX, y: event.clientY, scale: ctm.a };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };
  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const start = drag.current;
    if (!start) return;
    const dx = (event.clientX - start.x) / start.scale, dy = (event.clientY - start.y) / start.scale;
    drag.current = { ...start, x: event.clientX, y: event.clientY };
    setPan(current => clampPan({ x: current.x + dx, y: current.y + dy }, zoom, bounds));
  };
  const endDrag = () => { drag.current = null; setDragging(false); };
  const onModelKeyDown = (event: React.KeyboardEvent<SVGSVGElement>) => {
    const delta = panByKey(event.key);
    if (!delta) return;
    event.preventDefault();
    setPan(current => clampPan({ x: current.x + delta.x, y: current.y + delta.y }, zoom, bounds));
  };
  const panned = pan.x !== 0 || pan.y !== 0;

  const route = (path: Point[], active: boolean, key: string) => <g key={key} className={active ? 'spatial-route spatial-route--active' : 'spatial-route'}>
    <path d={line(path)} className="spatial-route-bed" />
    <path d={line(path)} className="spatial-route-line" markerEnd={active ? `url(#${uid}-arrow)` : undefined} />
  </g>;

  return <section className="spatial-panel" aria-label="Interactive spatial model">
    <header className="spatial-panel-header">
      <div className="spatial-panel-heading"><Box size={16} strokeWidth={1.5} /><h2>Spatial model</h2><span className="spatial-panel-slash">/</span><span>Tabletop 01</span></div>
      <div className="spatial-view-switch" role="group" aria-label="Model view">
        <button type="button" className={!flat ? 'is-active' : ''} onClick={() => setFlat(false)} aria-pressed={!flat}><Box size={13} />Cutaway</button>
        <button type="button" className={flat ? 'is-active' : ''} onClick={() => setFlat(true)} aria-pressed={flat}><Layers2 size={13} />Plan</button>
      </div>
    </header>

    <div className="spatial-canvas">
      <div className="spatial-scene-caption"><div>Illustrative floor plan</div><span>4 modeled zones · synthetic population</span></div>
      <div className={`spatial-result-indicator ${checked ? 'is-checked' : ''}`}><span />{checked ? 'Checked result' : snapshot ? 'Result unverified' : 'Awaiting model'}</div>

      <svg className={`spatial-model-svg ${dragging ? 'is-dragging' : ''}`} role="group" tabIndex={0} viewBox={viewBox} aria-label="Illustrative event hall with west, east and reserve corridors. Drag or use arrow keys to pan. Select P1, P2 or B2 to review a scenario change."
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endDrag} onPointerCancel={endDrag} onKeyDown={onModelKeyDown}>
        <defs>
          <linearGradient id={`${uid}-floor`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#303e3b" /><stop offset="1" stopColor="#1c2928" /></linearGradient>
          <linearGradient id={`${uid}-event`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#34433e" /><stop offset="1" stopColor="#293934" /></linearGradient>
          <radialGradient id={`${uid}-shadow`}><stop stopColor="#000" stopOpacity=".6" /><stop offset="1" stopColor="#000" stopOpacity="0" /></radialGradient>
          <marker id={`${uid}-arrow`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 1 1 L 7 5 L 1 9" fill="none" stroke="#bcf582" strokeWidth="1.5" /></marker>
          <clipPath id={`${uid}-floor-clip`}><polygon points={polygon(-14, -14, 328, 400)} /></clipPath>
        </defs>
        <g transform={`translate(${530 * (1 - zoom) + pan.x} ${345 * (1 - zoom) + pan.y}) scale(${zoom})`} className="spatial-model-camera">
          {!flat && <ellipse cx="498" cy="483" rx="460" ry="159" fill={`url(#${uid}-shadow)`} />}
          {!flat && <>
            <polygon points={points([project(-14, 386), project(314, 386), project(314, 386, -12), project(-14, 386, -12)])} fill="#1a2625" stroke="#41504b" strokeWidth=".6" />
            <polygon points={points([project(314, -14), project(314, 386), project(314, 386, -12), project(314, -14, -12)])} fill="#24332f" stroke="#41504b" strokeWidth=".6" />
          </>}
          <polygon points={polygon(-14, -14, 328, 400)} fill={`url(#${uid}-floor)`} stroke="#485953" strokeWidth="1" />
          <g clipPath={`url(#${uid}-floor-clip)`} className="spatial-floor-grid">
            {Array.from({ length: 18 }, (_, i) => <path key={`grid-x-${i}`} d={line([[-20 + i * 20, -20], [-20 + i * 20, 400]])} />)}
            {Array.from({ length: 22 }, (_, i) => <path key={`grid-y-${i}`} d={line([[-20, -20 + i * 20], [330, -20 + i * 20]])} />)}
          </g>

          {ZONES.map(zone => <polygon key={zone.id} points={polygon(zone.x, zone.y, zone.width, zone.height)} fill={zone.id === 'EVENT' ? `url(#${uid}-event)` : '#2a3b35'} fillOpacity={zone.id === 'EVENT' ? '.88' : '.7'} stroke="#637565" strokeOpacity=".26" strokeWidth=".8" />)}

          {/* White architectural rims preserve the canonical plan's four zones. */}
          <g className="spatial-architectural-insets">
            <polygon points={polygon(10, 10, 280, 180)} /><polygon points={polygon(10, 230, 100, 130)} /><polygon points={polygon(190, 230, 100, 130)} />
            {Array.from({ length: 9 }, (_, i) => <path key={`back-grid-${i}`} d={line([[30 + i * 30, 3], [30 + i * 30, 10]])} />)}
          </g>

          {route([[80, 113], [60, 147], [60, 210], [60, 264], [60, 355], [60, 384]], p1Flow, 'west')}
          {route([[208, 118], [240, 151], [240, 210], [240, 252], [240, 355], [240, 384]], Boolean(p2Flow), 'east')}
          {reserveFlow && route([[150, 152], [150, 204], [150, 280], [240, 280], [240, 358]], true, 'reserve')}
          {!reserveFlow && <path d={line([[150, 190], [150, 280], [190, 280]])} className={`spatial-reserve-path ${reserveConfirmed ? 'is-confirmed' : ''}`} />}

          {TARGETS.filter(target => isBlocked(target.id)).map(target => <g key={`closure-${target.id}`} className="spatial-closure">
            <polygon points={polygon(target.x - 22, target.y - 6, 44, 12)} />
            <path d={line([[target.x - 9, target.y - 4], [target.x + 9, target.y + 4]])} />
            <path d={line([[target.x + 9, target.y - 4], [target.x - 9, target.y + 4]])} />
          </g>)}

          {TARGETS.filter(target => forecastByTarget.has(target.id)).map(target => <polygon key={`forecast-${target.id}`} className="spatial-forecast-outline" points={polygon(target.x - 27, target.y - 14, 54, 28)} />)}

          {WALLS.map((wall, index) => <WallPrism key={`wall-${index}`} wall={wall} project={project} flat={flat} />)}
          {/* Reported position and checked route availability remain separate. */}
          {(gate === 'OPEN' || gate === 'CLOSED')
            ? <WallPrism wall={gate === 'OPEN' ? [126, 201, 126, 222, 12] : [127, 202, 173, 202, 12]} project={project} flat={flat} />
            : <path d={line([[127, 202], [173, 202]])} className="spatial-reserve-path" />}

          {ZONES.map(zone => {
            const [x, y] = project(zone.label[0], zone.label[1]);
            const reserve = zone.id === 'RESERVE';
            return <g key={`label-${zone.id}`} className={`spatial-room-label ${reserve ? 'spatial-room-label--small' : ''}`} transform={`translate(${x} ${y})`}>
              <text y={0} textAnchor="middle">{zone.title}</text>
              {!reserve && <text y="17" textAnchor="middle" className="spatial-room-subtitle">{zone.id === 'EVENT' ? 'SCHEMATIC / EVENT' : `ZONE / ${zone.id}`}</text>}
            </g>;
          })}

          {TARGETS.map(target => {
            const [x, y] = project(target.x, target.y);
            const selected = selectedTarget === target.id;
            const blocked = isBlocked(target.id);
            return <g key={target.id} role="button" tabIndex={0} aria-label={`${target.short}: ${target.title}, ${blocked ? 'blocked' : 'available'}. Select for review.`} aria-pressed={selected}
              onClick={() => onSelectTarget(target.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectTarget(target.id); } }}
              className={`spatial-model-target ${selected ? 'is-selected' : ''} ${blocked ? 'is-blocked' : ''}`}>
              <polygon className="spatial-target-hitbox" points={polygon(target.x - 27, target.y - 15, 54, 30)} />
              <polygon className="spatial-target-outline" points={polygon(target.x - 23, target.y - 10, 46, 20)} />
              <g transform={`translate(${x} ${y - (flat ? 0 : 31)})`}>
                {!flat && <line className="spatial-target-stem" x1="0" y1="14" x2="0" y2="30" />}
                <rect x="-26" y="-13" width="52" height="26" rx="5" className="spatial-target-badge" />
                <circle cx="-13" cy="0" r="2.5" className="spatial-target-dot" />
                <text x="5" y="4" textAnchor="middle">{target.short}</text>
                {forecastByTarget.has(target.id) && <g className="spatial-forecast-chip" transform="translate(0 25)">
                  <rect x="-62" y="-9" width="124" height="18" rx="4" /><text y="3.5" textAnchor="middle">{formatForecastClosure(forecastByTarget.get(target.id) ?? 0)}</text>
                </g>}
                {blocked && <g transform="translate(31 -18)"><circle r="9" className="spatial-blocked-mark" /><path d="M-3-3 3 3M3-3-3 3" className="spatial-blocked-cross" /></g>}
              </g>
            </g>;
          })}

          <g className={`spatial-gate-label ${reserveConfirmed ? 'is-confirmed' : ''}`} transform={`translate(${gatePosition[0] + (flat ? 48 : 36)} ${gatePosition[1] - (flat ? 0 : 34)})`}>
            <circle cx="-8" cy="-3" r="2.5" /><text x="0" y="0">P3 · {gateLabel}</text>
          </g>
          <g className="spatial-boundary-label" transform={`translate(${project(60, 388)[0]} ${project(60, 388)[1] + 14})`}><text textAnchor="middle">B1 / WEST BOUNDARY</text></g>
          <g className="spatial-boundary-label" transform={`translate(${project(240, 398)[0]} ${project(240, 398)[1] + 18})`}><text textAnchor="middle">B2 / EAST BOUNDARY</text></g>
        </g>
      </svg>

      <div className="spatial-zoom-controls" role="group" aria-label="View controls">
        <button type="button" onClick={() => changeZoom(.15)} disabled={zoom >= 1.65} aria-label="Zoom in"><Plus size={16} /></button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => changeZoom(-.15)} disabled={zoom <= .75} aria-label="Zoom out"><Minus size={16} /></button>
        <i /><button type="button" onClick={resetView} aria-label="Reset zoom and pan"><RotateCcw size={14} /></button>
      </div>
      <div className="spatial-view-legend"><span><i className="spatial-legend-route" />Checked boundary flow</span><span><i className="spatial-legend-wall" />Modeled architecture</span>{forecastByTarget.size > 0 && <span><i className="spatial-legend-forecast" />Forecast closure · modeled</span>}{blockedTargets.length > 0 && <span><i className="spatial-legend-blocked" />Blocked target</span>}</div>
      <div className="spatial-axis" aria-hidden="true"><svg viewBox="0 0 58 43"><path d="M29 34V9M29 34 5 22M29 34 53 22" /><text x="27" y="6">Z</text><text x="0" y="21">X</text><text x="53" y="21">Y</text></svg><span>SCHEMATIC</span></div>
    </div>

    <div className="spatial-selection-bar">
      <span className="spatial-selection-hint"><Scan size={15} /><span>Select a target <small>Review before applying</small></span></span>
      <div className="spatial-target-buttons" role="group" aria-label="Select a scenario target">{TARGETS.map(target => <React.Fragment key={target.id}>
        <button type="button" onClick={() => onSelectTarget(target.id)} className={`${selectedTarget === target.id ? 'is-selected' : ''} ${isBlocked(target.id) ? 'is-blocked' : ''}`} aria-describedby={`${uid}-${target.short}-state`} aria-pressed={selectedTarget === target.id}><span>{target.short}</span>{' '}<span>{target.title}</span>{selectedTarget === target.id ? <Check size={12} aria-hidden="true" /> : <ArrowUpRight size={12} aria-hidden="true" />}</button>
        <span id={`${uid}-${target.short}-state`} hidden>{target.title}, {isBlocked(target.id) ? 'blocked' : 'available'}. Select for review.</span>
      </React.Fragment>)}</div>
    </div>
    <footer className="spatial-panel-footer"><span><i />{snapshot ? 'Canonical targets · P1 / P2 / B2' : 'Awaiting connection'}</span><span>Illustrative schematic · not a venue survey</span>{onInspectPlan && <button type="button" onClick={onInspectPlan}>Inspect plan<ArrowUpRight size={12} /></button>}</footer>
  </section>;
};
