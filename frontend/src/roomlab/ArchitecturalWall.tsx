import React, { useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import type { Mesh } from "three";
import type { Wall } from "./contracts.generated";
import type { WallSegmentPiece } from "./editorState";

export function ArchitecturalWall({
  piece,
  wall,
  floor,
  cutaway,
  selected,
  color,
  onSelect,
}: {
  piece: WallSegmentPiece;
  wall: Wall | undefined;
  floor: number[][];
  cutaway: boolean;
  selected: boolean;
  color: string;
  onSelect: () => void;
}) {
  const mesh = useRef<Mesh>(null),
    cut = useRef(false);
  const { invalidate } = useThree();
  useFrame(({ camera }) => {
    if (!mesh.current) return;
    if (cutaway && !selected && (wall?.role ?? "shell") === "shell" && wall) {
      const area = floor.reduce(
        (a, p, i) =>
          a +
          p[0] * floor[(i + 1) % floor.length][1] -
          floor[(i + 1) % floor.length][0] * p[1],
        0,
      );
      const dx = wall.end[0] - wall.start[0],
        dz = wall.end[1] - wall.start[1],
        len = Math.hypot(dx, dz) || 1;
      const sign = area >= 0 ? 1 : -1,
        nx = (sign * dz) / len,
        nz = (-sign * dx) / len;
      const dot =
        nx * (camera.position.x - (wall.start[0] + wall.end[0]) / 2) +
        nz * (camera.position.z - (wall.start[1] + wall.end[1]) / 2);
      if (dot > 0.15) cut.current = true;
      else if (dot < -0.15) cut.current = false;
    } else cut.current = false;
    const bottom = piece.center[1] - piece.height / 2;
    const h = cut.current
      ? Math.max(0, Math.min(bottom + piece.height, 0.35) - bottom)
      : piece.height;
    const target = h / piece.height;
    mesh.current.scale.y += (target - mesh.current.scale.y) * 0.3;
    mesh.current.position.y =
      bottom + (piece.height * mesh.current.scale.y) / 2;
    mesh.current.visible = mesh.current.scale.y > 0.002;
    if (Math.abs(target - mesh.current.scale.y) > 0.001) invalidate();
  });
  return (
    <mesh
      ref={mesh}
      position={piece.center}
      rotation={[0, piece.yawRad, 0]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
    >
      <boxGeometry args={[piece.length, piece.height, piece.thickness]} />
      <meshStandardMaterial
        color={color}
        roughness={0.85}
        metalness={0.1}
        transparent
        opacity={wall?.role === "partition" ? 0.35 : 0.65}
      />
    </mesh>
  );
}
