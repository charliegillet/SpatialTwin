import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Html, Line } from "@react-three/drei";
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

function FloorMesh({
  floor,
  voids = [],
}: {
  floor: number[][];
  voids?: Array<{ polygon: number[][] }>;
}) {
  const geometry = useMemo(() => {
    if (!floor || floor.length < 3) return null;
    // Shape is in 2D (x, y); after rotation.x = +PI/2, shape (x, y, 0) maps to world (x, 0, y) = (x, 0, z)!
    const shape = new THREE.Shape();
    floor.forEach(([x, z], idx) => {
      if (idx === 0) shape.moveTo(x, z);
      else shape.lineTo(x, z);
    });
    shape.closePath();
    for (const v of voids) {
      const hole = new THREE.Path();
      v.polygon.forEach(([x, z], i) =>
        i === 0 ? hole.moveTo(x, z) : hole.lineTo(x, z),
      );
      hole.closePath();
      shape.holes.push(hole);
    }
    return new THREE.ShapeGeometry(shape);
  }, [floor, voids]);
  useEffect(() => () => geometry?.dispose(), [geometry]);

  if (!geometry) return null;
  return (
    <mesh
      geometry={geometry}
      rotation={[Math.PI / 2, 0, 0]}
      position={[0, 0.002, 0]}
    >
      <meshStandardMaterial
        color="#e5e7df"
        roughness={0.9}
        metalness={0.05}
        side={THREE.DoubleSide}
      />
    </mesh>
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

function categoryColor(category: string, source?: string): string {
  if (source === "user_measurement") return "#10b981";
  const c = (category || "").toLowerCase();
  if (c.includes("stair")) return "#c2ac85";
  if (c.includes("table") || c.includes("desk")) return "#9eb7a5";
  if (c.includes("chair") || c.includes("seat")) return "#aab4c3";
  if (c.includes("sofa") || c.includes("couch")) return "#b7aaa0";
  if (c.includes("pillar") || c.includes("column") || c.includes("fixed"))
    return "#b6bcb0";
  if (c.includes("plant")) return "#9cad8d";
  if (c.includes("stool")) return "#c4b295";
  return "#a9b8a1";
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

  const wallPieces = useMemo(() => buildSegmentedWallPieces(scene), [scene]);
  const walls = useMemo(() => deriveWallsFromFloor(scene), [scene]);
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
      <ambientLight intensity={1.15} color="#ffffff" />
      <directionalLight
        position={[8, 16, 10]}
        intensity={1.1}
        color="#f8fafc"
      />
      <directionalLight
        position={[-8, 10, -8]}
        intensity={0.45}
        color="#93c5fd"
      />

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
        position={[0, 0.001, 0]}
      />

      <FloorMesh floor={scene.floor} voids={scene.floor_voids} />
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

      {/* Segmented Architectural Walls */}
      {wallPieces.map((piece) => {
        const isSelected =
          selectedTarget?.kind === "wall" && selectedTarget.id === piece.wallId;
        const isAnchor = scene.calibration?.anchor_id === piece.wallId;
        const boundary = walls.find((w) => w.id === piece.wallId);
        const wallColor =
          boundary?.role === "railing"
            ? "#b6a27c"
            : boundary?.role === "partition"
              ? "#8eb1a3"
              : isSelected
                ? "#538568"
                : isAnchor
                  ? "#538568"
                  : "#bfc6b6";
        return (
          <mesh
            key={piece.key}
            position={piece.center}
            rotation={[0, piece.yawRad, 0]}
            onClick={(e) => {
              e.stopPropagation();
              onSelectTarget({ kind: "wall", id: piece.wallId });
            }}
          >
            <boxGeometry args={[piece.length, piece.height, piece.thickness]} />
            <meshStandardMaterial
              color={wallColor}
              roughness={0.85}
              metalness={0.1}
              transparent
              opacity={boundary?.role === "partition" ? 0.35 : 0.65}
            />
          </mesh>
        );
      })}

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

      {/* Room Objects (Solid if user-measured/anchored, Translucent with Uncertainty Ring if estimated/partial) */}
      {(scene.objects ?? []).map((obj: RoomObject) => {
        const isSelected =
          selectedTarget?.kind === "object" && selectedTarget.id === obj.id;
        const isAnchor = scene.calibration?.anchor_id === obj.id;
        const yawRad = ((obj.yaw_deg ?? 0) * Math.PI) / 180;
        const color = isSelected
          ? "#548768"
          : isAnchor
            ? "#10b981"
            : categoryColor(
                obj.category ?? "furniture",
                obj.provenance?.source,
              );
        const vis = obj.provenance?.visibility ?? "partial";
        const isSolid = obj.provenance?.source === "user_measurement";
        const uncRadius = obj.uncertainty_radius_m ?? 0;

        return (
          <group key={obj.id} position={[obj.center[0], 0, obj.center[1]]}>
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
              <meshStandardMaterial
                color={color}
                roughness={0.6}
                metalness={0.15}
                transparent={!isSolid}
                opacity={isSolid ? 0.96 : vis === "unobserved" ? 0.42 : 0.72}
              />
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
            <i className="rl-dot rl-dot--est" /> Model Estimate (Translucent)
          </span>
          <span className="rl-legend-item">
            <i className="rl-dot rl-dot--unc" /> Uncertainty Halo (±r)
          </span>
          <span className="rl-legend-item">
            Orange: railing/void edge · cyan: interior partition. Stair boxes
            are placeholders; no stair travel.
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
