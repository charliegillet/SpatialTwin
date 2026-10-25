import { useEffect, useState } from 'react';
import { prefersReducedMotion } from '../scene/webgl';
import type { TwinController } from '../twin/useTwin';
import type { DoorAgentMode, TwinMode } from '../twin/types';
import { cameraCardsLabel } from '../twin/camera';
import { twinChips, twinHero } from '../twin/twinHero';
import { toHazardInputs } from '../twin/placement';
import { useDoorAgent } from '../twin/useDoorAgent';
import { CameraPanel } from './CameraPanel';
import { DoorPlanBar } from './DoorPlanBar';
import { HazardToolbar } from './HazardToolbar';
import { LightsPanel } from './LightsPanel';
import { TwinHeroView } from './TwinHero';
import { TwinStage } from './TwinStage';
import { ZoneList } from './ZoneList';
import './TwinStage.css';

/** Everything the Simulation mode puts in the main grid: side column, scene, hero overlay and door plan. */
export function TwinWorkspace({ twin, notice, mode, calibrateTick, imageFile, analysisMode }: { twin: TwinController; notice: string | null; mode: TwinMode; calibrateTick: number; imageFile: File | null; analysisMode: DoorAgentMode }) {
  const { venue, flow } = twin;
  const reducedMotion = prefersReducedMotion();
  const plan = flow.plan;
  const pending = flow.status === 'pending';
  const agent = useDoorAgent({ hazards: toHazardInputs(twin.hazards), plan, pending, mode, analysisMode });
  const [seed, setSeed] = useState<'live' | 'fixture' | null>(null);
  const hasCamera = twin.hazards.some(item => item.source === 'camera');
  useEffect(() => { if (!hasCamera) setSeed(null); }, [hasCamera]);
  const hero = twinHero({ plan, pending, error: flow.status === 'error' ? flow.error : null });
  if (!venue) return <div className="twin-stage twin-loading" role="status">Loading the building…</div>;
  const zoneNames = Object.fromEntries(venue.zones.map(zone => [zone.id, zone.name]));
  const reference = plan ? `${plan.no_hazard_completed} of ${plan.chosen.initial_population} with no hazard` : undefined;
  return <>
    <div className="twin-side">
      {mode === 'camera' && <CameraPanel venue={venue} onConfirmed={twin.addCamera} calibrateTick={calibrateTick} imageFile={imageFile} onProvenance={setSeed} />}
      <HazardToolbar armed={twin.armed} onArm={twin.setArmed} smokeSeconds={twin.smokeSeconds} onSmokeStep={twin.stepSmoke} hazards={twin.hazards} zoneNames={zoneNames}
        selectedId={twin.selectedId} onSelect={twin.setSelectedId} onRemove={twin.remove} canUndo={twin.canUndo} onUndo={twin.undo} onClear={twin.clear} notice={notice} />
      <DoorPlanBar plan={plan} pending={pending} agent={agent} />
      <LightsPanel venue={venue} plan={plan} reducedMotion={reducedMotion} />
      <ZoneList venue={venue} hazards={twin.hazards} armed={twin.armed} onPlaceInZone={twin.placeInZone} />
    </div>
    <TwinStage venue={venue} plan={plan} hazards={twin.hazards} armedType={twin.armed} selectedHazardId={twin.selectedId} lowGraphics={false}
      reducedMotion={reducedMotion} onPlace={point => twin.place(point)} onSelectHazard={twin.setSelectedId} />
    <div className="stage-chips twin-hero"><TwinHeroView hero={hero} chips={[...twinChips(plan, twin.fixtureVenue), ...(cameraCardsLabel(twin.hazards, plan, seed) ?? [])]} title={reference} /></div>
  </>;
}
