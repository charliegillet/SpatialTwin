import { useEffect, useMemo, useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { exitRenders, type ExitRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { ORDER, OUTER_WALL_HEIGHT } from './Building.tsx';

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

const TREADS = 7;
const RAIL_HEIGHT = 0.85;
const RAIL_COLOR = '#c3ccc7';

/**
 * An interior exit stair (an upper floor's stair core): a dark well with treads stepping down in the direction of
 * travel, a guard rail on the three sides you cannot enter from, and its outline in the exit's state colour. Local
 * axes: x across the flight, z along the direction of travel (exit.outward), so the open side faces the run-up.
 */
function StairCore({ exit, side }: { exit: ExitRender; side: number }) {
  const [x, y] = exit.position;
  const [ox, oy] = exit.outward;
  const yaw = Math.atan2(ox, -oy); // local x -> the floor direction (-oy, ox); local z -> outward
  const h = side / 2;
  const tread = side / TREADS;
  const shade = (i: number) => new THREE.Color('#6b7d86').lerp(new THREE.Color('#151c20'), i / (TREADS - 1));
  const rails: [number, number, number, number][] = [[-h, 0, 0.05, side], [h, 0, 0.05, side], [0, h, side, 0.05]];
  const posts: [number, number][] = [[-h, -h], [-h, 0], [-h, h], [h, -h], [h, 0], [h, h], [0, h]];
  return (
    <group position={toWorld(x, y, 0)} rotation={[0, yaw, 0]}>
      <mesh position={[0, 0.006, 0]} rotation={[-Math.PI / 2, 0, 0]} renderOrder={ORDER.overlay}>
        <planeGeometry args={[side, side]} />
        <meshBasicMaterial color="#05080a" transparent opacity={0.92} depthWrite={false} />
      </mesh>
      {Array.from({ length: TREADS }, (_, i) => (
        <mesh key={i} position={[0, 0.012, -h + (i + 0.5) * tread]}>
          <boxGeometry args={[side * 0.86, 0.012, tread * 0.62]} />
          <meshBasicMaterial color={shade(i)} />
        </mesh>
      ))}
      {/* State outline: four bars around the well. */}
      {[[0, -h, side + 0.1, 0.09], [0, h, side + 0.1, 0.09], [-h, 0, 0.09, side + 0.1], [h, 0, 0.09, side + 0.1]].map(([cx, cz, w, d], i) => (
        <mesh key={`o${i}`} position={[cx, 0.03, cz]}>
          <boxGeometry args={[w, 0.02, d]} />
          <meshBasicMaterial color={exit.color} />
        </mesh>
      ))}
      {rails.map(([cx, cz, w, d], i) => (
        <mesh key={`r${i}`} position={[cx, RAIL_HEIGHT, cz]}>
          <boxGeometry args={[w, 0.05, d]} />
          <meshStandardMaterial color={RAIL_COLOR} roughness={0.5} metalness={0.3} />
        </mesh>
      ))}
      {posts.map(([cx, cz], i) => (
        <mesh key={`p${i}`} position={[cx, RAIL_HEIGHT / 2, cz]}>
          <boxGeometry args={[0.04, RAIL_HEIGHT, 0.04]} />
          <meshStandardMaterial color={RAIL_COLOR} roughness={0.5} metalness={0.3} />
        </mesh>
      ))}
    </group>
  );
}

function ExitSign({ exit, reducedMotion }: { exit: ExitRender; reducedMotion: boolean }) {
  const chevrons = useRef<(THREE.Mesh | null)[]>([]);
  const billboard = useRef<THREE.Group>(null);
  const flashStart = useRef<number | null>(null);
  const prevLamp = useRef(exit.lamp);
  const chevron = useMemo(chevronGeometry, []);
  const cross = useMemo(xGeometry, []);
  const stairSide = Math.max(exit.width, 1.0);
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
  // The exit sign: a lit panel over the doorway in the outer wall (or hung over a stair core), coloured by state.
  // Over a stair core it stands on the far rail, facing the run-up.
  const lampY = exit.interior ? RAIL_HEIGHT + 0.2 : OUTER_WALL_HEIGHT + 0.3;
  const signX = exit.interior ? x + ox * (stairSide / 2) : x;
  const signY = exit.interior ? y + oy * (stairSide / 2) : y;
  const signW = Math.min(1.4, Math.max(0.8, exit.width * 0.6));
  const signSize: [number, number, number] = exit.axis === 'x' ? [signW, 0.32, 0.08] : [0.08, 0.32, signW];
  // A wall exit's chevrons run through the doorway; an interior stair's lead up to its floor marker, and only those
  // whose tail (0.8 m behind the tip) stays on its room's floor are drawn. The floor X sits just inside a wall exit,
  // or on the stair itself.
  const lead = exit.interior ? -stairSide / 2 - 2.0 : -1.2;
  const inward = exit.interior ? 0 : 1.2;
  const shown = [0, 1, 2].filter((i) => i * 0.9 + lead - 0.8 >= -exit.approach + 0.1);
  return (
    <group>
      <mesh position={toWorld(signX, signY, lampY)}>
        <boxGeometry args={signSize} />
        <meshBasicMaterial color={exit.color} />
      </mesh>
      {exit.interior && <StairCore exit={exit} side={stairSide} />}
      {showSafe && shown.map((i) => (
        <mesh
          key={i}
          ref={(el) => { chevrons.current[i] = el; }}
          geometry={chevron}
          position={toWorld(x + ox * (i * 0.9 + lead), y + oy * (i * 0.9 + lead), 0.03)}
          rotation={[-Math.PI / 2, 0, yaw, 'YXZ']}
        >
          <meshBasicMaterial color={exit.color} transparent side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      ))}
      {showUnsafe && (
        <>
          <mesh geometry={cross} position={toWorld(x - ox * inward, y - oy * inward, 0.03)} rotation={[-Math.PI / 2, 0, 0]}>
            <meshBasicMaterial color={exit.color} side={THREE.DoubleSide} />
          </mesh>
          <group ref={billboard} position={toWorld(x, y, Math.max(lampY, OUTER_WALL_HEIGHT) + 0.8)}>
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
