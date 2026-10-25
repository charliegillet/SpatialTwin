import React, { useEffect, useId, useRef, useState } from 'react';
import { Minus, Plus, RotateCcw } from 'lucide-react';
import { clampPan, forecastTargets, formatForecastClosure, isDrag, panByKey, type ForecastClosure, type Pan } from '../features/spatial-view/spatialView';
import { arrowPolygon, exitArrows, plumePuffs, type Point as GeoPoint } from '../features/spatial-view/stageGeometry';
import type { ScenarioSnapshot } from '../types';
import type { HazardTool } from '../ai/hazardTools';
import './SpatialViewport.css';

type SpatialTarget = 'portal:P1' | 'portal:P2' | 'boundary:B2';
interface SpatialViewportProps {
  snapshot: ScenarioSnapshot | null;
  selectedTarget: string | null;
  onSelectTarget: (target: SpatialTarget) => void;
  forecast?: ForecastClosure[];
  /** The armed hazard tool: hotspots glow and a tap elsewhere reports through onBackgroundTap. */
  armedTool?: HazardTool | null;
  onBackgroundTap?: () => void;
  /** Smoke forecast: grey plumes on the smoke pads and dashed routes from the forecast's boundary counts (null when the server sent none). */
  smoke?: Partial<Record<SpatialTarget, number>>;
  forecastFlow?: Record<string, number> | null;
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

function WallPrism({ wall, project }: { wall: Wall; project: Project }) {
  const [x1, y1, x2, y2, height = 24] = wall;
  const half = 2.8;
  const horizontal = y1 === y2;
  const corners: Point[] = horizontal
    ? [[x1, y1 - half], [x2, y2 - half], [x2, y2 + half], [x1, y1 + half]]
    : [[x1 - half, y1], [x2 - half, y2], [x2 + half, y2], [x1 + half, y1]];
  const top = corners.map(([x, y]) => project(x, y, height));
  const base = corners.map(([x, y]) => project(x, y));
  return <g className="spatial-wall">
    <polygon points={points([base[1], base[2], top[2], top[1]])} fill="#a0afaa" />
    <polygon points={points([base[2], base[3], top[3], top[2]])} fill="#b9c6bf" />
    <polygon points={points([base[0], base[3], top[3], top[0]])} fill="#ced8d0" />
    <polygon points={points(top)} fill="#ecf0e5" stroke="#f9fbef" strokeWidth="0.7" />
    <polyline points={points([top[0], top[1], top[2]])} fill="none" stroke="#ffffff" strokeOpacity=".72" strokeWidth="1" />
  </g>;
}

const VIEW_BOX = '0 72 1060 520';
const BOUNDS = { width: 1060, height: 520 };
const project: Project = (x, y, height = 0) => [540 + (x - y) * 1.22, 146 + (x + y) * .58 - height];
// Screen direction of "outward" past the south boundaries (+y in model space).
const OUTWARD: Point = [project(0, 1)[0] - project(0, 0)[0], project(0, 1)[1] - project(0, 0)[1]];
const EXITS: { id: 'B1' | 'B2'; x: number }[] = [{ id: 'B1', x: 60 }, { id: 'B2', x: 240 }];
const PUFFS = plumePuffs(6, 165);

/** The physical token: a small coral prism standing on the blocked target. */
function TokenCube({ x, y }: { x: number; y: number }) {
  const s = 7, h = 20;
  const face = (corners: [number, number, number][]) => points(corners.map(([cx, cy, z]) => project(cx, cy, z)));
  return <g className="spatial-token">
    <polygon points={face([[x - s, y + s, 0], [x + s, y + s, 0], [x + s, y + s, h], [x - s, y + s, h]])} fill="#b55442" />
    <polygon points={face([[x + s, y - s, 0], [x + s, y + s, 0], [x + s, y + s, h], [x + s, y - s, h]])} fill="#da6d57" />
    <polygon points={face([[x - s, y - s, h], [x + s, y - s, h], [x + s, y + s, h], [x - s, y + s, h]])} fill="#fa9a7a" stroke="#ffbb96" strokeWidth=".8" />
  </g>;
}

export const SpatialViewport: React.FC<SpatialViewportProps> = ({ snapshot, selectedTarget, onSelectTarget, forecast, armedTool = null, onBackgroundTap, smoke, forecastFlow }) => {
  // The model is drawn wide; on phone-width screens it is unreadable at 1x, so the default view is closer.
  const defaultZoom = () => (typeof window !== 'undefined' && window.matchMedia?.('(max-width: 520px)').matches ? 1.05 : 1);
  const [zoom, setZoom] = useState(defaultZoom);
  const zoomChosen = useRef(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const [touchArmed, setTouchArmed] = useState(false);
  useEffect(() => {
    if (!touchArmed) return;
    const release = (event: PointerEvent) => { if (!svgRef.current?.contains(event.target as Node)) setTouchArmed(false); };
    document.addEventListener('pointerdown', release);
    return () => document.removeEventListener('pointerdown', release);
  }, [touchArmed]);
  useEffect(() => {
    // Follow rotation and resize until the viewer picks a zoom of their own.
    const query = window.matchMedia?.('(max-width: 520px)');
    if (!query) return;
    const onChange = () => { if (!zoomChosen.current) setZoom(defaultZoom()); };
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  const [pan, setPan] = useState<Pan>({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const drag = useRef<{ x: number; y: number; scale: number; captured: boolean } | null>(null);
  const downAt = useRef<{ x: number; y: number } | null>(null);
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
  const gateLabel = gate === 'OPEN' ? (reserveConfirmed ? 'OPEN · SWITCH CONFIRMED' : 'OPEN · REPORTED') : gate;
  const isBlocked = (id: SpatialTarget) => id === 'boundary:B2'
    ? Boolean(snapshot?.blocked_boundaries.includes('B2'))
    : Boolean(snapshot?.blocked_portals.includes(id.slice(7)));
  const p1Flow = checked && !isBlocked('portal:P1') && (plan?.boundary_breakdown.B1 ?? 0) > 0;
  const eastFlow = checked && !isBlocked('boundary:B2') && (plan?.boundary_breakdown.B2 ?? 0) > 0;
  const p2Flow = eastFlow && !isBlocked('portal:P2');
  const reserveFlow = reserveConfirmed && eastFlow && isBlocked('portal:P2');
  const blockedTargets = TARGETS.filter(target => isBlocked(target.id));
  const arrows = exitArrows({ checked, breakdown: plan?.boundary_breakdown, blockedBoundaries: snapshot?.blocked_boundaries });
  const polygon = (x: number, y: number, w: number, h: number, z = 0) => points([
    project(x, y, z), project(x + w, y, z), project(x + w, y + h, z), project(x, y + h, z),
  ]);
  const line = (path: Point[]) => path.map(([x, y], index) => `${index ? 'L' : 'M'} ${project(x, y).join(' ')}`).join(' ');
  const gatePosition = project(150, 205);
  const forecastByTarget = new Map(forecastTargets(forecast).map(item => [item.target, item.close_at_s]));
  const changeZoom = (delta: number) => {
    const next = Math.max(.75, Math.min(1.65, Math.round((zoom + delta) * 100) / 100));
    zoomChosen.current = true;
    setZoom(next); setPan(current => clampPan(current, next, BOUNDS));
  };
  const resetView = () => { zoomChosen.current = false; setZoom(defaultZoom()); setPan({ x: 0, y: 0 }); };
  const onPointerDown = (event: React.PointerEvent<SVGSVGElement>) => {
    if (event.button !== 0) return;
    downAt.current = { x: event.clientX, y: event.clientY };
    // A first touch only arms panning, so scrolling the page past the model keeps working.
    if (event.pointerType === 'touch' && !touchArmed) { setTouchArmed(true); return; }
    const ctm = event.currentTarget.getScreenCTM();
    if (!ctm || !ctm.a) return;
    // Capture waits for real movement: capturing on press would retarget a pad tap's click to the SVG.
    drag.current = { x: event.clientX, y: event.clientY, scale: ctm.a, captured: false };
  };
  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const start = drag.current;
    if (!start) return;
    if (!start.captured) {
      // Uncaptured, a release outside the SVG never reaches onPointerUp; a buttonless move ends that press.
      if (event.buttons === 0) { drag.current = null; return; }
      if (!isDrag(start, { x: event.clientX, y: event.clientY })) return;
      event.currentTarget.setPointerCapture(event.pointerId);
      setDragging(true);
    }
    const dx = (event.clientX - start.x) / start.scale, dy = (event.clientY - start.y) / start.scale;
    drag.current = { ...start, x: event.clientX, y: event.clientY, captured: true };
    setPan(current => clampPan({ x: current.x + dx, y: current.y + dy }, zoom, BOUNDS));
  };
  const onSvgClick = (event: React.MouseEvent<SVGSVGElement>) => {
    if (!armedTool || !onBackgroundTap || (event.target as Element).closest('.spatial-model-target')) return;
    const start = downAt.current;
    if (start && isDrag(start, { x: event.clientX, y: event.clientY })) return;
    onBackgroundTap();
  };
  const endDrag = () => { drag.current = null; setDragging(false); };
  const onModelKeyDown = (event: React.KeyboardEvent<SVGSVGElement>) => {
    const delta = panByKey(event.key);
    if (!delta) return;
    event.preventDefault();
    setPan(current => clampPan({ x: current.x + delta.x, y: current.y + delta.y }, zoom, BOUNDS));
  };

  const route = (path: Point[], active: boolean, key: string, variant = '') => <g key={key} className={`${active ? 'spatial-route spatial-route--active' : 'spatial-route'}${variant}`}>
    <path d={line(path)} className="spatial-route-bed" />
    <path d={line(path)} className="spatial-route-line" markerEnd={active && !variant ? `url(#${uid}-arrow)` : undefined} />
  </g>;
  const outward = (id: 'B1' | 'B2', distance: number): GeoPoint => {
    const base = project(EXITS.find(exit => exit.id === id)!.x, 392);
    const size = Math.hypot(OUTWARD[0], OUTWARD[1]);
    return [base[0] + OUTWARD[0] / size * distance, base[1] + OUTWARD[1] / size * distance];
  };

  return <section className="stage" aria-label="Interactive spatial model">
    <svg ref={svgRef} className={`stage-svg${dragging ? ' is-dragging' : ''}${touchArmed ? ' is-touch-armed' : ''}${forecastFlow ? ' has-forecast' : ''}${armedTool ? ' has-tool' : ''}`} role="group" tabIndex={0} viewBox={VIEW_BOX} aria-label="Illustrative event hall with west, east and reserve corridors. Drag or use arrow keys to pan; on a touch screen tap the model first, then drag. Select P1, P2 or B2 to review a scenario change, or pick a hazard tool and tap a pad."
      onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={endDrag} onPointerCancel={endDrag} onKeyDown={onModelKeyDown} onClick={onSvgClick}>
      <defs>
        <linearGradient id={`${uid}-floor`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#303e3b" /><stop offset="1" stopColor="#1c2928" /></linearGradient>
        <linearGradient id={`${uid}-event`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#34433e" /><stop offset="1" stopColor="#293934" /></linearGradient>
        <radialGradient id={`${uid}-shadow`}><stop stopColor="#000" stopOpacity=".6" /><stop offset="1" stopColor="#000" stopOpacity="0" /></radialGradient>
        <radialGradient id={`${uid}-plume`}><stop className="plume-core" offset="0" stopOpacity=".95" /><stop className="plume-core" offset=".6" stopOpacity=".8" /><stop className="plume-core" offset="1" stopOpacity="0" /></radialGradient>
        <filter id={`${uid}-soft`} x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="3.5" /></filter>
        <marker id={`${uid}-arrow`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="4" markerHeight="4" orient="auto-start-reverse"><path d="M 1 1 L 7 5 L 1 9" fill="none" stroke="#bcf582" strokeWidth="1.5" /></marker>
        <clipPath id={`${uid}-floor-clip`}><polygon points={polygon(-14, -14, 328, 400)} /></clipPath>
      </defs>
      <g transform={`translate(${530 * (1 - zoom) + pan.x} ${345 * (1 - zoom) + pan.y}) scale(${zoom})`} className="spatial-model-camera">
        <ellipse cx="498" cy="483" rx="460" ry="159" fill={`url(#${uid}-shadow)`} />
        <polygon points={points([project(-14, 386), project(314, 386), project(314, 386, -12), project(-14, 386, -12)])} fill="#1a2625" stroke="#41504b" strokeWidth=".6" />
        <polygon points={points([project(314, -14), project(314, 386), project(314, 386, -12), project(314, -14, -12)])} fill="#24332f" stroke="#41504b" strokeWidth=".6" />
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
        {forecastFlow && (forecastFlow.B1 ?? 0) > 0 && route([[80, 113], [60, 147], [60, 210], [60, 264], [60, 355], [60, 384]], true, 'forecast-west', ' spatial-route--forecast')}
        {forecastFlow && (forecastFlow.B2 ?? 0) > 0 && route([[208, 118], [240, 151], [240, 210], [240, 252], [240, 355], [240, 384]], true, 'forecast-east', ' spatial-route--forecast')}
        {reserveFlow && route([[150, 152], [150, 204], [150, 280], [240, 280], [240, 358]], true, 'reserve')}
        {!reserveFlow && <path d={line([[150, 190], [150, 280], [190, 280]])} className={`spatial-reserve-path ${reserveConfirmed ? 'is-confirmed' : ''}`} />}

        {blockedTargets.map(target => <g key={`closure-${target.id}`} className="spatial-closure">
          <polygon points={polygon(target.x - 22, target.y - 6, 44, 12)} />
          <path d={line([[target.x - 9, target.y - 4], [target.x + 9, target.y + 4]])} />
          <path d={line([[target.x + 9, target.y - 4], [target.x - 9, target.y + 4]])} />
        </g>)}

        {TARGETS.filter(target => forecastByTarget.has(target.id)).map(target => <polygon key={`forecast-${target.id}`} className="spatial-forecast-outline" points={polygon(target.x - 27, target.y - 14, 54, 28)} />)}

        {WALLS.map((wall, index) => <WallPrism key={`wall-${index}`} wall={wall} project={project} />)}
        {/* Reported position and checked route availability remain separate. */}
        {(gate === 'OPEN' || gate === 'CLOSED')
          ? <WallPrism wall={gate === 'OPEN' ? [126, 201, 126, 222, 12] : [127, 202, 173, 202, 12]} project={project} />
          : <path d={line([[127, 202], [173, 202]])} className="spatial-reserve-path" />}


        {/* Exit arrows: checked flow leaves through B1 and B2; a blocked boundary gets a dim marker instead. */}
        {arrows.map(arrow => arrow.state === 'flow'
          ? <g key={`exit-${arrow.id}`} className="stage-exit-arrow">
              <polygon points={points(arrowPolygon(outward(arrow.id, 34), outward(arrow.id, 118), 15, 46, 38))} />
            </g>
          : arrow.state === 'blocked'
            ? <g key={`exit-${arrow.id}`} className="stage-exit-blocked">{(() => { const [x, y] = outward(arrow.id, 52); return <path d={`M ${x - 14} ${y - 14} L ${x + 14} ${y + 14} M ${x + 14} ${y - 14} L ${x - 14} ${y + 14}`} />; })()}</g>
            : null)}
        {forecastFlow && exitArrows({ checked: true, breakdown: forecastFlow, blockedBoundaries: snapshot?.blocked_boundaries }).map(arrow => arrow.state === 'flow'
          ? <g key={`forecast-exit-${arrow.id}`} className="stage-exit-forecast"><polygon points={points(arrowPolygon(outward(arrow.id, 34), outward(arrow.id, 118), 15, 46, 38))} /></g>
          : arrow.state === 'none'
            ? <g key={`forecast-exit-${arrow.id}`} className="stage-exit-forecast stage-exit-forecast--none">{(() => { const [x, y] = outward(arrow.id, 52); return <path d={`M ${x - 14} ${y - 14} L ${x + 14} ${y + 14} M ${x + 14} ${y - 14} L ${x - 14} ${y + 14}`} />; })()}</g>
            : null)}
        {EXITS.filter(exit => !TARGETS.some(target => target.short === exit.id)).map(exit => {
          const [x, y] = outward(exit.id, 20);
          return <text key={`exit-label-${exit.id}`} className="spatial-boundary-label" x={x + 38} y={y - 6}>{exit.id}</text>;
        })}

        {/* Hazard plume: a static stack of soft shapes rising from each blocked target. */}
        {blockedTargets.map(target => {
          const [x, y] = project(target.x, target.y);
          return <g key={`plume-${target.id}`} className="stage-plume" aria-hidden="true" pointerEvents="none">
            <ellipse cx={x} cy={y + 2} rx="52" ry="20" className="stage-plume-glow" />
            <g filter={`url(#${uid}-soft)`}>
              {[...PUFFS].reverse().map((puff, index) => <ellipse key={index} cx={x + puff.dx * 1.4} cy={y - 10 + puff.dy} rx={puff.rx * 1.35} ry={puff.ry * 1.3} fill={`url(#${uid}-plume)`} opacity={Math.min(1, puff.opacity + .38)} />)}
              <ellipse cx={x} cy={y - 14} rx="16" ry="22" className="stage-plume-core" />
            </g>
          </g>;
        })}
        {TARGETS.filter(target => smoke?.[target.id] !== undefined).map(target => {
          const [x, y] = project(target.x, target.y);
          return <g key={`smoke-${target.id}`} className="stage-smoke" aria-hidden="true" pointerEvents="none">
            <ellipse cx={x} cy={y + 2} rx="46" ry="17" className="stage-smoke-base" />
            <g filter={`url(#${uid}-soft)`}>{[...PUFFS].reverse().map((puff, index) => <ellipse key={index} cx={x + puff.dx * 1.2} cy={y - 8 + puff.dy * .8} rx={puff.rx * 1.2} ry={puff.ry * 1.15} className="stage-smoke-puff" opacity={Math.min(.8, puff.opacity + .12)} />)}</g>
          </g>;
        })}
        {blockedTargets.map(target => {
          const [x, y] = project(target.x, target.y);
          return <path key={`flame-${target.id}`} className="stage-flame" aria-hidden="true" pointerEvents="none" transform={`translate(${x} ${y - 22})`} d="M0 -44 C 9 -30 18 -20 14 -6 C 12 2 -12 2 -14 -6 C -18 -20 -6 -30 0 -44 Z" />;
        })}
        {blockedTargets.map(target => <TokenCube key={`token-${target.id}`} x={target.x} y={target.y} />)}

        {/* Room labels draw over the plume so they stay readable. */}
        {ZONES.map(zone => {
          const [x, y] = project(zone.label[0], zone.label[1]);
          const reserve = zone.id === 'RESERVE';
          return <g key={`label-${zone.id}`} className={`spatial-room-label ${reserve ? 'spatial-room-label--small' : ''}`} transform={`translate(${x} ${y})`}>
            <text y={0} textAnchor="middle">{zone.title}</text>
          </g>;
        })}

        {TARGETS.map(target => {
          const [x, y] = project(target.x, target.y);
          const selected = selectedTarget === target.id;
          const blocked = isBlocked(target.id);
          return <g key={target.id} role="button" tabIndex={0} aria-label={`${target.short}: ${target.title}, ${blocked ? 'closed' : 'available'}.${smoke?.[target.id] !== undefined ? ` Smoke forecast at ${smoke[target.id]} seconds.` : ''} ${armedTool ? `${armedTool} tool armed. Press Enter to place.` : 'Select for review.'}`} aria-pressed={selected}
            onClick={() => onSelectTarget(target.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelectTarget(target.id); } }}
            className={`spatial-model-target ${selected ? 'is-selected' : ''} ${blocked ? 'is-blocked' : ''} ${armedTool ? 'is-armed' : ''}`}>
            <polygon className="spatial-target-hitbox" points={polygon(target.x - 27, target.y - 15, 54, 30)} />
            <polygon className="spatial-target-outline" points={polygon(target.x - 23, target.y - 10, 46, 20)} />
            <g transform={`translate(${x} ${y - 31})`}>
              <line className="spatial-target-stem" x1="0" y1="14" x2="0" y2="30" />
              <rect x="-26" y="-13" width="52" height="26" rx="5" className="spatial-target-badge" />
              <circle cx="-13" cy="0" r="2.5" className="spatial-target-dot" />
              <text x="5" y="5" textAnchor="middle">{target.short}</text>
              {forecastByTarget.has(target.id) && <g className="spatial-forecast-chip" transform="translate(-84 -40)">
                <rect x="0" y="-11" width="168" height="22" rx="4" /><text x="84" y="4.5" textAnchor="middle">{formatForecastClosure(forecastByTarget.get(target.id) ?? 0)}</text>
              </g>}
            </g>
          </g>;
        })}

        <g className={`spatial-gate-label ${reserveConfirmed ? 'is-confirmed' : ''}`} transform={`translate(${gatePosition[0] + 36} ${gatePosition[1] - 34})`}>
          <circle cx="-8" cy="-3" r="2.5" /><text x="0" y="0">P3 · {gateLabel}</text>
        </g>
      </g>
    </svg>

    <div className="stage-zoom" role="group" aria-label="View controls">
      <button type="button" onClick={() => changeZoom(-.15)} disabled={zoom <= .75} aria-label="Zoom out"><Minus size={15} aria-hidden="true" /></button>
      <span aria-live="polite">{Math.round(zoom * 100)}%</span>
      <button type="button" onClick={() => changeZoom(.15)} disabled={zoom >= 1.65} aria-label="Zoom in"><Plus size={15} aria-hidden="true" /></button>
      <button type="button" onClick={resetView} aria-label="Reset zoom and pan"><RotateCcw size={14} aria-hidden="true" /></button>
    </div>
  </section>;
};
