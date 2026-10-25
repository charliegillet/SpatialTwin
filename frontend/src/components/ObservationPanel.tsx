import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Camera, Check, CircleAlert, Image, LoaderCircle, ScanLine, Unplug, Video } from 'lucide-react';
import type { GroundingProposalV1 } from '../types';
import './ObservationPanel.css';

export interface ObservationPanelProps {
  proposal: GroundingProposalV1 | null;
  provenance: string | null;
  isLoading: boolean;
  isApplying: boolean;
  isProposalCurrent: boolean;
  error: string | null;
  onCapture: (imageBase64?: string, fixtureTarget?: 'P1' | 'P2' | 'B2') => Promise<void>;
  onApply: () => Promise<void>;
}

type FixtureTarget = 'P1' | 'P2' | 'B2';
type CameraState = 'idle' | 'connecting' | 'connected' | 'error';

const fixtureNames: Record<FixtureTarget, string> = { P1: 'West passage', P2: 'East passage', B2: 'East boundary' };

/** An illustrative tabletop, deliberately separate from camera or detection evidence. */
function TabletopPreview({ target }: { target: FixtureTarget }) {
  const point = (x: number, y: number, z = 0) => `${134 + x * .91 - y * .26},${53 + x * .055 + y * .55 - z * .8}`;
  const face = (x: number, y: number, w: number, d: number, z = 0) => [point(x, y, z), point(x + w, y, z), point(x + w, y + d, z), point(x, y + d, z)].join(' ');
  const walls = [[0, 0, 420, 6], [0, 0, 6, 288], [414, 0, 6, 288], [0, 282, 420, 6], [0, 108, 105, 5], [144, 108, 116, 5], [300, 108, 120, 5], [144, 0, 5, 108], [285, 108, 5, 106], [285, 252, 5, 36]];
  const token = target === 'P1' ? [121, 108] : target === 'P2' ? [280, 108] : [398, 242];
  return (
    <svg className="observation-board" viewBox="0 0 600 275" role="img" aria-label={`Illustrative tabletop with a red blockage cube at ${target}. This is a diagram, not a camera image.`}>
      <defs>
        <filter id="observation-board-shadow" x="-40%" y="-50%" width="180%" height="220%"><feGaussianBlur stdDeviation="10" /></filter>
        <pattern id="observation-table-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M 28 0 L 0 0 0 28" fill="none" stroke="#263739" strokeWidth=".7" /></pattern>
      </defs>
      <ellipse cx="302" cy="235" rx="216" ry="19" fill="#000" opacity=".5" filter="url(#observation-board-shadow)" />
      <polygon points={face(-15, -15, 450, 318, -8)} fill="#182325" stroke="#364345" />
      <polygon points={face(-15, -15, 450, 318)} fill="#263032" stroke="#58615b" strokeWidth="1.3" />
      <polygon points={face(0, 0, 420, 288)} fill="#343e37" />
      <polygon points={face(0, 0, 420, 288)} fill="url(#observation-table-grid)" opacity=".7" />
      <polygon points={face(149, 0, 265, 108)} fill="#444b3d" />
      <polygon points={face(290, 113, 124, 169)} fill="#3d473a" />
      <path d={`M${point(193, 224)} L${point(193, 150)} L${point(278, 150)} L${point(278, 111)} L${point(338, 75)}`} fill="none" stroke="#b7d68b" strokeWidth="2" strokeDasharray="5 6" opacity=".7" />
      <path d={`M${point(193, 178)} L${point(122, 178)} L${point(122, 110)} L${point(71, 63)}`} fill="none" stroke="#b7d68b" strokeWidth="2" strokeDasharray="5 6" opacity=".7" />
      {[[45, 158], [100, 215], [206, 217], [335, 165], [328, 30]].map(([x, y]) => <g key={`${x}-${y}`}><polygon points={face(x, y + 3, 38, 22)} fill="#202d29" /><polygon points={face(x, y, 38, 22, 7)} fill="#75806a" stroke="#92977f" strokeWidth=".6" /></g>)}
      {walls.map(([x, y, w, d], index) => <g key={index}><polygon points={[point(x, y + d), point(x + w, y + d), point(x + w, y + d, 19), point(x, y + d, 19)].join(' ')} fill="#636c5c" /><polygon points={[point(x + w, y), point(x + w, y + d), point(x + w, y + d, 19), point(x + w, y, 19)].join(' ')} fill="#78816e" /><polygon points={face(x, y, w, d, 19)} fill="#a5ac94" /></g>)}
      <g className="observation-board-labels" fill="#cbd2ba" textAnchor="middle">
        <text x={196} y={87}>WEST</text><text x={415} y={96}>EAST</text><text x={267} y={166}>EVENT HALL</text><text x={422} y={196}>RESERVE</text>
      </g>
      {[['P1', 122, 126], ['P2', 280, 126], ['B2', 398, 264]].map(([label, x, y]) => <g key={label}><ellipse cx={Number(point(Number(x), Number(y)).split(',')[0])} cy={Number(point(Number(x), Number(y)).split(',')[1])} rx="13" ry="8" fill={target === label ? '#633c32' : '#243e35'} stroke={target === label ? '#f68c7c' : '#83a28b'} strokeWidth=".8" /><text x={Number(point(Number(x), Number(y)).split(',')[0])} y={Number(point(Number(x), Number(y)).split(',')[1]) + 2.5} fill={target === label ? '#ffb8a8' : '#bdcfb2'} textAnchor="middle" className="observation-board-pad">{label}</text></g>)}
      <g>
        <polygon points={[point(token[0] - 10, token[1] + 10), point(token[0] + 11, token[1] + 10), point(token[0] + 11, token[1] + 10, 22), point(token[0] - 10, token[1] + 10, 22)].join(' ')} fill="#b55442" />
        <polygon points={[point(token[0] + 11, token[1] - 10), point(token[0] + 11, token[1] + 10), point(token[0] + 11, token[1] + 10, 22), point(token[0] + 11, token[1] - 10, 22)].join(' ')} fill="#da6d57" />
        <polygon points={face(token[0] - 10, token[1] - 10, 21, 20, 22)} fill="#fa9a7a" stroke="#ffbb96" strokeWidth=".8" />
      </g>
    </svg>
  );
}

export function ObservationPanel({ proposal, provenance, isLoading, isApplying, isProposalCurrent, error, onCapture, onApply }: ObservationPanelProps) {
  const [source, setSource] = useState<'demo' | 'camera'>('demo');
  const [fixtureTarget, setFixtureTarget] = useState<FixtureTarget>('P2');
  const [cameraState, setCameraState] = useState<CameraState>('idle');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [frameReady, setFrameReady] = useState(false);
  const [snapshot, setSnapshot] = useState<string | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestRef = useRef(0);

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

  function changeSource(next: 'demo' | 'camera') {
    if (next === source) return;
    stopCamera();
    setSource(next);
    setSnapshot(null);
    setCameraError(null);
    setActionError(null);
  }

  async function capture() {
    setActionError(null);
    try {
      if (source === 'demo') { await onCapture(undefined, fixtureTarget); return; }
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
      await onCapture(data.slice(data.indexOf(',') + 1));
    } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'The capture could not be interpreted.'); }
  }

  const typedTarget = proposal?.selected_entity_type && proposal.selected_entity_id ? `${proposal.selected_entity_type}:${proposal.selected_entity_id}` : null;
  const validTarget = typedTarget !== null && ['portal:P1', 'portal:P2', 'boundary:B2'].includes(typedTarget) && !!proposal?.candidate_ids.includes(typedTarget);
  const canApply = !!proposal && proposal.status === 'matched' && proposal.operation === 'SET_UNAVAILABLE' && validTarget && isProposalCurrent && !isLoading && !isApplying;
  const reviewState = !proposal ? 'idle' : !isProposalCurrent ? 'stale' : proposal.status;
  const reviewTitle = reviewState === 'stale' ? 'Scenario changed · capture again' : reviewState === 'matched' && validTarget ? `${typedTarget} · proposed closure` : reviewState === 'ambiguous' ? 'Needs your choice' : reviewState === 'no_match' ? 'No target matched' : proposal ? 'Invalid target · capture again' : 'Observe. Review. Apply.';
  const provenanceLabel = provenance === 'live' ? 'Live model result' : provenance === 'fixture' ? 'Fixture result' : provenance;
  const visibleError = actionError || error;

  return (
    <section className="observation-panel" aria-labelledby="observation-title">
      <header className="observation-header">
        <div className="observation-heading"><span className="observation-camera-icon"><Camera size={16} /></span><div><h2 id="observation-title">Camera 01 <span>/ Physical tabletop</span></h2><p>Observe the board. Review the proposed change.</p></div></div>
        <div className="observation-source-switch" aria-label="Observation source"><button type="button" aria-pressed={source === 'demo'} onClick={() => changeSource('demo')}><Image size={12} />Demo</button><button type="button" aria-pressed={source === 'camera'} onClick={() => changeSource('camera')}><Video size={12} />Live camera</button></div>
      </header>

      <div className={`observation-viewport observation-viewport-${source}`}>
        <div className="observation-viewport-top"><span className={`observation-source-badge ${source === 'camera' && cameraState === 'connected' ? 'observation-source-connected' : ''}`}><i />{source === 'demo' ? 'Illustrative preview' : snapshot ? 'Captured still' : cameraState === 'connected' ? 'Camera connected' : cameraState === 'connecting' ? 'Connecting camera' : 'Camera disconnected'}</span><span className="observation-view-label">{source === 'demo' ? 'SCHEMATIC / DEMO' : 'LOCAL CAMERA'}</span></div>
        {source === 'demo' ? <><TabletopPreview target={fixtureTarget} /><div className="observation-demo-caption"><span className="observation-cube-key" />Blockage cube <span>at {fixtureTarget}</span></div></> : <>
          <video ref={videoRef} autoPlay muted playsInline className={`observation-video ${cameraState !== 'connected' || snapshot ? 'observation-media-hidden' : ''}`} onLoadedData={() => setFrameReady(true)} />
          {snapshot && <img className="observation-captured-image" src={snapshot} alt="Captured tabletop still submitted for review" />}
          {!snapshot && cameraState !== 'connected' && <div className="observation-camera-empty"><span className="observation-empty-icon"><Video size={23} strokeWidth={1.4} /></span><strong>{cameraState === 'connecting' ? 'Connecting your camera' : cameraState === 'error' ? 'Camera unavailable' : 'Bring your tabletop into view'}</strong><p>{cameraError || 'Connect a camera to preview the board, then choose a still to interpret.'}</p><button className="observation-connect-button" type="button" onClick={connectCamera} disabled={cameraState === 'connecting'}>{cameraState === 'connecting' ? <LoaderCircle size={13} className="observation-spin" /> : <Camera size={13} />}{cameraState === 'connecting' ? 'Waiting for permission…' : 'Connect camera'}</button></div>}
          {(cameraState === 'connected' || snapshot) && <div className="observation-camera-controls">{snapshot && <button type="button" onClick={() => setSnapshot(null)}>Return to preview</button>}{cameraState === 'connected' ? <button type="button" onClick={() => { stopCamera(); setSnapshot(null); }}><Unplug size={11} />Disconnect</button> : <button type="button" onClick={connectCamera}><Camera size={11} />Reconnect</button>}</div>}
        </>}
      </div>

      <div className="observation-capture-bar">
        {source === 'demo' ? <label className="observation-fixture-select"><span>DEMO TARGET</span><select value={fixtureTarget} onChange={event => setFixtureTarget(event.target.value as FixtureTarget)} disabled={isLoading}><option value="P1">P1 · {fixtureNames.P1}</option><option value="P2">P2 · {fixtureNames.P2}</option><option value="B2">B2 · {fixtureNames.B2}</option></select></label> : <p className="observation-capture-hint">{snapshot ? 'Captured image held for review' : 'Only the selected still is analyzed'}</p>}
        <button className="observation-capture-button" type="button" onClick={capture} disabled={isLoading || isApplying || (source === 'camera' && (!frameReady || cameraState !== 'connected'))}>{isLoading ? <LoaderCircle size={14} className="observation-spin" /> : <ScanLine size={14} />}{isLoading ? 'Interpreting…' : source === 'demo' ? 'Load demo proposal' : 'Capture & interpret'}{!isLoading && <ArrowUpRight size={13} />}</button>
      </div>

      {visibleError && <div className="observation-error" role="alert"><CircleAlert size={13} /><span>{visibleError}</span></div>}
      <div className={`observation-review observation-review-${reviewState}`} aria-live="polite" aria-busy={isLoading || isApplying}>
        <span className="observation-review-icon">{canApply ? <Check size={14} /> : reviewState === 'idle' ? <ScanLine size={14} /> : <CircleAlert size={14} />}</span>
        <div className="observation-review-content"><div className="observation-review-title">{reviewTitle}{proposal && provenanceLabel && <span className="observation-provenance">{provenanceLabel}</span>}</div><p>{proposal ? proposal.evidence : 'A proposal changes the scenario only after your approval.'}</p></div>
        <button className="observation-apply-button" type="button" onClick={async () => { setActionError(null); try { await onApply(); } catch (cause) { setActionError(cause instanceof Error ? cause.message : 'The proposal could not be applied.'); } }} disabled={!canApply}>{isApplying ? <LoaderCircle size={12} className="observation-spin" /> : <Check size={12} />}{isApplying ? 'Applying…' : 'Apply closure'}</button>
      </div>
    </section>
  );
}
