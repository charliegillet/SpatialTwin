import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  calibrateScene,
  cancelJob,
  extractRoom,
  getConfig,
  getJob,
  getMedia,
  getScene,
  importScene,
  optimizeScene,
  saveScene,
  solveScene,
  uploadVideo,
  validateScene,
  type Config,
} from './api';
import type {
  CalibrateRequest,
  JobRecord,
  MediaRecord,
  OptimizeResult,
  RoomObject,
  RoomSceneV1,
  SolveRequest,
  SolveResult,
  ValidationReport,
} from './contracts.generated';
import {
  addObjectToScene,
  createInitialHistory,
  deriveWallsFromFloor,
  discardUnsavedEdits,
  loadAuthoritativeScene,
  pushSceneEdit,
  redoSceneEdit,
  removeObjectFromScene,
  undoSceneEdit,
  updateObjectInScene,
  type HistoryState,
  type SelectionTarget,
  type ViewMode,
} from './editorState';
import { RoomToolbar } from './RoomToolbar';
import { RoomCanvas3D } from './RoomCanvas3D';
import { RoomEvidencePanel } from './RoomEvidencePanel';
import { CalibrationPanel } from './CalibrationPanel';
import { RoomEditor } from './RoomEditor';
import { ClearancePanel } from './ClearancePanel';
import './roomlab.css';

export default function RoomLabWorkspace() {
  const [config, setConfig] = useState<Config | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
  const [job, setJob] = useState<JobRecord | null>(null);
  const [history, setHistory] = useState<HistoryState>(() => createInitialHistory(null));

  const [selectedTarget, setSelectedTarget] = useState<SelectionTarget>(null);
  const [activeFrameId, setActiveFrameId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('orbit');
  const [showCSpace, setShowCSpace] = useState<boolean>(true);

  const [startPoint, setStartPoint] = useState<[number, number]>([-1.5, -1.0]);
  const [goalPoint, setGoalPoint] = useState<[number, number]>([1.5, 1.0]);
  const [agentDiameterM, setAgentDiameterM] = useState<number>(0.65);
  const [marginM, setMarginM] = useState<number>(0.02);
  const [pickEndpointMode, setPickEndpointMode] = useState<'start' | 'goal' | null>(null);

  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [solveResult, setSolveResult] = useState<SolveResult | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(null);

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isCalibrating, setIsCalibrating] = useState<boolean>(false);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [isSolving, setIsSolving] = useState<boolean>(false);
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [bannerError, setBannerError] = useState<string | null>(null);
  const [bannerInfo, setBannerInfo] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);
  const analysisEpoch = useRef(0);
  const scene = history.present;
  const sceneRef = useRef(scene);
  sceneRef.current = scene;

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch((err) => {
        setBannerError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
    };
  }, []);

  const clearAnalysisOverlays = useCallback(() => {
    analysisEpoch.current += 1;
    setSolveResult(null);
    setOptimizeResult(null);
    setValidation(null);
  }, []);

  const applyNewAuthoritativeScene = useCallback(
    (loaded: RoomSceneV1, infoMsg?: string) => {
      const sceneUrl=new URL(window.location.href);sceneUrl.searchParams.set('scene',loaded.scene_id);window.history.replaceState(null,'',sceneUrl);
      try { localStorage.setItem('roomlab:last-scene', loaded.scene_id); } catch { /* Storage can be unavailable. */ }
      setHistory((prev) => loadAuthoritativeScene(prev, loaded));
      clearAnalysisOverlays();
      if (infoMsg) setBannerInfo(infoMsg);
    },
    [clearAnalysisOverlays],
  );

  useEffect(() => {
    let cancelled = false;
    let id: string | null = new URLSearchParams(window.location.search).get('scene');
    try { id = id || localStorage.getItem('roomlab:last-scene'); } catch { /* Server persistence still works. */ }
    if (id) {
      getScene(id).then(async (loaded) => {
        if (cancelled) return;
        applyNewAuthoritativeScene(loaded, 'Restored your last saved scene. Unsaved edits are not persisted.');
        const mediaId = loaded.evidence_frames?.[0]?.media_id;
        if (mediaId) {
          try { const restored = await getMedia(mediaId); if (!cancelled) setMedia(restored); } catch { /* Imported scene can lack local media. */ }
        }
      }).catch(() => { if (!cancelled) setBannerInfo('Previous scene is unavailable. Upload a video or import saved JSON.'); });
    }
    return () => { cancelled = true; };
  }, [applyNewAuthoritativeScene]);

  // Poll active extraction job
  useEffect(() => {
    if (!job || (job.status !== 'queued' && job.status !== 'running')) {
      setIsExtracting(false);
      return;
    }
    setIsExtracting(true);
    let cancelled = false;

    const tick = async () => {
      try {
        const nextJob = await getJob(job.job_id);
        if (cancelled) return;
        if (nextJob.status === 'completed' && nextJob.scene_id) {
          setIsExtracting(false);
          const extractedScene = await getScene(nextJob.scene_id);
          if (!cancelled) {
            applyNewAuthoritativeScene(
              extractedScene,
              `Extracted estimated room '${extractedScene.name ?? extractedScene.scene_id}' (Rev ${
                extractedScene.scene_revision ?? 1
              }).`,
            );
            setJob(nextJob);
          }
        } else if (nextJob.status === 'failed' || nextJob.status === 'cancelled') {
          setJob(nextJob);
          setIsExtracting(false);
          if (nextJob.error) {
            setBannerError(nextJob.error);
          }
        } else {
          setJob(nextJob);
          pollTimerRef.current = window.setTimeout(tick, 900);
        }
      } catch (err) {
        if (!cancelled) {
          setIsExtracting(false);
          setBannerError(err instanceof Error ? err.message : String(err));
        }
      }
    };

    pollTimerRef.current = window.setTimeout(tick, 750);
    return () => {
      cancelled = true;
      if (pollTimerRef.current !== null) {
        window.clearTimeout(pollTimerRef.current);
      }
    };
  }, [job?.job_id, job?.status, applyNewAuthoritativeScene]);

  const handleSelectVideoFile = async (file: File) => {
    setBannerError(null);
    setBannerInfo(null);
    setIsUploading(true);
    try {
      const record = await uploadVideo(file);
      setMedia(record);
      setJob(null);
      setBannerInfo(`Uploaded '${record.filename}' (${record.duration_s.toFixed(1)}s, ${record.frames.length} keyframes).`);
    } catch (err) {
      setBannerError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleUseSampleVideo = async () => {
    if (!config?.sample_video_url) return;
    setBannerError(null);
    setBannerInfo(null);
    setIsUploading(true);
    try {
      const resp = await fetch(config.sample_video_url);
      if (!resp.ok) throw new Error(`Failed to fetch sample video (${resp.status})`);
      const blob = await resp.blob();
      const sampleFile = new File([blob], 'synthetic_room_sample.mp4', { type: 'video/mp4' });
      const record = await uploadVideo(sampleFile);
      setMedia(record);
      setJob(null);
      setBannerInfo(
        `Loaded synthetic sample clip (${record.duration_s.toFixed(1)}s, ${record.frames.length} frames). Click 'Extract Editable 3D Room' to run live Gemini extraction.`,
      );
    } catch (err) {
      setBannerError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleExtractRoom = async () => {
    if (!media) return;
    setBannerError(null);
    setBannerInfo(null);
    setIsExtracting(true);
    try {
      const startedJob = await extractRoom(media.media_id);
      setJob(startedJob);
    } catch (err) {
      setIsExtracting(false);
      setBannerError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleCancelJob = async () => {
    if (!job) return;
    try {
      const updated = await cancelJob(job.job_id);
      setJob(updated);
      setIsExtracting(false);
    } catch (err) {
      setBannerError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleSaveScene = async () => {
    if (!scene || !history.authoritative) return;
    setBannerError(null);
    setBannerInfo(null);
    setIsSaving(true);
    try {
      const expected = history.authoritative.scene_revision ?? scene.scene_revision ?? 1;
      const saved = await saveScene(scene.scene_id, {
        expected_revision: expected,
        scene,
      });
      if (sceneRef.current !== scene && sceneRef.current?.scene_id === scene.scene_id) {
        setHistory((prev) => ({ ...prev, authoritative: saved,
          present: prev.present ? { ...prev.present, scene_revision: saved.scene_revision } : saved, dirty: true }));
        clearAnalysisOverlays();
        setBannerInfo(`Saved revision ${saved.scene_revision}; newer local edits are preserved and still unsaved.`);
      } else if (sceneRef.current?.scene_id === scene.scene_id) {
        applyNewAuthoritativeScene(saved, `Saved revision ${saved.scene_revision}.`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setBannerError(
        `Save conflict or validation failure: ${msg}. Your local edits remain preserved in the editor so you can adjust or export them.`,
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleExportJson = () => {
    if (!scene) return;
    const blob = new Blob([JSON.stringify(scene, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${scene.scene_id}-rev${scene.scene_revision ?? 1}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleImportJsonFile = async (file: File) => {
    setBannerError(null);
    setBannerInfo(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text) as RoomSceneV1;
      const imported = await importScene(parsed);
      applyNewAuthoritativeScene(
        imported,
        `Imported scene '${imported.name ?? imported.scene_id}' as ${imported.scene_id} (Rev ${imported.scene_revision}).`,
      );
    } catch (err) {
      setBannerError(`Import failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleCalibrate = async (req: CalibrateRequest) => {
    if (!scene) return;
    setBannerError(null);
    setBannerInfo(null);
    setIsCalibrating(true);
    try {
      const calibrated = await calibrateScene(scene.scene_id, req);
      applyNewAuthoritativeScene(
        calibrated,
        `Calibrated metric scale ×${calibrated.calibration?.scale_factor.toFixed(3)} using ${req.anchor_id} (${req.dimension}=${req.measured_m}m).`,
      );
    } catch (err) {
      setBannerError(`Calibration failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsCalibrating(false);
    }
  };

  const handleValidateScene = async () => {
    if (!scene) return;
    if (history.dirty) { setBannerError('Save your local edits before checking server geometry.'); return; }
    const epoch = analysisEpoch.current;
    setBannerError(null);
    setIsValidating(true);
    try {
      const report = await validateScene(scene.scene_id);
      if (epoch === analysisEpoch.current) setValidation(report);
    } catch (err) {
      setBannerError(`Validation failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsValidating(false);
    }
  };

  const handleRunSolve = async (req: SolveRequest) => {
    if (!scene) return;
    if (history.dirty) return;
    const epoch = analysisEpoch.current;
    setBannerError(null);
    setIsSolving(true);
    try {
      const res = await solveScene(scene.scene_id, req);
      if (epoch === analysisEpoch.current) setSolveResult(res);
    } catch (err) {
      setBannerError(`Reachability check failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsSolving(false);
    }
  };

  const handleRunOptimize = async (req: SolveRequest) => {
    if (!scene) return;
    if (history.dirty) return;
    const epoch = analysisEpoch.current;
    setBannerError(null);
    setIsOptimizing(true);
    try {
      const res = await optimizeScene(scene.scene_id, req);
      if (epoch === analysisEpoch.current) setOptimizeResult(res);
    } catch (err) {
      setBannerError(`Layout search failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleUpdateObject = useCallback(
    (objectId: string, updater: (obj: RoomObject) => RoomObject) => {
      setHistory((prev) => {
        if (!prev.present) return prev;
        return pushSceneEdit(prev, updateObjectInScene(prev.present, objectId, updater));
      });
      clearAnalysisOverlays();
    },
    [clearAnalysisOverlays],
  );

  const handleMoveObject = useCallback(
    (objectId: string, newCenter: [number, number]) => {
      handleUpdateObject(objectId, (o) => ({ ...o, center: [newCenter[0], newCenter[1]] }));
    },
    [handleUpdateObject],
  );

  const handleAddObject = useCallback(
    (category: string) => {
      setHistory((prev) => {
        if (!prev.present) return prev;
        const { scene: nextScene, newId } = addObjectToScene(prev.present, category);
        setSelectedTarget({ kind: 'object', id: newId });
        return pushSceneEdit(prev, nextScene);
      });
      clearAnalysisOverlays();
    },
    [clearAnalysisOverlays],
  );

  const handleDeleteObject = useCallback(
    (objectId: string) => {
      setHistory((prev) => {
        if (!prev.present) return prev;
        return pushSceneEdit(prev, removeObjectFromScene(prev.present, objectId));
      });
      setSelectedTarget(null);
      clearAnalysisOverlays();
    },
    [clearAnalysisOverlays],
  );

  const selectedEvidenceFrameIds = useMemo(() => {
    if (!scene || !selectedTarget) return [];
    if(selectedTarget.kind==='void')return scene.floor_voids?.find(v=>v.id===selectedTarget.id)?.provenance?.evidence_frame_ids??[];
    if (selectedTarget.kind === 'object') {
      const obj = (scene.objects ?? []).find((o) => o.id === selectedTarget.id);
      return obj?.provenance?.evidence_frame_ids ?? [];
    }
    if (selectedTarget.kind === 'wall') {
      const wall = deriveWallsFromFloor(scene).find((w) => w.id === selectedTarget.id);
      return wall?.provenance?.evidence_frame_ids ?? [];
    }
    if (selectedTarget.kind === 'opening') {
      const op = (scene.openings ?? []).find((o) => o.id === selectedTarget.id);
      return op?.provenance?.evidence_frame_ids ?? [];
    }
    return [];
  }, [scene, selectedTarget]);

  return (
    <div className="rl-workspace">
      <RoomToolbar
        config={config}
        sceneName={scene?.name ?? ''}
        sceneRevision={scene?.scene_revision ?? null}
        geometrySource={scene?.geometry_source ?? null}
        isConfigured={Boolean(config?.gemini_configured)}
        dirty={history.dirty}
        canUndo={history.past.length > 0}
        canRedo={history.future.length > 0}
        isUploading={isUploading}
        isExtracting={isExtracting}
        isSaving={isSaving}
        viewMode={viewMode}
        showCSpace={showCSpace}
        onSelectVideoFile={handleSelectVideoFile}
        onUseSampleVideo={handleUseSampleVideo}
        onUndo={() => {
          setHistory(undoSceneEdit);
          clearAnalysisOverlays();
        }}
        onRedo={() => {
          setHistory(redoSceneEdit);
          clearAnalysisOverlays();
        }}
        onDiscardEdits={() => {
          setHistory(discardUnsavedEdits);
          clearAnalysisOverlays();
        }}
        onSaveScene={handleSaveScene}
        onExportJson={handleExportJson}
        onImportJsonFile={handleImportJsonFile}
        onAddObject={handleAddObject}
        onChangeViewMode={setViewMode}
        onToggleCSpace={() => setShowCSpace((v) => !v)}
      />

      {bannerError && (
        <div className="rl-alert rl-alert--error" role="alert">
          <span>{bannerError}</span>
          <button type="button" onClick={() => setBannerError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {bannerInfo && (
        <div className="rl-alert rl-alert--info" role="status">
          <span>{bannerInfo}</span>
          <button type="button" onClick={() => setBannerInfo(null)}>
            Dismiss
          </button>
        </div>
      )}

      <main className="rl-main-grid">
        <aside className="rl-sidebar rl-sidebar--left">
          <RoomEvidencePanel
            media={media}
            job={job}
            scene={scene}
            selectedFrameIds={selectedEvidenceFrameIds}
            activeFrameId={activeFrameId}
            isExtracting={isExtracting}
            onSelectFrame={setActiveFrameId}
            onExtractRoom={handleExtractRoom}
            onCancelJob={handleCancelJob}
          />
          <CalibrationPanel
            scene={scene}
            selectedTarget={selectedTarget}
            dirty={history.dirty}
            isCalibrating={isCalibrating}
            onCalibrate={handleCalibrate}
          />
        </aside>

        <section className="rl-center-stage" aria-label="3D Room Viewport">
          <RoomCanvas3D
            scene={scene}
            selectedTarget={selectedTarget}
            viewMode={viewMode}
            showCSpace={showCSpace}
            startPoint={startPoint}
            goalPoint={goalPoint}
            agentDiameterM={agentDiameterM}
            marginM={marginM}
            solveResult={solveResult}
            pickEndpointMode={pickEndpointMode}
            onSelectTarget={setSelectedTarget}
            onMoveObject={handleMoveObject}
            onPickEndpoint={(pt) => {
              if (pickEndpointMode === 'start') setStartPoint(pt);
              else if (pickEndpointMode === 'goal') setGoalPoint(pt);
              setPickEndpointMode(null);
              clearAnalysisOverlays();
            }}
          />
        </section>

        <aside className="rl-sidebar rl-sidebar--right">
          <RoomEditor
            scene={scene}
            dirty={history.dirty}
            selectedTarget={selectedTarget}
            validation={validation}
            isValidating={isValidating}
            onSelectTarget={setSelectedTarget}
            onUpdateObject={handleUpdateObject}
            onDeleteObject={handleDeleteObject}
            onUpdateScene={(next) => {setHistory(prev=>pushSceneEdit(prev,next));clearAnalysisOverlays();}}
            onValidateScene={handleValidateScene}
          />
          <ClearancePanel
            scene={scene}
            dirty={history.dirty}
            startPoint={startPoint}
            goalPoint={goalPoint}
            agentDiameterM={agentDiameterM}
            marginM={marginM}
            solveResult={solveResult}
            optimizeResult={optimizeResult}
            isSolving={isSolving}
            isOptimizing={isOptimizing}
            pickEndpointMode={pickEndpointMode}
            onChangeStart={(pt) => {
              setStartPoint(pt);
              clearAnalysisOverlays();
            }}
            onChangeGoal={(pt) => {
              setGoalPoint(pt);
              clearAnalysisOverlays();
            }}
            onChangeAgentDiameter={(d) => {
              setAgentDiameterM(d);
              clearAnalysisOverlays();
            }}
            onChangeMargin={(m) => {
              setMarginM(m);
              clearAnalysisOverlays();
            }}
            onTogglePickEndpoint={setPickEndpointMode}
            onRunSolve={handleRunSolve}
            onRunOptimize={handleRunOptimize}
            onApplyOptimizedScene={(candidateScene) => {
              setHistory((prev) => pushSceneEdit(prev, candidateScene));
              clearAnalysisOverlays();
              setBannerInfo(
                'Staged candidate layout change locally. Click "Save Revision" to commit and re-verify.',
              );
            }}
          />
        </aside>
      </main>
    </div>
  );
}
