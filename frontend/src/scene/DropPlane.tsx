import { useMemo, useRef, useState } from 'react';
import type { ThreeEvent } from '@react-three/fiber';
import * as THREE from 'three';
import { DROP_REFUSED, locateZone } from '../twin/geometry.ts';
import type { HazardType, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { HAZARD_COLOR, PALETTE } from './palette.ts';

interface Props {
  venue: VenueV2;
  armedType: HazardType | null;
  onPlace: (point: { x: number; y: number }) => void;
  onEmptyClick: () => void;
}

export default function DropPlane({ venue, armedType, onPlace, onEmptyClick }: Props) {
  const [w, h] = venue.extent;
  const ghost = useRef<THREE.Group>(null);
  const [hit, setHit] = useState<{ ok: boolean; zoneId: string | null }>({ ok: false, zoneId: null });
  const last = useRef<{ ok: boolean; zoneId: string | null }>({ ok: false, zoneId: null });

  const shapes = useMemo(() => Object.fromEntries(venue.zones.map((z) => {
    const s = new THREE.Shape();
    z.polygon.forEach(([x, y], i) => (i === 0 ? s.moveTo(x, y) : s.lineTo(x, y)));
    return [z.id, new THREE.ShapeGeometry(s)];
  })), [venue]);

  const onMove = (event: ThreeEvent<PointerEvent>) => {
    if (!armedType) return;
    const x = event.point.x;
    const y = -event.point.z;
    if (ghost.current) {
      ghost.current.position.set(x, 0, -y);
      ghost.current.visible = true;
    }
    const result = locateZone(venue, { x, y });
    const next = result.ok ? { ok: true, zoneId: result.zone_id } : { ok: false, zoneId: null };
    if (next.ok !== last.current.ok || next.zoneId !== last.current.zoneId) {
      last.current = next;
      setHit(next);
    }
    event.stopPropagation();
  };

  const onClick = (event: ThreeEvent<MouseEvent>) => {
    if (armedType) onPlace({ x: event.point.x, y: -event.point.z });
    else onEmptyClick();
  };

  const color = hit.ok ? HAZARD_COLOR[armedType ?? 'FIRE'] : PALETTE.hazard;
  return (
    <group>
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={toWorld(w / 2, h / 2, 0.002)}
        onPointerMove={onMove}
        onPointerOut={() => { if (ghost.current) ghost.current.visible = false; }}
        onClick={onClick}
      >
        <planeGeometry args={[w + 40, h + 40]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>
      {armedType && (
        <>
          {hit.zoneId && (
            <group rotation={[-Math.PI / 2, 0, 0]}>
              <mesh geometry={shapes[hit.zoneId]} position={[0, 0, 0.02]}>
                <meshBasicMaterial color={HAZARD_COLOR[armedType]} transparent opacity={0.2} depthWrite={false} />
              </mesh>
            </group>
          )}
          <group ref={ghost} visible={false}>
            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.08, 0]}>
              {hit.ok ? <circleGeometry args={[1, 32]} /> : <ringGeometry args={[0.8, 1, 32]} />}
              <meshBasicMaterial color={color} transparent opacity={hit.ok ? 0.45 : 0.95} depthWrite={false} />
            </mesh>
          </group>
        </>
      )}
    </group>
  );
}

export { DROP_REFUSED };
