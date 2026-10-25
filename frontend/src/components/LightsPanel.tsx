import { NO_CHECKED_PLAN, planChecked } from '../twin/twinHero';
import { legendFor, LIGHTS_TITLE, lightsView } from '../twin/lightsView';
import type { DoorPlanResponse, VenueV2 } from '../twin/types';

/** The 24 on-screen pixels of the exit signs, grouped by element. A mirror of the model output, not the hardware. */
export function LightsPanel({ venue, plan, reducedMotion }: { venue: VenueV2; plan: DoorPlanResponse | null; reducedMotion: boolean }) {
  const groups = lightsView(plan, venue.led_map, reducedMotion);
  const legend = legendFor(groups);
  return <section className="twin-lights" aria-label={LIGHTS_TITLE}>
    <h3>{LIGHTS_TITLE}</h3>
    {groups.length === 0 ? <p className="twin-quiet">{plan && !planChecked(plan) ? NO_CHECKED_PLAN : 'Waiting for a plan.'}</p> : <>
      <div className="twin-light-groups">
        {groups.map(group => <div key={group.id} className="twin-light-group">
          <span className="twin-light-id">{group.id}</span>
          <div className="twin-light-row">{group.pixels.map(pixel => <i key={pixel.index} className={`px px-${pixel.meaning.tone}${pixel.flashing ? ' is-flash' : ''}`} title={`${group.id} · ${pixel.meaning.label} (${pixel.code})`} />)}</div>
        </div>)}
      </div>
      <ul className="twin-legend">{legend.map(item => <li key={item.code}><i className={`px px-${item.meaning.tone}`} aria-hidden="true" />{item.meaning.label}{item.meaning.flashing && !reducedMotion ? ' · flashes' : ''}</li>)}</ul>
    </>}
  </section>;
}
