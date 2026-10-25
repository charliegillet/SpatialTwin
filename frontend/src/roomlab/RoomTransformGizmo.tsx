import React, { useEffect, useRef, useState } from "react";
import { TransformControls } from "@react-three/drei";
import { useThree } from "@react-three/fiber";
import type { TransformControls as TransformControlsImpl } from "three-stdlib";
import type { Group } from "three";
import type { RoomObject } from "./contracts.generated";

export function RoomTransformGizmo({
  target,
  object,
  mode,
  onDragging,
  onCommit,
}: {
  target: Group;
  object: RoomObject;
  mode: "translate" | "rotate";
  onDragging: (value: boolean) => void;
  onCommit: (id: string, center: [number, number], yaw: number) => void;
}) {
  const control = useRef<TransformControlsImpl>(null);
  const snapshot = useRef<{ x: number; z: number; yaw: number } | null>(null);
  const [cancelled, setCancelled] = useState(false);
  const { invalidate } = useThree();
  const restore = () => {
    const s = snapshot.current;
    if (s) {
      target.position.set(s.x, 0, s.z);
      target.rotation.set(0, s.yaw, 0);
      target.updateMatrixWorld();
      invalidate();
    }
  };
  useEffect(() => {
    const escape = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !snapshot.current) return;
      restore();
      snapshot.current = null;
      setCancelled(true);
      onDragging(false);
    };
    const release = () => setCancelled(false);
    window.addEventListener("keydown", escape);
    window.addEventListener("pointerup", release);
    return () => {
      window.removeEventListener("keydown", escape);
      window.removeEventListener("pointerup", release);
      restore();
      snapshot.current = null;
      onDragging(false);
    };
  }, [target]);
  return (
    <TransformControls
      ref={control}
      object={target}
      enabled={!cancelled}
      mode={mode}
      showX={mode === "translate"}
      showY={mode === "rotate"}
      showZ={mode === "translate"}
      space="world"
      translationSnap={0.05}
      rotationSnap={Math.PI / 36}
      size={0.85}
      onMouseDown={() => {
        snapshot.current = {
          x: target.position.x,
          z: target.position.z,
          yaw: target.rotation.y,
        };
        onDragging(true);
      }}
      onObjectChange={() => {
        target.position.y = 0;
        target.rotation.x = 0;
        target.rotation.z = 0;
      }}
      onMouseUp={() => {
        const s = snapshot.current;
        snapshot.current = null;
        onDragging(false);
        if (!s) return;
        const x = target.position.x,
          z = target.position.z,
          yaw = target.rotation.y;
        // The canonical state changes only once per gesture. No per-frame history entries.
        if (
          Math.abs(x - s.x) + Math.abs(z - s.z) + Math.abs(yaw - s.yaw) >
          1e-6
        )
          onCommit(
            object.id,
            [x, z],
            (((((yaw * 180) / Math.PI + 180) % 360) + 360) % 360) - 180,
          );
      }}
    />
  );
}
