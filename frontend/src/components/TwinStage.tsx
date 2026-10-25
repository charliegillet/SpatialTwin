import { lazy, Suspense, useEffect, useMemo } from 'react';
import TwinPlan2D from '../scene/TwinPlan2D';
import SceneErrorBoundary from '../scene/SceneErrorBoundary';
import { canUseWebGL } from '../scene/webgl';
import type { TwinScene3DProps } from '../twin/types';

/** The 3D chunk (three.js). Loaded by the lazy import below or warmed at idle by preloadScene3D. */
const loadScene3D = () => import('../scene/TwinScene3D');
const Scene3D = lazy(loadScene3D);

/** Warms the chunk after first load so the switch to Simulation is instant. Skipped when WebGL is missing. */
export function preloadScene3D(): () => void {
  if (typeof window === 'undefined' || !canUseWebGL()) return () => undefined;
  const run = () => { void loadScene3D().catch(() => undefined); };
  const idle = (window as Window & { requestIdleCallback?: (cb: () => void, options?: { timeout: number }) => number; cancelIdleCallback?: (id: number) => void });
  if (idle.requestIdleCallback) {
    const id = idle.requestIdleCallback(run, { timeout: 4000 });
    return () => idle.cancelIdleCallback?.(id);
  }
  const timer = window.setTimeout(run, 1500);
  return () => window.clearTimeout(timer);
}

/** Scene area: 3D when WebGL works, otherwise the SVG plan. A failing 3D chunk drops to the plan too. */
export function TwinStage(props: TwinScene3DProps) {
  const webgl = useMemo(canUseWebGL, []);
  useEffect(() => { if (webgl) void loadScene3D().catch(() => undefined); }, [webgl]);
  const plan2d = <TwinPlan2D {...props} />;
  return <div className="twin-stage" role="group" aria-label="Building model">
    {webgl
      ? <SceneErrorBoundary fallback={plan2d}><Suspense fallback={plan2d}><Scene3D {...props} /></Suspense></SceneErrorBoundary>
      : plan2d}
  </div>;
}
