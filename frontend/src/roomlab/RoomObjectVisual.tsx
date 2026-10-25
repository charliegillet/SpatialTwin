import React, { useMemo } from "react";
import { createPartGeometry } from "./visualGeometry";
import { objectRoleAppearance } from "./appearance";
import { Edges } from "@react-three/drei";
import type { RoomObject } from "./contracts.generated";
import {
  buildObjectVisualParts,
  classifyVisualCategory,
  type LocalVisualPart,
  type VisualDisplayMode,
} from "./visualBounds";

export interface RoomObjectVisualProps {
  object: RoomObject;
  selected: boolean;
  mode: VisualDisplayMode;
}

/**
 * Pure local-space visual component for a RoomObject.
 *
 * Centered at local XZ origin (`x = 0, z = 0`) with floor at `y = 0`.
 * Parent applies world `center`, `yaw_deg` rotation, pointer events, and uncertainty overlays.
 * All child geometry fits strictly inside `[-width_m/2, +width_m/2] x [0, height_m] x [-depth_m/2, +depth_m/2]`.
 */
export const RoomObjectVisual: React.FC<RoomObjectVisualProps> = ({
  object,
  selected,
  mode,
}) => {
  const parts = useMemo(
    () =>
      buildObjectVisualParts(
        object.width_m,
        object.height_m,
        object.depth_m,
        object.category,
        object.label,
        mode,
      ),
    [
      object.width_m,
      object.height_m,
      object.depth_m,
      object.category,
      object.label,
      mode,
    ],
  );

  const vis = object.provenance?.visibility ?? "partial";
  const isSolid = object.provenance?.source === "user_measurement";
  const baseOpacity = isSolid ? 0.96 : vis === "unobserved" ? 0.45 : 0.78;
  const edgeColor = selected ? "#284b37" : isSolid ? "#729b91" : "#6b7768";

  return (
    <group>
      {parts.map((part) => {
        const appearance = objectRoleAppearance(object, part.role);
        return (
          <mesh key={part.id} position={part.position}>
            <PartGeometry part={part} />
            <meshStandardMaterial
              color={appearance.color}
              roughness={
                appearance.material === "marble"
                  ? 0.3
                  : part.role === "frame"
                    ? 0.45
                    : 0.75
              }
              metalness={part.role === "frame" ? 0.25 : 0.1}
              transparent={!isSolid}
              opacity={baseOpacity}
            />
            {part.shape === "box" && <Edges threshold={15} color={edgeColor} />}
          </mesh>
        );
      })}
    </group>
  );
};

function PartGeometry({ part }: { part: LocalVisualPart }) {
  const geometry = useMemo(() => createPartGeometry(part), [part]);
  React.useEffect(() => () => geometry.dispose(), [geometry]);
  return <primitive object={geometry} attach="geometry" />;
}
export default RoomObjectVisual;
