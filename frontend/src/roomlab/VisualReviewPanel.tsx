import React from "react";
import { Eye, Sparkles } from "lucide-react";
import type { RoomSceneV1, SolveRequest } from "./contracts.generated";
import { useSceneCritique } from "./useSceneCritique";

export function VisualReviewPanel({
  scene,
  dirty,
  request,
  focus,
  onFrame,
  contextVersion,
  onStartReview,
}: {
  scene: RoomSceneV1 | null;
  dirty: boolean;
  contextVersion: number;
  onStartReview: () => void;
  request: SolveRequest | null;
  focus: string[];
  onFrame: (id: string) => void;
}) {
  const review = useSceneCritique(scene, dirty, contextVersion);
  if (!scene || !request) return null;
  return (
    <section
      className="rl-panel rl-v2-section"
      aria-label="Visual scene review"
    >
      <div className="rl-panel-header">
        <span className="rl-panel-title">
          <Eye size={15} />
          Compare with the walkthrough
        </span>
      </div>
      <p className="rl-muted-note">
        Argon compares this room plan with up to six source frames. Its notes
        are advisory, not measurements or clearance verification.
      </p>
      <button
        className="rl-btn rl-btn--full"
        disabled={dirty || review.busy || !scene.evidence_frames?.length}
        onClick={() => {
          onStartReview();
          void review.start(request, focus);
        }}
      >
        <Sparkles size={14} />
        {dirty
          ? "Save before reviewing"
          : review.busy
            ? "Reviewing evidence…"
            : "Review scene with Argon"}
      </button>
      {review.busy && (
        <div className="rl-inline-inputs">
          <span className="rl-muted-note">
            {review.job?.status ?? "Preparing"} · room unchanged
          </span>
          <button className="rl-btn rl-btn--xs" onClick={review.cancel}>
            Cancel review
          </button>
        </div>
      )}
      {review.error && (
        <p role="alert" className="rl-job-error">
          {review.error}
        </p>
      )}
      {review.result && (
        <div className="rl-critic-result" role="status">
          <small>
            ADVISORY · {review.result.model} ·{" "}
            {(review.result.latency_ms / 1000).toFixed(1)}s · revision{" "}
            {review.result.scene_revision}
          </small>
          <p>{review.result.summary}</p>
          {(review.result.findings ?? []).map((f, i) => (
            <div className="rl-critic-finding" key={i}>
              <strong>
                {f.kind === "needs_evidence"
                  ? "More evidence needed"
                  : "Observation"}
              </strong>
              <p>{f.message}</p>
              {f.measurement_request && (
                <p className="rl-muted-note">
                  Measure: {f.measurement_request}
                </p>
              )}
              <div className="rl-pill-list">
                {(f.frame_ids ?? []).map((id) => {
                  const frame = scene.evidence_frames?.find(
                    (fr) => fr.frame_id === id,
                  );
                  return (
                    <button
                      className="rl-pill"
                      key={id}
                      onClick={() => onFrame(id)}
                    >
                      Frame {frame?.timestamp_s.toFixed(1)}s
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
      <details className="rl-notes-box">
        <summary>Plan sent for review</summary>
        <img
          loading="lazy"
          className="rl-bev-preview"
          src={
            "/api/roomlab/scenes/" +
            encodeURIComponent(scene.scene_id) +
            "/preview.png?revision=" +
            scene.scene_revision
          }
          alt="Labelled estimated floor plan with voids, partitions and object footprints"
        />
      </details>
    </section>
  );
}
