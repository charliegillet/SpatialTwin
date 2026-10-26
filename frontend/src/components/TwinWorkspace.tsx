import { useEffect, useState } from 'react';
import { prefersReducedMotion } from '../scene/webgl';
import type { TwinController } from '../twin/useTwin';
import type { DoorAgentMode, TwinMode, VenueV2 } from '../twin/types';
import { cameraCardsLabel } from '../twin/camera';
import { twinChips, twinHero, withFallback } from '../twin/twinHero';
import { toHazardInputs } from '../twin/placement';
import { useAgentTeam } from '../twin/useAgentTeam';
import { executingNote, failsafeAnnounceKey } from '../twin/incidentFlow';
import { useIncident } from '../twin/useIncident';
import { CameraPanel } from './CameraPanel';
import { DoorPlanBar } from './DoorPlanBar';
import { HazardToolbar } from './HazardToolbar';
import { IncidentPanel } from './IncidentPanel';
import { Real2SimPanel } from './Real2SimPanel';
import { SignsPanel } from './SignsPanel';
import { LightsPanel } from './LightsPanel';
import { TwinHeroView } from './TwinHero';
import { TwinStage } from './TwinStage';
import { ZoneList } from './ZoneList';
import './TwinStage.css';

/** Everything the twin modes put in the main grid: side column, scene, hero overlay and door plan.
 *  Build (Act 1) shows the Real2Sim panel beside the active building; Simulation and Camera twin add the incident
 *  panel, whose virtual gates also drive the 3D door leaves. */
export function TwinWorkspace({ twin, notice, mode, calibrateTick, imageFile, analysisMode, onBuilt }: { twin: TwinController; notice: string | null; mode: TwinMode; calibrateTick: number; imageFile: File | null; analysisMode: DoorAgentMode; onBuilt?: (venueId: string) => void }) {
  const { venue, flow } = twin;
  const reducedMotion = prefersReducedMotion();
  const plan = flow.plan;
  const pending = flow.status === 'pending';
  const building = mode === 'build';
  const hazardInputs = toHazardInputs(twin.hazards);
  // Live by default: the team starts by itself once the planner has a checked plan for the judge's hazards.
  const team = useAgentTeam({ hazards: hazardInputs, plan, pending, mode, analysisMode, venueId: twin.venueId, auto: !building });
  // One incident mirror per mount (one EventSource, one hazard sync); idle while a floor plan is being read.
  const incident = useIncident(twin.venueId, hazardInputs, { enabled: !building });
  const [seed, setSeed] = useState<'live' | 'fixture' | null>(null);
  const [preview, setPreview] = useState<VenueV2 | null>(null);
  const hasCamera = twin.hazards.some(item => item.source === 'camera');
  useEffect(() => { if (!hasCamera) setSeed(null); }, [hasCamera]);
  // Accepted venues are named after their floor plan; the built-in keeps its id.
  const listed = twin.venues.find(item => item.venue_id === twin.venueId);
  const hero = twinHero({ plan, pending, error: flow.status === 'error' ? flow.error : null, venueId: twin.venueId,
    venueName: listed && !listed.builtin ? listed.name : null });
  // After a jam (fallback) or once the fail-safe holds a gate closed, the doors follow the incident's own plan: the twin
  // draws that plan (routes, lamps, door list) and the hero says so. Otherwise the stateless plan is what the doors would
  // follow, so it is drawn as is.
  const executed = incident.executedPlan && incident.state.incident?.venue_id === twin.venueId ? incident.executedPlan : null;
  const summary = executed ? incident.state.plan : null;
  const drawn = executed ?? plan;
  const shown = withFallback(hero, summary && { valid: summary.valid, completed: summary.completed_crossings,
    population: summary.initial_population, stuck: summary.stuck_doors, held: summary.held_doors }, plan);
  const executedChip = summary ? (summary.stuck_doors.length ? 'Fallback in force' : 'Fail-safe plan') : null;
  const accepted = (venueId: string) => { twin.refreshVenues(); onBuilt?.(venueId); };
  if (building) return <>
    <div className="twin-side twin-build"><Real2SimPanel onAccepted={accepted} onPreview={setPreview} /></div>
    {preview && <div className="stage-chips twin-preview-chip"><span className="chip chip-warn">Draft preview · not accepted</span></div>}
    {preview ?? venue ? <TwinStage venue={(preview ?? venue)!} plan={null} hazards={[]} armedType={null} selectedHazardId={null} lowGraphics={false}
      reducedMotion={reducedMotion} onPlace={() => undefined} onSelectHazard={() => undefined} />
      : <div className="twin-stage twin-loading" role="status">Loading the building…</div>}
  </>;
  if (!venue) return <div className="twin-stage twin-loading" role="status">Loading the building…</div>;
  const zoneNames = Object.fromEntries(venue.zones.map(zone => [zone.id, zone.name]));
  const reference = plan ? `${plan.no_hazard_completed} of ${plan.chosen.initial_population} with no hazard` : undefined;
  return <>
    <div className="twin-side">
      {mode === 'camera' && <CameraPanel venue={venue} onConfirmed={twin.addCamera} calibrateTick={calibrateTick} imageFile={imageFile} onProvenance={setSeed} />}
      <HazardToolbar armed={twin.armed} onArm={twin.setArmed} smokeSeconds={twin.smokeSeconds} onSmokeStep={twin.stepSmoke} hazards={twin.hazards} zoneNames={zoneNames}
        selectedId={twin.selectedId} onSelect={twin.setSelectedId} onRemove={twin.remove} canUndo={twin.canUndo} onUndo={twin.undo} onClear={twin.clear} notice={notice} />
      <DoorPlanBar plan={drawn} pending={pending} team={team} gates={incident.state.gates} executing={executingNote(summary)}
        announceKey={failsafeAnnounceKey(incident.state.incident, drawn?.chosen.candidate_hash ?? null, incident.hazardsSynced)} />
      <IncidentPanel incident={incident} />
      <SignsPanel venue={venue} onConfirmed={hazard => twin.addCamera([hazard])} />
      <LightsPanel venue={venue} plan={drawn} reducedMotion={reducedMotion} />
      <ZoneList venue={venue} hazards={twin.hazards} armed={twin.armed} onPlaceInZone={twin.placeInZone} />
    </div>
    <TwinStage venue={venue} plan={drawn} hazards={twin.hazards} armedType={twin.armed} selectedHazardId={twin.selectedId} lowGraphics={false}
      reducedMotion={reducedMotion} onPlace={point => twin.place(point)} onSelectHazard={twin.setSelectedId} gates={incident.doors} />
    <div className="stage-chips twin-hero"><TwinHeroView hero={shown} chips={[...twinChips(plan, twin.fixtureVenue), ...(executedChip ? [executedChip] : []), ...(incident.state.failsafe.armed ? ['Fail-safe armed'] : []), ...(cameraCardsLabel(twin.hazards, plan, seed) ?? [])]} title={reference} /></div>
  </>;
}
