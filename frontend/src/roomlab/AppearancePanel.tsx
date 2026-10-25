import React, { useEffect, useState } from "react";
import type {
  AppearanceChoice,
  RoomSceneV1,
  SurfaceAppearance,
} from "./contracts.generated";
import { cloneScene, type SelectionTarget } from "./editorState";
import {
  objectRoleAppearance,
  resolveAppearance,
  resolveFloorAppearance,
  resolveWallAppearance,
  setAppearanceChoice,
  type ResolvedAppearance,
} from "./appearance";
const materials: NonNullable<AppearanceChoice["material"]>[] = [
  "unknown",
  "paint",
  "glass",
  "wood",
  "terrazzo",
  "tile",
  "stone",
  "marble",
  "carpet",
  "concrete",
  "fabric",
  "metal",
  "ceramic",
  "foliage",
];
function SurfaceControl({
  label,
  value,
  resolved,
  onChange,
}: {
  label: string;
  value: SurfaceAppearance | null | undefined;
  resolved: ResolvedAppearance;
  onChange: (value: SurfaceAppearance | null) => void;
}) {
  const [color, setColor] = useState(resolved.color);
  useEffect(() => setColor(resolved.color), [resolved.color]);
  const choice = (change: AppearanceChoice) =>
    onChange(
      setAppearanceChoice(value, {
        color: resolved.color,
        material: resolved.material,
        ...change,
      }),
    );
  return (
    <fieldset className="rl-appearance-surface">
      <legend>{label}</legend>
      <label>
        Material
        <select
          aria-label={`${label} material`}
          value={resolved.material}
          onChange={(e) =>
            choice({ material: e.target.value as AppearanceChoice["material"] })
          }
        >
          {materials.map((m) => (
            <option key={m} value={m}>
              {m === "unknown" ? "Neutral / unknown" : m}
            </option>
          ))}
        </select>
      </label>
      <div className="rl-appearance-colors">
        <input
          aria-label={`${label} color`}
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
        />
        <button className="rl-btn rl-btn--xs" onClick={() => choice({ color })}>
          Apply {label.toLowerCase()} color
        </button>
      </div>
      <div className="rl-appearance-swatches">
        {["#d9d8cf", "#bba184", "#9ba99a", "#aaa1a0", "#777f7b", "#dfdfda"].map(
          (c) => (
            <button
              key={c}
              aria-label={`${label} color ${c}`}
              style={{ background: c }}
              onClick={() => choice({ color: c })}
            />
          ),
        )}
      </div>
      <p className="rl-muted-note">
        {resolved.source === "user_choice"
          ? "User choice"
          : resolved.source === "model_estimate"
            ? "Model estimate · not pixel measured"
            : "Heuristic / default · not extracted"}{" "}
        · {resolved.note}
      </p>
      {resolved.evidence_frame_ids.length > 0 && (
        <p className="rl-muted-note">
          Source frames: {resolved.evidence_frame_ids.join(", ")}
        </p>
      )}
      {value?.user_override && (
        <button
          className="rl-btn rl-btn--xs"
          onClick={() => onChange({ ...value, user_override: null })}
        >
          Reset {label.toLowerCase()} to estimate/default
        </button>
      )}
    </fieldset>
  );
}
export function AppearancePanel({
  scene,
  selected,
  onChange,
}: {
  scene: RoomSceneV1;
  selected: SelectionTarget;
  onChange: (next: RoomSceneV1) => void;
}) {
  const obj =
    selected?.kind === "object"
      ? scene.objects?.find((o) => o.id === selected.id)
      : null;
  const wall =
    selected?.kind === "wall"
      ? scene.walls?.find((w) => w.id === selected.id)
      : null;
  const update = (
    key: "floor_appearance" | "wall_appearance",
    value: SurfaceAppearance | null,
  ) => {
    const next = cloneScene(scene);
    next[key] = value;
    onChange(next);
  };
  return (
    <details className="rl-appearance">
      <summary>
        Appearance <span>· display only</span>
      </summary>
      <p className="rl-muted-note">
        Colors and patterns are illustrative under estimated lighting. One floor
        finish covers the whole room; mixed zones are not modeled. Textures use
        a generic repeat, not recovered plank or tile sizes.
      </p>
      <SurfaceControl
        label="Floor"
        value={scene.floor_appearance}
        resolved={resolveFloorAppearance(scene)}
        onChange={(v) => update("floor_appearance", v)}
      />
      <SurfaceControl
        label="Default wall"
        value={scene.wall_appearance}
        resolved={resolveAppearance(scene.wall_appearance, "#c9cec0")}
        onChange={(v) => update("wall_appearance", v)}
      />
      {obj && (
        <SurfaceControl
          label="Selected object"
          value={obj.appearance}
          resolved={objectRoleAppearance(obj, "primary")}
          onChange={(v) => {
            const next = cloneScene(scene);
            const o = next.objects?.find((x) => x.id === obj.id);
            if (o) o.appearance = v;
            onChange(next);
          }}
        />
      )}
      {wall && (
        <SurfaceControl
          label="Selected wall"
          value={wall.appearance}
          resolved={resolveWallAppearance(wall, scene.wall_appearance)}
          onChange={(v) => {
            const next = cloneScene(scene);
            const w = next.walls?.find((x) => x.id === wall.id);
            if (w) w.appearance = v;
            onChange(next);
          }}
        />
      )}
    </details>
  );
}
