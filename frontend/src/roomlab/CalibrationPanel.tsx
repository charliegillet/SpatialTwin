import React, { useEffect, useState } from "react";
import { Ruler, CheckCircle2, AlertCircle } from "lucide-react";
import type { CalibrateRequest, RoomSceneV1 } from "./contracts.generated";
import {
  deriveWallsFromFloor,
  wallLengthMeters,
  type SelectionTarget,
} from "./editorState";

interface CalibrationPanelProps {
  scene: RoomSceneV1 | null;
  selectedTarget: SelectionTarget;
  dirty: boolean;
  isCalibrating: boolean;
  onCalibrate: (req: CalibrateRequest) => void;
}

export const CalibrationPanel: React.FC<CalibrationPanelProps> = ({
  scene,
  selectedTarget,
  dirty,
  isCalibrating,
  onCalibrate,
}) => {
  const walls = scene ? deriveWallsFromFloor(scene) : [];
  const objects = scene?.objects ?? [];

  const [anchorId, setAnchorId] = useState<string>("");
  const [dimension, setDimension] = useState<
    "wall_length" | "object_width" | "object_depth"
  >("wall_length");
  const [measuredM, setMeasuredM] = useState<string>("3.50");
  const [toleranceM, setToleranceM] = useState<string>("0.02");

  const [useHoldout, setUseHoldout] = useState<boolean>(false);
  const [holdoutAnchorId, setHoldoutAnchorId] = useState<string>("");
  const [holdoutDimension, setHoldoutDimension] = useState<
    "wall_length" | "object_width" | "object_depth"
  >("object_width");
  const [holdoutMeasuredM, setHoldoutMeasuredM] = useState<string>("1.40");

  useEffect(() => {
    if (!scene) return;
    if (selectedTarget?.kind === "wall") {
      setAnchorId(selectedTarget.id);
      setDimension("wall_length");
      const w = walls.find((item) => item.id === selectedTarget.id);
      if (w) setMeasuredM(wallLengthMeters(w).toFixed(2));
    } else if (selectedTarget?.kind === "object") {
      setAnchorId(selectedTarget.id);
      setDimension("object_width");
      const o = objects.find((item) => item.id === selectedTarget.id);
      if (o) setMeasuredM(o.width_m.toFixed(2));
    } else if (
      (!anchorId ||
        ![...walls, ...objects].some((item) => item.id === anchorId)) &&
      walls.length > 0
    ) {
      setAnchorId(walls[0].id);
      setDimension("wall_length");
      setMeasuredM(wallLengthMeters(walls[0]).toFixed(2));
    }
  }, [scene?.scene_id, selectedTarget]);

  if (!scene) return null;

  const cal = scene.calibration;
  const anchorOptions = [
    ...walls.map((w) => ({
      id: w.id,
      kind: "wall" as const,
      label: `${w.id} (Wall · est ${wallLengthMeters(w).toFixed(2)}m)`,
    })),
    ...objects.map((o) => ({
      id: o.id,
      kind: "object" as const,
      label: `${o.label} (${o.id} · est ${o.width_m.toFixed(2)}×${o.depth_m.toFixed(2)}m)`,
    })),
  ];

  const selectedIsWall = walls.some((w) => w.id === anchorId);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(measuredM);
    const tol = parseFloat(toleranceM);
    if (!anchorId || !Number.isFinite(val) || val <= 0) return;

    const req: CalibrateRequest = {
      expected_revision: scene.scene_revision ?? 1,
      anchor_id: anchorId,
      dimension: selectedIsWall
        ? "wall_length"
        : dimension === "wall_length"
          ? "object_width"
          : dimension,
      measured_m: val,
      tolerance_m: Number.isFinite(tol) && tol >= 0 ? tol : 0.01,
    };

    if (useHoldout && holdoutAnchorId) {
      const hVal = parseFloat(holdoutMeasuredM);
      if (Number.isFinite(hVal) && hVal > 0) {
        const holdoutIsWall = walls.some((w) => w.id === holdoutAnchorId);
        req.holdout_anchor_id = holdoutAnchorId;
        req.holdout_dimension = holdoutIsWall
          ? "wall_length"
          : holdoutDimension === "wall_length"
            ? "object_width"
            : holdoutDimension;
        req.holdout_measured_m = hVal;
      }
    }
    onCalibrate(req);
  };

  return (
    <section className="rl-panel" aria-label="Scale calibration">
      <div className="rl-panel-header">
        <span className="rl-panel-title">
          <Ruler size={15} /> Set the scale
        </span>
        {cal ? (
          <span className="rl-badge rl-badge--ok">
            <CheckCircle2 size={12} /> Scale ×{cal.scale_factor.toFixed(3)}
          </span>
        ) : (
          <span className="rl-badge rl-badge--warn">
            <AlertCircle size={12} /> Uncalibrated Draft
          </span>
        )}
      </div>

      <p className="rl-muted-note">
        One measured anchor scales the estimated draft hypothesis. It confirms
        only the measured dimension, not unobserved walls or other objects.
      </p>

      {cal && (
        <div className="rl-cal-summary">
          <div>
            <strong>Anchor:</strong> {cal.anchor_id} ({cal.dimension}) ={" "}
            {cal.measured_m.toFixed(2)}m ±{" "}
            {(cal.tolerance_m ?? 0.01).toFixed(2)}m (was{" "}
            {cal.original_estimate_m.toFixed(2)}m)
          </div>
          {cal.holdout_residual_m != null && (
            <div>
              <strong>Held-out check:</strong> predicted{" "}
              {cal.holdout_predicted_m?.toFixed(2)}m vs measured{" "}
              {cal.holdout_measured_m?.toFixed(2)}m (residual{" "}
              {cal.holdout_residual_m >= 0 ? "+" : ""}
              {cal.holdout_residual_m.toFixed(3)}m)
            </div>
          )}
        </div>
      )}

      <form onSubmit={handleSubmit} className="rl-form">
        <label className="rl-field">
          <span>Reference Wall or Object</span>
          <select
            value={anchorId}
            onChange={(e) => {
              const nextId = e.target.value;
              setAnchorId(nextId);
              if (walls.some((w) => w.id === nextId)) {
                setDimension("wall_length");
              } else if (dimension === "wall_length") {
                setDimension("object_width");
              }
            }}
          >
            {anchorOptions.map((opt) => (
              <option key={opt.id} value={opt.id}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>

        {!selectedIsWall && (
          <label className="rl-field">
            <span>Object Axis</span>
            <select
              value={dimension === "wall_length" ? "object_width" : dimension}
              onChange={(e) =>
                setDimension(e.target.value as "object_width" | "object_depth")
              }
            >
              <option value="object_width">Width (X axis)</option>
              <option value="object_depth">Depth (Z axis)</option>
            </select>
          </label>
        )}

        <div className="rl-field-row">
          <label className="rl-field">
            <span>Measured (m)</span>
            <input
              type="number"
              step="0.01"
              min="0.1"
              max="100"
              value={measuredM}
              onChange={(e) => setMeasuredM(e.target.value)}
              required
            />
          </label>
          <label className="rl-field">
            <span>Tolerance ±(m)</span>
            <input
              type="number"
              step="0.005"
              min="0"
              max="2"
              value={toleranceM}
              onChange={(e) => setToleranceM(e.target.value)}
            />
          </label>
        </div>

        <label className="rl-checkbox-row">
          <input
            type="checkbox"
            checked={useHoldout}
            onChange={(e) => setUseHoldout(e.target.checked)}
          />
          <span>
            Include independent held-out dimension check (does not fit scale)
          </span>
        </label>

        {useHoldout && (
          <div className="rl-holdout-box">
            <label className="rl-field">
              <span>Held-Out Element</span>
              <select
                value={holdoutAnchorId}
                onChange={(e) => setHoldoutAnchorId(e.target.value)}
              >
                <option value="">Select element…</option>
                {anchorOptions
                  .filter((o) => o.id !== anchorId)
                  .map((opt) => (
                    <option key={opt.id} value={opt.id}>
                      {opt.label}
                    </option>
                  ))}
              </select>
            </label>
            <div className="rl-field-row">
              <label className="rl-field">
                <span>Dimension</span>
                <select
                  value={holdoutDimension}
                  onChange={(e) =>
                    setHoldoutDimension(
                      e.target.value as
                        | "wall_length"
                        | "object_width"
                        | "object_depth",
                    )
                  }
                >
                  <option value="wall_length">Wall length</option>
                  <option value="object_width">Object width</option>
                  <option value="object_depth">Object depth</option>
                </select>
              </label>
              <label className="rl-field">
                <span>Measured (m)</span>
                <input
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="100"
                  value={holdoutMeasuredM}
                  onChange={(e) => setHoldoutMeasuredM(e.target.value)}
                />
              </label>
            </div>
          </div>
        )}

        <button
          type="submit"
          className="rl-btn rl-btn--primary rl-btn--full"
          disabled={isCalibrating || dirty}
          title={
            dirty
              ? "Save or revert local edits before running server scale calibration"
              : undefined
          }
        >
          <span>
            {dirty
              ? "Save Local Edits First to Calibrate"
              : isCalibrating
                ? "Applying Scale…"
                : "Apply Measured Scale Anchor"}
          </span>
        </button>
      </form>
    </section>
  );
};
