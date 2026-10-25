import { useCallback, useMemo, useRef, useState, type DragEvent } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import { playbackView } from '../twin/playback.ts';
import { ariaSummary } from '../twin/sceneModel.ts';
import type { TwinScene3DProps } from '../twin/types.ts';
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

export default function TwinScene3D(props: TwinScene3DProps) {
  const { venue, plan, hazards, armedType, selectedHazardId, lowGraphics, reducedMotion, onPlace, onSelectHazard } = props;
  const pickRef = useRef<Picker | null>(null);
  const [preset, setPreset] = useState<CameraPreset>('overview');
  const [nonce, setNonce] = useState(0);
  const [showLabels, setShowLabels] = useState(true);
  const summary = useMemo(() => ariaSummary(venue, plan, hazards), [venue, plan, hazards]);
  const playback = usePlayback(plan, reducedMotion);
  const view = useMemo(() => playbackView(venue, plan, playback.index), [venue, plan, playback.index]);
  const fills = useMemo(() => (view ? Object.fromEntries(view.zones.map((z) => [z.id, z.intensity])) : undefined), [view]);
  const labels = useMemo(() => buildLabels(venue, plan, hazards, view), [venue, plan, hazards, view]);
  const labelRefs = useRef(new Map<string, HTMLElement>());
  const animating = !reducedMotion && hazards.length > 0;
  // Video colours read true under neutral light; the dark twin keeps its green-grey wash.
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
        <ambientLight intensity={lit ? 1.15 : 1.3} color={lit ? '#ffffff' : '#a9bfb3'} />
        <directionalLight position={[10, 25, 12]} intensity={lit ? 1.1 : 0.9} color={lit ? '#ffffff' : '#dfeee6'} />
        {/* Keyed by geometry so a new venue with the same footprint still re-frames from scratch. */}
        <CameraRig key={venue.geometry_revision} extent={venue.extent} preset={preset} nonce={nonce} />
        <PickBridge pickRef={pickRef} />
        <LabelProjector labels={labels} refs={labelRefs} />
        <Building venue={venue} plan={plan} fills={fills} />
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
      <div className="twin-presets">
        <button type="button" onClick={() => setShowLabels((on) => !on)} aria-pressed={showLabels}>Labels</button>
        <button type="button" onClick={() => choose('overview')} aria-pressed={preset === 'overview'}>Overview</button>
        <button type="button" onClick={() => choose('top')} aria-pressed={preset === 'top'}>Top</button>
      </div>
    </div>
  );
}
