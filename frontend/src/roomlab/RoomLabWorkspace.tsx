import { Film, Layers3, Ruler, Route } from "lucide-react";
import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  calibrateScene,
  cancelJob,
  extractRoom,
  getConfig,
  proposeOverlapRepair,
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
} from "./api";
import type {
  CalibrateRequest,
  JobRecord,
  MediaRecord,
  OptimizeResult,
  RoomObject,
  RoomSceneV1,
  RoomSubmission,
  SolveRequest,
  SolveResult,
  ValidationReport,
} from "./contracts.generated";
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
} from "./editorState";
import { GeometryCapturePanel, type GeometryPreview } from "./GeometryCapturePanel";
import { GeometryCloud } from "./GeometryCloud";
import { MyRooms } from "./MyRooms";
import { OverlapRepairPanel } from "./OverlapRepairPanel";
import { AccuracyPanel } from "./AccuracyPanel";
import { VisualReviewPanel } from "./VisualReviewPanel";
import type { RepairResult } from "./contracts.generated";
import { RoomToolbar, RoomCanvasTools } from "./RoomToolbar";
import { RoomCanvas3D } from "./RoomCanvas3D";
import { RoomEvidencePanel } from "./RoomEvidencePanel";
import { CalibrationPanel } from "./CalibrationPanel";
import { RoomEditor } from "./RoomEditor";
import { ClearancePanel } from "./ClearancePanel";
import "./roomlab.css";

export default function RoomLabWorkspace() {
  const [config, setConfig] = useState<Config | null>(null);
  const [media, setMedia] = useState<MediaRecord | null>(null);
  const [job, setJob] = useState<JobRecord | null>(null);
  const [history, setHistory] = useState<HistoryState>(() =>
    createInitialHistory(null),
  );

  const [geometryPreview, setGeometryPreview] = useState<GeometryPreview | null>(null);
  const [geometrySelected, setGeometrySelected] = useState<number[]>([]);
  const showGeometry = useCallback((value: GeometryPreview | null) => { setGeometryPreview(value); setGeometrySelected([]); }, []);
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [openingRoom, setOpeningRoom] = useState(false);
  const [startingRoom, setStartingRoom] = useState(false);
  const navigationEpoch = useRef(0);
  const followJob = useRef<{ id: string; epoch: number } | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<SelectionTarget>(null);
  const [activeFrameId, setActiveFrameId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("orbit");
  const [showCSpace, setShowCSpace] = useState<boolean>(false);
  const [sidebarTab, setSidebarTab] = useState<
    "source" | "scene" | "scale" | "analysis"
  >("source");
  const selectTarget = useCallback((target: SelectionTarget) => {
    setSelectedTarget(target);
    if (target) {
      setSidebarTab("scene");
      setLibraryOpen(false);
    }
  }, []);

  const [startPoint, setStartPoint] = useState<[number, number]>([-1.5, -1.0]);
  const [goalPoint, setGoalPoint] = useState<[number, number]>([1.5, 1.0]);
  const [agentDiameterM, setAgentDiameterM] = useState<number>(0.65);
  const [marginM, setMarginM] = useState<number>(0.02);
  const [pickEndpointMode, setPickEndpointMode] = useState<
    "start" | "goal" | null
  >(null);

  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [solveResult, setSolveResult] = useState<SolveResult | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<OptimizeResult | null>(
    null,
  );

  const [repairResult, setRepairResult] = useState<RepairResult | null>(null);
  const [isRepairing, setRepairing] = useState(false);

  const [extractionQuality, setExtractionQuality] = useState<"balanced" | "high">("high");
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
  useEffect(() => { showGeometry(null); }, [scene?.scene_id, showGeometry]);
  useEffect(() => {
    if (!scene || !selectedTarget) return;
    const items =
      selectedTarget.kind === "object"
        ? scene.objects
        : selectedTarget.kind === "wall"
          ? scene.walls
          : selectedTarget.kind === "opening"
            ? scene.openings
            : scene.floor_voids;
    if (!items?.some((item) => item.id === selectedTarget.id))
      setSelectedTarget(null);
  }, [scene, selectedTarget]);
  const historyRef = useRef(history);
  historyRef.current = history;
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
    setRepairResult(null);
    setValidation(null);
  }, []);

  const applyNewAuthoritativeScene = useCallback(
    (loaded: RoomSceneV1, infoMsg?: string) => {
      const sceneUrl = new URL(window.location.href);
      sceneUrl.searchParams.set("scene", loaded.scene_id);
      window.history.replaceState(null, "", sceneUrl);
      try {
        localStorage.setItem("roomlab:last-scene", loaded.scene_id);
      } catch {
        /* Storage can be unavailable. */
      }
      setHistory((prev) => loadAuthoritativeScene(prev, loaded));
      clearAnalysisOverlays();
      if (infoMsg) setBannerInfo(infoMsg);
    },
    [clearAnalysisOverlays],
  );

  useEffect(() => {
    let cancelled = false;
    let id: string | null = new URLSearchParams(window.location.search).get(
      "scene",
    );
    try {
      id = id || localStorage.getItem("roomlab:last-scene");
    } catch {
      /* Server persistence still works. */
    }
    if (id) {
      getScene(id)
        .then(async (loaded) => {
          if (cancelled) return;
          applyNewAuthoritativeScene(
            loaded,
            "Restored your last saved scene. Unsaved edits are not persisted.",
          );
          const mediaId = loaded.evidence_frames?.[0]?.media_id;
          if (mediaId) {
            try {
              const restored = await getMedia(mediaId);
              if (!cancelled) setMedia(restored);
            } catch {
              /* Imported scene can lack local media. */
            }
          }
        })
        .catch(() => {
          if (!cancelled)
            setBannerInfo(
              "Previous scene is unavailable. Upload a video or import saved JSON.",
            );
        });
    }
    return () => {
      cancelled = true;
    };
  }, [applyNewAuthoritativeScene]);

  // Poll active extraction job
  useEffect(() => {
    if (!job || (job.status !== "queued" && job.status !== "running")) {
      setIsExtracting(false);
      return;
    }
    setIsExtracting(true);
    let cancelled = false;

    const tick = async () => {
      try {
        const nextJob = await getJob(job.job_id);
        if (cancelled) return;
        if (nextJob.status === "completed" && nextJob.scene_id) {
          setIsExtracting(false);
          const extractedScene = await getScene(nextJob.scene_id);
          if (!cancelled) {
            if (
              !historyRef.current.dirty &&
              followJob.current?.id === nextJob.job_id &&
              followJob.current.epoch === navigationEpoch.current
            ) {
              applyNewAuthoritativeScene(
                extractedScene,
                `Your room is ready: ${extractedScene.name}.`,
              );
            } else
              setBannerInfo(
                "Your new room is ready in My rooms. Your current view and edits were preserved.",
              );
            setJob(nextJob);
          }
        } else if (
          nextJob.status === "failed" ||
          nextJob.status === "cancelled"
        ) {
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

  const requireCleanRoom = () => {
    if (!historyRef.current.dirty) return true;
    setLibraryOpen(false);
    setSidebarTab("scene");
    setBannerError(
      "Save or discard your current edits before opening another walkthrough. Your edits are preserved.",
    );
    return false;
  };
  const openLibraryRoom = async (
    entry: RoomSubmission,
    requestedSceneId?: string,
  ) => {
    if (!requireCleanRoom()) return;
    const token = ++navigationEpoch.current;
    setOpeningRoom(true);
    setBannerError(null);
    try {
      const id = requestedSceneId ?? entry.scene_id;
      const [loaded, restoredMedia] = await Promise.all([
        id ? getScene(id) : Promise.resolve(null),
        entry.media_id
          ? getMedia(entry.media_id).catch(() => null)
          : Promise.resolve(null),
      ]);
      if (token !== navigationEpoch.current || !requireCleanRoom()) return;
      setSelectedTarget(null);
      setActiveFrameId(null);
      setMedia(restoredMedia);
      setJob(null);
      followJob.current = null;
      if (loaded) applyNewAuthoritativeScene(loaded);
      else {
        if (entry.job_id && entry.status === "processing") {
          const current = await getJob(entry.job_id);
          if (token !== navigationEpoch.current) return;
          followJob.current = { id: current.job_id, epoch: token };
          setJob(current);
        }
        setLibraryOpen(false);
        setSidebarTab("source");
      }
    } catch (e) {
      setBannerError(
        e instanceof Error ? e.message : "Could not open this room.",
      );
    } finally {
      setOpeningRoom(false);
    }
  };
  const buildLibraryRoom = async (entry: RoomSubmission) => {
    if (!entry.media_id || !requireCleanRoom()) return;
    const token = ++navigationEpoch.current;
    setStartingRoom(true);
    setBannerError(null);
    try {
      const record = await getMedia(entry.media_id);
      const started = await extractRoom(entry.media_id, extractionQuality);
      if (token !== navigationEpoch.current) return;
      setMedia(record);
      followJob.current = { id: started.job_id, epoch: token };
      setJob(started);
    } catch (e) {
      setBannerError(
        e instanceof Error ? e.message : "Could not start room building.",
      );
    } finally {
      setStartingRoom(false);
    }
  };
  const uploadFromLibrary = (file: File) => {
    if (!requireCleanRoom()) return;
    navigationEpoch.current++;
    setLibraryOpen(false);
    setSidebarTab("source");
    void handleSelectVideoFile(file);
  };

  const handleSelectVideoFile = async (file: File) => {
    setBannerError(null);
    setBannerInfo(null);
    setIsUploading(true);
    try {
      const record = await uploadVideo(file);
      setMedia(record);
      setJob(null);
      setBannerInfo(
        `Uploaded '${record.filename}' (${record.duration_s.toFixed(1)}s, ${record.frames.length} keyframes).`,
      );
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
      if (!resp.ok)
        throw new Error(`Failed to fetch sample video (${resp.status})`);
      const blob = await resp.blob();
      const sampleFile = new File([blob], "synthetic_room_sample.mp4", {
        type: "video/mp4",
      });
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
      const startedJob = await extractRoom(media.media_id, extractionQuality);
      followJob.current = {
        id: startedJob.job_id,
        epoch: navigationEpoch.current,
      };
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
      const expected =
        history.authoritative.scene_revision ?? scene.scene_revision ?? 1;
      const saved = await saveScene(scene.scene_id, {
        expected_revision: expected,
        scene,
      });
      if (
        sceneRef.current !== scene &&
        sceneRef.current?.scene_id === scene.scene_id
      ) {
        setHistory((prev) => ({
          ...prev,
          authoritative: saved,
          present: prev.present
            ? { ...prev.present, scene_revision: saved.scene_revision }
            : saved,
          dirty: true,
        }));
        clearAnalysisOverlays();
        setBannerInfo(
          `Saved revision ${saved.scene_revision}; newer local edits are preserved and still unsaved.`,
        );
      } else if (sceneRef.current?.scene_id === scene.scene_id) {
        applyNewAuthoritativeScene(
          saved,
          `Saved revision ${saved.scene_revision}.`,
        );
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
    const blob = new Blob([JSON.stringify(scene, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
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
      setBannerError(
        `Import failed: ${err instanceof Error ? err.message : String(err)}`,
      );
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
      setBannerError(
        `Calibration failed: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setIsCalibrating(false);
    }
  };

  const handleValidateScene = async () => {
    if (!scene) return;
    if (history.dirty) {
      setBannerError("Save your local edits before checking server geometry.");
      return;
    }
    const epoch = analysisEpoch.current;
    setBannerError(null);
    setIsValidating(true);
    try {
      const report = await validateScene(scene.scene_id);
      if (epoch === analysisEpoch.current) setValidation(report);
    } catch (err) {
      setBannerError(
        `Validation failed: ${err instanceof Error ? err.message : String(err)}`,
      );
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
      setBannerError(
        `Reachability check failed: ${err instanceof Error ? err.message : String(err)}`,
      );
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
    setRepairResult(null);
    try {
      const res = await optimizeScene(scene.scene_id, req);
      if (epoch === analysisEpoch.current) setOptimizeResult(res);
    } catch (err) {
      setBannerError(
        `Layout search failed: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRepair = async (max: number) => {
    if (!scene || history.dirty) return;
    const epoch = analysisEpoch.current;
    setRepairing(true);
    setBannerError(null);
    setOptimizeResult(null);
    try {
      const result = await proposeOverlapRepair(scene.scene_id, {
        expected_revision: scene.scene_revision ?? 1,
        max_displacement_m: max,
      });
      if (epoch === analysisEpoch.current) setRepairResult(result);
    } catch (e) {
      if (epoch === analysisEpoch.current)
        setBannerError(e instanceof Error ? e.message : String(e));
    } finally {
      setRepairing(false);
    }
  };
  const applyCandidate = (next: RoomSceneV1) => {
    setHistory((prev) => pushSceneEdit(prev, next));
    clearAnalysisOverlays();
    setBannerInfo(
      "Staged a proposed layout. Save changes, then check geometry and reachability again.",
    );
  };
  const handleUpdateObject = useCallback(
    (objectId: string, updater: (obj: RoomObject) => RoomObject) => {
      setHistory((prev) => {
        if (!prev.present) return prev;
        return pushSceneEdit(
          prev,
          updateObjectInScene(prev.present, objectId, updater),
        );
      });
      clearAnalysisOverlays();
    },
    [clearAnalysisOverlays],
  );

  const handleAddObject = useCallback(
    (category: string) => {
      setLibraryOpen(false);
      setSidebarTab("scene");
      setHistory((prev) => {
        if (!prev.present) return prev;
        const { scene: nextScene, newId } = addObjectToScene(
          prev.present,
          category,
        );
        setSelectedTarget({ kind: "object", id: newId });
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
        return pushSceneEdit(
          prev,
          removeObjectFromScene(prev.present, objectId),
        );
      });
      setSelectedTarget(null);
      clearAnalysisOverlays();
    },
    [clearAnalysisOverlays],
  );

  const selectedEvidenceFrameIds = useMemo(() => {
    if (!scene || !selectedTarget) return [];
    if (selectedTarget.kind === "void")
      return (
        scene.floor_voids?.find((v) => v.id === selectedTarget.id)?.provenance
          ?.evidence_frame_ids ?? []
      );
    if (selectedTarget.kind === "object") {
      const obj = (scene.objects ?? []).find((o) => o.id === selectedTarget.id);
      return obj?.provenance?.evidence_frame_ids ?? [];
    }
    if (selectedTarget.kind === "wall") {
      const wall = deriveWallsFromFloor(scene).find(
        (w) => w.id === selectedTarget.id,
      );
      return wall?.provenance?.evidence_frame_ids ?? [];
    }
    if (selectedTarget.kind === "opening") {
      const op = (scene.openings ?? []).find((o) => o.id === selectedTarget.id);
      return op?.provenance?.evidence_frame_ids ?? [];
    }
    return [];
  }, [scene, selectedTarget]);

  return (
    <div className="rl-workspace">
      {bannerError && (
        <div className="rl-alert rl-alert--error" role="alert">
          <span>{bannerError}</span>
          <button type="button" onClick={() => setBannerError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {bannerInfo && (
        <div key={bannerInfo} className="rl-alert rl-alert--info" role="status">
          <span>{bannerInfo}</span>
          <button type="button" onClick={() => setBannerInfo(null)}>
            Dismiss
          </button>
        </div>
      )}

      <main className="rl-main-grid">
        <aside className="rl-sidebar" aria-label="Room workspace">
          {libraryOpen && (
            <MyRooms
              sceneId={scene?.scene_id ?? null}
              refreshToken={`${scene?.scene_id}:${scene?.scene_revision}:${media?.media_id}:${job?.job_id}:${job?.status}`}
              busy={isUploading || openingRoom || startingRoom}
              onOpen={openLibraryRoom}
              onBuild={buildLibraryRoom}
              onUpload={uploadFromLibrary}
              onBack={() => {
                navigationEpoch.current++;
                setLibraryOpen(false);
              }}
            />
          )}
          <div className="rl-editor-panel" hidden={libraryOpen}>
            <RoomToolbar
              onOpenRooms={() => setLibraryOpen(true)}
              config={config}
              sceneName={scene?.name ?? ""}
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
              onInspect={() => {
                setLibraryOpen(false);
                setSidebarTab("scene");
              }}
              onSelectVideoFile={(file) => {
                if (!requireCleanRoom()) return;
                navigationEpoch.current++;
                setSidebarTab("source");
                handleSelectVideoFile(file);
              }}
              onUseSampleVideo={() => {
                setSidebarTab("source");
                handleUseSampleVideo();
              }}
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
            <nav
              className="rl-tabs"
              aria-label="Workspace sections"
              role="tablist"
              onKeyDown={(e) => {
                const keys = ["source", "scene", "scale", "analysis"] as const;
                let i = keys.indexOf(sidebarTab);
                if (e.key === "ArrowRight") i = (i + 1) % 4;
                else if (e.key === "ArrowLeft") i = (i + 3) % 4;
                else if (e.key === "Home") i = 0;
                else if (e.key === "End") i = 3;
                else return;
                e.preventDefault();
                setSidebarTab(keys[i]);
                document.getElementById("tab-" + keys[i])?.focus();
              }}
            >
              {(
                [
                  { id: "source", label: "Source", icon: Film },
                  { id: "scene", label: "Objects", icon: Layers3 },
                  { id: "scale", label: "Scale", icon: Ruler },
                  { id: "analysis", label: "Analysis", icon: Route },
                ] as const
              ).map((t) => (
                <button
                  key={t.id}
                  id={"tab-" + t.id}
                  role="tab"
                  tabIndex={sidebarTab === t.id ? 0 : -1}
                  aria-selected={sidebarTab === t.id}
                  aria-controls={"panel-" + t.id}
                  onClick={() => setSidebarTab(t.id)}
                >
                  <t.icon size={15} />
                  {t.label}
                </button>
              ))}
            </nav>
            <div className="rl-sidebar-content">
              <div
                id="panel-source"
                role="tabpanel"
                aria-labelledby="tab-source"
                hidden={sidebarTab !== "source"}
              >
                <label className="rl-field">
                  <span>Reconstruction quality</span>
                  <select value={extractionQuality} disabled={isExtracting}
                    onChange={e => setExtractionQuality(e.target.value as "high" | "balanced")}>
                    <option value="high">Detailed · quality sampling, camera tracking &amp; reinspection</option>
                    <option value="balanced">Quick · estimated layout</option>
                  </select>
                  <small>Detailed takes longer. Tracking can fail on glass, blur or stationary pans; measurements still establish scale.</small>
                </label>
                <details className="rl-notes-box">
                  <summary>Record a better walkthrough</summary>
                  <p>Walk slowly with overlapping views. Move around furniture rather than only turning in place. Show both sides of doors and glass, the foot and top of stairs, and revisit your starting view. Keep lighting steady and avoid zooming.</p>
                  <p>Measure one reference to set scale, then different dimensions and object separations to check accuracy. A longer recording helps when it adds new viewpoints.</p>
                </details>
                <GeometryCapturePanel media={media} scene={scene} onSelectPoints={setGeometrySelected} dirty={history.dirty} selected={geometrySelected} preview={geometryPreview} onPreview={showGeometry} onScene={value => { if (requireCleanRoom()) applyNewAuthoritativeScene(value, "Imported geometry proposal; review dimensions and topology."); }} />
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
              </div>
              <div
                id="panel-scene"
                role="tabpanel"
                aria-labelledby="tab-scene"
                hidden={sidebarTab !== "scene"}
              >
                {!scene && (
                  <p className="rl-empty-card">
                    Your objects will appear here after you create a room.
                  </p>
                )}
                <RoomEditor
                  scene={scene}
                  dirty={history.dirty}
                  selectedTarget={selectedTarget}
                  validation={validation}
                  isValidating={isValidating}
                  onSelectTarget={selectTarget}
                  onUpdateObject={handleUpdateObject}
                  onDeleteObject={handleDeleteObject}
                  onUpdateScene={(next) => {
                    setHistory((prev) => pushSceneEdit(prev, next));
                    clearAnalysisOverlays();
                  }}
                  onValidateScene={handleValidateScene}
                />
              </div>
              <div
                id="panel-scale"
                role="tabpanel"
                aria-labelledby="tab-scale"
                hidden={sidebarTab !== "scale"}
              >
                {!scene && (
                  <p className="rl-empty-card">
                    Create a room, then add a real measurement to set its scale.
                  </p>
                )}
                <CalibrationPanel
                  scene={scene}
                  selectedTarget={selectedTarget}
                  dirty={history.dirty}
                  isCalibrating={isCalibrating}
                  onCalibrate={handleCalibrate}
                />
              </div>
              <div
                id="panel-analysis"
                role="tabpanel"
                aria-labelledby="tab-analysis"
                hidden={sidebarTab !== "analysis"}
              >
                {!scene && (
                  <p className="rl-empty-card">
                    Create a room and set the scale to explore paths and
                    clearance.
                  </p>
                )}
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
                <OverlapRepairPanel
                  scene={scene}
                  dirty={history.dirty}
                  result={repairResult}
                  busy={isRepairing}
                  onRun={handleRepair}
                  onApply={applyCandidate}
                  onDiscard={() => setRepairResult(null)}
                />
                <AccuracyPanel scene={scene} dirty={history.dirty} />
                <VisualReviewPanel
                  scene={scene}
                  dirty={history.dirty}
                  onStartReview={() => {
                    setRepairResult(null);
                    setOptimizeResult(null);
                  }}
                  contextVersion={analysisEpoch.current}
                  request={
                    scene
                      ? {
                          expected_revision: scene.scene_revision ?? 1,
                          start: startPoint,
                          goal: goalPoint,
                          agent_diameter_m: agentDiameterM,
                          margin_m: marginM,
                        }
                      : null
                  }
                  focus={selectedTarget ? [selectedTarget.id] : []}
                  onFrame={(id) => {
                    setActiveFrameId(id);
                    setSidebarTab("source");
                  }}
                />
              </div>
            </div>
            <div className="rl-sidebar-footer">
              <span className="rl-status-dot" />
              <span>
                {isExtracting
                  ? "Building your room…"
                  : scene
                    ? "Evidence-linked · editable"
                    : "Ready for your walkthrough"}
              </span>
              <span>
                {scene?.scene_revision ? "v" + scene.scene_revision : ""}
              </span>
            </div>
          </div>
        </aside>
        <section className="rl-center-stage" aria-label="3D Room Viewport">
          <RoomCanvasTools
            viewMode={viewMode}
            showCSpace={showCSpace}
            sceneRevision={scene?.scene_revision ?? null}
            onInspect={() => {
              setLibraryOpen(false);
              setSidebarTab("scene");
            }}
            onChangeViewMode={setViewMode}
            onToggleCSpace={() => setShowCSpace((v) => !v)}
            onAddObject={handleAddObject}
            canUndo={history.past.length > 0}
            canRedo={history.future.length > 0}
            onUndo={() => {
              setHistory(undoSceneEdit);
              clearAnalysisOverlays();
            }}
            onRedo={() => {
              setHistory(redoSceneEdit);
              clearAnalysisOverlays();
            }}
          />
          <div className="rl-stage-caption">
            <span className="rl-status-dot" />
            <span className="rl-canvas-title">{scene?.name ?? "A little room for possibility"}</span>
            <span>
              {scene
                ? history.dirty
                  ? "Unsaved changes"
                  : "Saved"
                : "3D workspace"}
            </span>
          </div>
          <RoomCanvas3D
            scene={scene}
            selectedTarget={selectedTarget}
            viewMode={viewMode}
            showCSpace={showCSpace}
            showEndpoints={sidebarTab === "analysis" || showCSpace}
            candidateScene={
              optimizeResult?.scene ?? repairResult?.scene ?? null
            }
            onTransformObject={(id, center, yaw) =>
              handleUpdateObject(id, (o) => ({ ...o, center, yaw_deg: yaw }))
            }
            startPoint={startPoint}
            goalPoint={goalPoint}
            agentDiameterM={agentDiameterM}
            marginM={marginM}
            solveResult={solveResult}
            pickEndpointMode={pickEndpointMode}
            onSelectTarget={selectTarget}
            onPickEndpoint={(pt) => {
              if (pickEndpointMode === "start") setStartPoint(pt);
              else if (pickEndpointMode === "goal") setGoalPoint(pt);
              setPickEndpointMode(null);
              clearAnalysisOverlays();
            }}
          />
          {geometryPreview && <GeometryCloud report={geometryPreview.report} selected={geometrySelected} onSelect={id => setGeometrySelected(old => old.includes(id) ? old.filter(i => i !== id) : [...old, id].slice(0,40))} onClose={() => showGeometry(null)} />}
          <div className="rl-stage-footer">
            <span>
              {scene
                ? "Estimated geometry" +
                  (scene.calibration
                    ? " · scale reference added"
                    : " · add a measurement to set scale")
                : "Up to 10 minutes · MP4, MOV or WebM"}
            </span>
            <span>Drag to orbit · scroll to zoom</span>
          </div>
        </section>
      </main>
    </div>
  );
}
