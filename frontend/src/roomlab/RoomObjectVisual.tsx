import React, { useMemo } from "react";
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

function roleColor(
  category: string,
  role: LocalVisualPart["role"],
  selected: boolean,
  source?: string,
): string {
  if (selected) {
    if (role === "frame") return "#3f6a50";
    if (role === "secondary") return "#67987b";
    return "#548768";
  }
  if (source === "user_measurement") {
    return role === "frame" ? "#0d9488" : "#10b981";
  }

  const kind = classifyVisualCategory(category, category);
  if (role === "foliage") return "#7d9c6c";
  if (role === "frame") return "#827c72";

  if (kind === "stairs") return role === "primary" ? "#c2ac85" : "#b39c74";
  if (kind === "counter") return role === "primary" ? "#dadcd5" : "#aab8af";
  if (kind === "table") return role === "primary" ? "#9eb7a5" : "#89a190";
  if (kind === "stool") return "#c4b295";
  if (kind === "sofa") return role === "primary" ? "#b7aaa0" : "#a3958b";
  if (kind === "chair") return role === "primary" ? "#aab4c3" : "#96a1b0";
  if (kind === "plant") return "#b89f82";
  if (kind === "bicycle") return role === "primary" ? "#7796a8" : "#64748b";
  if (kind === "bin") return role === "primary" ? "#d1d5db" : "#9ca3af";
  if (kind === "pillar") return "#b6bcb0";
  return "#a9b8a1";
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
    [object.width_m, object.height_m, object.depth_m, object.category, object.label, mode],
  );

  const vis = object.provenance?.visibility ?? "partial";
  const isSolid = object.provenance?.source === "user_measurement";
  const baseOpacity = isSolid ? 0.96 : vis === "unobserved" ? 0.45 : 0.78;
  const edgeColor = selected ? "#284b37" : "#6b7768";

  return (
    <group>
      {parts.map((part) => {
        const color = roleColor(
          object.category ?? "furniture",
          part.role,
          selected,
          object.provenance?.source,
        );
        const radius = part.size[0] * 0.5;
        return (
          <mesh key={part.id} position={part.position}>
            {part.shape === "cylinder" ? (
              <cylinderGeometry args={[radius, radius, part.size[1], 20]} />
            ) : (
              <boxGeometry args={part.size} />
            )}
            <meshStandardMaterial
              color={color}
              roughness={part.role === "frame" ? 0.45 : 0.65}
              metalness={part.role === "frame" ? 0.25 : 0.1}
              transparent={!isSolid}
              opacity={baseOpacity}
            />
            {part.shape === "box" && (
              <Edges
                threshold={15}
                color={edgeColor}
              />
            )}
          </mesh>
        );
      })}
    </group>
  );
};

export default RoomObjectVisual;
