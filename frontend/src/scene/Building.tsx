import { useEffect, useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { pointInPolygon } from '../twin/geometry.ts';
import { buildWalls, zoneRenders } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, Point2, VenueV2 } from '../twin/types.ts';
import { makeFloorTexture, resolveZoneLook, type ResolvedAppearance } from './FurnitureModels.tsx';
import { PALETTE } from './palette.ts';

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
    <mesh geometry={geometry}>
      <meshStandardMaterial map={texture} roughness={0.8} metalness={0.02} />
    </mesh>
  );
}

export const WALL_HEIGHT = 1.2;
const WALL_THICK = 0.24;

function polygonShape(polygon: Point2[]): THREE.Shape {
  const shape = new THREE.Shape();
  polygon.forEach(([x, y], i) => (i === 0 ? shape.moveTo(x, y) : shape.lineTo(x, y)));
  shape.closePath();
  return shape;
}

function Walls({ venue }: { venue: VenueV2 }) {
  const walls = useMemo(() => buildWalls(venue), [venue]);
  const color = useMemo(() => wallColor(venue), [venue]);
  const body = useRef<THREE.InstancedMesh>(null);
  const cap = useRef<THREE.InstancedMesh>(null);
  useLayoutEffect(() => {
    const m = new THREE.Matrix4();
    const q = new THREE.Quaternion();
    walls.forEach((w, i) => {
      const dx = w.b[0] - w.a[0];
      const dy = w.b[1] - w.a[1];
      const length = Math.hypot(dx, dy) + WALL_THICK; // overlap so corners close
      const angle = Math.atan2(dy, dx);
      q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), -angle);
      const cx = (w.a[0] + w.b[0]) / 2;
      const cy = (w.a[1] + w.b[1]) / 2;
      m.compose(new THREE.Vector3(cx, WALL_HEIGHT / 2, -cy), q, new THREE.Vector3(length, WALL_HEIGHT, WALL_THICK));
      body.current?.setMatrixAt(i, m);
      m.compose(new THREE.Vector3(cx, WALL_HEIGHT + 0.02, -cy), q, new THREE.Vector3(length, 0.04, WALL_THICK + 0.02));
      cap.current?.setMatrixAt(i, m);
    });
    for (const mesh of [body.current, cap.current]) {
      if (mesh) mesh.instanceMatrix.needsUpdate = true;
    }
  }, [walls]);
  return (
    <>
      <instancedMesh ref={body} args={[undefined, undefined, walls.length]} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial color={color ?? PALETTE.wall} roughness={0.9} metalness={0} />
      </instancedMesh>
      <instancedMesh ref={cap} args={[undefined, undefined, walls.length]} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={color ? new THREE.Color(color).offsetHSL(0, 0, -0.18) : PALETTE.wallTop} />
      </instancedMesh>
    </>
  );
}

function Grid({ venue, faint }: { venue: VenueV2; faint: boolean }) {
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
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color={PALETTE.grid} transparent opacity={faint ? 0.18 : 0.8} />
    </lineSegments>
  );
}

export default function Building({ venue, plan, fills }: { venue: VenueV2; plan: DoorPlanResponse | null; fills?: Record<string, number> }) {
  const zones = useMemo(() => zoneRenders(venue, plan), [venue, plan]);
  const shapes = useMemo(() => zones.map((z) => new THREE.ShapeGeometry(polygonShape(z.polygon))), [zones]);
  const looks = useMemo(() => Object.fromEntries(venue.zones.map((z) => [z.id, resolveZoneLook(venue.appearance?.zones[z.id])])), [venue]);
  const lit = hasLooks(venue);
  return (
    <group>
      {zones.map((z, i) => {
        const look = looks[z.id];
        return (
          <group key={z.id} rotation={[-Math.PI / 2, 0, 0]}>
            {look ? <LookFloor geometry={shapes[i]} look={look} /> : (
              <mesh geometry={shapes[i]}>
                <meshStandardMaterial color={PALETTE.floor} roughness={0.85} metalness={0.05} />
              </mesh>
            )}
            {/* On light video floors a white occupant wash and a faint hazard tint vanish: darken and strengthen them. */}
            {fills && fills[z.id] > 0 && (
              <mesh geometry={shapes[i]} position={[0, 0, 0.02]}>
                <meshBasicMaterial color={lit ? PALETTE.canvas : PALETTE.text} transparent opacity={(lit ? 0.08 : 0.04) + fills[z.id] * (lit ? 0.4 : 0.26)} depthWrite={false} />
              </mesh>
            )}
            {z.tintOpacity > 0 && (
              <mesh geometry={shapes[i]} position={[0, 0, 0.012]}>
                <meshBasicMaterial color={z.tintColor} transparent opacity={lit ? Math.min(0.6, z.tintOpacity * 2.4) : z.tintOpacity} depthWrite={false} />
              </mesh>
            )}
          </group>
        );
      })}
      <Grid venue={venue} faint={lit} />
      <Walls venue={venue} />
    </group>
  );
}
