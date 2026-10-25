// Plain-DOM labels projected from world space each rendered frame (no drei Html: one overlay div per label).
import { useEffect, useMemo, type MutableRefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { PlaybackView } from '../twin/playback.ts';
import { doorRenders, exitRenders, hazardRenders, zoneRenders } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, PlacedHazard, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { WALL_HEIGHT } from './Building.tsx';
import { PALETTE } from './palette.ts';

export interface LabelSpec {
  key: string;
  text: string;
  className: string;
  position: [number, number, number];
  color?: string;
}

export function buildLabels(
  venue: VenueV2, plan: DoorPlanResponse | null, hazards: PlacedHazard[], view: PlaybackView | null = null,
): LabelSpec[] {
  const out: LabelSpec[] = [];
  for (const z of zoneRenders(venue, plan)) {
    let [cx, cy] = z.centroid;
    const xs = z.polygon.map((p) => p[0]);
    const ys = z.polygon.map((p) => p[1]);
    const narrow = Math.min(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys)) < 6;
    const near = venue.doors.find((d) => Math.hypot(d.position[0] - cx, d.position[1] - cy) < 3.2);
    if (narrow && near && !view) continue; // small rooms keep only their door and exit labels (unless counts are shown)
    if (near) cy += cy >= near.position[1] ? 1.0 : -1.0;
    out.push({ key: `z-${z.id}`, text: view?.zones.find((v) => v.id === z.id)?.label ?? z.name, className: view ? 'twin-label twin-label--zone twin-label--count' : 'twin-label twin-label--zone', position: toWorld(cx, cy, 0.02) });
  }
  for (const d of doorRenders(venue, plan)) {
    out.push({
      key: `d-${d.id}`, text: `${d.label}${d.locked ? ' · locked' : ''}`, className: 'twin-label twin-label--door',
      position: toWorld(d.position[0] + (d.simulated && d.axis === 'x' ? 2.2 : 0), d.position[1] + (d.simulated && d.axis === 'y' ? 2.2 : 0), WALL_HEIGHT + 0.75), color: d.simulated ? PALETTE.pending : undefined,
    });
  }
  for (const e of exitRenders(venue, plan)) {
    out.push({
      key: `e-${e.id}`, text: view?.exits.find((v) => v.id === e.id)?.label ?? e.label, className: 'twin-label twin-label--exit',
      position: toWorld(e.position[0] + e.outward[0] * 1.5, e.position[1] + e.outward[1] * 1.5, 0.1),
    });
  }
  for (const h of hazardRenders(plan, hazards, null)) {
    if (h.type === 'GAS') out.push({ key: `g-${h.id}`, text: 'No switching', className: 'twin-badge', position: toWorld(h.position[0], h.position[1], 2.4) });
  }
  return out;
}

export function LabelLayer({ labels, refs }: { labels: LabelSpec[]; refs: MutableRefObject<Map<string, HTMLElement>> }) {
  return (
    <div className="twin-labels" aria-hidden="true">
      {labels.map((l) => (
        <div
          key={l.key}
          className={l.className}
          style={{ color: l.color, position: 'absolute', left: 0, top: 0, visibility: 'hidden' }}
          ref={(el) => { if (el) refs.current.set(l.key, el); else refs.current.delete(l.key); }}
        >
          {l.text}
        </div>
      ))}
    </div>
  );
}

/** Inside the Canvas: positions each label element after every rendered frame. */
export function LabelProjector({ labels, refs }: { labels: LabelSpec[]; refs: MutableRefObject<Map<string, HTMLElement>> }) {
  const v = useMemo(() => new THREE.Vector3(), []);
  const project = (camera: THREE.Camera, width: number, height: number) => {
    for (const l of labels) {
      const el = refs.current.get(l.key);
      if (!el) continue;
      v.set(...l.position).project(camera);
      const visible = v.z < 1;
      el.style.visibility = visible ? 'visible' : 'hidden';
      el.style.transform = `translate(${((v.x + 1) / 2) * width}px, ${((1 - v.y) / 2) * height}px) translate(-50%, -50%)`;
    }
  };
  useFrame(({ camera, size }) => project(camera, size.width, size.height));
  useEffect(() => { /* labels list changed: next rendered frame repositions */ }, [labels]);
  return null;
}
