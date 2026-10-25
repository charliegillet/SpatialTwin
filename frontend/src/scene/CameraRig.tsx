import { useEffect } from 'react';
import { useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib';
import { frameFootprint } from './frame.ts';
import type { Point2 } from '../twin/types.ts';

export type CameraPreset = 'overview' | 'top';
export const FOV = 40;
const POLAR: Record<CameraPreset, number> = { overview: 0.72, top: 0.12 };

export default function CameraRig({ extent, preset, nonce }: { extent: Point2; preset: CameraPreset; nonce: number }) {
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;
  const { camera, size, invalidate } = useThree();
  const aspect = size.width / Math.max(size.height, 1);
  // Narrow portrait viewports get a steeper view so the plan uses the available height.
  const polar = preset === 'overview' && aspect < 0.8 ? 0.4 : POLAR[preset];
  // Wide stages keep the top band free for the hero overlay; phones use the whole canvas.
  const topBand = size.width >= 700 ? 0.22 : 0;
  const framing = frameFootprint(extent, FOV, aspect, polar, 0.08, topBand);
  const distance = framing.distance;

  useEffect(() => {
    camera.position.copy(framing.position);
    controls?.target.copy(framing.target);
    controls?.update();
    camera.lookAt(framing.target);
    invalidate();
    // Re-frame on preset change or when the viewport shape changes, not on every render.
  }, [preset, nonce, Math.round(aspect * 20), Math.round(size.width / 50), controls]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <OrbitControls
      makeDefault
      enablePan={false}
      enableDamping
      dampingFactor={0.12}
      minPolarAngle={0.08}
      maxPolarAngle={1.3}
      minAzimuthAngle={-1.0}
      maxAzimuthAngle={1.0}
      minDistance={14}
      maxDistance={distance * 1.35}
    />
  );
}
