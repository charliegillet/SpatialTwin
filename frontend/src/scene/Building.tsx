import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { pointInPolygon } from '../twin/geometry.ts';
import { openingFrames, wallRuns, zoneRenders, type WallRun } from '../twin/sceneModel.ts';
import { floorOpacity } from '../twin/underlay.ts';
import type { DoorPlanResponse, Point2, VenueV2 } from '../twin/types.ts';
import { makeFloorTexture, resolveZoneLook, type ResolvedAppearance } from './FurnitureModels.tsx';
import { FLOOR_COLOR, PALETTE } from './palette.ts';

/** True when the venue carries a look from a video walkthrough (room colours or furniture). */
export const hasLooks = (venue: VenueV2) =>
  Boolean(venue.appearance && (venue.appearance.furniture.length > 0 || Object.keys(venue.appearance.zones).length > 0));

/** One wall colour for the building: the most common room wall colour (shared walls have no single owner). */
function wallColor(venue: VenueV2): string | null {
  const counts = new Map<string, number>();
  for (const look of Object.values(venue.appearance?.zones ?? {})) {
    if (look.wall_color) counts.set(look.wall_color, (counts.get(look.wall_color) ?? 0) + 1);
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
}

/** A video room's floor: its colour and material as a texture in world metres (ShapeGeometry UVs are metres). */
function LookFloor({ geometry, look }: { geometry: THREE.ShapeGeometry; look: ResolvedAppearance }) {
  const texture = useMemo(() => makeFloorTexture(look.floorMaterial, look.floorColor), [look.floorMaterial, look.floorColor]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <mesh geometry={geometry} renderOrder={ORDER.floor}>
      <meshStandardMaterial map={texture} roughness={0.8} metalness={0.02} />
    </mesh>
  );
}

/** Inner partitions: low enough to see into every room from the overview camera. Door lamps and labels sit on it. */
export const WALL_HEIGHT = 1.2;
/** The building's shell stands a little taller, so the outline reads as one building and exits as gaps in it. */
export const OUTER_WALL_HEIGHT = 1.6;
const INNER_THICK = 0.16;
const OUTER_THICK = 0.26;
const CAP = 0.03;
const SHADOW_REACH = 0.55; // metres of floor darkened beside each wall (a cheap stand-in for ambient occlusion)

/** Draw order for the see-through floor stack: photo, floor plate, then wall shadows and state tints. */
export const ORDER = { underlay: -3, floor: -2, overlay: -1 } as const;

function polygonShape(polygon: Point2[]): THREE.Shape {
  const shape = new THREE.Shape();
  polygon.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();
  return shape;
}

interface Box { centre: [number, number]; length: number; angle: number }

/** A run as a box footprint: extended by half the thickness at each joint so corners close, never into an opening. */
function runBox(w: WallRun, thick: number): Box {
  const dx = w.b[0] - w.a[0];
  const dy = w.b[1] - w.a[1];
  const len = Math.hypot(dx, dy) || 1;
  const extA = w.openA ? 0 : thick / 2;
  const extB = w.openB ? 0 : thick / 2;
  const shift = (extB - extA) / 2;
  return {
    centre: [(w.a[0] + w.b[0]) / 2 + (dx / len) * shift, (w.a[1] + w.b[1]) / 2 + (dy / len) * shift],
    length: len + extA + extB,
    angle: Math.atan2(dy, dx),
  };
}

function WallSet({ runs, height, thick, color }: { runs: WallRun[]; height: number; thick: number; color: string }) {
  const body = useRef<THREE.InstancedMesh>(null);
  const cap = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    runs.forEach((w, i) => {
      const box = runBox(w, thick);
      q.setFromAxisAngle(up, box.angle);
      const [cx, cy] = box.centre;
      m.compose(new THREE.Vector3(cx, height / 2, -cy), q, new THREE.Vector3(box.length, height, thick));
      body.current?.setMatrixAt(i, m);
      m.compose(new THREE.Vector3(cx, height + CAP / 2, -cy), q, new THREE.Vector3(box.length + 0.01, CAP, thick + 0.02));
      cap.current?.setMatrixAt(i, m);
    });
    for (const mesh of [body.current, cap.current]) {
      if (mesh) {
        mesh.instanceMatrix.needsUpdate = true;
        mesh.computeBoundingSphere();
      }
    }
  }, [runs, height, thick]);
  if (runs.length === 0) return null;
  return (
    <>
      <instancedMesh ref={body} args={[undefined, undefined, runs.length]} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color={color} roughness={0.82} metalness={0} />
      </instancedMesh>
      {/* Caps are unlit and bright: crisp plan lines from the top view, a clean cut edge from the overview. */}
      <instancedMesh ref={cap} args={[undefined, undefined, runs.length]} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={PALETTE.wallTop} />
      </instancedMesh>
    </>
  );
}

/** Frame posts at both sides of every doorway and wall exit, so an opening reads as a door, not a missing wall. */
function Jambs({ venue }: { venue: VenueV2 }) {
  const frames = useMemo(() => openingFrames(venue), [venue]);
  const mesh = useRef<THREE.InstancedMesh>(null);
  const count = frames.length * 2;
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    const up = new THREE.Vector3(0, 1, 0);
    let i = 0;
    for (const f of frames) {
      const exit = f.role === 'exit';
      const height = (exit ? OUTER_WALL_HEIGHT : WALL_HEIGHT) + 0.04;
      const across = (exit ? OUTER_THICK : INNER_THICK) + 0.06;
      // The post's long side runs across the wall; it stands on the wall's cut end, just outside the gap.
      q.setFromAxisAngle(up, f.axis === 'x' ? Math.PI / 2 : 0);
      f.jambs.forEach(([x, y], side) => {
        const away = side === 0 ? -0.04 : 0.04;
        const px = f.axis === 'x' ? x + away : x;
        const py = f.axis === 'y' ? y + away : y;
        m.compose(new THREE.Vector3(px, height / 2, -py), q, new THREE.Vector3(across, height, 0.08));
        mesh.current?.setMatrixAt(i++, m);
      });
    }
    if (mesh.current) {
      mesh.current.instanceMatrix.needsUpdate = true;
      mesh.current.computeBoundingSphere();
    }
  }, [frames]);
  if (count === 0) return null;
  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, count]} frustumCulled={false}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color={PALETTE.jamb} roughness={0.6} metalness={0.15} />
    </instancedMesh>
  );
}

/** Soft dark bands on the floor along both faces of every wall: one draw call that grounds the walls. */
function WallShadows({ inner, outer }: { inner: WallRun[]; outer: WallRun[] }) {
  const geometry = useMemo(() => {
    const pos: number[] = [];
    const col: number[] = [];
    const idx: number[] = [];
    const band = (w: WallRun, thick: number, strength: number) => {
      const box = runBox(w, thick);
      const ux = Math.cos(box.angle);
      const uy = Math.sin(box.angle);
      const [cx, cy] = box.centre;
      const half = box.length / 2;
      for (const side of [1, -1]) {
        const nx = -uy * side;
        const ny = ux * side;
        const base = pos.length / 3;
        for (const [along, off, alpha] of [[-half, thick / 2, strength], [half, thick / 2, strength], [half, thick / 2 + SHADOW_REACH, 0], [-half, thick / 2 + SHADOW_REACH, 0]]) {
          const x = cx + ux * along + nx * off;
          const y = cy + uy * along + ny * off;
          pos.push(x, 0.008, -y);
          col.push(0, 0, 0, alpha);
        }
        idx.push(base, base + 1, base + 2, base, base + 2, base + 3);
      }
    };
    for (const w of inner) band(w, INNER_THICK, 0.42);
    for (const w of outer) band(w, OUTER_THICK, 0.5);
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 4));
    g.setIndex(idx);
    return g;
  }, [inner, outer]);
  return (
    <mesh geometry={geometry} renderOrder={ORDER.overlay} raycast={() => null}>
      <meshBasicMaterial vertexColors transparent depthWrite={false} side={THREE.DoubleSide} />
    </mesh>
  );
}

function Grid({ venue }: { venue: VenueV2 }) {
  const geometry = useMemo(() => {
    const pts: number[] = [];
    const [w, h] = venue.extent;
    const inside = (x: number, y: number) => venue.zones.some((z) => pointInPolygon(x, y, z.polygon));
    for (let x = 0; x <= w; x++) {
      for (let y = 0; y < h; y++) if (inside(x, y + 0.5) && (inside(x - 0.01, y + 0.5) || inside(x + 0.01, y + 0.5))) pts.push(x, 0.004, -y, x, 0.004, -(y + 1));
    }
    for (let y = 0; y <= h; y++) {
      for (let x = 0; x < w; x++) if (inside(x + 0.5, y) && (inside(x + 0.5, y - 0.01) || inside(x + 0.5, y + 0.01))) pts.push(x, 0.004, -y, x + 1, 0.004, -y);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    return g;
  }, [venue]);
  return (
    <lineSegments geometry={geometry} renderOrder={ORDER.overlay}>
      <lineBasicMaterial color={PALETTE.grid} transparent opacity={0.55} depthWrite={false} />
    </lineSegments>
  );
}

export default function Building({ venue, plan, fills, underlayOpacity = 0, lowGraphics = false }: {
  venue: VenueV2; plan: DoorPlanResponse | null; fills?: Record<string, number>; underlayOpacity?: number; lowGraphics?: boolean;
}) {
  const zones = useMemo(() => zoneRenders(venue, plan), [venue, plan]);
  const shapes = useMemo(() => zones.map((z) => new THREE.ShapeGeometry(polygonShape(z.polygon))), [zones]);
  const runs = useMemo(() => wallRuns(venue), [venue]);
  const outer = useMemo(() => runs.filter((w) => w.exterior), [runs]);
  const inner = useMemo(() => runs.filter((w) => !w.exterior), [runs]);
  // With the source photo underneath, the floor plate turns see-through so the drawing shows inside every room.
  const seeThrough = underlayOpacity > 0;
  const plate = floorOpacity(underlayOpacity);
  const looks = useMemo(() => Object.fromEntries(venue.zones.map((z) => [z.id, resolveZoneLook(venue.appearance?.zones[z.id])])), [venue]);
  const lit = hasLooks(venue);
  const walls = useMemo(() => wallColor(venue), [venue]);
  return (
    <group>
      {zones.map((z, i) => (
        <group key={z.id} rotation={[-Math.PI / 2, 0, 0]}>
          {looks[z.id] && !seeThrough ? <LookFloor geometry={shapes[i]} look={looks[z.id]!} /> : <mesh geometry={shapes[i]} renderOrder={ORDER.floor}>
            <meshStandardMaterial
              key={seeThrough ? 'see-through' : 'solid'}
              color={FLOOR_COLOR[z.floorKind]}
              roughness={0.9}
              metalness={0.02}
              transparent={seeThrough}
              opacity={seeThrough ? plate : 1}
              depthWrite={!seeThrough}
              // Filmic tone mapping crushes near-black albedo to black; the floor keeps its own (already dark) value.
              toneMapped={false}
            />
          </mesh>}
          {/* On light video floors a white occupant wash and a faint hazard tint vanish: darken and strengthen them. */}
          {fills && fills[z.id] > 0 && (
            <mesh geometry={shapes[i]} position={[0, 0, 0.02]} renderOrder={ORDER.overlay}>
              <meshBasicMaterial color={lit ? PALETTE.canvas : PALETTE.text} transparent opacity={(lit ? 0.08 : 0.04) + fills[z.id] * (lit ? 0.4 : 0.26)} depthWrite={false} />
            </mesh>
          )}
          {z.tintOpacity > 0 && (
            <mesh geometry={shapes[i]} position={[0, 0, 0.012]} renderOrder={ORDER.overlay}>
              <meshBasicMaterial color={z.tintColor} transparent opacity={lit ? Math.min(0.6, z.tintOpacity * 2.4) : z.tintOpacity} depthWrite={false} />
            </mesh>
          )}
        </group>
      ))}
      {!seeThrough && !lit && <Grid venue={venue} />}
      {!lowGraphics && <WallShadows inner={inner} outer={outer} />}
      <WallSet runs={inner} height={WALL_HEIGHT} thick={INNER_THICK} color={walls ?? PALETTE.wall} />
      <WallSet runs={outer} height={OUTER_WALL_HEIGHT} thick={OUTER_THICK} color={walls ? `#${new THREE.Color(walls).offsetHSL(0, 0, -0.08).getHexString()}` : PALETTE.wallOuter} />
      <Jambs venue={venue} />
    </group>
  );
}
