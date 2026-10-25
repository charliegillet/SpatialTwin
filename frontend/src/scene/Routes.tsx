import { Line } from '@react-three/drei';
import { routeRenders } from '../twin/sceneModel.ts';
import type { DoorPlanResponse, VenueV2 } from '../twin/types.ts';
import { toWorld } from './coords.ts';

export default function Routes({ venue, plan }: { venue: VenueV2; plan: DoorPlanResponse | null }) {
  const routes = routeRenders(venue, plan);
  return (
    <group>
      {routes.map((r, i) => (
        <Line
          key={r.key}
          points={r.points.map(([x, y]) => toWorld(x, y, 0.1 + i * 0.004))}
          color={r.color}
          lineWidth={1.5 + r.width * 5}
          dashed={r.slowed}
          dashSize={0.6}
          gapSize={0.45}
          transparent
          opacity={r.slowed ? 0.55 : 0.95}
          depthWrite={false}
        />
      ))}
    </group>
  );
}
