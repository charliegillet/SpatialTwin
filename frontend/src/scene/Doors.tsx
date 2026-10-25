import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import { gateAmount } from '../twin/gateDraw.ts';
import { doorRenders, type DoorRender } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, GateVisual, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';
import { ORDER, WALL_HEIGHT } from './Building.tsx';
import { LEAF_COLOR } from './palette.ts';

const SWING = Math.PI / 2 - 0.12;
const WARNING = '#efa28c';
const DOUBT_LEAF = '#5a4a44';
const LEAF_HEIGHT = WALL_HEIGHT - 0.06;
const LEAF_THICK = 0.06;

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

  const leaf = doubtful ? DOUBT_LEAF : LEAF_COLOR[door.kind];
  // The threshold strip shows the door's lamp on the floor, so open / denied reads from the top view too.
  const sill: [number, number, number] = door.axis === 'x' ? [door.width, 0.012, 0.26] : [0.26, 0.012, door.width];
  return (
    <group>
      <mesh position={toWorld(x, y, 0.012)} renderOrder={ORDER.overlay}>
        <boxGeometry args={sill} />
        <meshBasicMaterial color={doubtful ? WARNING : door.color} transparent opacity={0.7} depthWrite={false} />
      </mesh>
      {door.hasLeaf && (
        <group position={hingeWorld} ref={pivot}>
          <mesh position={[half, LEAF_HEIGHT / 2 + 0.02, 0]}>
            <boxGeometry args={[door.width - 0.04, LEAF_HEIGHT, LEAF_THICK]} />
            <meshStandardMaterial color={leaf} roughness={0.55} metalness={door.kind === 'servo_door' || door.kind === 'roller_door' ? 0.45 : 0.08} />
          </mesh>
          {/* Fire and smoke doors carry a pale rated band across the leaf, so they stay distinct from room doors. */}
          {(door.kind === 'fire_door' || door.kind === 'smoke_door') && !doubtful && (
            <mesh position={[half, LEAF_HEIGHT * 0.72, 0]}>
              <boxGeometry args={[door.width - 0.1, 0.07, LEAF_THICK + 0.012]} />
              <meshBasicMaterial color="#e9d8c7" />
            </mesh>
          )}
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
