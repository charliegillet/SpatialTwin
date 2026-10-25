import React, { useState } from "react";
import type { RoomSceneV1, RepairResult } from "./contracts.generated";
export function OverlapRepairPanel({
  scene,
  dirty,
  result,
  busy,
  onRun,
  onApply,
  onDiscard,
}: {
  scene: RoomSceneV1 | null;
  dirty: boolean;
  result: RepairResult | null;
  busy: boolean;
  onRun: (max: number) => void;
  onApply: (scene: RoomSceneV1) => void;
  onDiscard: () => void;
}) {
  const [limit, setLimit] = useState(0.5);
  if (!scene) return null;
  return (
    <section
      className="rl-panel rl-v2-section"
      aria-label="Overlap repair preview"
    >
      <div className="rl-panel-header">
        <span className="rl-panel-title">Refine overlapping boxes</span>
      </div>
      <p className="rl-muted-note">
        Coarse boxes can overlap intentionally. Preview bounded adjustments to
        movable objects and compare them with the source before applying.
      </p>
      <label className="rl-field">
        <span>Maximum adjustment per object (m)</span>
        <input
          type="number"
          min=".05"
          max="1"
          step=".05"
          value={limit}
          onChange={(e) =>
            setLimit(Math.min(1, Math.max(0.05, Number(e.target.value) || 0.5)))
          }
        />
      </label>
      <button
        className="rl-btn rl-btn--full"
        disabled={dirty || busy}
        onClick={() => onRun(limit)}
      >
        {busy
          ? "Finding a bounded fit…"
          : dirty
            ? "Save before proposing repair"
            : "Preview box separation"}
      </button>
      {result && (
        <div className="rl-opt-card">
          <strong>{result.status.replace("_", " ")}</strong>
          <p>{result.message}</p>
          <p className="rl-muted-note">
            {result.before_overlap_pairs.length} →{" "}
            {result.after_overlap_pairs.length} overlapping pairs. No saved room
            changes.
          </p>
          {result.changes?.map((c) => (
            <p className="rl-muted-note" key={c.object_id}>
              {scene.objects?.find((o) => o.id === c.object_id)?.label ??
                c.object_id}
              : Δx {(c.to_center[0] - c.from_center[0]).toFixed(2)}m · Δz{" "}
              {(c.to_center[1] - c.from_center[1]).toFixed(2)}m
            </p>
          ))}
          {result.scene && (
            <div className="rl-action-pair">
              <button
                className="rl-btn rl-btn--primary"
                onClick={() => onApply(result.scene!)}
              >
                Apply proposed fit
              </button>
              <button className="rl-btn" onClick={onDiscard}>
                Discard preview
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
