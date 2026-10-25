import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import type * as THREE from 'three';
import { gateAmount } from '../twin/gateDraw.ts';
import { doorRenders, type DoorRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, GateVisual, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { WALL_HEIGHT } from './Building.tsx';

const SWING = Math.PI / 2 - 0.12;
const WARNING = '#efa28c';

function Door({ door, gate, reducedMotion }: { door: DoorRender; gate?: GateVisual; reducedMotion: boolean }) {
  const pivot = useRef<THREE.Group>(null);
  const amount = useRef(gate ? gateAmount(gate, Date.now()) : door.open ? 1 : 0);
  const [x, y] = door.position;
  const half = door.width / 2;
  // Hinge at the low end of the wall axis; leaf extends along +x (axis x) or +y (axis y).
  const hingeWorld = door.axis === 'x' ? toWorld(x - half, y, 0) : toWorld(x, y - half, 0);
  const base = door.axis === 'x' ? 0 : Math.PI / 2; // leaf direction in world (x or -z)
  const moving = gate?.draw === 'opening' || gate?.draw === 'closing';
  const doubtful = gate?.draw === 'unknown' || gate?.draw === 'fault';

  useFrame(({ invalidate }) => {
    const target = gate ? gateAmount(gate, Date.now()) : door.open ? 1 : 0;
    // Transit follows the controller's clock directly; plan changes and arrivals ease in.
    if (reducedMotion || moving) amount.current = target;
    else amount.current += Math.sign(target - amount.current) * Math.min(Math.abs(target - amount.current), 1 / 36);
    if (pivot.current) pivot.current.rotation.y = base + door.swing * amount.current * SWING;
    if (moving || amount.current !== target) invalidate();
  });

  const open = gate ? gate.draw === 'open' : door.open;
  return (
    <group>
      {door.hasLeaf && (
        <group position={hingeWorld} ref={pivot}>
          <mesh position={[half, 0.55, 0]}>
            <boxGeometry args={[door.width, 1.1, 0.1]} />
            <meshStandardMaterial color={doubtful ? '#5a4a44' : open ? '#33403b' : '#46544e'} roughness={0.6} metalness={0.2} />
          </mesh>
        </group>
      )}
      <mesh position={toWorld(x, y, WALL_HEIGHT + 0.32)}>
        <sphereGeometry args={[0.16, 14, 10]} />
        <meshBasicMaterial color={doubtful ? WARNING : door.color} />
      </mesh>
    </group>
  );
}

export default function Doors({ venue, plan, reducedMotion, gates }: { venue: VenueV2; plan: DoorPlanResponse | null; reducedMotion: boolean; gates?: Record<string, GateVisual> }) {
  return <group>{doorRenders(venue, plan).map((d) => <Door key={d.id} door={d} gate={gates?.[d.id]} reducedMotion={reducedMotion} />)}</group>;
}
