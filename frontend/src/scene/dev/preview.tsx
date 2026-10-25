/// <reference types="vite/client" />
// Dev-only harness (not part of the production build): scene-preview.html?case=fire-lobby&view=3d|2d
import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import venueJson from '../../twin/fixtures/building-v2.json';
import TwinScene3D from '../TwinScene3D.tsx';
import TwinPlan2D from '../TwinPlan2D.tsx';
import SceneErrorBoundary from '../SceneErrorBoundary.tsx';
import { locateZone } from '../../twin/geometry.ts';
import type { DoorPlanResponse, HazardType, PlacedHazard, VenueV2 } from '../../twin/types.ts';

const venue = venueJson as unknown as VenueV2;
const plans = import.meta.glob('../../twin/fixtures/door-plan-*.json', { eager: true, import: 'default' }) as Record<string, DoorPlanResponse>;
const byCase: Record<string, DoorPlanResponse> = {};
for (const [path, plan] of Object.entries(plans)) byCase[path.match(/door-plan-(.*)\.json$/)![1]] = plan;

const SPOT: Record<string, { type: HazardType; x: number; y: number }> = {
  'fire-lobby': { type: 'FIRE', x: 20, y: 4 },
  'fire-hall': { type: 'FIRE', x: 20, y: 14 },
  'smoke-hall': { type: 'SMOKE', x: 20, y: 14 },
  'gas-hall': { type: 'GAS', x: 20, y: 14 },
  'gas-kitchen': { type: 'GAS', x: 36, y: 4 },
  'chemical-east-corr': { type: 'CHEMICAL', x: 30, y: 12 },
  'water-west-corr': { type: 'WATER', x: 10, y: 12 },
};

const q = new URLSearchParams(location.search);
const caseName = q.get('case') ?? 'none';
const spot = SPOT[caseName];
const extra = (q.get('extra') ?? '').split(',').filter(Boolean);

function initialHazards(): PlacedHazard[] {
  const list = spot ? [spot] : [];
  for (const name of extra) if (SPOT[name]) list.push(SPOT[name]);
  return list.map((s, i) => {
    const hit = locateZone(venue, s);
    return { id: `h${i}`, type: s.type, x: s.x, y: s.y, zone_id: hit.ok ? hit.zone_id : '', untenable_s: null, source: 'simulated' as const };
  });
}

function Preview() {
  const [hazards, setHazards] = useState(initialHazards);
  const [armed, setArmed] = useState<HazardType | null>((q.get('armed') as HazardType) || null);
  const [selected, setSelected] = useState<string | null>(null);
  const [log, setLog] = useState('');
  const view = q.get('view') ?? '3d';
  const props = {
    venue, plan: byCase[caseName] ?? null, hazards, armedType: armed, selectedHazardId: selected,
    lowGraphics: q.has('low'), reducedMotion: q.has('reduced'),
    onPlace: (p: { x: number; y: number }) => {
      const hit = locateZone(venue, p);
      setLog(`place ${p.x.toFixed(1)},${p.y.toFixed(1)} ${hit.ok ? hit.zone_id : hit.reason}`);
      if (hit.ok && armed) setHazards((h) => [...h, { id: `h${h.length}`, type: armed, x: p.x, y: p.y, zone_id: hit.zone_id, untenable_s: null, source: 'simulated' }]);
    },
    onSelectHazard: (id: string | null) => { setSelected(id); setLog(`select ${id}`); },
  };
  return (
    <div style={{ height: '100%', position: 'relative' }}>
      {view === '2d' ? <TwinPlan2D {...props} /> : <SceneErrorBoundary fallback={<TwinPlan2D {...props} />}><TwinScene3D {...props} /></SceneErrorBoundary>}
      <div style={{ position: 'absolute', left: 8, top: 8, font: '12px monospace', display: 'flex', gap: 6, zIndex: 3 }}>
        {(['FIRE', 'SMOKE', 'GAS', 'CHEMICAL', 'WATER'] as HazardType[]).map((t) => (
          <button key={t} onClick={() => setArmed(armed === t ? null : t)} style={{ background: armed === t ? '#5cf28a' : '#171d1b', color: armed === t ? '#000' : '#fff' }}>{t}</button>
        ))}
        <button onClick={() => setHazards([])}>clear</button>
        <span id="log">{log}</span><span> cases: {Object.keys(byCase).join(' ') || 'none (no plan fixtures)'}</span>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<Preview />);
