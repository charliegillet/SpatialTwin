import React from "react";
import {
  Film,
  Play,
  XCircle,
  Image as ImageIcon,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import type {
  EvidenceFrame,
  JobRecord,
  MediaRecord,
  RoomSceneV1,
} from "./contracts.generated";

interface RoomEvidencePanelProps {
  media: MediaRecord | null;
  job: JobRecord | null;
  scene: RoomSceneV1 | null;
  selectedFrameIds: string[];
  activeFrameId: string | null;
  isExtracting: boolean;
  onSelectFrame: (frameId: string | null) => void;
  onExtractRoom: () => void;
  onCancelJob: () => void;
}

export const RoomEvidencePanel: React.FC<RoomEvidencePanelProps> = ({
  media,
  job,
  scene,
  selectedFrameIds,
  activeFrameId,
  isExtracting,
  onSelectFrame,
  onExtractRoom,
  onCancelJob,
}) => {
  const frames: EvidenceFrame[] = scene?.evidence_frames?.length &&
    (!media || scene.evidence_frames[0].media_id === media.media_id)
    ? scene.evidence_frames : media?.frames ?? [];
  const highlightedSet = new Set(selectedFrameIds);
  const activeFrame = frames.find((f) => f.frame_id === activeFrameId) ?? null;

  return (
    <section className="rl-panel" aria-label="Video and frame evidence">
      <div className="rl-panel-header">
        <span className="rl-panel-title">
          <Film size={15} /> Your walkthrough
        </span>
        {media && (
          <span className="rl-badge">
            {media.duration_s.toFixed(1)}s · {frames.length} frames
          </span>
        )}
      </div>

      {media ? (
        <div className="rl-video-box">
          <video
            key={media.video_url}
            src={media.video_url}
            controls
            playsInline
            muted
            className="rl-video-player"
          />
          <div className="rl-video-actions">
            <button
              type="button"
              className="rl-btn rl-btn--primary rl-btn--full"
              disabled={isExtracting}
              onClick={onExtractRoom}
            >
              <Play size={14} />
              <span>
                {isExtracting ? "Building your room…" : "Create editable room"}
              </span>
            </button>
            {isExtracting && job && (
              <button
                type="button"
                className="rl-btn rl-btn--danger"
                onClick={onCancelJob}
              >
                <XCircle size={14} />
                <span>Cancel</span>
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="rl-empty-card">
          <p>
            Bring in a room walkthrough. MP4, MOV or WebM, up to 10 minutes and
            1 GiB. You can also import a saved room.
          </p>
          <p className="rl-muted-note">
            Walk slowly with overlapping views. A moving viewpoint captures more
            depth than a stationary pan.
          </p>
        </div>
      )}

      {job && (
        <div className={`rl-job-banner rl-job-banner--${job.status}`}>
          <div className="rl-job-row">
            <strong>
              Extraction Job: {job.status.toUpperCase()}
              {job.stage ? ` (${job.stage.replace(/_/g, " ")})` : ""}
            </strong>
            {job.latency_ms != null && (
              <span>{(job.latency_ms / 1000).toFixed(2)}s</span>
            )}
          </div>
          {job.model && (
            <div className="rl-job-meta">
              Model: {job.model} · Provenance: live
            </div>
          )}
          {job.agent_steps && job.agent_steps.length > 0 && (
            <ul className="rl-job-warnings" aria-label="Agent progress steps">
              {job.agent_steps.map((step, idx) => (
                <li key={idx}>• {step}</li>
              ))}
            </ul>
          )}
          {job.error && (
            <div className="rl-job-error">
              <AlertTriangle size={14} /> <span>{job.error}</span>
            </div>
          )}
          {job.warnings && job.warnings.length > 0 && (
            <details>
              <summary>{job.warnings.length} review notes</summary>
              <ul className="rl-job-warnings">
                {job.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {frames.length > 0 && (
        <div className="rl-frames-section">
          <div className="rl-frames-header">
            <span>
              <ImageIcon size={13} /> Evidence frames ({frames.length})
            </span>
            {highlightedSet.size > 0 && (
              <span className="rl-badge rl-badge--accent">
                {highlightedSet.size} linked to selected element
              </span>
            )}
          </div>

          <div className="rl-frames-grid">
            {frames.map((frame) => {
              const isLinked = highlightedSet.has(frame.frame_id);
              const isActive = activeFrameId === frame.frame_id;
              return (
                <button
                  key={frame.frame_id}
                  type="button"
                  className={`rl-frame-thumb ${isLinked ? "rl-frame-thumb--linked" : ""} ${
                    isActive ? "rl-frame-thumb--active" : ""
                  }`}
                  onClick={() =>
                    onSelectFrame(isActive ? null : frame.frame_id)
                  }
                  title={`${frame.frame_id} at ${frame.timestamp_s.toFixed(2)}s`}
                >
                  <img
                    src={frame.url}
                    alt={`Frame at ${frame.timestamp_s}s`}
                    loading="lazy"
                  />
                  <div className="rl-frame-caption">
                    <span>{frame.timestamp_s.toFixed(1)}s</span>
                    {isLinked && <CheckCircle2 size={11} />}
                  </div>
                </button>
              );
            })}
          </div>

          {activeFrame && (
            <div className="rl-frame-lightbox">
              <div className="rl-frame-lightbox-bar">
                <span>
                  {activeFrame.frame_id} · t=
                  {activeFrame.timestamp_s.toFixed(2)}s
                </span>
                <button
                  type="button"
                  className="rl-btn rl-btn--xs"
                  onClick={() => onSelectFrame(null)}
                >
                  Close
                </button>
              </div>
              <img src={activeFrame.url} alt={activeFrame.frame_id} />
            </div>
          )}
        </div>
      )}

      {scene?.notes && scene.notes.length > 0 && (
        <details className="rl-notes-box">
          <summary>Scene notes & assumptions</summary>
          <ul>
            {scene.notes.map((n, i) => (
              <li key={i}>{n}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
};
