import React from "react";
import {
  Upload,
  Sparkles,
  Undo2,
  Redo2,
  Save,
  Download,
  FolderOpen,
  Compass,
  Grid2X2,
  RotateCcw,
  MoreHorizontal,
  MousePointer2,
  Layers3,
  Armchair,
  Table2,
  ChevronDown,
  ScanLine,
} from "lucide-react";
import type { Config } from "./api";
import type { ViewMode } from "./editorState";

interface RoomToolbarProps {
  onInspect: () => void;
  config: Config | null;
  sceneName: string;
  sceneRevision: number | null;
  geometrySource: string | null;
  isConfigured: boolean;
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
  isUploading: boolean;
  isExtracting: boolean;
  isSaving: boolean;
  viewMode: ViewMode;
  showCSpace: boolean;
  onSelectVideoFile: (file: File) => void;
  onUseSampleVideo: () => void;
  onUndo: () => void;
  onRedo: () => void;
  onDiscardEdits: () => void;
  onSaveScene: () => void;
  onExportJson: () => void;
  onImportJsonFile: (file: File) => void;
  onAddObject: (category: string) => void;
  onChangeViewMode: (mode: ViewMode) => void;
  onToggleCSpace: () => void;
}

export const RoomToolbar: React.FC<RoomToolbarProps> = (p) => {
  const videoRef = React.useRef<HTMLInputElement>(null),
    jsonRef = React.useRef<HTMLInputElement>(null);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => {
    if (!menuOpen) return;
    const close = (e: PointerEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node))
        setMenuOpen(false);
    };
    const escape = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [menuOpen]);
  return (
    <>
      <header className="rl-toolbar" role="banner">
        <div className="rl-toolbar-brand">
          <div className="rl-logo-badge">
            <ScanLine size={23} strokeWidth={1.7} />
          </div>
          <div>
            <h1 className="rl-title">
              RoomLab <ChevronDown size={13} />
            </h1>
            <span className="rl-brand-note">A new perspective.</span>
          </div>
        </div>
        <div className="rl-document-title">
          <span>{p.sceneName || "Untitled room"}</span>
          <small>
            {p.sceneRevision ? "Revision " + p.sceneRevision : "New workspace"}
          </small>
        </div>
        <div className="rl-toolbar-actions">
          <input
            ref={videoRef}
            type="file"
            accept="video/mp4,video/webm,video/quicktime"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) p.onSelectVideoFile(file);
              e.target.value = "";
            }}
          />
          <input
            ref={jsonRef}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) p.onImportJsonFile(file);
              e.target.value = "";
            }}
          />
          <span className="rl-save-state">
            <span
              className={`rl-status-dot ${p.dirty ? "rl-status-dot--dirty" : ""}`}
            />
            {p.isSaving
              ? "Saving…"
              : p.dirty
                ? "Unsaved"
                : p.sceneRevision === null
                  ? "New room"
                  : "All changes saved"}
          </span>
          <button
            className="rl-btn rl-upload-button"
            aria-label="Upload video"
            disabled={p.isUploading || p.isExtracting}
            onClick={() => videoRef.current?.click()}
          >
            <Upload size={15} />
            {p.isUploading ? "Decoding…" : "Upload video"}
          </button>
          {p.dirty ? (
            <button
              className="rl-btn rl-btn--primary"
              disabled={p.isSaving}
              onClick={p.onSaveScene}
            >
              <Save size={15} />
              Save changes
            </button>
          ) : (
            <button
              className="rl-btn rl-btn--primary"
              disabled={p.sceneRevision === null}
              onClick={p.onExportJson}
            >
              <Download size={15} />
              Export room
            </button>
          )}
          <div className="rl-overflow-wrap" ref={menuRef}>
            <button
              className="rl-icon-btn"
              aria-label="More actions"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((v) => !v)}
            >
              <MoreHorizontal size={20} />
            </button>
            {menuOpen && (
              <div
                className="rl-overflow-menu"
                aria-label="More workspace actions"
              >
                <span className="rl-menu-label">WORKSPACE</span>
                <button
                  onClick={() => {
                    jsonRef.current?.click();
                    setMenuOpen(false);
                  }}
                >
                  <FolderOpen size={15} />
                  Import room JSON
                </button>
                <button
                  disabled={p.sceneRevision === null}
                  onClick={() => {
                    p.onExportJson();
                    setMenuOpen(false);
                  }}
                >
                  <Download size={15} />
                  Export JSON
                </button>
                {p.config?.sample_video_url && (
                  <button
                    disabled={p.isUploading || p.isExtracting}
                    onClick={() => {
                      p.onUseSampleVideo();
                      setMenuOpen(false);
                    }}
                  >
                    <Sparkles size={15} />
                    Try synthetic clip
                  </button>
                )}
                <button
                  disabled={!p.dirty}
                  onClick={() => {
                    p.onDiscardEdits();
                    setMenuOpen(false);
                  }}
                >
                  <RotateCcw size={15} />
                  Discard unsaved edits
                </button>
                <div className="rl-menu-foot">
                  <span className="rl-status-dot" />
                  {p.isConfigured
                    ? "Gemini connected"
                    : "Gemini not configured"}
                  <small>{p.config?.model}</small>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
      <nav className="rl-floating-tools" aria-label="Canvas tools">
        <button
          className="rl-icon-btn"
          aria-label="Inspect objects"
          title="Inspect objects"
          onClick={p.onInspect}
        >
          <MousePointer2 size={19} />
        </button>
        <span className="rl-tool-separator" />
        <button
          className={`rl-icon-btn ${p.viewMode === "orbit" ? "is-active" : ""}`}
          aria-label="3D Orbit"
          aria-pressed={p.viewMode === "orbit"}
          title="3D orbit"
          onClick={() => p.onChangeViewMode("orbit")}
        >
          <Compass size={19} />
        </button>
        <button
          className={`rl-icon-btn ${p.viewMode === "top" ? "is-active" : ""}`}
          aria-label="Top Plan"
          aria-pressed={p.viewMode === "top"}
          title="Top plan"
          onClick={() => p.onChangeViewMode("top")}
        >
          <Grid2X2 size={18} />
        </button>
        <button
          className={`rl-icon-btn ${p.showCSpace ? "is-active" : ""}`}
          aria-label="Clearance overlay"
          aria-pressed={p.showCSpace}
          title="Clearance overlay"
          onClick={p.onToggleCSpace}
        >
          <Layers3 size={19} />
        </button>
        <span className="rl-tool-separator" />
        <button
          className="rl-icon-btn"
          aria-label="Add table"
          title="Add table"
          disabled={p.sceneRevision === null}
          onClick={() => p.onAddObject("table")}
        >
          <Table2 size={19} />
        </button>
        <button
          className="rl-icon-btn"
          aria-label="Add chair"
          title="Add chair"
          disabled={p.sceneRevision === null}
          onClick={() => p.onAddObject("chair")}
        >
          <Armchair size={19} />
        </button>
        <span className="rl-tool-separator" />
        <button
          className="rl-icon-btn"
          aria-label="Undo edit"
          title="Undo"
          disabled={!p.canUndo}
          onClick={p.onUndo}
        >
          <Undo2 size={18} />
        </button>
        <button
          className="rl-icon-btn"
          aria-label="Redo edit"
          title="Redo"
          disabled={!p.canRedo}
          onClick={p.onRedo}
        >
          <Redo2 size={18} />
        </button>
      </nav>
    </>
  );
};
