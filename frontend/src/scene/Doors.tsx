import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type * as THREE from 'three';
import { doorRenders, type DoorRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { WALL_HEIGHT } from './Building.tsx';

const SWING = Math.PI / 2 - 0.12;

function Door({ door, reducedMotion }: { door: DoorRender; reducedMotion: boolean }) {
  const pivot = useRef<THREE.Group>(null);
  const amount = useRef(door.open ? 1 : 0);
  const [x, y] = door.position;
  const half = door.width / 2;
  // Hinge at the low end of the wall axis; leaf extends along +x (axis x) or +y (axis y).
  const hingeWorld = door.axis === 'x' ? toWorld(x - half, y, 0) : toWorld(x, y - half, 0);
  const base = door.axis === 'x' ? 0 : Math.PI / 2; // leaf direction in world (x or -z)

  useFrame(({ invalidate }) => {
    const target = door.open ? 1 : 0;
    if (reducedMotion) amount.current = target;
    else amount.current += Math.sign(target - amount.current) * Math.min(Math.abs(target - amount.current), 1 / 36);
    if (pivot.current) pivot.current.rotation.y = base + door.swing * amount.current * SWING;
    if (amount.current !== target) invalidate();
  });

  return (
    <group>
      {door.hasLeaf && (
        <group position={hingeWorld} ref={pivot}>
          <mesh position={[half, 0.55, 0]}>
            <boxGeometry args={[door.width, 1.1, 0.1]} />
            <meshStandardMaterial color={door.open ? '#33403b' : '#46544e'} roughness={0.6} metalness={0.2} />
          </mesh>
        </group>
      )}
      <mesh position={toWorld(x, y, WALL_HEIGHT + 0.32)}>
        <sphereGeometry args={[0.16, 14, 10]} />
        <meshBasicMaterial color={door.color} />
      </mesh>
    </group>
  );
}

export default function Doors({ venue, plan, reducedMotion }: { venue: VenueV2; plan: DoorPlanResponse | null; reducedMotion: boolean }) {
  return <group>{doorRenders(venue, plan).map((d) => <Door key={d.id} door={d} reducedMotion={reducedMotion} />)}</group>;
}
