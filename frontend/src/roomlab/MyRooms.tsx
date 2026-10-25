import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Plus,
  Search,
  ArrowUpRight,
  Upload,
  Loader2,
  Film,
  ChevronLeft,
} from "lucide-react";
import type { RoomSubmission } from "./contracts.generated";
import { getRoomLibrary } from "./api";
import { RoomBrand } from "./RoomBrand";

const statusLabel = {
  ready: "Ready",
  processing: "Building your room…",
  uploaded: "Ready to build",
  needs_attention: "Needs attention",
};
function when(timestamp: number) {
  const d = new Date(timestamp * 1000),
    today = new Date();
  if (d.toDateString() === today.toDateString())
    return `Today, ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  return d.toDateString() === yesterday.toDateString()
    ? "Yesterday"
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}
export function MyRooms({
  sceneId,
  refreshToken,
  busy,
  onOpen,
  onBuild,
  onUpload,
  onBack,
}: {
  sceneId: string | null;
  refreshToken: string;
  busy: boolean;
  onOpen: (entry: RoomSubmission, sceneId?: string) => void;
  onBuild: (entry: RoomSubmission) => void;
  onUpload: (file: File) => void;
  onBack: () => void;
}) {
  const [items, setItems] = useState<RoomSubmission[]>([]),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState<"all" | "ready" | "processing">("all");
  const [loading, setLoading] = useState(true),
    [error, setError] = useState<string | null>(null),
    [retry, setRetry] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let stopped = false,
      timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const result = await getRoomLibrary();
        if (!stopped) {
          setItems(result.items);
          setError(null);
        }
      } catch (e) {
        if (!stopped)
          setError(e instanceof Error ? e.message : "Could not load rooms.");
      } finally {
        if (!stopped) {
          setLoading(false);
          timer = setTimeout(refresh, 4000);
        }
      }
    };
    void refresh();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [refreshToken, retry]);
  const visible = useMemo(
    () =>
      items.filter(
        (item) =>
          (filter === "all" || item.status === filter) &&
          [
            item.title,
            item.filename,
            ...(item.scenes ?? []).map((s) => s.name),
          ].some((t) => t?.toLowerCase().includes(query.trim().toLowerCase())),
      ),
    [items, filter, query],
  );
  const chooseFile = () => input.current?.click();
  const grouped = [
    "ready",
    "processing",
    "needs_attention",
    "uploaded",
  ] as const;
  return (
    <section className="rl-library" aria-label="My rooms">
      <RoomBrand />
      <div className="rl-library-header">
        <div className="rl-library-breadcrumb">
          <span>Workspace</span>
          <span>/</span>
          <span>My rooms</span>
        </div>
        <div className="rl-library-title">
          <h2>My rooms</h2>
          <button
            aria-label="Upload new walkthrough"
            title="Upload walkthrough"
            className="rl-new-room"
            onClick={chooseFile}
            disabled={busy}
          >
            <Plus size={22} />
          </button>
        </div>
        <label className="rl-room-search">
          <Search size={18} />
          <input
            aria-label="Search rooms"
            placeholder="Search rooms…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <div className="rl-room-filters" role="group" aria-label="Filter rooms">
          {(["all", "ready", "processing"] as const).map((f) => (
            <button
              key={f}
              aria-pressed={filter === f}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? (
                <>
                  All <span>{items.length}</span>
                </>
              ) : f === "ready" ? (
                "Ready"
              ) : (
                "Processing"
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="rl-room-list" aria-live="polite" aria-busy={loading}>
        {error && (
          <div className="rl-library-error" role="alert">
            {error}
            <button
              className="rl-btn rl-btn--xs"
              onClick={() => setRetry((n) => n + 1)}
            >
              Try again
            </button>
          </div>
        )}
        {loading && !items.length && (
          <p className="rl-library-empty">
            <Loader2 size={18} className="rl-spin" /> Loading your rooms…
          </p>
        )}
        {!loading && !visible.length && (
          <div className="rl-library-empty">
            <Film size={25} />
            <h3>
              {items.length ? "No matching rooms" : "Your rooms start here"}
            </h3>
            <p>
              {items.length
                ? "Try another search or filter."
                : "Upload a walkthrough to create your first editable room."}
            </p>
          </div>
        )}
        {grouped.map((status) => {
          const group = visible.filter((i) => i.status === status);
          if (!group.length) return null;
          return (
            <div key={status} className="rl-room-section">
              {status !== "ready" && (
                <div className="rl-room-section-title">
                  {status === "processing"
                    ? "Processing"
                    : status === "needs_attention"
                      ? "Needs attention"
                      : "To build"}
                  <span />
                </div>
              )}
              {group.map((item) => {
                const selected = (item.scenes ?? []).some(
                  (s) => s.scene_id === sceneId,
                );
                const current = (item.scenes ?? []).find(
                  (s) => s.scene_id === sceneId,
                );
                const title = current?.name ?? item.title;
                return (
                  <article
                    key={item.submission_id}
                    className={`rl-room-card ${selected ? "is-selected" : ""}`}
                    aria-label={title}
                  >
                    <button
                      className="rl-room-card-main"
                      aria-label={`Open ${title}`}
                      aria-current={selected ? "true" : undefined}
                      onClick={() => onOpen(item, current?.scene_id)}
                      disabled={busy}
                    >
                      <span className="rl-room-thumbnail">
                        {item.thumbnail_url ? (
                          <img
                            src={item.thumbnail_url}
                            alt="Walkthrough preview"
                            loading="lazy"
                            onError={(e) => {
                              e.currentTarget.style.display = "none";
                            }}
                          />
                        ) : (
                          <Film size={24} />
                        )}
                      </span>
                      <span className="rl-room-card-body">
                        <strong>{title}</strong>
                        <span className="rl-room-date">
                          {item.filename ? `${item.filename} · ` : ""}
                          {when(item.submitted_at)}
                        </span>
                        <span className={`rl-room-status is-${status}`}>
                          {status === "processing" ? (
                            <Loader2 size={12} className="rl-spin" />
                          ) : (
                            <i />
                          )}
                          {statusLabel[status]}
                        </span>
                        {status === "processing" && (
                          <span
                            className="rl-room-progress"
                            role="progressbar"
                            aria-label="Building room"
                          />
                        )}
                      </span>
                      <span className="rl-room-open">
                        {item.scene_id
                          ? "Open"
                          : status === "processing"
                            ? "View"
                            : "View"}{" "}
                        <ArrowUpRight size={12} />
                      </span>
                    </button>
                    {item.error && (
                      <p className="rl-room-error-detail">{item.error}</p>
                    )}
                    {(status === "needs_attention" || status === "uploaded") &&
                      item.media_id && (
                        <button
                          className="rl-room-retry"
                          onClick={() => onBuild(item)}
                          disabled={busy}
                        >
                          {status === "uploaded" ? "Build room" : "Retry"}
                        </button>
                      )}
                    {(item.scenes?.length ?? 0) > 1 && (
                      <details className="rl-room-versions">
                        <summary>{item.scenes!.length} saved outputs</summary>
                        {item.scenes!.map((s) => (
                          <button
                            key={s.scene_id}
                            onClick={() => onOpen(item, s.scene_id)}
                            disabled={busy}
                          >
                            {s.name}
                            <small>
                              Revision {s.scene_revision} · {when(s.updated_at)}
                            </small>
                          </button>
                        ))}
                      </details>
                    )}
                  </article>
                );
              })}
            </div>
          );
        })}
      </div>
      <div className="rl-library-footer">
        {sceneId && (
          <button className="rl-room-back" onClick={onBack}>
            <ChevronLeft size={14} /> Back to current room
          </button>
        )}
        <button
          className="rl-upload-walkthrough"
          onClick={chooseFile}
          disabled={busy}
        >
          {busy ? (
            <Loader2 className="rl-spin" size={17} />
          ) : (
            <Plus size={19} />
          )}{" "}
          {busy ? "Uploading…" : "Upload walkthrough"}
        </button>
        <span>
          {items.length} {items.length === 1 ? "submission" : "submissions"} ·
          Saved locally
        </span>
      </div>
      <input
        ref={input}
        type="file"
        accept="video/mp4,video/webm,video/quicktime"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) onUpload(file);
          e.currentTarget.value = "";
        }}
      />
    </section>
  );
}
