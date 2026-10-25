// Accessible top-down SVG plan. No three.js: used when WebGL is missing or the 3D chunk fails.
import { useMemo, type MouseEvent } from 'react';
import { playbackView } from '../twin/playback.ts';
import {
  ariaSummary, buildWalls, doorRenders, exitRenders, hazardRenders, routeRenders, zoneRenders,
} from '../twin/sceneModel.ts';
import { HAZARD_COLOR, PALETTE } from './palette.ts';
import type { HazardType, TwinScene3DProps } from '../twin/types.ts';

const PAD = 3;
const GLYPH: Record<HazardType, string> = { FIRE: 'F', SMOKE: 'S', GAS: 'G', CHEMICAL: 'C', WATER: 'W' };

export default function TwinPlan2D(props: TwinScene3DProps) {
  const { venue, plan, hazards, armedType, selectedHazardId, onPlace, onSelectHazard } = props;
  const [w, h] = venue.extent;
  const model = useMemo(() => ({
    walls: buildWalls(venue),
    zones: zoneRenders(venue, plan),
    doors: doorRenders(venue, plan),
    exits: exitRenders(venue, plan),
    routes: routeRenders(venue, plan),
    hazards: hazardRenders(plan, hazards, selectedHazardId),
  }), [venue, plan, hazards, selectedHazardId]);

  const finalFrame = useMemo(() => playbackView(venue, plan, Number.MAX_SAFE_INTEGER), [venue, plan]);
  const countOf = (id: string) => finalFrame?.zones.find((z) => z.id === id);

  // SVG y grows down; floor y grows north.
  const fy = (y: number) => h - y;

  const onClickFloor = (event: MouseEvent<SVGSVGElement>) => {
    const svg = event.currentTarget;
    const matrix = svg.getScreenCTM();
    if (!matrix) return;
    const point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    const local = point.matrixTransform(matrix.inverse());
    if (armedType) onPlace({ x: local.x, y: h - local.y });
    else onSelectHazard(null);
  };

  return (
    <svg
      role="group"
      aria-label={`${ariaSummary(venue, plan, hazards)} Top-down plan.`}
      viewBox={`${-PAD} ${-PAD} ${w + PAD * 2} ${h + PAD * 2}`}
      style={{ width: '100%', height: '100%', background: PALETTE.canvas, cursor: armedType ? 'crosshair' : 'default' }}
      onClick={onClickFloor}
    >
      <rect x={0} y={0} width={w} height={h} fill={PALETTE.floor} />
      {model.zones.map((z) => (
        <g key={z.id}>
          <polygon
            points={z.polygon.map(([x, y]) => `${x},${fy(y)}`).join(' ')}
            fill={z.tintColor}
            fillOpacity={z.tintOpacity}
            stroke={PALETTE.grid}
            strokeWidth={0.05}
          />
          <text x={z.centroid[0]} y={fy(z.centroid[1])} fill={PALETTE.muted} fontSize={0.65} textAnchor="middle" opacity={0.7}>
            {countOf(z.id)?.label ?? z.name}
          </text>
        </g>
      ))}
      {model.walls.map((wall, i) => (
        <line
          key={i}
          x1={wall.a[0]} y1={fy(wall.a[1])} x2={wall.b[0]} y2={fy(wall.b[1])}
          stroke={PALETTE.wallTop} strokeWidth={0.28} strokeLinecap="square"
        />
      ))}
      {model.routes.map((r) => (
        <polyline
          key={r.key}
          points={r.points.map(([x, y]) => `${x},${fy(y)}`).join(' ')}
          fill="none" stroke={r.color} strokeWidth={r.width * 0.4} strokeLinejoin="round" strokeLinecap="round"
          strokeDasharray={r.slowed ? '0.8 0.6' : undefined} opacity={r.slowed ? 0.6 : 0.85}
        />
      ))}
      {model.doors.map((d) => {
        const half = d.width / 2;
        const [x, y] = d.position;
        const [dx, dy] = d.axis === 'x' ? [half, 0] : [0, half];
        return (
          <g key={d.id}>
            <line
              x1={x - dx} y1={fy(y) - dy} x2={x + dx} y2={fy(y) + dy}
              stroke={d.open ? PALETTE.wallTop : d.color} strokeWidth={d.open ? 0.1 : 0.3}
              strokeDasharray={d.open ? '0.3 0.3' : undefined}
            />
            <circle cx={x} cy={fy(y)} r={0.35} fill={d.color} />
            <text x={x} y={fy(y) - 0.7} fill={PALETTE.muted} fontSize={0.55} textAnchor="middle">{d.label}</text>
          </g>
        );
      })}
      {model.exits.map((e) => {
        const [x, y] = e.position;
        const [ox, oy] = e.outward; // floor-space outward; svg y is flipped
        const cx = x + ox * 1.1;
        const cy = fy(y) - oy * 1.1;
        return (
          <g key={e.id} fill="none" stroke={e.color} strokeWidth={0.28} strokeLinecap="round" strokeLinejoin="round">
            {e.kind === 'unsafe' ? (
              <path d={`M${cx - 0.6} ${cy - 0.6}L${cx + 0.6} ${cy + 0.6}M${cx + 0.6} ${cy - 0.6}L${cx - 0.6} ${cy + 0.6}`} />
            ) : (
              <path d={`M${cx - ox * 0.5 - oy * 0.7} ${cy + oy * 0.5 - ox * 0.7}L${cx + ox * 0.5} ${cy - oy * 0.5}L${cx - ox * 0.5 + oy * 0.7} ${cy + oy * 0.5 + ox * 0.7}`} />
            )}
            <text x={cx + ox * 1.6 - oy * 0} y={cy - oy * 1.6 + (oy === 0 ? 0.3 : 0.3)} fill={PALETTE.muted} stroke="none" fontSize={0.6} textAnchor="middle">
              {finalFrame?.exits.find((x) => x.id === e.id)?.label ?? e.label}
            </text>
          </g>
        );
      })}
      {model.hazards.map((hz) => (
        <g
          key={hz.id}
          role="button"
          tabIndex={0}
          aria-label={`${hz.type.toLowerCase()} hazard${hz.selected ? ', selected' : ''}`}
          onClick={(event) => { event.stopPropagation(); onSelectHazard(hz.id); }}
          onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') onSelectHazard(hz.id); }}
          style={{ cursor: 'pointer' }}
        >
          <circle
            cx={hz.position[0]} cy={fy(hz.position[1])} r={1.1}
            fill={HAZARD_COLOR[hz.type]} fillOpacity={hz.effective ? 0.85 : 0.4}
            stroke={hz.selected ? PALETTE.text : 'none'} strokeWidth={0.18}
          />
          <text x={hz.position[0]} y={fy(hz.position[1]) + 0.4} fontSize={1.2} fontWeight={700} textAnchor="middle" fill={PALETTE.canvas}>
            {GLYPH[hz.type]}
          </text>
        </g>
      ))}
    </svg>
  );
}
