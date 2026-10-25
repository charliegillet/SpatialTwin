import { useLayoutEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { pointInPolygon } from '../twin/geometry.ts';
import { buildWalls, zoneRenders } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, Point2, VenueV2 } from '../twin/types.ts';
import { PALETTE } from './palette.ts';

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
        <meshStandardMaterial color={PALETTE.wall} roughness={0.9} metalness={0} />
      </instancedMesh>
      <instancedMesh ref={cap} args={[undefined, undefined, walls.length]} frustumCulled={false}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={PALETTE.wallTop} />
      </instancedMesh>
    </>
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
    <lineSegments geometry={geometry}>
      <lineBasicMaterial color={PALETTE.grid} transparent opacity={0.8} />
    </lineSegments>
  );
}

export default function Building({ venue, plan, fills }: { venue: VenueV2; plan: DoorPlanResponse | null; fills?: Record<string, number> }) {
  const zones = useMemo(() => zoneRenders(venue, plan), [venue, plan]);
  const shapes = useMemo(() => zones.map((z) => new THREE.ShapeGeometry(polygonShape(z.polygon))), [zones]);
  return (
    <group>
      {zones.map((z, i) => (
        <group key={z.id} rotation={[-Math.PI / 2, 0, 0]}>
          <mesh geometry={shapes[i]}>
            <meshStandardMaterial color={PALETTE.floor} roughness={0.85} metalness={0.05} />
          </mesh>
          {fills && fills[z.id] > 0 && (
            <mesh geometry={shapes[i]} position={[0, 0, 0.02]}>
              <meshBasicMaterial color={PALETTE.text} transparent opacity={0.04 + fills[z.id] * 0.26} depthWrite={false} />
            </mesh>
          )}
          {z.tintOpacity > 0 && (
            <mesh geometry={shapes[i]} position={[0, 0, 0.012]}>
              <meshBasicMaterial color={z.tintColor} transparent opacity={z.tintOpacity} depthWrite={false} />
            </mesh>
          )}
        </group>
      ))}
      <Grid venue={venue} />
      <Walls venue={venue} />
    </group>
  );
}
