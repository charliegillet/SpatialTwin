import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Html, Line, Edges } from "@react-three/drei";
import * as THREE from "three";
import type {
  RoomObject,
  RoomSceneV1,
  SolveResult,
} from "./contracts.generated";
import {
  buildSegmentedWallPieces,
  deriveWallsFromFloor,
  wallLengthMeters,
  type SelectionTarget,
  type ViewMode,
} from "./editorState";
import {
  GlowContext,
  ObjectModel,
  TexturedFloor,
  objectColor,
  objectKind,
  resolveAppearance,
  shade,
} from "./RoomModels";

interface RoomCanvas3DProps {
  scene: RoomSceneV1 | null;
  selectedTarget: SelectionTarget;
  viewMode: ViewMode;
  showCSpace: boolean;
  showEndpoints: boolean;
  startPoint: [number, number];
  goalPoint: [number, number];
  agentDiameterM: number;
  marginM: number;
  solveResult: SolveResult | null;
  pickEndpointMode: "start" | "goal" | null;
  onSelectTarget: (target: SelectionTarget) => void;
  onMoveObject: (objectId: string, newCenter: [number, number]) => void;
  onPickEndpoint: (pt: [number, number]) => void;
}

function detectWebGLAvailable(): boolean {
  if (typeof window === "undefined" || typeof document === "undefined")
    return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(
      window.WebGLRenderingContext &&
        (canvas.getContext("webgl2") ||
          canvas.getContext("webgl") ||
          canvas.getContext("experimental-webgl")),
    );
  } catch {
    return false;
  }
}

const NO_GLOW = { color: "#000000", intensity: 0 };
const SELECTED_GLOW = { color: "#f59e0b", intensity: 0.35 };
const WALL_SELECTED_GLOW = { color: "#38bdf8", intensity: 0.45 };
const ANCHOR_GLOW = { color: "#10b981", intensity: 0.3 };
const DOOR_COLOR = "#9c6b3f";
const WINDOW_FRAME_COLOR = "#5b6470";
const GLASS_FRAME_COLOR = "#6e5a43";
const GLASS_COLOR = "#bfe3ee";
// Hidden (cut-away) walls must not swallow clicks meant for objects behind them.
const NO_RAYCAST = () => {};

function floorCentroid(floor: number[][]): [number, number] {
  const n = Math.max(1, floor.length);
  return [
    floor.reduce((s, p) => s + p[0], 0) / n,
    floor.reduce((s, p) => s + p[1], 0) / n,
  ];
}

type WallGlow = { color: string; intensity: number };

/** Interior glass partition or atrium railing piece: a glass pane with a frame. */
function GlassWallPiece({
  piece,
  role,
  glow,
}: {
  piece: ReturnType<typeof buildSegmentedWallPieces>[number];
  role: "partition" | "railing";
  glow: WallGlow;
}) {
  const { length, height, thickness } = piece;
  const frame = (
    <meshStandardMaterial
      color={GLASS_FRAME_COLOR}
      roughness={0.4}
      metalness={0.5}
      emissive={glow.color}
      emissiveIntensity={glow.intensity}
    />
  );
  const railT = Math.min(thickness, 0.1);
  const mullions =
    role === "partition" ? Math.max(1, Math.round(length / 1.2)) : 0;
  return (
    <group position={piece.center} rotation={[0, piece.yawRad, 0]}>
      <mesh>
        <boxGeometry args={[length, height, 0.03]} />
        <meshStandardMaterial
          color={glow.intensity > 0 ? glow.color : GLASS_COLOR}
          transparent
          opacity={glow.intensity > 0 ? 0.4 : 0.28}
          roughness={0.05}
          metalness={0.1}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[0, height / 2 - 0.03, 0]} castShadow>
        <boxGeometry args={[length, 0.06, railT]} />
        {frame}
      </mesh>
      <mesh position={[0, -height / 2 + 0.04, 0]}>
        <boxGeometry args={[length, 0.08, railT]} />
        {frame}
      </mesh>
      {Array.from({ length: mullions + 1 }, (_, i) => (
        <mesh
          key={i}
          position={[-length / 2 + (i * length) / Math.max(1, mullions), 0, 0]}
          castShadow
        >
          <boxGeometry args={[0.05, height, railT]} />
          {frame}
        </mesh>
      ))}
    </group>
  );
}

/**
 * Solid full-height shell walls; any shell wall whose outward side faces the camera
 * hides itself so the room stays visible while orbiting, leaving a baseboard stub.
 * Interior partitions and railings are drawn as framed glass and never hide.
 */
function RoomWalls({
  scene,
  wallColor,
  selectedWallId,
  anchorId,
  onSelectWall,
}: {
  scene: RoomSceneV1;
  wallColor: string;
  selectedWallId: string | null;
  anchorId: string | undefined;
  onSelectWall: (wallId: string) => void;
}) {
  const { camera } = useThree();
  const pieces = useMemo(() => buildSegmentedWallPieces(scene), [scene]);
  const walls = useMemo(() => deriveWallsFromFloor(scene), [scene]);
  const centroid = useMemo(() => floorCentroid(scene.floor), [scene.floor]);
  const outwardNormals = useMemo(() => {
    const map = new Map<string, [number, number]>();
    for (const w of walls) {
      if ((w.role ?? "shell") !== "shell") continue;
      const dx = w.end[0] - w.start[0];
      const dz = w.end[1] - w.start[1];
      const len = Math.hypot(dx, dz) || 1;
      let nx = dz / len;
      let nz = -dx / len;
      const mx = (w.start[0] + w.end[0]) / 2 - centroid[0];
      const mz = (w.start[1] + w.end[1]) / 2 - centroid[1];
      if (nx * mx + nz * mz < 0) {
        nx = -nx;
        nz = -nz;
      }
      map.set(w.id, [nx, nz]);
    }
    return map;
  }, [walls, centroid]);
  const groupRefs = useRef(new Map<string, THREE.Group>());

  useFrame(() => {
    const vx = camera.position.x - centroid[0];
    const vz = camera.position.z - centroid[1];
    const horiz = Math.hypot(vx, vz);
    const overhead = horiz < 0.35 * Math.abs(camera.position.y);
    groupRefs.current.forEach((group, wallId) => {
      const n = outwardNormals.get(wallId);
      const visible =
        overhead || !n || (n[0] * vx + n[1] * vz) / horiz < 0.3;
      if (group.visible === visible) return;
      group.visible = visible;
      group.traverse((o) => {
        if ((o as THREE.Mesh).isMesh)
          o.raycast = visible ? THREE.Mesh.prototype.raycast : NO_RAYCAST;
      });
    });
  });

  const baseboard = shade(wallColor, -0.18);

  return (
    <>
      {walls.map((wall) => {
        const role = wall.role ?? "shell";
        const glow =
          selectedWallId === wall.id
            ? WALL_SELECTED_GLOW
            : anchorId === wall.id
              ? ANCHOR_GLOW
              : NO_GLOW;
        const wallPieces = pieces.filter((p) => p.wallId === wall.id);
        const dx = wall.end[0] - wall.start[0];
        const dz = wall.end[1] - wall.start[1];
        const total = Math.hypot(dx, dz) || 1;
        const yawRad = Math.atan2(-dz, dx);
        const thickness = wall.thickness_m ?? 0.12;
        const select = (e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          onSelectWall(wall.id);
        };
        return (
          <React.Fragment key={wall.id}>
            <group
              ref={(g) => {
                if (g && role === "shell") groupRefs.current.set(wall.id, g);
                else groupRefs.current.delete(wall.id);
              }}
            >
              {wallPieces.map((piece) =>
                role === "shell" ? (
                  <mesh
                    key={piece.key}
                    position={piece.center}
                    rotation={[0, piece.yawRad, 0]}
                    castShadow
                    receiveShadow
                    onClick={select}
                  >
                    <boxGeometry
                      args={[piece.length, piece.height, piece.thickness]}
                    />
                    <meshStandardMaterial
                      color={wallColor}
                      roughness={0.9}
                      metalness={0.02}
                      emissive={glow.color}
                      emissiveIntensity={glow.intensity}
                    />
                  </mesh>
                ) : (
                  <group key={piece.key}>
                    <GlassWallPiece piece={piece} role={role} glow={glow} />
                    {/* Invisible box keeps the whole glass panel clickable. */}
                    <mesh
                      position={piece.center}
                      rotation={[0, piece.yawRad, 0]}
                      onClick={select}
                    >
                      <boxGeometry
                        args={[piece.length, piece.height, piece.thickness]}
                      />
                      <meshBasicMaterial
                        transparent
                        opacity={0}
                        depthWrite={false}
                        colorWrite={false}
                      />
                    </mesh>
                  </group>
                ),
              )}
              {(scene.openings ?? [])
                .filter((op) => op.wall_id === wall.id && op.kind !== "passage")
                .map((op) => {
                  const s = op.offset_m + op.width_m / 2;
                  const cx = wall.start[0] + (dx / total) * s;
                  const cz = wall.start[1] + (dz / total) * s;
                  const h = op.height_m ?? 2.1;
                  const sill = op.sill_m ?? 0;
                  return (
                    <group
                      key={`vis-${op.id}`}
                      position={[cx, sill, cz]}
                      rotation={[0, yawRad, 0]}
                    >
                      {op.kind === "door" ? (
                        <>
                          <mesh position={[0, h / 2, 0]} castShadow>
                            <boxGeometry
                              args={[Math.max(0.1, op.width_m - 0.04), h - 0.02, 0.05]}
                            />
                            <meshStandardMaterial color={DOOR_COLOR} roughness={0.6} />
                          </mesh>
                          {[-1, 1].map((side) => (
                            <mesh
                              key={side}
                              position={[side * op.width_m * 0.22, h * 0.6, 0]}
                            >
                              <boxGeometry args={[op.width_m * 0.3, h * 0.5, 0.06]} />
                              <meshStandardMaterial
                                color={GLASS_COLOR}
                                transparent
                                opacity={0.35}
                                roughness={0.05}
                              />
                            </mesh>
                          ))}
                        </>
                      ) : (
                        <>
                          <mesh position={[0, h / 2, 0]}>
                            <boxGeometry args={[op.width_m, h, 0.03]} />
                            <meshStandardMaterial
                              color={GLASS_COLOR}
                              transparent
                              opacity={0.35}
                              roughness={0.05}
                              depthWrite={false}
                            />
                          </mesh>
                          {[0, h].map((y) => (
                            <mesh key={y} position={[0, y, 0]}>
                              <boxGeometry args={[op.width_m, 0.05, thickness + 0.02]} />
                              <meshStandardMaterial
                                color={WINDOW_FRAME_COLOR}
                                roughness={0.5}
                              />
                            </mesh>
                          ))}
                        </>
                      )}
                    </group>
                  );
                })}
            </group>
            {role === "shell" &&
              wallPieces
                .filter((piece) => piece.center[1] - piece.height / 2 < 0.01)
                .map((piece) => {
                  const stubH = Math.min(0.12, piece.height);
                  return (
                    <mesh
                      key={`base-${piece.key}`}
                      position={[piece.center[0], stubH / 2, piece.center[2]]}
                      rotation={[0, piece.yawRad, 0]}
                      receiveShadow
                    >
                      <boxGeometry
                        args={[piece.length, stubH, piece.thickness + 0.012]}
                      />
                      <meshStandardMaterial color={baseboard} roughness={0.8} />
                    </mesh>
                  );
                })}
          </React.Fragment>
        );
      })}
    </>
  );
}

function CameraController({
  viewMode,
  isDraggingObject,
  floor,
}: {
  viewMode: ViewMode;
  isDraggingObject: boolean;
  floor: number[][];
}) {
  const { camera, size } = useThree();
  const fit = Math.max(
    1,
    1.15 / Math.max(0.2, size.width / Math.max(1, size.height)),
  );
  const controlsRef = useRef<any>(null);
  const bounds = useMemo(() => {
    const xs = floor.map((p) => p[0]),
      zs = floor.map((p) => p[1]);
    return {
      x: (Math.min(...xs) + Math.max(...xs)) / 2,
      z: (Math.min(...zs) + Math.max(...zs)) / 2,
      span: Math.max(
        3,
        Math.max(...xs) - Math.min(...xs),
        Math.max(...zs) - Math.min(...zs),
      ),
    };
  }, [floor]);

  useEffect(() => {
    if (viewMode === "top") {
      camera.position.set(bounds.x, bounds.span * 1.6 * fit, bounds.z + 0.01);
      camera.lookAt(bounds.x, 0, bounds.z);
    } else {
      camera.position.set(
        bounds.x + bounds.span * 0.9 * fit,
        bounds.span * 1.1 * fit,
        bounds.z + bounds.span * 1.1 * fit,
      );
      camera.lookAt(bounds.x, 0.6, bounds.z);
    }
    if (controlsRef.current) {
      controlsRef.current.target.set(bounds.x, 0.4, bounds.z);
      controlsRef.current.update();
    }
  }, [viewMode, camera, bounds, fit]);

  return (
    <OrbitControls
      ref={controlsRef}
      makeDefault
      enabled={!isDraggingObject}
      enableRotate={viewMode === "orbit" && !isDraggingObject}
      maxPolarAngle={Math.PI / 2 - 0.04}
      minDistance={1.5}
      maxDistance={Math.max(35, bounds.span * 5)}
    />
  );
}

function RoomSceneContent({
  scene,
  selectedTarget,
  viewMode,
  showCSpace,
  showEndpoints,
  startPoint,
  goalPoint,
  agentDiameterM,
  marginM,
  solveResult,
  pickEndpointMode,
  onSelectTarget,
  onMoveObject,
  onPickEndpoint,
  showLabels,
}: RoomCanvas3DProps & { scene: RoomSceneV1; showLabels: boolean }) {
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const dragOffsetRef = useRef<[number, number]>([0, 0]);
  // Preserve selection through the trailing click after pressing or dragging an object.
  const objectPressRef = useRef(false);
  const floorPlane = useMemo(
    () => new THREE.Plane(new THREE.Vector3(0, 1, 0), 0),
    [],
  );

  const walls = useMemo(() => deriveWallsFromFloor(scene), [scene]);
  const appearance = useMemo(() => resolveAppearance(scene), [scene]);
  const [cx, cz] = useMemo(() => floorCentroid(scene.floor), [scene.floor]);
  const span = useMemo(() => {
    const xs = scene.floor.map((p) => p[0]);
    const zs = scene.floor.map((p) => p[1]);
    return Math.max(
      3,
      Math.max(...xs) - Math.min(...xs),
      Math.max(...zs) - Math.min(...zs),
    );
  }, [scene.floor]);
  const rEff = agentDiameterM * 0.5 + marginM;

  const handleFloorPointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (!draggingId) return;
    e.stopPropagation();
    const hit = new THREE.Vector3();
    if (e.ray.intersectPlane(floorPlane, hit)) {
      const nx = Math.round((hit.x + dragOffsetRef.current[0]) * 50) / 50;
      const nz = Math.round((hit.z + dragOffsetRef.current[1]) * 50) / 50;
      onMoveObject(draggingId, [nx, nz]);
    }
  };

  const handleFloorPointerUp = (e: ThreeEvent<PointerEvent>) => {
    if (draggingId) {
      e.stopPropagation();
      setDraggingId(null);
    }
  };

  const handleFloorClick = (e: ThreeEvent<MouseEvent>) => {
    if (pickEndpointMode) {
      e.stopPropagation();
      const hit = new THREE.Vector3();
      if (e.ray.intersectPlane(floorPlane, hit)) {
        onPickEndpoint([
          Math.round(hit.x * 50) / 50,
          Math.round(hit.z * 50) / 50,
        ]);
      }
      return;
    }
    // Ignore the click that ends an object press/drag or a camera orbit; only a plain click on empty floor deselects.
    if (objectPressRef.current || e.delta > 4) return;
    onSelectTarget(null);
  };

  return (
    <>
      <color attach="background" args={["#f5f5f2"]} />
      <hemisphereLight args={["#fff8ec", "#4a4f57", 1.1]} />
      <directionalLight
        position={[cx + span * 0.6, span * 1.4, cz + span * 0.4]}
        intensity={1.5}
        color="#fffaf0"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0005}
        shadow-camera-left={-span}
        shadow-camera-right={span}
        shadow-camera-top={span}
        shadow-camera-bottom={-span}
        shadow-camera-far={span * 5}
      >
        <object3D attach="target" position={[cx, 0, cz]} />
      </directionalLight>

      <CameraController
        viewMode={viewMode}
        floor={scene.floor}
        isDraggingObject={draggingId !== null}
      />

      {/* Interactive Ground Plane for Dragging & Endpoint Picking */}
      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[0, -0.002, 0]}
        onPointerDown={() => {
          objectPressRef.current = false;
        }}
        onPointerMove={handleFloorPointerMove}
        onPointerUp={handleFloorPointerUp}
        onClick={handleFloorClick}
      >
        <planeGeometry args={[80, 80]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>

      <gridHelper
        args={[24, 24, "#dfe2d8", "#e9ece4"]}
        position={[0, -0.01, 0]}
      />

      <TexturedFloor
        floor={scene.floor}
        voids={scene.floor_voids}
        appearance={appearance}
      />
      {(scene.floor_voids ?? []).map((v) => (
        <group key={v.id}>
          <Line
            points={[...v.polygon, v.polygon[0]].map(
              (p) => [p[0], 0.04, p[1]] as [number, number, number],
            )}
            color="#b9a274"
            lineWidth={3}
          />
          <Html
            position={[
              v.polygon.reduce((a, p) => a + p[0], 0) / v.polygon.length,
              0.1,
              v.polygon.reduce((a, p) => a + p[1], 0) / v.polygon.length,
            ]}
            center
          >
            <button
              className="rl-3d-tag"
              onClick={() => onSelectTarget({ kind: "void", id: v.id })}
            >
              ⚠ {v.id} · NO FLOOR
            </button>
          </Html>
        </group>
      ))}

      <RoomWalls
        scene={scene}
        wallColor={appearance.wallColor}
        selectedWallId={
          selectedTarget?.kind === "wall" ? selectedTarget.id : null
        }
        anchorId={scene.calibration?.anchor_id}
        onSelectWall={(id) => onSelectTarget({ kind: "wall", id })}
      />

      {/* Wall Dimension Badges */}
      {walls.map((w) => {
        const mx = (w.start[0] + w.end[0]) * 0.5;
        const mz = (w.start[1] + w.end[1]) * 0.5;
        const len = wallLengthMeters(w);
        const isSelected =
          selectedTarget?.kind === "wall" && selectedTarget.id === w.id;
        return (
          <Html
            style={{ display: showLabels || isSelected ? "block" : "none" }}
            key={`lbl-${w.id}`}
            position={[mx, (w.height_m ?? 2.7) + 0.16, mz]}
            center
          >
            <button
              type="button"
              className={`rl-3d-tag ${isSelected ? "rl-3d-tag--active" : ""}`}
              onClick={() => onSelectTarget({ kind: "wall", id: w.id })}
            >
              {w.id}: {len.toFixed(2)}m
            </button>
          </Html>
        );
      })}

      {/* Door & Window Frame Threshold Markers */}
      {(scene.openings ?? []).map((op) => {
        const wall = walls.find((w) => w.id === op.wall_id);
        if (!wall) return null;
        const dx = wall.end[0] - wall.start[0];
        const dz = wall.end[1] - wall.start[1];
        const total = Math.hypot(dx, dz);
        if (total < 0.05) return null;
        const mid = op.offset_m + op.width_m * 0.5;
        const cx = wall.start[0] + (dx / total) * mid;
        const cz = wall.start[1] + (dz / total) * mid;
        const yawRad = Math.atan2(-dz, dx);
        const isSelected =
          selectedTarget?.kind === "opening" && selectedTarget.id === op.id;
        return (
          <group
            key={op.id}
            position={[cx, 0.02, cz]}
            rotation={[0, yawRad, 0]}
          >
            <mesh
              onClick={(e) => {
                e.stopPropagation();
                onSelectTarget({ kind: "opening", id: op.id });
              }}
            >
              <boxGeometry
                args={[op.width_m, 0.03, (wall.thickness_m ?? 0.12) + 0.06]}
              />
              <meshBasicMaterial
                color={
                  isSelected
                    ? "#f59e0b"
                    : op.kind === "window"
                      ? "#a3bdb0"
                      : "#8bb29a"
                }
              />
            </mesh>
          </group>
        );
      })}

      {/* Room Objects: a recognizable model per kind, colored from the video; an invisible box handles picking */}
      {(scene.objects ?? []).map((obj: RoomObject) => {
        const isSelected =
          selectedTarget?.kind === "object" && selectedTarget.id === obj.id;
        const isAnchor = scene.calibration?.anchor_id === obj.id;
        const yawRad = ((obj.yaw_deg ?? 0) * Math.PI) / 180;
        const kind = objectKind(obj);
        const glow = isSelected
          ? SELECTED_GLOW
          : isAnchor
            ? ANCHOR_GLOW
            : NO_GLOW;
        const uncRadius = obj.uncertainty_radius_m ?? 0;

        return (
          <group key={obj.id} position={[obj.center[0], 0, obj.center[1]]}>
            <group rotation={[0, yawRad, 0]}>
              <GlowContext.Provider value={glow}>
                <ObjectModel
                  kind={kind}
                  w={obj.width_m}
                  d={obj.depth_m}
                  h={obj.height_m}
                  color={objectColor(obj, kind)}
                />
              </GlowContext.Provider>
            </group>
            <mesh
              position={[0, obj.height_m * 0.5, 0]}
              rotation={[0, yawRad, 0]}
              onPointerDown={(e) => {
                e.stopPropagation();
                objectPressRef.current = true;
                onSelectTarget({ kind: "object", id: obj.id });
                const hit = new THREE.Vector3();
                if (e.ray.intersectPlane(floorPlane, hit)) {
                  dragOffsetRef.current = [
                    obj.center[0] - hit.x,
                    obj.center[1] - hit.z,
                  ];
                  setDraggingId(obj.id);
                }
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <boxGeometry args={[obj.width_m, obj.height_m, obj.depth_m]} />
              <meshBasicMaterial
                transparent
                opacity={0}
                depthWrite={false}
                colorWrite={false}
              />
              {(isSelected || isAnchor) && (
                <Edges
                  scale={1.03}
                  color={isSelected ? "#f59e0b" : "#10b981"}
                  renderOrder={2}
                />
              )}
            </mesh>

            {/* Uncertainty Halo Footprint */}
            {uncRadius > 0.01 && (showCSpace || isSelected) && (
              <mesh position={[0, 0.01, 0]} rotation={[0, yawRad, 0]}>
                <boxGeometry
                  args={[
                    obj.width_m + uncRadius * 2,
                    0.01,
                    obj.depth_m + uncRadius * 2,
                  ]}
                />
                <meshBasicMaterial
                  color="#adb99d"
                  wireframe
                  transparent
                  opacity={0.35}
                />
              </mesh>
            )}

            {/* C-Space Minkowski Inflation Footprint */}
            {showCSpace && (
              <mesh position={[0, 0.015, 0]} rotation={[0, yawRad, 0]}>
                <boxGeometry
                  args={[
                    obj.width_m + (rEff + uncRadius) * 2,
                    0.012,
                    obj.depth_m + (rEff + uncRadius) * 2,
                  ]}
                />
                <meshBasicMaterial
                  color="#f43f5e"
                  transparent
                  opacity={0.18}
                  depthWrite={false}
                />
              </mesh>
            )}

            <Html
              style={{ display: showLabels || isSelected ? "block" : "none" }}
              position={[0, obj.height_m + 0.22, 0]}
              center
            >
              <button
                type="button"
                className={`rl-3d-tag ${isSelected ? "rl-3d-tag--active" : ""}`}
                onClick={() => onSelectTarget({ kind: "object", id: obj.id })}
              >
                {obj.label} ({obj.width_m.toFixed(2)}×{obj.depth_m.toFixed(2)}m)
              </button>
            </Html>
          </group>
        );
      })}

      {/* Server-Returned C-Space Inflated Obstacles */}
      {showCSpace &&
        solveResult?.obstacles &&
        solveResult.obstacles.map((ring, idx) => {
          if (ring.length < 2) return null;
          const pts: [number, number, number][] = [
            ...ring.map(([x, z]): [number, number, number] => [x, 0.03, z]),
            [ring[0][0], 0.03, ring[0][1]],
          ];
          return (
            <Line
              key={`obs-${idx}`}
              points={pts}
              color="#f43f5e"
              lineWidth={1.5}
              dashed
              dashSize={0.15}
              gapSize={0.1}
            />
          );
        })}

      {/* Start & Goal Disc Agent Markers */}
      <group
        visible={showEndpoints}
        position={[startPoint[0], 0.03, startPoint[1]]}
      >
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[Math.max(0.05, rEff - 0.03), rEff, 32]} />
          <meshBasicMaterial color="#22c55e" side={THREE.DoubleSide} />
        </mesh>
        <Html
          style={{ display: showEndpoints ? "block" : "none" }}
          position={[0, 0.35, 0]}
          center
        >
          <span className="rl-endpoint-badge rl-endpoint-badge--start">
            START
          </span>
        </Html>
      </group>

      <group
        visible={showEndpoints}
        position={[goalPoint[0], 0.03, goalPoint[1]]}
      >
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[Math.max(0.05, rEff - 0.03), rEff, 32]} />
          <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} />
        </mesh>
        <Html
          style={{ display: showEndpoints ? "block" : "none" }}
          position={[0, 0.35, 0]}
          center
        >
          <span className="rl-endpoint-badge rl-endpoint-badge--goal">
            GOAL
          </span>
        </Html>
      </group>

      {/* Checked Reachability Path */}
      {solveResult?.path && solveResult.path.length >= 2 && (
        <Line
          points={solveResult.path.map(([x, z]): [number, number, number] => [
            x,
            0.06,
            z,
          ])}
          color={solveResult.status === "ROBUST_PASS" ? "#22c55e" : "#f59e0b"}
          lineWidth={3.5}
        />
      )}
    </>
  );
}

/** 2D SVG Plan Fallback when WebGL is unavailable or disabled */
function FallbackPlan2D({
  showEndpoints,
  scene,
  selectedTarget,
  startPoint,
  goalPoint,
  solveResult,
  onSelectTarget,
}: {
  scene: RoomSceneV1;
  showEndpoints: boolean;
  selectedTarget: SelectionTarget;
  startPoint: [number, number];
  goalPoint: [number, number];
  solveResult: SolveResult | null;
  onSelectTarget: (target: SelectionTarget) => void;
}) {
  const xs = scene.floor.map((p) => p[0]),
    zs = scene.floor.map((p) => p[1]);
  const midX = (Math.min(...xs) + Math.max(...xs)) / 2,
    midZ = (Math.min(...zs) + Math.max(...zs)) / 2;
  const scale = Math.min(
    440 / Math.max(1, Math.max(...xs) - Math.min(...xs)),
    380 / Math.max(1, Math.max(...zs) - Math.min(...zs)),
  );
  const toSvg = ([x, z]: number[]) =>
    `${250 + (x - midX) * scale},${220 + (z - midZ) * scale}`;
  const floorPts = (scene.floor ?? []).map(toSvg).join(" ");

  return (
    <div
      className="rl-fallback-2d"
      role="region"
      aria-label="2D Room Plan Fallback"
    >
      <div className="rl-fallback-banner">
        2D Top-Down Plan View (WebGL-Independent Mode)
      </div>
      <svg viewBox="0 0 500 440" className="rl-fallback-svg">
        <path
          d={[scene.floor, ...(scene.floor_voids ?? []).map((v) => v.polygon)]
            .map((poly) => "M" + poly.map(toSvg).join(" L") + " Z")
            .join(" ")}
          fillRule="evenodd"
          fill="#e6e9de"
          stroke="#a9b59c"
          strokeWidth="3"
        />
        {(scene.floor_voids ?? []).map((v) => (
          <polygon
            key={v.id}
            points={v.polygon.map(toSvg).join(" ")}
            fill="none"
            stroke="#b9a274"
            strokeWidth="2"
            onClick={() => onSelectTarget({ kind: "void", id: v.id })}
          />
        ))}
        {buildSegmentedWallPieces(scene)
          .filter((p) => p.center[1] - p.height / 2 < 0.01)
          .map((p) => (
            <line
              key={p.key}
              x1={
                250 +
                (p.center[0] - midX - (Math.cos(p.yawRad) * p.length) / 2) *
                  scale
              }
              y1={
                220 +
                (p.center[2] - midZ + (Math.sin(p.yawRad) * p.length) / 2) *
                  scale
              }
              x2={
                250 +
                (p.center[0] - midX + (Math.cos(p.yawRad) * p.length) / 2) *
                  scale
              }
              y2={
                220 +
                (p.center[2] - midZ - (Math.sin(p.yawRad) * p.length) / 2) *
                  scale
              }
              stroke="#8eb1a3"
              strokeWidth={Math.max(2, p.thickness * scale)}
              onClick={() => onSelectTarget({ kind: "wall", id: p.wallId })}
            />
          ))}
        {(scene.objects ?? []).map((o) => {
          const cx = 250 + (o.center[0] - midX) * scale;
          const cz = 220 + (o.center[1] - midZ) * scale;
          const w = o.width_m * scale;
          const d = o.depth_m * scale;
          const selected =
            selectedTarget?.kind === "object" && selectedTarget.id === o.id;
          return (
            <g
              key={o.id}
              transform={`translate(${cx},${cz}) rotate(${-(o.yaw_deg ?? 0)})`}
              onClick={() => onSelectTarget({ kind: "object", id: o.id })}
              style={{ cursor: "pointer" }}
            >
              <rect
                x={-w / 2}
                y={-d / 2}
                width={w}
                height={d}
                fill={selected ? "#548768" : "#a4b79b"}
                fillOpacity="0.65"
                stroke="#e2e8f0"
                strokeWidth="1.5"
              />
              <text
                x="0"
                y="4"
                textAnchor="middle"
                fill="#536947"
                fontSize="10"
              >
                {o.label}
              </text>
            </g>
          );
        })}
        {solveResult?.path && solveResult.path.length >= 2 && (
          <polyline
            fill="none"
            stroke="#22c55e"
            strokeWidth="3"
            points={solveResult.path.map(toSvg).join(" ")}
          />
        )}
        {showEndpoints && (
          <>
            <circle
              cx={250 + (startPoint[0] - midX) * scale}
              cy={220 + (startPoint[1] - midZ) * scale}
              r="6"
              fill="#22c55e"
            />
            <circle
              cx={250 + (goalPoint[0] - midX) * scale}
              cy={220 + (goalPoint[1] - midZ) * scale}
              r="6"
              fill="#38bdf8"
            />
          </>
        )}
      </svg>
    </div>
  );
}

export const RoomCanvas3D: React.FC<RoomCanvas3DProps> = (props) => {
  const [webglSupported] = useState<boolean>(() => detectWebGLAvailable());
  const [force2D, setForce2D] = useState<boolean>(false);
  const [showLabels, setShowLabels] = useState(false);

  if (!props.scene) {
    return (
      <div className="rl-canvas-empty">
        <div className="rl-canvas-empty-card">
          <h2>A new perspective on your space.</h2>
          <p>
            Start with a walkthrough. Explore an editable room, refine its
            details, and find a layout that feels right.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="rl-canvas-wrap">
      <div className="rl-canvas-hud-top">
        <details className="rl-legend">
          <summary>Estimated geometry · legend & limits</summary>
          <span className="rl-legend-item">
            <i className="rl-dot rl-dot--solid" /> Measured reference ·
            estimated geometry
          </span>
          <span className="rl-legend-item">
            <i className="rl-dot rl-dot--est" /> Shapes & colors approximated
            from video
          </span>
          <span className="rl-legend-item">
            <i className="rl-dot rl-dot--unc" /> Uncertainty Halo (±r)
          </span>
          <span className="rl-legend-item">
            Glass panels: interior partitions and railings · orange outline:
            floor void. Stairs are fixed placeholders; no stair travel.
          </span>
          <span className="rl-legend-item">
            Clearance fills are previews. Checked path outlines come from the
            solver.
          </span>
        </details>
        <button
          type="button"
          className="rl-btn rl-btn--xs"
          onClick={() => setShowLabels((v) => !v)}
        >
          {showLabels ? "Hide Labels" : "Show Labels"}
        </button>
        <button
          type="button"
          className="rl-btn rl-btn--xs"
          onClick={() => setForce2D((v) => !v)}
        >
          {force2D || !webglSupported
            ? "Switch to 3D WebGL"
            : "2D SVG Plan Fallback"}
        </button>
      </div>

      {(!webglSupported || force2D) && (
        <FallbackPlan2D
          showEndpoints={props.showEndpoints}
          scene={props.scene}
          selectedTarget={props.selectedTarget}
          startPoint={props.startPoint}
          goalPoint={props.goalPoint}
          solveResult={props.solveResult}
          onSelectTarget={props.onSelectTarget}
        />
      )}
      {webglSupported && (
        <div
          style={{
            display: force2D ? "none" : "block",
            width: "100%",
            height: "100%",
          }}
        >
          <Canvas
            camera={{ position: [5.5, 6.2, 6.5], fov: 48, near: 0.1, far: 120 }}
            dpr={[1, 1.5]}
            gl={{ antialias: true }}
            flat
            shadows
            frameloop="demand"
            onPointerMissed={() => props.onSelectTarget(null)}
          >
            <RoomSceneContent
              {...props}
              scene={props.scene}
              showLabels={showLabels}
            />
          </Canvas>
        </div>
      )}
    </div>
  );
};
