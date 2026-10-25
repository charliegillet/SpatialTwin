import React, { useMemo } from "react";
import { glassPalette, resolveWallAppearance } from "./appearance";
import type { Opening, Wall } from "./contracts.generated";
import { buildOpeningVisualParts } from "./visualBounds";

export interface OpeningVisualProps {
  opening: Opening;
  wall: Wall;
  selected?: boolean;
}

/**
 * Pure aperture-local visual component for a door, window, or passage.
 *
 * Local `+X` runs along `wall.start -> wall.end`; local origin `(0, 0, 0)` is at the
 * opening's horizontal center on the floor (`y = 0`).
 * Parent positions and rotates the group in world space.
 * Fits strictly within the declared aperture `[width_m, height_m, wall.thickness_m]`.
 * No assumed hinge or swing arc is rendered because `Opening` v1 lacks hinge/leaf metadata.
 */
export const OpeningVisual: React.FC<OpeningVisualProps> = ({
  opening,
  wall,
  selected = false,
}) => {
  const parts = useMemo(
    () =>
      buildOpeningVisualParts(
        opening.kind,
        opening.width_m,
        opening.height_m ?? 2.1,
        opening.sill_m ?? 0,
        wall.thickness_m ?? 0.12,
      ),
    [
      opening.kind,
      opening.width_m,
      opening.height_m,
      opening.sill_m,
      wall.thickness_m,
    ],
  );

  const palette = glassPalette(resolveWallAppearance(wall));
  const frameColor = palette.frame;
  const glassColor = palette.pane;
  const thresholdColor = selected ? "#d79e54" : palette.frame;

  return (
    <group>
      {parts.map((part) => {
        const isGlass = part.role === "glass";
        const isFrame = part.role === "frame";
        return (
          <mesh key={part.id} position={part.position}>
            <boxGeometry args={part.size} />
            <meshStandardMaterial
              color={
                isGlass ? glassColor : isFrame ? frameColor : thresholdColor
              }
              roughness={isGlass ? 0.15 : 0.7}
              metalness={isGlass ? 0.1 : 0.15}
              transparent={isGlass}
              opacity={isGlass ? 0.14 : 0.95}
              depthWrite={!isGlass}
            />
          </mesh>
        );
      })}
    </group>
  );
};

export default OpeningVisual;
