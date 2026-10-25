import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { fetchUnderlay } from '../api/underlay.ts';
import { playbackView } from '../twin/playback.ts';
import { ariaSummary } from '../twin/sceneModel.ts';
import type { TwinScene3DProps, VenueV2 } from '../twin/types.ts';
import { DEFAULT_UNDERLAY_OPACITY, underlayMatches, type Underlay as UnderlaySpec } from '../twin/underlay.ts';
import Building, { hasLooks } from './Building.tsx';
import Furniture, { justDragged } from './Furniture.tsx';
import CameraRig, { FOV, type CameraPreset } from './CameraRig.tsx';
import Doors from './Doors.tsx';
import DropPlane from './DropPlane.tsx';
import ExitSigns from './ExitSigns.tsx';
import Hazards from './Hazards.tsx';
import { LabelLayer, LabelProjector, buildLabels } from './Labels.tsx';
import PlaybackBar from './PlaybackBar.tsx';
import { usePlayback } from './usePlayback.ts';
import Routes from './Routes.tsx';
import Underlay from './Underlay.tsx';
import { PALETTE } from './palette.ts';
import './scene.css';

type Picker = (clientX: number, clientY: number) => { x: number; y: number } | null;

/** Exposes a client-pixel -> floor-metres raycast so HTML5 drops can be placed. */
function PickBridge({ pickRef }: { pickRef: { current: Picker | null } }) {
  const { camera, gl } = useThree();
  pickRef.current = (clientX, clientY) => {
    const rect = gl.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((clientX - rect.left) / rect.width) * 2 - 1, -(((clientY - rect.top) / rect.height) * 2 - 1));
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, camera);
    const point = ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), new THREE.Vector3());
    return point ? { x: point.x, y: -point.z } : null;
  };
  return null;
}

/** The accepted venue's source photo, if it has one placed against exactly this geometry. Fetched per venue revision. */
function useUnderlay(venue: VenueV2): UnderlaySpec | null {
  const [found, setFound] = useState<UnderlaySpec | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    setFound(null);
    fetchUnderlay(venue.venue_id, controller.signal)
      .then((answer) => { if (answer.available) setFound(answer.underlay); })
      .catch(() => undefined); // aborted: a newer venue is on screen
    return () => controller.abort();
  }, [venue.venue_id, venue.geometry_revision]);
  return underlayMatches(found, venue) ? found : null;
}

/** Shown only once the photo is on screen: a toggle, its opacity and the provenance of what is drawn. */
function UnderlayControl({ label, shown, opacity, onShown, onOpacity }: {
  label: string; shown: boolean; opacity: number; onShown: (shown: boolean) => void; onOpacity: (opacity: number) => void;
}) {
  return (
    <div className="twin-underlay" role="group" aria-label="Map photo under the model">
      <div className="twin-underlay__row">
        <button type="button" aria-pressed={shown} onClick={() => onShown(!shown)}>Map photo</button>
        <input
          type="range" min={10} max={100} step={5} value={Math.round(opacity * 100)} disabled={!shown}
          aria-label="Map photo opacity" aria-valuetext={`${Math.round(opacity * 100)} percent`}
          onChange={(event) => onOpacity(Number(event.target.value) / 100)}
        />
      </div>
      <p className="twin-underlay__note">{label}</p>
    </div>
  );
}

export default function TwinScene3D(props: TwinScene3DProps) {
  const { venue, plan, hazards, armedType, selectedHazardId, lowGraphics, reducedMotion, onPlace, onSelectHazard } = props;
  const pickRef = useRef<Picker | null>(null);
  const [preset, setPreset] = useState<CameraPreset>('overview');
  const [nonce, setNonce] = useState(0);
  const summary = useMemo(() => ariaSummary(venue, plan, hazards), [venue, plan, hazards]);
  const playback = usePlayback(plan, reducedMotion);
  const view = useMemo(() => playbackView(venue, plan, playback.index), [venue, plan, playback.index]);
  const fills = useMemo(() => (view ? Object.fromEntries(view.zones.map((z) => [z.id, z.intensity])) : undefined), [view]);
  const labels = useMemo(() => buildLabels(venue, plan, hazards, view), [venue, plan, hazards, view]);
  const labelRefs = useRef(new Map<string, HTMLElement>());
  const animating = !reducedMotion && hazards.length > 0;
  const underlay = useUnderlay(venue);
  const [underlayReady, setUnderlayReady] = useState(false);
  const [underlayShown, setUnderlayShown] = useState(true);
  const [underlayOpacity, setUnderlayOpacity] = useState(DEFAULT_UNDERLAY_OPACITY);
  const photo = underlay && underlayReady && underlayShown ? underlayOpacity : 0;
  const [showLabels, setShowLabels] = useState(true);
  // A video walkthrough's light floors: room labels get a dark backing.
  const lit = hasLooks(venue);

  const choose = useCallback((next: CameraPreset) => {
    setPreset(next);
    setNonce((n) => n + 1);
  }, []);
  const onDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  };
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const point = pickRef.current?.(event.clientX, event.clientY);
    if (point) onPlace(point);
  };

  return (
    <div
      className={lit ? 'twin-scene twin-scene--lit' : 'twin-scene'}
      role="group"
      aria-label={summary}
      style={{ cursor: armedType ? 'crosshair' : undefined }}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <Canvas
        dpr={[1, 1.5]}
        shadows={false}
        frameloop={animating ? 'always' : 'demand'}
        camera={{ fov: FOV, near: 0.5, far: 200, position: [20, 30, 10] }}
        gl={{ antialias: true, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => gl.setClearColor(PALETTE.canvas)}
      >
        {/* Soft model lighting: sky / ground fill, a warm key from the camera side (south-west) and a cool rim, so
            each wall face takes its own shade and the plan reads in depth without shadows or post-processing. */}
        <hemisphereLight args={['#e4eee8', '#0b100e', 1.0]} />
        <directionalLight position={[-14, 30, 22]} intensity={1.25} color="#fff3e4" />
        <directionalLight position={[24, 12, -18]} intensity={0.4} color="#a9c1d4" />
        {/* Keyed by geometry so a new venue with the same footprint still re-frames from scratch. */}
        <CameraRig key={venue.geometry_revision} extent={venue.extent} preset={preset} nonce={nonce} />
        <PickBridge pickRef={pickRef} />
        <LabelProjector labels={labels} refs={labelRefs} />
        {underlay && <Underlay underlay={underlay} extent={venue.extent} opacity={photo} onReady={setUnderlayReady} />}
        <Building venue={venue} plan={plan} fills={fills} underlayOpacity={photo} lowGraphics={lowGraphics} />
        <Furniture venue={venue} edit={props.furnitureEdit} />
        <Routes venue={venue} plan={plan} />
        <Doors venue={venue} plan={plan} reducedMotion={reducedMotion} gates={props.gates} />
        <ExitSigns venue={venue} plan={plan} reducedMotion={reducedMotion} />
        <Hazards
          plan={plan}
          hazards={hazards}
          selectedId={selectedHazardId}
          armed={armedType !== null}
          lowGraphics={lowGraphics}
          reducedMotion={reducedMotion}
          onSelect={onSelectHazard}
        />
        <DropPlane venue={venue} armedType={armedType} onPlace={onPlace} onEmptyClick={() => { onSelectHazard(null); if (!justDragged()) props.furnitureEdit?.onSelect(null); }} />
      </Canvas>
      <LabelLayer labels={labels} refs={labelRefs} hidden={!showLabels} />
      {view && <PlaybackBar view={view} playback={playback} />}
      {underlay && underlayReady && (
        <UnderlayControl label={underlay.provenanceLabel} shown={underlayShown} opacity={underlayOpacity}
          onShown={setUnderlayShown} onOpacity={setUnderlayOpacity} />
      )}
      <div className="twin-presets">
        <button type="button" onClick={() => setShowLabels((on) => !on)} aria-pressed={showLabels}>Labels</button>
        <button type="button" onClick={() => choose('overview')} aria-pressed={preset === 'overview'}>Overview</button>
        <button type="button" onClick={() => choose('top')} aria-pressed={preset === 'top'}>Top</button>
      </div>
    </div>
  );
}
