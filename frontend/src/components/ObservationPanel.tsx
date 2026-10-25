import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { Camera, Check, CircleAlert, Image, Layers2, LoaderCircle, ScanLine, Unplug, Upload, Video, X } from 'lucide-react';
import type { CaptureRequest, GroundingProposalV1, GroundingResult, RunContext, ThinkingLevel } from '../types';
import { canApplyGrounding } from '../ai/policy';
import { provenanceChip } from '../ai/stageView';
import { captureEvidence } from '../ai/evidence';
import { createRequestGate } from '../ai/requestGate';
import { DEMO_BOARD_SIZE, demoBoardCapture, demoBoardSvg } from '../ai/demoBoard';
import './ObservationPanel.css';

export type BoardView = 'live' | 'fallback' | 'none';
const CAMERA_WAIT_MS = 8000;
const CAMERA_KEY = 'spatialtwin.cameraId';

export interface ObservationPanelProps {
  proposal: GroundingProposalV1 | null;
  result: GroundingResult | null;
  currentContext?: RunContext;
  liveConfigured: boolean;
  fixturesEnabled: boolean;
  isLoading: boolean;
  isApplying: boolean;
  isProposalCurrent: boolean;
  availabilityMessage?: string;
  isAvailable?: boolean;
  appliedCaptureId?: string | null;
  error: string | null;
  onCapture: (capture: CaptureRequest) => Promise<void>;
  onApply: () => Promise<void>;
  onClearProposal?: () => void;
  /** Content of the Upload source (file picker). Selecting a file there starts its own capture. */
  uploadSlot?: ReactNode;
  /** Presenter-menu element that receives the source, target and thinking controls. */
  settingsSlot?: HTMLElement | null;
  /** An analysis is running: Read the board is locked and says why when tapped. */
  locked?: boolean;
  onLockedTap?: () => void;
  /** Seconds the last read took, for the provenance chip. */
  readSeconds?: number | null;
  onCameraLive?: (live: boolean) => void;
  /** What the board shows: the live camera, the labelled demo board or fixture, or nothing usable yet. */
  onBoardView?: (view: BoardView) => void;
  /** Physical hardware: the stage never falls back to the synthetic board on its own. */
  physical?: boolean;
  /** Changes on every workflow reset: the held still and local errors clear without restarting the camera. */
  resetKey?: number;
}

type FixtureTarget = 'P1' | 'P2' | 'B2';
type Source = 'demo' | 'fixture' | 'camera' | 'upload';
type CameraState = 'idle' | 'connecting' | 'connected' | 'error';

const fixtureNames: Record<FixtureTarget, string> = { P1: 'West passage', P2: 'East passage', B2: 'East boundary' };

/** An illustrative tabletop, deliberately separate from camera or detection evidence. */
function TabletopPreview({ target }: { target: FixtureTarget }) {
  // The same four illustrative zone polygons and target positions as SpatialViewport,
  // translated from venue/reviewed_venue.json. Projection has no metric authority.
  const point = (x: number, y: number, z = 0) => `${210 + x * .93 - y * .23},${46 + x * .075 + y * .45 - z * .8}`;
  const face = (x: number, y: number, w: number, d: number, z = 0) => [point(x, y, z), point(x + w, y, z), point(x + w, y + d, z), point(x, y + d, z)].join(' ');
  const walls = [
    [0, 0, 300, 5], [0, 0, 5, 200], [295, 0, 5, 200],
    [0, 195, 35, 5], [85, 195, 40, 5], [175, 195, 40, 5], [265, 195, 35, 5],
    [0, 220, 35, 5], [85, 220, 35, 5], [0, 220, 5, 150], [115, 220, 5, 150],
    [0, 365, 38, 5], [82, 365, 38, 5],
    [180, 220, 35, 5], [265, 220, 35, 5], [295, 220, 5, 150],
    [180, 220, 5, 46], [180, 294, 5, 76], [180, 365, 38, 5], [262, 365, 38, 5],
    [130, 210, 3, 120], [167, 210, 3, 56], [167, 294, 3, 36], [130, 327, 40, 3],
  ];
  const token = target === 'P1' ? [60, 210] : target === 'P2' ? [240, 210] : [240, 374];
  return (
    <svg className="board-image" viewBox="0 0 600 275" role="img" aria-label={`Illustrative tabletop with a red blockage cube at ${target}. This is a diagram, not a camera image.`}>
      <defs>
        <filter id="observation-board-shadow" x="-40%" y="-50%" width="180%" height="220%"><feGaussianBlur stdDeviation="10" /></filter>
        <pattern id="observation-table-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="#263739" strokeWidth=".7" /></pattern>
      </defs>
      <ellipse cx="302" cy="235" rx="216" ry="19" fill="#000" opacity=".5" filter="url(#observation-board-shadow)" />
      <polygon points={face(-15, -15, 330, 400, -8)} fill="#182325" stroke="#364345" />
      <polygon points={face(-15, -15, 330, 400)} fill="#263032" stroke="#58615b" strokeWidth="1.3" />
      <polygon points={face(0, 0, 300, 200)} fill="#444b3d" />
      <polygon points={face(0, 220, 120, 150)} fill="#343e37" />
      <polygon points={face(180, 220, 120, 150)} fill="#3d473a" />
      <polygon points={face(130, 210, 40, 120)} fill="#46503d" />
      <polygon points={face(-15, -15, 330, 400)} fill="url(#observation-table-grid)" opacity=".45" />
      <path d={`M${point(210, 150)} L${point(240, 180)} L${point(240, 210)} L${point(240, 355)}`} fill="none" stroke="#b7d68b" strokeWidth="2" strokeDasharray="5 6" opacity=".7" />
      <path d={`M${point(100, 150)} L${point(60, 180)} L${point(60, 210)} L${point(60, 355)}`} fill="none" stroke="#b7d68b" strokeWidth="2" strokeDasharray="5 6" opacity=".7" />
      {[[30, 110], [105, 110], [230, 110], [30, 35], [230, 35]].map(([x, y]) => <g key={`${x}-${y}`}><polygon points={face(x, y + 3, 30, 20)} fill="#202d29" /><polygon points={face(x, y, 30, 20, 7)} fill="#75806a" stroke="#92977f" strokeWidth=".6" /></g>)}
      {walls.map(([x, y, w, d], index) => <g key={index}><polygon points={[point(x, y + d), point(x + w, y + d), point(x + w, y + d, 19), point(x, y + d, 19)].join(' ')} fill="#636c5c" /><polygon points={[point(x + w, y), point(x + w, y + d), point(x + w, y + d, 19), point(x + w, y, 19)].join(' ')} fill="#78816e" /><polygon points={face(x, y, w, d, 19)} fill="#a5ac94" /></g>)}
      <g className="observation-board-labels" fill="#cbd2ba" textAnchor="middle">
        {[[150, 70, 'MAIN EVENT HALL'], [60, 285, 'WEST'], [240, 285, 'EAST'], [150, 286, 'RESERVE']].map(([x, y, label]) => <text key={label} x={Number(point(Number(x), Number(y)).split(',')[0])} y={Number(point(Number(x), Number(y)).split(',')[1])} fontSize={label === 'RESERVE' ? 10 : undefined}>{label}</text>)}
      </g>
      {[['P1', 60, 230], ['P2', 240, 230], ['B2', 240, 386]].map(([label, x, y]) => <g key={label}><ellipse cx={Number(point(Number(x), Number(y)).split(',')[0])} cy={Number(point(Number(x), Number(y)).split(',')[1])} rx="13" ry="8" fill={target === label ? '#633c32' : '#243e35'} stroke={target === label ? '#f68c7c' : '#83a28b'} strokeWidth=".8" /><text x={Number(point(Number(x), Number(y)).split(',')[0])} y={Number(point(Number(x), Number(y)).split(',')[1]) + 2.5} fill={target === label ? '#ffb8a8' : '#bdcfb2'} textAnchor="middle" className="observation-board-pad">{label}</text></g>)}
      <g>
        <polygon points={[point(token[0] - 10, token[1] + 10), point(token[0] + 11, token[1] + 10), point(token[0] + 11, token[1] + 10, 22), point(token[0] - 10, token[1] + 10, 22)].join(' ')} fill="#b55442" />
        <polygon points={[point(token[0] + 11, token[1] - 10), point(token[0] + 11, token[1] + 10), point(token[0] + 11, token[1] + 10, 22), point(token[0] + 11, token[1] - 10, 22)].join(' ')} fill="#da6d57" />
        <polygon points={face(token[0] - 10, token[1] - 10, 21, 20, 22)} fill="#fa9a7a" stroke="#ffbb96" strokeWidth=".8" />
      </g>
    </svg>
  );
}

export function ObservationPanel({ proposal, result, currentContext, liveConfigured, fixturesEnabled, isLoading, isApplying, isProposalCurrent, availabilityMessage, isAvailable = true, appliedCaptureId, error, onCapture, onApply, onClearProposal, uploadSlot, settingsSlot, locked = false, onLockedTap, readSeconds = null, onCameraLive, onBoardView, physical = false, resetKey = 0 }: ObservationPanelProps) {
  const [source, setSource] = useState<Source>('camera');
  const [demoTarget, setDemoTarget] = useState<FixtureTarget>('P2');
  const [fixtureTarget, setFixtureTarget] = useState<FixtureTarget>('P2');
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel>('low');
  const [cameraState, setCameraState] = useState<CameraState>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [isPreparing, setIsPreparing] = useState(false);
  const [preparationGate] = useState(createRequestGate);
  const [frameReady, setFrameReady] = useState(false);
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const [capturedDimensions, setCapturedDimensions] = useState<[number, number]>([1920, 1080]);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);
  const autoCamera = useRef(true);
  const physicalRef = useRef(physical);
  physicalRef.current = physical;
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState(() => { try { return localStorage.getItem(CAMERA_KEY) ?? ''; } catch { return ''; } });
  const rememberDevice = (id: string) => { setDeviceId(id); try { if (id) localStorage.setItem(CAMERA_KEY, id); else localStorage.removeItem(CAMERA_KEY); } catch { /* The choice only lasts for this page. */ } };
  const refreshDevices = async () => {
    try { setDevices((await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'videoinput')); } catch { setDevices([]); }
  };
  const [cameraNote, setCameraNote] = useState<string | null>(null);
  const connectRef = useRef<() => Promise<void>>(async () => undefined);
  const demoImage = useMemo(() => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(demoBoardSvg(demoTarget))}`, [demoTarget]);

  function stopCamera() {
    requestRef.current += 1;
    preparationGate.invalidate();
    setIsPreparing(false);
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraState('idle');
    setFrameReady(false);
  }

  useEffect(() => () => {
    requestRef.current += 1;
    preparationGate.invalidate();
    streamRef.current?.getTracks().forEach(track => track.stop());
  }, [preparationGate]);

  useEffect(() => {
    // A context change can arrive while decode or hashing is pending, before
    // the parent has received a capture request to invalidate.
    preparationGate.invalidate();
    setIsPreparing(false);
  }, [currentContext?.context_hash, preparationGate]);

  async function connectCamera(preferred: string = deviceId) {
    stopCamera();
    setSnapshot(null);
    onClearProposal?.();
    setCameraError(null);
    setCameraState('connecting');
    const request = requestRef.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires localhost or a secure connection in a supported browser.');
      const size = { width: { ideal: 1920 }, height: { ideal: 1080 } };
      const open = (id: string) => navigator.mediaDevices.getUserMedia({ video: id ? { ...size, deviceId: { exact: id } } : { ...size, facingMode: { ideal: 'environment' } }, audio: false });
      // A remembered camera that is gone falls back to the default one.
      const pending = open(preferred).catch(failure => {
        const gone = failure instanceof DOMException && ['OverconstrainedError', 'NotFoundError'].includes(failure.name);
        if (!preferred || !gone) throw failure;
        rememberDevice('');
        return open('');
      });
      // On the automatic start, an unanswered permission prompt must not freeze the stage: fall back after
      // CAMERA_WAIT_MS, and release a stream that arrives afterwards so the camera light does not stay on.
      const stream = autoCamera.current ? await Promise.race([pending, new Promise<never>((_, reject) => setTimeout(() => {
        if (physicalRef.current) return; // Physical hardware keeps waiting for the live camera; there is no silent fallback.
        pending.then(late => { if (request !== requestRef.current || streamRef.current !== late) late.getTracks().forEach(track => track.stop()); }).catch(() => undefined);
        reject(new Error('Camera permission was not answered'));
      }, CAMERA_WAIT_MS))]) : await pending;
      if (request !== requestRef.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      if (request !== requestRef.current) return;
      setCameraState('connected');
      void refreshDevices();
      stream.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
        if (request !== requestRef.current) return;
        setCameraState('error');
        setFrameReady(false);
        setCameraError('Camera disconnected.');
      }));
    } catch (cause) {
      if (request !== requestRef.current) return;
      streamRef.current?.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      setCameraState('error');
      const name = cause instanceof DOMException ? cause.name : '';
      const reason = name === 'NotAllowedError' ? 'Camera permission denied' : name === 'NotFoundError' ? 'No camera found' : cause instanceof Error ? cause.message.replace(/\.$/, '') : 'Unable to connect the camera';
      setCameraError(`${reason}.`);
      // Without a camera the stage falls back to the demo board image; the presenter menu can retry the camera.
      if (autoCamera.current && !physicalRef.current) { autoCamera.current = false; setCameraNote(`${reason}. Showing the demo board.`); setSource('demo'); }
    }
  }

  function changeSource(next: Source) {
    if (next === source) return;
    autoCamera.current = false;
    setCameraNote(null);
    stopCamera();
    setSource(next);
    setSnapshot(null);
    setCameraError(null);
    setActionError(null);
    onClearProposal?.();
  }

  connectRef.current = connectCamera;
  const firstReset = useRef(true);
  useEffect(() => {
    if (firstReset.current) { firstReset.current = false; return; }
    preparationGate.invalidate(); setIsPreparing(false); setSnapshot(null); setActionError(null);
  }, [resetKey, preparationGate]);
  useEffect(() => {
    void refreshDevices();
    const media = navigator.mediaDevices;
    media?.addEventListener?.('devicechange', refreshDevices);
    return () => media?.removeEventListener?.('devicechange', refreshDevices);
  }, []);
  // The live camera is the default board view. It starts once; a failure falls back to the demo board.
  useEffect(() => { void connectRef.current(); }, []);
  const cameraLive = source === 'camera' && cameraState === 'connected';
  useEffect(() => { onCameraLive?.(cameraLive); }, [cameraLive, onCameraLive]);
  const boardView: BoardView = cameraLive ? 'live' : source === 'demo' || source === 'fixture' ? 'fallback' : 'none';
  useEffect(() => { onBoardView?.(boardView); }, [boardView, onBoardView]);

  async function capture() {
    if (locked) { onLockedTap?.(); return; }
    if (isLoading || isApplying || !isAvailable || source === 'upload' || (source === 'fixture' ? !fixturesEnabled : !liveConfigured)) return;
    const preparation = preparationGate.start();
    if (preparation === null) return;
    setIsPreparing(true);
    setActionError(null);
    try {
      if (!currentContext) throw new Error('Wait for a current scenario before capturing.');
      const sourceRequest = requestRef.current;
      const metadata = { capture_id: crypto.randomUUID(), timestamp_iso: new Date().toISOString(), source_context: { ...currentContext }, thinking_level: thinkingLevel };
      if (source === 'fixture') { await onCapture({ ...metadata, dimensions: [600, 275], source_kind: 'fixture', mode: 'fixture', fixture_target: fixtureTarget }); return; }
      if (source === 'demo') {
        // Rasterize the exact displayed SVG. The provider receives image pixels, not a forced target.
        const image = new window.Image();
        image.src = demoImage;
        await image.decode();
        if (sourceRequest !== requestRef.current || !preparationGate.isCurrent(preparation)) return;
        const canvas = document.createElement('canvas');
        [canvas.width, canvas.height] = DEMO_BOARD_SIZE;
        const drawing = canvas.getContext('2d');
        if (!drawing) throw new Error('This browser could not render the synthetic board.');
        drawing.drawImage(image, 0, 0, canvas.width, canvas.height);
        const data = canvas.toDataURL('image/jpeg', .95);
        const evidence = await captureEvidence(demoBoardCapture(data.slice(data.indexOf(',') + 1), {
          captureId: metadata.capture_id, timestampIso: metadata.timestamp_iso,
          context: metadata.source_context, thinkingLevel: metadata.thinking_level,
        }));
        if (sourceRequest !== requestRef.current || !preparationGate.isCurrent(preparation)) return;
        setSnapshot(data);
        await onCapture(evidence);
        return;
      }
      const video = videoRef.current;
      if (!video || video.readyState < 2 || !video.videoWidth || cameraState !== 'connected') throw new Error('Wait for the camera image.');
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('This browser could not capture a still.');
      context.drawImage(video, 0, 0);
      const data = canvas.toDataURL('image/jpeg', .9);
      setCapturedDimensions([canvas.width, canvas.height]);
      setSnapshot(data);
      const evidence = await captureEvidence({ ...metadata, dimensions: [canvas.width, canvas.height], source_kind: 'tabletop_camera', mode: 'live', image_base64: data.slice(data.indexOf(',') + 1), deadline_seconds: 45 });
      if (sourceRequest !== requestRef.current || !preparationGate.isCurrent(preparation)) return;
      await onCapture(evidence);
    } catch (cause) {
      if (preparationGate.isCurrent(preparation)) setActionError(cause instanceof Error ? cause.message : 'The capture could not be interpreted.');
    } finally {
      if (preparationGate.isCurrent(preparation)) {
        preparationGate.finish(preparation);
        setIsPreparing(false);
      }
    }
  }

  const typedTarget = proposal?.selected_entity_type && proposal.selected_entity_id ? `${proposal.selected_entity_type}:${proposal.selected_entity_id}` : null;
  const validTarget = typedTarget !== null && ['portal:P1', 'portal:P2', 'boundary:B2'].includes(typedTarget) && !!proposal?.candidate_ids.includes(typedTarget);
  const isApplied = !!proposal && appliedCaptureId === proposal.capture_id && validTarget;
  const busy = isLoading || isPreparing;
  const canApply = canApplyGrounding(result, currentContext) && isProposalCurrent && isAvailable && !isApplied && !busy && !isApplying && !locked;
  const reviewState = !proposal ? 'idle' : isApplied ? 'applied' : !isProposalCurrent ? 'stale' : proposal.status;
  const targetName = proposal?.selected_entity_id ?? 'target';
  const provenance = provenanceChip(result);
  const needsPad = reviewState === 'no_match' || reviewState === 'ambiguous';
  const proofChip = proposal && validTarget && reviewState !== 'stale' && !needsPad ? [targetName, provenance?.label, readSeconds !== null ? `${Math.max(1, Math.round(readSeconds))} s` : null].filter(Boolean).join(' \u00b7 ') : null;
  const reviewTitle = reviewState === 'applied' ? `${targetName} \u00b7 confirmed` : reviewState === 'stale' ? 'Outdated \u00b7 read the board again' : needsPad ? 'Move the token onto a pad' : reviewState === 'matched' && validTarget ? `${proofChip} \u00b7 proposed closure` : proposal ? 'Invalid target' : isLoading ? 'Reading the board\u2026' : isPreparing ? 'Preparing image\u2026' : result ? 'No proposal' : '';
  const visibleError = actionError || error;
  const sourceNote = source === 'fixture' ? (fixturesEnabled ? '' : 'Fixtures are disabled.') : source === 'upload' ? '' : !isAvailable ? '' : !liveConfigured ? 'Gemini is not configured. Choose Fixture in the presenter menu.' : '';
  const sources: { id: Source; label: string; full: string; icon: ReactNode }[] = [
    { id: 'camera', label: 'Camera', full: 'Camera', icon: <Video size={14} aria-hidden="true" /> },
    { id: 'demo', label: 'Demo', full: 'Demo board', icon: <Layers2 size={14} aria-hidden="true" /> },
    { id: 'fixture', label: 'Fixture', full: 'Fixture', icon: <Image size={14} aria-hidden="true" /> },
    { id: 'upload', label: 'Upload', full: 'Upload image or clip', icon: <Upload size={14} aria-hidden="true" /> },
  ];
  const sourceBadge = source === 'demo' ? (snapshot ? 'Synthetic board \u00b7 token placed by presenter \u00b7 sent to Gemini' : 'Synthetic board \u00b7 token placed by presenter') : source === 'fixture' ? 'Fixture \u00b7 presenter-selected' : source === 'upload' ? 'Upload' : snapshot ? 'Sent to Gemini' : cameraState === 'connected' ? 'Live' : 'Camera';
  const stillSize: [number, number] = source === 'demo' ? [DEMO_BOARD_SIZE[0], DEMO_BOARD_SIZE[1]] : capturedDimensions;
  const box = snapshot && proposal?.box_2d && proposal.box_2d.length === 4 ? proposal.box_2d : null;
  const releaseStill = () => { preparationGate.invalidate(); setIsPreparing(false); setSnapshot(null); };
  useEffect(() => {
    if (!isApplied) return;
    const timer = setTimeout(() => setSnapshot(null), 2500);
    return () => clearTimeout(timer);
  }, [isApplied]);
  const readDisabled = !isAvailable || busy || isApplying || (source === 'fixture' && !fixturesEnabled) || (source !== 'fixture' && !liveConfigured) || (source === 'camera' && (!frameReady || cameraState !== 'connected'));

  const settings = <>
    <div className="seg board-sources" role="group" aria-label="Observation source">{sources.map(item => <button key={item.id} type="button" aria-pressed={source === item.id} aria-label={item.full} onClick={() => changeSource(item.id)}>{item.icon}<span>{item.label}</span></button>)}</div>
    {source !== 'camera' && source !== 'upload' && <div className="board-row">
      <select aria-label={source === 'demo' ? 'Blocked token target' : 'Fixture target'} value={source === 'demo' ? demoTarget : fixtureTarget} onChange={event => { source === 'demo' ? setDemoTarget(event.target.value as FixtureTarget) : setFixtureTarget(event.target.value as FixtureTarget); requestRef.current++; preparationGate.invalidate(); setIsPreparing(false); setSnapshot(null); setActionError(null); onClearProposal?.(); }} disabled={busy}><option value="P1">P1 · {fixtureNames.P1}</option><option value="P2">P2 · {fixtureNames.P2}</option><option value="B2">B2 · {fixtureNames.B2}</option></select>
    </div>}
    {source !== 'upload' && source !== 'fixture' && <div className="board-row"><select className="board-think" aria-label="Gemini thinking level" value={thinkingLevel} onChange={event => setThinkingLevel(event.target.value as ThinkingLevel)} disabled={busy}><option value="low">Think low</option><option value="medium">Think med</option><option value="high">Think high</option></select></div>}
    {source === 'camera' && devices.length > 0 && <label className="board-device"><span>Camera</span><select aria-label="Camera device" value={devices.some(device => device.deviceId === deviceId) ? deviceId : ''} onChange={event => { rememberDevice(event.target.value); autoCamera.current = false; void connectCamera(event.target.value); }}><option value="">Default camera</option>{devices.map((device, index) => <option key={device.deviceId || index} value={device.deviceId}>{device.label || `Camera ${index + 1}`}</option>)}</select></label>}
    {sourceNote && <p className="pm-note">{sourceNote}</p>}
    {source === 'camera' && cameraState === 'connected' && <button type="button" className="btn btn-quiet" onClick={() => { stopCamera(); setSnapshot(null); onClearProposal?.(); }}><Unplug size={13} aria-hidden="true" />Disconnect camera</button>}
    {source === 'camera' && cameraState !== 'connected' && <button className="btn btn-quiet" type="button" onClick={() => void connectCamera()} disabled={cameraState === 'connecting'}><Camera size={13} aria-hidden="true" />Connect camera</button>}
  </>;

  return (
    <section id="observation-workspace" tabIndex={-1} className="board" aria-label="Board">
      {settingsSlot && createPortal(settings, settingsSlot)}
      <div className="board-media">
        <span className="board-badge">{sourceBadge}</span>
        {source === 'demo' ? <img className="board-image board-image-demo" src={snapshot ?? demoImage} width={1200} height={1000} alt={`Synthetic four-zone board with a red BLOCKED token on ${demoTarget}. This exact illustration is sent to Gemini; no physical hardware is present.`} /> : source === 'fixture' ? <TabletopPreview target={fixtureTarget} /> : source === 'upload' ? <div className="board-upload">{uploadSlot}</div> : <>
          <video ref={videoRef} autoPlay muted playsInline aria-label="Live tabletop camera preview" className={`board-image ${cameraState !== 'connected' || snapshot ? 'board-hidden' : ''}`} onLoadedData={() => setFrameReady(true)} />
          {snapshot && <img className="board-image" src={snapshot} width={capturedDimensions[0]} height={capturedDimensions[1]} alt="The exact still sent to Gemini" />}
          {!snapshot && cameraState !== 'connected' && <div className="board-empty"><span>{cameraState === 'connecting' ? 'Waiting for camera permission\u2026' : `Camera not live${cameraError ? ` \u00b7 ${cameraError.replace(/\.$/, '')}` : ''}`}</span>{cameraState !== 'connecting' && <button className="btn" type="button" onClick={() => void connectCamera()}><Camera size={14} aria-hidden="true" />Connect camera</button>}</div>}
        </>}
        {box && <svg className={`board-overlay${source === 'demo' ? ' is-demo' : ''}`} viewBox={`0 0 ${stillSize[0]} ${stillSize[1]}`} preserveAspectRatio="xMidYMid meet" aria-hidden="true"><rect x={box[1] / 1000 * stillSize[0]} y={box[0] / 1000 * stillSize[1]} width={(box[3] - box[1]) / 1000 * stillSize[0]} height={(box[2] - box[0]) / 1000 * stillSize[1]} vectorEffect="non-scaling-stroke" /></svg>}
        {snapshot && source !== 'upload' && !busy && <button type="button" className="btn btn-quiet board-live" onClick={() => { releaseStill(); onClearProposal?.(); }}>Back to live view</button>}
      </div>
      {cameraNote && source === 'demo' && <p className="board-note" role="status">{cameraNote}</p>}

      {source !== 'upload' && <button className={`btn ${canApply || needsPad ? '' : 'btn-primary'} board-capture`} type="button" aria-disabled={locked || readDisabled} onClick={() => { if (locked) onLockedTap?.(); else if (!readDisabled) void capture(); }}>{busy ? <LoaderCircle size={15} className="spin" aria-hidden="true" /> : <ScanLine size={15} aria-hidden="true" />}{!isAvailable ? 'Backend offline' : isLoading ? 'Reading\u2026' : isPreparing ? 'Preparing\u2026' : source === 'fixture' ? 'Load fixture' : !liveConfigured ? 'Gemini offline \u00b7 use Fire on the model' : 'Read the board'}</button>}
      {visibleError && <p className="board-error" role="alert"><CircleAlert size={13} aria-hidden="true" /><span>{visibleError}</span></p>}

      <div id="observation-review" tabIndex={-1} className={`board-proposal board-proposal-${reviewState}`} aria-live="polite" aria-busy={busy || isApplying}>
        {reviewTitle && <div className="board-proposal-title"><span className={`chip chip-${isApplied || canApply ? 'ok' : reviewState === 'idle' || busy ? 'muted' : 'warn'}`}>{canApply || isApplied ? <Check size={12} aria-hidden="true" /> : null}{reviewTitle}</span></div>}
        {proposal && <span className="sr-only">{proposal.evidence}</span>}
        {proposal && <div className="board-proposal-actions">
          {!needsPad && <button className="btn btn-primary" type="button" onClick={async () => { setActionError(null); try { await onApply(); } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'The proposal could not be applied.'); } }} disabled={!canApply}>{isApplying ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <Check size={14} aria-hidden="true" />}{isApplied ? 'Confirmed' : isApplying ? 'Confirming\u2026' : 'Confirm'}</button>}
          <button className="btn" type="button" onClick={() => { releaseStill(); onClearProposal?.(); }} disabled={isApplying}><X size={14} aria-hidden="true" />Dismiss</button>
        </div>}
      </div>
      {availabilityMessage && !isProposalCurrent && proposal && <p className="board-note">{availabilityMessage}</p>}
    </section>
  );
}
