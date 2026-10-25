import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { exitRenders, type ExitRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { WALL_HEIGHT } from './Building.tsx';

const FLASH_CYCLES = 4;
const CYCLE_S = 0.8;

function chevronGeometry(): THREE.ShapeGeometry {
  const s = new THREE.Shape();
  s.moveTo(-0.5, -0.45);
  s.lineTo(0, 0.1);
  s.lineTo(0.5, -0.45);
  s.lineTo(0.5, -0.8);
  s.lineTo(0, -0.25);
  s.lineTo(-0.5, -0.8);
  s.closePath();
  return new THREE.ShapeGeometry(s);
}

function xGeometry(): THREE.BufferGeometry {
  const bar = (angle: number) => {
    const g = new THREE.PlaneGeometry(1.5, 0.28);
    g.rotateZ(angle);
    return g;
  };
  const a = bar(Math.PI / 4);
  const b = bar(-Math.PI / 4);
  const merged = new THREE.BufferGeometry();
  const pos = new Float32Array([...a.getAttribute('position').array, ...b.getAttribute('position').array]);
  merged.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  const idx = [...Array.from(a.getIndex()!.array), ...Array.from(b.getIndex()!.array, (i) => i + 4)];
  merged.setIndex(idx);
  return merged;
}

function ExitSign({ exit, reducedMotion }: { exit: ExitRender; reducedMotion: boolean }) {
  const chevrons = useRef<(THREE.Mesh | null)[]>([]);
  const billboard = useRef<THREE.Group>(null);
  const flashStart = useRef<number | null>(null);
  const prevLamp = useRef(exit.lamp);
  const chevron = useMemo(chevronGeometry, []);
  const cross = useMemo(xGeometry, []);
  const [x, y] = exit.position;
  const [ox, oy] = exit.outward;
  // Direction of travel on the floor: chevron local +y must point along outward (floor) = world (ox, 0, -oy).
  const yaw = Math.atan2(-ox, oy); // in-plane rotation taking the chevron's +y (north) onto the outward vector

  useEffect(() => {
    if (prevLamp.current !== exit.lamp) {
      flashStart.current = exit.flashes && !reducedMotion ? -1 : null; // -1: stamp on next frame
      prevLamp.current = exit.lamp;
    } else if (exit.flashes && !reducedMotion && flashStart.current === null) {
      flashStart.current = -1;
    }
  }, [exit.lamp, exit.flashes, reducedMotion]);

  useFrame(({ clock, camera, invalidate }) => {
    const now = clock.elapsedTime;
    if (flashStart.current === -1) flashStart.current = now;
    let flashing = false;
    if (flashStart.current !== null && exit.kind === 'safe' && exit.lamp === 'green_flash') {
      const t = now - flashStart.current;
      flashing = t < FLASH_CYCLES * CYCLE_S;
      if (!flashing) flashStart.current = null;
      chevrons.current.forEach((mesh, i) => {
        if (!mesh) return;
        const phase = (t / CYCLE_S - i * 0.22) % 1;
        (mesh.material as THREE.MeshBasicMaterial).opacity = flashing ? (phase > 0 && phase < 0.5 ? 1 : 0.18) : 1;
      });
      if (flashing) invalidate();
    } else {
      chevrons.current.forEach((mesh) => mesh && ((mesh.material as THREE.MeshBasicMaterial).opacity = 1));
    }
    if (billboard.current) billboard.current.rotation.y = Math.atan2(camera.position.x - billboard.current.position.x, camera.position.z - billboard.current.position.z);
  });

  const showSafe = exit.kind === 'safe';
  const showUnsafe = exit.kind === 'unsafe';
  const lampY = WALL_HEIGHT + 0.3;
  const barSize: [number, number, number] = exit.axis === 'x' ? [exit.width, 0.1, 0.1] : [0.1, 0.1, exit.width];
  return (
    <group>
      <mesh position={toWorld(x, y, lampY)}>
        <boxGeometry args={barSize} />
        <meshBasicMaterial color={exit.color} />
      </mesh>
      {showSafe && [0, 1, 2].map((i) => (
        <mesh
          key={i}
          ref={(el) => { chevrons.current[i] = el; }}
          geometry={chevron}
          position={toWorld(x + ox * (i * 0.9 - 1.2), y + oy * (i * 0.9 - 1.2), 0.03)}
          rotation={[-Math.PI / 2, 0, yaw, 'YXZ']}
        >
          <meshBasicMaterial color={exit.color} transparent side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      ))}
      {showUnsafe && (
        <>
          <mesh geometry={cross} position={toWorld(x - ox * 1.2, y - oy * 1.2, 0.03)} rotation={[-Math.PI / 2, 0, 0]}>
            <meshBasicMaterial color={exit.color} side={THREE.DoubleSide} />
          </mesh>
          <group ref={billboard} position={toWorld(x, y, WALL_HEIGHT + 1.0)}>
            <mesh geometry={cross}>
              <meshBasicMaterial color={exit.color} side={THREE.DoubleSide} />
            </mesh>
          </group>
        </>
      )}
    </group>
  );
}

export default function ExitSigns({ venue, plan, reducedMotion }: { venue: VenueV2; plan: DoorPlanResponse | null; reducedMotion: boolean }) {
  return <group>{exitRenders(venue, plan).map((e) => <ExitSign key={e.id} exit={e} reducedMotion={reducedMotion} />)}</group>;
}
