import React from 'react';
import {
  Upload,
  Sparkles,
  Undo2,
  Redo2,
  Save,
  Download,
  FolderOpen,
  Compass,
  Grid,
  Plus,
  RotateCcw,
} from 'lucide-react';
import type { Config } from './api';
import type { ViewMode } from './editorState';

interface RoomToolbarProps {
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

export const RoomToolbar: React.FC<RoomToolbarProps> = ({
  config,
  sceneName,
  sceneRevision,
  geometrySource,
  isConfigured,
  dirty,
  canUndo,
  canRedo,
  isUploading,
  isExtracting,
  isSaving,
  viewMode,
  showCSpace,
  onSelectVideoFile,
  onUseSampleVideo,
  onUndo,
  onRedo,
  onDiscardEdits,
  onSaveScene,
  onExportJson,
  onImportJsonFile,
  onAddObject,
  onChangeViewMode,
  onToggleCSpace,
}) => {
  const videoInputRef = React.useRef<HTMLInputElement>(null);
  const jsonInputRef = React.useRef<HTMLInputElement>(null);

  return (
    <header className="rl-toolbar" role="banner">
      <div className="rl-toolbar-brand">
        <div className="rl-logo-badge">RL</div>
        <div>
          <div className="rl-brand-row">
            <h1 className="rl-title">RoomLab</h1>
            <span className={`rl-chip ${isConfigured ? 'rl-chip--ok' : 'rl-chip--warn'}`}>
              {isConfigured ? `Gemini ready · ${config?.model ?? 'gemini-4-argon'}` : 'Gemini not configured'}
            </span>
            {sceneRevision !== null && (
              <span className="rl-chip">
                Rev {sceneRevision} · {geometrySource ?? 'model_estimate'}
              </span>
            )}
            {dirty && <span className="rl-chip rl-chip--dirty">Unsaved Local Edits</span>}
          </div>
          <p className="rl-subtitle">
            {sceneName || 'Video to Editable 3D Room · Evidence-Linked Draft, Scale Calibration & Clearance'}
          </p>
        </div>
      </div>

      <div className="rl-toolbar-actions">
        <input
          ref={videoInputRef}
          type="file"
          accept="video/mp4,video/webm,video/quicktime"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onSelectVideoFile(file);
            e.target.value = '';
          }}
        />
        <button
          type="button"
          className="rl-btn rl-btn--primary"
          disabled={isUploading || isExtracting}
          onClick={() => videoInputRef.current?.click()}
        >
          <Upload size={15} />
          <span>{isUploading ? 'Decoding Video…' : 'Upload Room Video'}</span>
        </button>

        {config?.sample_video_url && (
          <button
            type="button"
            className="rl-btn"
            disabled={isUploading || isExtracting}
            onClick={onUseSampleVideo}
            title="Load synthetic sample clip and run live Gemini extraction"
          >
            <Sparkles size={15} />
            <span>Try Synthetic Clip</span>
          </button>
        )}

        <div className="rl-divider" />

        <div className="rl-btn-group" role="group" aria-label="View mode">
          <button
            type="button"
            className={`rl-btn ${viewMode === 'orbit' ? 'rl-btn--active' : ''}`}
            onClick={() => onChangeViewMode('orbit')}
          >
            <Compass size={14} />
            <span>3D Orbit</span>
          </button>
          <button
            type="button"
            className={`rl-btn ${viewMode === 'top' ? 'rl-btn--active' : ''}`}
            onClick={() => onChangeViewMode('top')}
          >
            <Grid size={14} />
            <span>Top Plan</span>
          </button>
          <button
            type="button"
            className={`rl-btn ${showCSpace ? 'rl-btn--active' : ''}`}
            onClick={onToggleCSpace}
            title="Toggle 2D Configuration-Space obstacle & path overlay"
          >
            <span>C-Space Overlay</span>
          </button>
        </div>

        <div className="rl-divider" />

        <div className="rl-btn-group" role="group" aria-label="Add object">
          <button type="button" className="rl-btn" onClick={() => onAddObject('table')} title="Add Table">
            <Plus size={14} />
            <span>+ Table</span>
          </button>
          <button type="button" className="rl-btn" onClick={() => onAddObject('chair')} title="Add Chair">
            <span>+ Chair</span>
          </button>
        </div>

        <div className="rl-divider" />

        <div className="rl-btn-group" role="group" aria-label="History and persistence">
          <button type="button" className="rl-btn" disabled={!canUndo} onClick={onUndo} title="Undo edit">
            <Undo2 size={14} />
          </button>
          <button type="button" className="rl-btn" disabled={!canRedo} onClick={onRedo} title="Redo edit">
            <Redo2 size={14} />
          </button>
          {dirty && (
            <button
              type="button"
              className="rl-btn"
              onClick={onDiscardEdits}
              title="Revert unsaved local changes to authoritative revision"
            >
              <RotateCcw size={14} />
            </button>
          )}
          <button
            type="button"
            className={`rl-btn ${dirty ? 'rl-btn--accent' : ''}`}
            disabled={!dirty || isSaving || sceneRevision === null}
            onClick={onSaveScene}
          >
            <Save size={14} />
            <span>{isSaving ? 'Saving…' : 'Save Revision'}</span>
          </button>
          <button
            type="button"
            className="rl-btn"
            disabled={sceneRevision === null}
            onClick={onExportJson}
            title="Export current RoomSceneV1 JSON"
          >
            <Download size={14} />
            <span>Export JSON</span>
          </button>
          <input
            ref={jsonInputRef}
            type="file"
            accept="application/json,.json"
            style={{ display: 'none' }}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onImportJsonFile(file);
              e.target.value = '';
            }}
          />
          <button
            type="button"
            className="rl-btn"
            onClick={() => jsonInputRef.current?.click()}
            title="Import a saved RoomSceneV1 JSON file"
          >
            <FolderOpen size={14} />
            <span>Import JSON</span>
          </button>
        </div>
      </div>
    </header>
  );
};
