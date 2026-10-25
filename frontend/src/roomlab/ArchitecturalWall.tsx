import React, { useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { Mesh } from "three";
import { Edges } from "@react-three/drei";
import { shellOutwardNormal, setPiecePicking } from "./visualGeometry";
import { wallFrameParts } from "./wallVisualParts";
import type { ResolvedAppearance } from "./appearance";
import type { Wall } from "./contracts.generated";
import type { WallSegmentPiece } from "./editorState";

export function ArchitecturalWall({
  piece,
  wall,
  floor,
  cutaway,
  selected,
  appearance,
  measured,
  onSelect,
}: {
  piece: WallSegmentPiece;
  wall: Wall | undefined;
  floor: number[][];
  cutaway: boolean;
  selected: boolean;
  appearance: ResolvedAppearance;
  measured: boolean;
  onSelect: () => void;
}) {
  const mesh = useRef<Mesh>(null),
    cut = useRef(false);
  const pickers = useRef(new WeakMap<Mesh, Mesh["raycast"]>());
  const { invalidate } = useThree();
  const followsFloor = Boolean(
    wall &&
      floor.some(
        (p, i) =>
          Math.hypot(p[0] - wall.start[0], p[1] - wall.start[1]) < 1e-4 &&
          Math.hypot(
            floor[(i + 1) % floor.length][0] - wall.end[0],
            floor[(i + 1) % floor.length][1] - wall.end[1],
          ) < 1e-4,
      ),
  );
  const frames = useMemo(
    () => wallFrameParts(piece.length, piece.height, piece.thickness),
    [piece.length, piece.height, piece.thickness],
  );
  useFrame(({ camera }) => {
    if (!mesh.current) return;
    if (followsFloor && cutaway && !selected && (wall?.role ?? "shell") === "shell" && wall) {
      const [nx, nz] = shellOutwardNormal(floor, wall.start, wall.end);
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
    const visible = mesh.current.scale.y > 0.002;
    mesh.current.traverse((child) => {
      if (child instanceof Mesh) {
        if (!pickers.current.has(child))
          pickers.current.set(child, child.raycast);
        setPiecePicking(child, visible, pickers.current.get(child)!);
      }
    });
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
        color={appearance.color}
        roughness={0.85}
        metalness={0.1}
        transparent
        opacity={appearance.material === "glass" ? 0.22 : 0.9}
      />
      {appearance.material === "glass" &&
        frames.map((p) => (
          <mesh key={p.id} position={p.position}>
            <boxGeometry args={p.size} />
            <meshStandardMaterial
              color="#8e9183"
              roughness={0.5}
              metalness={0.35}
            />
          </mesh>
        ))}
      {(selected || measured) && (
        <Edges
          raycast={() => {}}
          color={selected ? "#3f7059" : "#779b91"}
          threshold={15}
        />
      )}
    </mesh>
  );
}
