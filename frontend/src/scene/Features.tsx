import type { VenueV2 } from '../twin/types.ts';
import { OUTER_WALL_HEIGHT } from './Building.tsx';

const GLASS = '#a9d4e6';
const RAIL = '#7b5a32';

/** Railings, glass partitions and windows from a video walkthrough's room reading. Looks only: the planner never sees
 *  them (a partition that divides rooms is already a wall between zones). Heights are capped to the cutaway shell so
 *  nothing towers over the walls and hides the rooms behind. */
export default function Features({ venue }: { venue: VenueV2 }) {
  const features = venue.appearance?.features ?? [];
  if (features.length === 0) return null;
  return (
    <group>
      {features.map((f, index) => {
        const dx = f.b[0] - f.a[0];
        const dy = f.b[1] - f.a[1];
        const length = Math.hypot(dx, dy);
        if (length < 0.05) return null;
        const angle = Math.atan2(dy, dx);
        const cx = (f.a[0] + f.b[0]) / 2;
        const cy = (f.a[1] + f.b[1]) / 2;
        if (f.kind === 'railing') {
          const h = Math.min(f.height, 1.1);
          return (
            <group key={index} position={[cx, 0, -cy]} rotation={[0, angle, 0]}>
              <mesh position={[0, h, 0]}><boxGeometry args={[length, 0.05, 0.06]} /><meshStandardMaterial color={RAIL} roughness={0.5} /></mesh>
              <mesh position={[0, h / 2, 0]}><boxGeometry args={[length, h, 0.02]} /><meshStandardMaterial color={GLASS} transparent opacity={0.28} depthWrite={false} /></mesh>
            </group>
          );
        }
        const bottom = f.kind === 'window' ? Math.min(f.sill, OUTER_WALL_HEIGHT - 0.4) : 0;
        const top = Math.min(f.kind === 'window' ? f.sill + f.height : f.height, OUTER_WALL_HEIGHT + 0.05);
        const h = Math.max(0.2, top - bottom);
        return (
          <mesh key={index} position={[cx, bottom + h / 2, -cy]} rotation={[0, angle, 0]} raycast={() => null}>
            <boxGeometry args={[length, h, f.kind === 'window' ? 0.3 : 0.04]} />
            <meshStandardMaterial color={GLASS} transparent opacity={f.kind === 'window' ? 0.55 : 0.32} roughness={0.1} metalness={0.1} depthWrite={false} />
          </mesh>
        );
      })}
    </group>
  );
}
