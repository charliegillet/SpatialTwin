import React from "react";
import { AppearancePanel } from "./AppearancePanel";
import { Sliders, Trash2, Lock, Unlock, ShieldAlert } from "lucide-react";
import type {
  RoomObject,
  RoomSceneV1,
  ValidationReport,
} from "./contracts.generated";
import {
  addObjectToScene,
  cloneScene,
  deriveWallsFromFloor,
  wallLengthMeters,
  type SelectionTarget,
} from "./editorState";

interface RoomEditorProps {
  scene: RoomSceneV1 | null;
  dirty?: boolean;
  selectedTarget: SelectionTarget;
  validation: ValidationReport | null;
  isValidating: boolean;
  onSelectTarget: (target: SelectionTarget) => void;
  onUpdateObject: (
    objectId: string,
    updater: (obj: RoomObject) => RoomObject,
  ) => void;
  onDeleteObject: (objectId: string) => void;
  onUpdateScene: (next: RoomSceneV1) => void;
  onValidateScene: () => void;
}

export const RoomEditor: React.FC<RoomEditorProps> = ({
  scene,
  dirty = false,
  selectedTarget,
  validation,
  isValidating,
  onSelectTarget,
  onUpdateObject,
  onDeleteObject,
  onUpdateScene,
  onValidateScene,
}) => {
  if (!scene) return null;

  const walls = deriveWallsFromFloor(scene);
  const objects = scene.objects ?? [];
  const openings = scene.openings ?? [];

  const selectedObject =
    selectedTarget?.kind === "object"
      ? (objects.find((o) => o.id === selectedTarget.id) ?? null)
      : null;
  const selectedWall =
    selectedTarget?.kind === "wall"
      ? (walls.find((w) => w.id === selectedTarget.id) ?? null)
      : null;
  const selectedOpening =
    selectedTarget?.kind === "opening"
      ? (openings.find((op) => op.id === selectedTarget.id) ?? null)
      : null;

  const num = (val: string, fallback: number) => {
    const parsed = parseFloat(val);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const editCorner = (end: boolean, axis: number, value: string) => {
    if (!selectedWall) return;
    const next = cloneScene(scene);
    const shell = walls.filter((w) => (w.role ?? "shell") === "shell");
    if ((selectedWall.role ?? "shell") === "shell") {
      const index = shell.findIndex((w) => w.id === selectedWall.id),
        vertex = (index + (end ? 1 : 0)) % next.floor.length;
      next.floor[vertex][axis] = num(value, next.floor[vertex][axis]);
      next.walls = walls.map((w) => {
        const i = shell.findIndex((v) => v.id === w.id);
        return i < 0
          ? w
          : {
              ...w,
              start: [...next.floor[i]],
              end: [...next.floor[(i + 1) % next.floor.length]],
              provenance: { ...w.provenance, source: "user_edit" as const },
            };
      });
    } else {
      const wall = next.walls?.find((w) => w.id === selectedWall.id);
      if (wall) {
        wall[end ? "end" : "start"][axis] = num(
          value,
          wall[end ? "end" : "start"][axis],
        );
        wall.provenance = { ...wall.provenance, source: "user_edit" };
      }
    }
    onUpdateScene(next);
  };
  const editWall = (field: "height_m" | "thickness_m", value: string) => {
    if (!selectedWall) return;
    const next = cloneScene(scene);
    const wall = next.walls?.find((w) => w.id === selectedWall.id);
    if (wall) {
      wall[field] = Math.max(0.01, num(value, wall[field] ?? 0.1));
      wall.provenance = { ...wall.provenance, source: "user_edit" };
      onUpdateScene(next);
    }
  };
  const editOpening = (
    field: "offset_m" | "width_m" | "height_m" | "sill_m",
    value: string,
  ) => {
    if (!selectedOpening) return;
    const next = cloneScene(scene);
    const opening = next.openings?.find((o) => o.id === selectedOpening.id);
    if (opening) {
      opening[field] = Math.max(
        field === "offset_m" || field === "sill_m" ? 0 : 0.01,
        num(value, opening[field] ?? 0),
      );
      opening.provenance = { ...opening.provenance, source: "user_edit" };
      onUpdateScene(next);
    }
  };

  return (
    <section className="rl-panel" aria-label="3D Room Inspector">
      <div className="rl-panel-header">
        <span className="rl-panel-title">
          <Sliders size={15} /> Room details
        </span>
        <button
          type="button"
          className="rl-btn rl-btn--xs"
          disabled={isValidating || dirty}
          title={
            dirty
              ? "Save local edits first to check server geometry"
              : undefined
          }
          onClick={onValidateScene}
        >
          <span>
            {dirty
              ? "Save First to Check"
              : isValidating
                ? "Checking…"
                : "Check Geometry"}
          </span>
        </button>
      </div>

      <AppearancePanel
        scene={scene}
        selected={selectedTarget}
        onChange={onUpdateScene}
      />
      <details
        className="rl-scene-checks"
        open={Boolean(validation) || scene.topology_review_required}
      >
        <summary>
          Architectural review
          {scene.topology_review_required ? " · required" : ""}
        </summary>
        <label className="rl-muted-note">
          <input
            type="checkbox"
            checked={scene.topology_review_required ?? false}
            onChange={(e) => {
              const next = cloneScene(scene);
              next.topology_review_required = e.target.checked;
              onUpdateScene(next);
            }}
          />{" "}
          Architecture needs review (blocks clearance). Clear only after
          checking voids and boundaries against evidence.
        </label>
        {validation && (
          <div
            className={`rl-validation-box ${validation.valid ? "rl-validation-box--ok" : "rl-validation-box--err"}`}
          >
            <div className="rl-validation-title">
              <ShieldAlert size={14} />
              <strong>
                {validation.valid
                  ? "Model consistency passed · visual accuracy unverified"
                  : `${validation.issues.length} Geometry Issue(s)`}
              </strong>
            </div>
            {validation.issues.length > 0 && (
              <ul className="rl-validation-list">
                {validation.issues.map((issue, idx) => (
                  <li key={idx}>
                    <span
                      className={`rl-sev rl-sev--${issue.severity ?? "error"}`}
                    >
                      {issue.code}:
                    </span>{" "}
                    {issue.message}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </details>
      {selectedObject && (
        <div className="rl-inspector-card">
          <div className="rl-inspector-top">
            <div>
              <span className="rl-kicker">
                Selected Object · {selectedObject.id}
              </span>
              <h4>{selectedObject.label}</h4>
            </div>
            <button
              type="button"
              className="rl-btn rl-btn--danger rl-btn--xs"
              onClick={() => onDeleteObject(selectedObject.id)}
              title="Delete object from scene"
            >
              <Trash2 size={13} />
            </button>
          </div>

          <div className="rl-provenance-row">
            <span className="rl-badge">
              Source: {selectedObject.provenance?.source ?? "model_estimate"}
            </span>
            <span className="rl-badge">
              Visibility: {selectedObject.provenance?.visibility ?? "partial"}
            </span>
          </div>

          <div className="rl-field-row">
            <label className="rl-field">
              <span>Label</span>
              <input
                type="text"
                value={selectedObject.label}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    label: e.target.value || o.label,
                  }))
                }
              />
            </label>
            <label className="rl-field">
              <span>Category</span>
              <input
                type="text"
                value={selectedObject.category ?? "furniture"}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    category: e.target.value || "furniture",
                  }))
                }
              />
            </label>
          </div>

          <div className="rl-field-row">
            <label className="rl-field">
              <span>Center X (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedObject.center[0]}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    center: [num(e.target.value, o.center[0]), o.center[1]],
                  }))
                }
              />
            </label>
            <label className="rl-field">
              <span>Center Z (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedObject.center[1]}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    center: [o.center[0], num(e.target.value, o.center[1])],
                  }))
                }
              />
            </label>
            <label className="rl-field">
              <span>Yaw (°)</span>
              <input
                type="number"
                step="5"
                value={selectedObject.yaw_deg ?? 0}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    yaw_deg: num(e.target.value, o.yaw_deg ?? 0),
                  }))
                }
              />
            </label>
          </div>

          <div className="rl-field-row">
            <label className="rl-field">
              <span>Width X (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.1"
                disabled={selectedObject.resize_allowed === false}
                value={selectedObject.width_m}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    width_m: Math.max(0.1, num(e.target.value, o.width_m)),
                  }))
                }
              />
            </label>
            <label className="rl-field">
              <span>Depth Z (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.1"
                disabled={selectedObject.resize_allowed === false}
                value={selectedObject.depth_m}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    depth_m: Math.max(0.1, num(e.target.value, o.depth_m)),
                  }))
                }
              />
            </label>
            <label className="rl-field">
              <span>Height Y (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.1"
                disabled={selectedObject.resize_allowed === false}
                value={selectedObject.height_m}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    height_m: Math.max(0.1, num(e.target.value, o.height_m)),
                  }))
                }
              />
            </label>
          </div>

          <div className="rl-field-row">
            <label className="rl-field">
              <span>Uncertainty Radius ±(m)</span>
              <input
                type="number"
                step="0.02"
                min="0"
                max="2"
                value={selectedObject.uncertainty_radius_m ?? 0}
                onChange={(e) =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    uncertainty_radius_m: Math.max(
                      0,
                      num(e.target.value, o.uncertainty_radius_m ?? 0),
                    ),
                  }))
                }
              />
            </label>
            <div className="rl-field">
              <span>Automatic layout search</span>
              <button
                type="button"
                className="rl-btn"
                onClick={() =>
                  onUpdateObject(selectedObject.id, (o) => ({
                    ...o,
                    movable: !(o.movable ?? true),
                  }))
                }
              >
                {selectedObject.movable !== false ? (
                  <Unlock size={13} />
                ) : (
                  <Lock size={13} />
                )}
                <span>
                  {selectedObject.movable !== false
                    ? "Movable in search"
                    : "Fixed in search"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}

      {selectedWall && (
        <div className="rl-inspector-card">
          <span className="rl-kicker">
            Selected Boundary · {selectedWall.id} ·{" "}
            {selectedWall.role ?? "shell"}
          </span>
          <h4>
            Length: {wallLengthMeters(selectedWall).toFixed(2)}m · Height:{" "}
            {(selectedWall.height_m ?? 2.7).toFixed(2)}m
          </h4>
          <p className="rl-muted-note">
            Start [{selectedWall.start[0].toFixed(2)},{" "}
            {selectedWall.start[1].toFixed(2)}] → End [
            {selectedWall.end[0].toFixed(2)}, {selectedWall.end[1].toFixed(2)}]
          </p>
          <p className="rl-muted-note">
            Source: {selectedWall.provenance?.source ?? "model_estimate"} (
            {selectedWall.provenance?.visibility ?? "partial"})
          </p>
          <div className="rl-field-row">
            <label className="rl-field">
              <span>Wall start X (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedWall.start[0]}
                onChange={(e) => editCorner(false, 0, e.target.value)}
              />
            </label>
            <label className="rl-field">
              <span>Wall start Z (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedWall.start[1]}
                onChange={(e) => editCorner(false, 1, e.target.value)}
              />
            </label>
          </div>
          <div className="rl-field-row">
            <label className="rl-field">
              <span>Wall end X (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedWall.end[0]}
                onChange={(e) => editCorner(true, 0, e.target.value)}
              />
            </label>
            <label className="rl-field">
              <span>Wall end Z (m)</span>
              <input
                type="number"
                step="0.05"
                value={selectedWall.end[1]}
                onChange={(e) => editCorner(true, 1, e.target.value)}
              />
            </label>
          </div>
          <div className="rl-field-row">
            <label className="rl-field">
              <span>Wall height (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.1"
                value={selectedWall.height_m ?? 2.7}
                onChange={(e) => editWall("height_m", e.target.value)}
              />
            </label>
            <label className="rl-field">
              <span>Wall thickness (m)</span>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={selectedWall.thickness_m ?? 0.12}
                onChange={(e) => editWall("thickness_m", e.target.value)}
              />
            </label>
          </div>
          <p className="rl-muted-note">
            Outer corners stay connected; partition and railing endpoints move
            independently. Boundary edits may invalidate your scale reference or
            opening positions; save and check geometry.
          </p>
        </div>
      )}

      {selectedTarget?.kind === "void" &&
        (scene.floor_voids ?? [])
          .filter((v) => v.id === selectedTarget.id)
          .map((v) => (
            <div className="rl-inspector-card" key={v.id}>
              <h4>Floor void · {v.id}</h4>
              <p>
                No floor or traversal inside this polygon. Compare every corner
                against video evidence.
              </p>
              {v.polygon.map((point, i) => (
                <div className="rl-field-row" key={i}>
                  {point.map((n, axis) => (
                    <label className="rl-field" key={axis}>
                      <span>
                        Void vertex {i + 1} {axis === 0 ? "X" : "Z"} (m)
                      </span>
                      <input
                        type="number"
                        step=".1"
                        value={n}
                        onChange={(e) => {
                          const next = cloneScene(scene);
                          const hole = next.floor_voids?.find(
                            (h) => h.id === v.id,
                          );
                          if (hole) {
                            hole.polygon[i][axis] = num(e.target.value, n);
                            hole.provenance = {
                              ...hole.provenance,
                              source: "user_edit",
                            };
                            onUpdateScene(next);
                          }
                        }}
                      />
                    </label>
                  ))}
                </div>
              ))}
            </div>
          ))}
      <div className="rl-pill-list">
        {(scene.floor_voids ?? []).map((v) => (
          <button
            className="rl-pill"
            key={v.id}
            onClick={() => onSelectTarget({ kind: "void", id: v.id })}
          >
            ⚠ {v.id} · no floor
          </button>
        ))}
      </div>
      {selectedOpening && (
        <div className="rl-inspector-card">
          <span className="rl-kicker">
            Selected Opening · {selectedOpening.id} (
            {selectedOpening.kind.toUpperCase()})
          </span>
          <h4>
            Wall: {selectedOpening.wall_id} · Width:{" "}
            {selectedOpening.width_m.toFixed(2)}m · Offset:{" "}
            {selectedOpening.offset_m.toFixed(2)}m
          </h4>
          <div className="rl-field-row">
            <label className="rl-field">
              <span>Opening offset (m)</span>
              <input
                type="number"
                step="0.05"
                min="0"
                value={selectedOpening.offset_m}
                onChange={(e) => editOpening("offset_m", e.target.value)}
              />
            </label>
            <label className="rl-field">
              <span>Opening width (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.01"
                value={selectedOpening.width_m}
                onChange={(e) => editOpening("width_m", e.target.value)}
              />
            </label>
          </div>
          <div className="rl-field-row">
            <label className="rl-field">
              <span>Opening height (m)</span>
              <input
                type="number"
                step="0.05"
                min="0.01"
                value={selectedOpening.height_m ?? 2.1}
                onChange={(e) => editOpening("height_m", e.target.value)}
              />
            </label>
            <label className="rl-field">
              <span>Opening sill (m)</span>
              <input
                type="number"
                step="0.05"
                min="0"
                value={selectedOpening.sill_m ?? 0}
                onChange={(e) => editOpening("sill_m", e.target.value)}
              />
            </label>
          </div>
          {selectedOpening.width_interval_m && (
            <p className="rl-muted-note">
              Uncertainty Width Interval: [
              {selectedOpening.width_interval_m[0].toFixed(2)}m,{" "}
              {selectedOpening.width_interval_m[1].toFixed(2)}m]
            </p>
          )}
        </div>
      )}

      <div className="rl-element-list">
        <h4>Objects ({objects.length})</h4>
        <div
          className="rl-preset-row"
          aria-label="Add everyday furniture presets"
        >
          {(
            [
              { cat: "sofa", label: "+ Sofa" },
              { cat: "counter", label: "+ Desk" },
              { cat: "table", label: "+ Table" },
              { cat: "chair", label: "+ Chair" },
              { cat: "plant", label: "+ Plant" },
            ] as const
          ).map((item) => (
            <button
              key={item.cat}
              type="button"
              className="rl-pill"
              onClick={() => {
                const { scene: nextScene, newId } = addObjectToScene(
                  scene,
                  item.cat,
                );
                onUpdateScene(nextScene);
                onSelectTarget({ kind: "object", id: newId });
              }}
            >
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        <p className="rl-muted-note">
          Example furniture sizes—adjust them to your item’s measurements.
        </p>
        <div className="rl-pill-list">
          {objects.map((o) => {
            const active =
              selectedTarget?.kind === "object" && selectedTarget.id === o.id;
            return (
              <button
                key={o.id}
                type="button"
                className={`rl-pill ${active ? "rl-pill--active" : ""}`}
                onClick={() => onSelectTarget({ kind: "object", id: o.id })}
              >
                <span>{o.label}</span>
                <small>
                  {o.width_m.toFixed(o.width_m < 0.1 ? 3 : 1)}×
                  {o.depth_m.toFixed(o.depth_m < 0.1 ? 3 : 1)}m
                </small>
              </button>
            );
          })}
        </div>

        <details className="rl-layer-group">
          <summary>
            Architecture <span>{walls.length + openings.length}</span>
          </summary>
          <div className="rl-pill-list">
            {walls.map((w) => {
              const active =
                selectedTarget?.kind === "wall" && selectedTarget.id === w.id;
              return (
                <button
                  key={w.id}
                  type="button"
                  className={`rl-pill ${active ? "rl-pill--active" : ""}`}
                  onClick={() => onSelectTarget({ kind: "wall", id: w.id })}
                >
                  <span>{w.id}</span>
                  <small>{wallLengthMeters(w).toFixed(2)}m</small>
                </button>
              );
            })}
            {openings.map((op) => {
              const active =
                selectedTarget?.kind === "opening" &&
                selectedTarget.id === op.id;
              return (
                <button
                  key={op.id}
                  type="button"
                  className={`rl-pill ${active ? "rl-pill--active" : ""}`}
                  onClick={() => onSelectTarget({ kind: "opening", id: op.id })}
                >
                  <span>
                    {op.id} ({op.kind})
                  </span>
                  <small>{op.width_m.toFixed(2)}m</small>
                </button>
              );
            })}
          </div>
        </details>
      </div>
    </section>
  );
};
