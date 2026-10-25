import React from "react";
import { Line } from "@react-three/drei";
import type { RoomSceneV1 } from "./contracts.generated";

export function LayoutCandidatePreview({
  current,
  candidate,
}: {
  current: RoomSceneV1;
  candidate: RoomSceneV1;
}) {
  return (
    <group>
      {(candidate.objects ?? []).map((next) => {
        const old = current.objects?.find((o) => o.id === next.id);
        if (!old) return null;
        const dx = next.center[0] - old.center[0],
          dz = next.center[1] - old.center[1];
        if (
          Math.hypot(dx, dz) < 1e-6 &&
          Math.abs((next.yaw_deg ?? 0) - (old.yaw_deg ?? 0)) < 1e-6
        )
          return null;
        const length = Math.hypot(dx, dz),
          ux = length ? dx / length : 0,
          uz = length ? dz / length : 0;
        const tip: [number, number, number] = [
          next.center[0],
          0.12,
          next.center[1],
        ];
        return (
          <group key={next.id}>
            <mesh
              position={[old.center[0], (old.height_m ?? 1) / 2, old.center[1]]}
              rotation={[0, ((old.yaw_deg ?? 0) * Math.PI) / 180, 0]}
            >
              <boxGeometry args={[old.width_m, old.height_m, old.depth_m]} />
              <meshBasicMaterial
                color="#b29267"
                wireframe
                transparent
                opacity={0.7}
              />
            </mesh>
            <mesh
              position={[
                next.center[0],
                (next.height_m ?? 1) / 2,
                next.center[1],
              ]}
              rotation={[0, ((next.yaw_deg ?? 0) * Math.PI) / 180, 0]}
            >
              <boxGeometry args={[next.width_m, next.height_m, next.depth_m]} />
              <meshBasicMaterial
                color="#508460"
                wireframe
                transparent
                opacity={0.95}
              />
            </mesh>
            {length > 1e-6 && (
              <>
                <Line
                  points={[[old.center[0], 0.12, old.center[1]], tip]}
                  color="#508460"
                  lineWidth={2}
                />
                <Line
                  points={[
                    [
                      tip[0] - 0.15 * ux + 0.1 * uz,
                      0.12,
                      tip[2] - 0.15 * uz - 0.1 * ux,
                    ],
                    tip,
                    [
                      tip[0] - 0.15 * ux - 0.1 * uz,
                      0.12,
                      tip[2] - 0.15 * uz + 0.1 * ux,
                    ],
                  ]}
                  color="#508460"
                  lineWidth={2}
                />
              </>
            )}
          </group>
        );
      })}
    </group>
  );
}
