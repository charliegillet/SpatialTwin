import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, Camera, Check, CircleAlert, Image, Layers2, LoaderCircle, ScanLine, Unplug, Video } from 'lucide-react';
import type { CaptureRequest, GroundingProposalV1, GroundingResult, RunContext, ThinkingLevel } from '../types';
import { canApplyGrounding, groundingLabel } from '../ai/policy';
import { captureEvidence } from '../ai/evidence';
import { DEMO_BOARD_SIZE, demoBoardCapture, demoBoardSvg } from '../ai/demoBoard';
import { ExecutionReceipt } from './ExecutionReceipt';
import './ObservationPanel.css';

export interface ObservationPanelProps {
  proposal: GroundingProposalV1 | null;
  result: GroundingResult | null;
  currentContext?: RunContext;
  liveConfigured: boolean;
  fixturesEnabled: boolean;
  isLoading: boolean;
  isApplying: boolean;
  isProposalCurrent: boolean;
  isAvailable?: boolean;
  appliedCaptureId?: string | null;
  error: string | null;
  onCapture: (capture: CaptureRequest) => Promise<void>;
  onApply: () => Promise<void>;
  onClearProposal?: () => void;
}

type FixtureTarget = 'P1' | 'P2' | 'B2';
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
    <svg className="observation-board" viewBox="0 0 600 275" role="img" aria-label={`Illustrative tabletop with a red blockage cube at ${target}. This is a diagram, not a camera image.`}>
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
        {[[150, 70, 'MAIN EVENT HALL'], [60, 285, 'WEST'], [240, 285, 'EAST'], [150, 286, 'RESERVE']].map(([x, y, label]) => <text key={label} x={Number(point(Number(x), Number(y)).split(',')[0])} y={Number(point(Number(x), Number(y)).split(',')[1])} fontSize={label === 'RESERVE' ? 5.5 : undefined}>{label}</text>)}
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

export function ObservationPanel({ proposal, result, currentContext, liveConfigured, fixturesEnabled, isLoading, isApplying, isProposalCurrent, isAvailable = true, appliedCaptureId, error, onCapture, onApply, onClearProposal }: ObservationPanelProps) {
  const [source, setSource] = useState<'demo' | 'fixture' | 'camera'>('demo');
  const [demoTarget, setDemoTarget] = useState<FixtureTarget>('P2');
  const [fixtureTarget, setFixtureTarget] = useState<FixtureTarget>('P2');
  const [thinkingLevel, setThinkingLevel] = useState<ThinkingLevel>('low');
  const [cameraState, setCameraState] = useState<CameraState>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [frameReady, setFrameReady] = useState(false);
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);
  const demoImage = useMemo(() => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(demoBoardSvg(demoTarget))}`, [demoTarget]);

  function stopCamera() {
    requestRef.current += 1;
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraState('idle');
    setFrameReady(false);
  }

  useEffect(() => () => {
    requestRef.current += 1;
    streamRef.current?.getTracks().forEach(track => track.stop());
  }, []);

  async function connectCamera() {
    stopCamera();
    setSnapshot(null);
    onClearProposal?.();
    setCameraError(null);
    setCameraState('connecting');
    const request = requestRef.current;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires localhost or a secure connection in a supported browser.');
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false });
      if (request !== requestRef.current) { stream.getTracks().forEach(track => track.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      if (request !== requestRef.current) return;
      setCameraState('connected');
      stream.getVideoTracks().forEach(track => track.addEventListener('ended', () => {
        if (request !== requestRef.current) return;
        setCameraState('error');
        setFrameReady(false);
        setCameraError('Camera disconnected. Reconnect to capture another still.');
      }));
    } catch (cause) {
      if (request !== requestRef.current) return;
      streamRef.current?.getTracks().forEach(track => track.stop());
      streamRef.current = null;
      setCameraState('error');
      const name = cause instanceof DOMException ? cause.name : '';
      setCameraError(name === 'NotAllowedError' ? 'Camera permission was denied. Allow access in your browser, then reconnect.' : name === 'NotFoundError' ? 'No camera was found. Connect a camera or use the demo source.' : cause instanceof Error ? cause.message : 'Unable to connect the camera.');
    }
  }

  function changeSource(next: 'demo' | 'fixture' | 'camera') {
    if (next === source) return;
    stopCamera();
    setSource(next);
    setSnapshot(null);
    setCameraError(null);
    setActionError(null);
    onClearProposal?.();
  }

  async function capture() {
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
        if (sourceRequest !== requestRef.current) return;
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
        if (sourceRequest !== requestRef.current) return;
        setSnapshot(data);
        await onCapture(evidence);
        return;
      }
      const video = videoRef.current;
      if (!video || video.readyState < 2 || !video.videoWidth || cameraState !== 'connected') throw new Error('Wait for the camera image before capturing.');
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('This browser could not capture a still.');
      context.drawImage(video, 0, 0);
      const data = canvas.toDataURL('image/jpeg', .9);
      setSnapshot(data);
      const evidence = await captureEvidence({ ...metadata, dimensions: [canvas.width, canvas.height], source_kind: 'tabletop_camera', mode: 'live', image_base64: data.slice(data.indexOf(',') + 1), deadline_seconds: 45 });
      if (sourceRequest !== requestRef.current) return;
      await onCapture(evidence);
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'The capture could not be interpreted.'); }
  }

  const typedTarget = proposal?.selected_entity_type && proposal.selected_entity_id ? `${proposal.selected_entity_type}:${proposal.selected_entity_id}` : null;
  const validTarget = typedTarget !== null && ['portal:P1', 'portal:P2', 'boundary:B2'].includes(typedTarget) && !!proposal?.candidate_ids.includes(typedTarget);
  const isApplied = !!proposal && appliedCaptureId === proposal.capture_id && validTarget;
  const canApply = canApplyGrounding(result, currentContext) && isProposalCurrent && isAvailable && !isApplied && !isLoading && !isApplying;
  const reviewState = !proposal ? 'idle' : isApplied ? 'applied' : !isProposalCurrent ? 'stale' : proposal.status;
  const reviewTitle = reviewState === 'applied' ? `${typedTarget} · closure applied` : reviewState === 'stale' ? 'Scenario changed · capture again' : reviewState === 'matched' && validTarget ? `${typedTarget} · proposed closure` : reviewState === 'ambiguous' ? 'Needs your choice' : reviewState === 'no_match' ? 'No target matched' : proposal ? 'Invalid target · capture again' : 'Observe. Review. Apply.';
  const provenanceLabel = groundingLabel(result);
  const visibleError = actionError || error;

  return (
    <section className="observation-panel" aria-labelledby="observation-title">
      <header className="observation-header">
        <div className="observation-heading"><span className="observation-camera-icon">{source === 'camera' ? <Camera size={16} /> : <Layers2 size={16} />}</span><div><h2 id="observation-title">Observation 01 <span>/ {source === 'camera' ? 'Physical tabletop' : source === 'demo' ? 'Synthetic board' : 'Offline fixture'}</span></h2><p>Observe the board. Review the proposed change.</p></div></div>
        <div className="observation-source-switch" aria-label="Observation source"><button type="button" aria-pressed={source === 'demo'} onClick={() => changeSource('demo')}><Layers2 size={12} />Demo board</button><button type="button" aria-pressed={source === 'camera'} onClick={() => changeSource('camera')}><Video size={12} />Camera</button><button type="button" aria-pressed={source === 'fixture'} onClick={() => changeSource('fixture')}><Image size={12} />Fixture</button></div>
      </header>

      <div className={`observation-viewport observation-viewport-${source}`}>
        <div className="observation-viewport-top"><span className={`observation-source-badge ${source === 'camera' && cameraState === 'connected' ? 'observation-source-connected' : ''}`}><i />{source === 'demo' ? 'Synthetic board image' : source === 'fixture' ? 'Illustrative fixture preview' : snapshot ? 'Captured still' : cameraState === 'connected' ? 'Camera connected' : cameraState === 'connecting' ? 'Connecting camera' : 'Camera disconnected'}</span><span className="observation-view-label">{source === 'demo' ? 'LIVE INFERENCE INPUT' : source === 'fixture' ? 'OFFLINE FIXTURE' : 'LOCAL CAMERA'}</span></div>
        {source === 'demo' ? <img className="observation-synthetic-board" src={snapshot ?? demoImage} alt={`Synthetic four-zone board with a red BLOCKED token on ${demoTarget}. This exact illustration is sent to Gemini; no physical hardware is present.`} /> : source === 'fixture' ? <><TabletopPreview target={fixtureTarget} /><div className="observation-demo-caption"><span className="observation-cube-key" />Fixture cube <span>at {fixtureTarget}</span></div></> : <>
          <video ref={videoRef} autoPlay muted playsInline className={`observation-video ${cameraState !== 'connected' || snapshot ? 'observation-media-hidden' : ''}`} onLoadedData={() => setFrameReady(true)} />
          {snapshot && <img className="observation-captured-image" src={snapshot} alt="Captured tabletop still submitted for review" />}
          {!snapshot && cameraState !== 'connected' && <div className="observation-camera-empty"><span className="observation-empty-icon"><Video size={23} strokeWidth={1.4} /></span><strong>{cameraState === 'connecting' ? 'Connecting your camera' : cameraState === 'error' ? 'Camera unavailable' : 'Bring your tabletop into view'}</strong><p>{cameraError || 'Connect a camera to preview the board, then choose a still to interpret.'}</p><button className="observation-connect-button" type="button" onClick={connectCamera} disabled={cameraState === 'connecting'}>{cameraState === 'connecting' ? <LoaderCircle size={13} className="observation-spin" /> : <Camera size={13} />}{cameraState === 'connecting' ? 'Waiting for permission…' : 'Connect camera'}</button></div>}
          {(cameraState === 'connected' || snapshot) && <div className="observation-camera-controls">{snapshot && <button type="button" onClick={() => { setSnapshot(null); onClearProposal?.(); }}>Return to preview</button>}{cameraState === 'connected' ? <button type="button" onClick={() => { stopCamera(); setSnapshot(null); onClearProposal?.(); }}><Unplug size={11} />Disconnect</button> : <button type="button" onClick={connectCamera}><Camera size={11} />Reconnect</button>}</div>}
        </>}
      </div>

      <div className="observation-capture-bar">
        {source !== 'camera' ? <label className="observation-fixture-select"><span>{source === 'demo' ? 'SYNTHETIC BLOCKED TOKEN' : 'FIXTURE TARGET'}</span><select aria-label={source === 'demo' ? 'Synthetic blocked token' : 'Fixture target'} value={source === 'demo' ? demoTarget : fixtureTarget} onChange={event => { source === 'demo' ? setDemoTarget(event.target.value as FixtureTarget) : setFixtureTarget(event.target.value as FixtureTarget); requestRef.current++; setSnapshot(null); setActionError(null); onClearProposal?.(); }} disabled={isLoading}><option value="P1">P1 · {fixtureNames.P1}</option><option value="P2">P2 · {fixtureNames.P2}</option><option value="B2">B2 · {fixtureNames.B2}</option></select></label> : <p className="observation-capture-hint">{snapshot ? 'Captured image held for review' : 'Only the selected still is analyzed'}</p>}
        <button className="observation-capture-button" type="button" onClick={capture} disabled={!isAvailable || isLoading || isApplying || (source === 'fixture' && !fixturesEnabled) || (source !== 'fixture' && !liveConfigured) || (source === 'camera' && (!frameReady || cameraState !== 'connected'))}>{isLoading ? <LoaderCircle size={14} className="observation-spin" /> : <ScanLine size={14} />}{!isAvailable ? 'Backend offline' : isLoading ? 'Interpreting…' : source === 'fixture' ? 'Load fixture proposal' : source === 'demo' ? 'Analyze board · Gemini' : 'Capture · Gemini'}{!isLoading && <ArrowUpRight size={13} />}</button>
      </div>
      <div className="observation-execution-options">{source !== 'fixture' ? <><label>Thinking<select aria-label="Gemini thinking level" value={thinkingLevel} onChange={event => setThinkingLevel(event.target.value as ThinkingLevel)} disabled={isLoading}><option value="low">Low · quick review</option><option value="medium">Medium</option><option value="high">High</option></select></label><span>{!liveConfigured ? 'Gemini unavailable · configure server credentials' : source === 'demo' ? 'Synthetic image · real Gemini request · up to 45s · no hardware' : 'Gemini configured · up to 45s · completed response required'}</span></> : <span>{fixturesEnabled ? 'Explicit fixture · no camera inference or Gemini tokens' : 'Fixtures disabled by the server'}</span>}</div>

      {visibleError && <div className="observation-error" role="alert"><CircleAlert size={13} /><span>{visibleError}</span></div>}
      <div className={`observation-review observation-review-${reviewState}`} aria-live="polite" aria-busy={isLoading || isApplying}>
        <span className="observation-review-icon">{canApply || isApplied ? <Check size={14} /> : reviewState === 'idle' ? <ScanLine size={14} /> : <CircleAlert size={14} />}</span>
        <div className="observation-review-content"><div className="observation-review-title">{reviewTitle}{result && <span className="observation-provenance">{provenanceLabel}</span>}</div><p>{proposal ? proposal.evidence : result && result.status !== 'completed' ? 'No proposal was accepted. Retry a fresh capture, or explicitly select a fixture.' : 'A proposal changes the scenario only after your approval.'}</p></div>
        <button className="observation-apply-button" type="button" onClick={async () => { setActionError(null); try { await onApply(); } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'The proposal could not be applied.'); } }} disabled={!canApply}>{isApplying ? <LoaderCircle size={12} className="observation-spin" /> : <Check size={12} />}{isApplied ? 'Applied' : isApplying ? 'Applying…' : 'Apply closure'}</button>
      </div>
      <ExecutionReceipt result={result} label={provenanceLabel} />
    </section>
  );
}
