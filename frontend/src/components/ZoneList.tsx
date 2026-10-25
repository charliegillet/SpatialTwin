import { useId, useState, type KeyboardEvent } from 'react';
import type { HazardType, PlacedHazard, VenueV2 } from '../twin/types';
import { hazardLabel } from '../twin/hazardModel';

interface Props {
  venue: VenueV2;
  hazards: PlacedHazard[];
  armed: HazardType | null;
  onPlaceInZone: (zoneId: string) => void;
}

/** Keyboard route to the floor: arrow to a room, Enter places the armed hazard at its centre. */
export function ZoneList({ venue, hazards, armed, onPlaceInZone }: Props) {
  const uid = useId();
  const [active, setActive] = useState(0);
  const zones = venue.zones;
  const move = (delta: number) => setActive(current => (current + delta + zones.length) % zones.length);
  const onKeyDown = (event: KeyboardEvent) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(-1); }
    else if (event.key === 'Home') { event.preventDefault(); setActive(0); }
    else if (event.key === 'End') { event.preventDefault(); setActive(zones.length - 1); }
    else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onPlaceInZone(zones[active].id); }
  };
  return <details className="twin-zones">
    <summary>Place by room</summary>
    <ul role="listbox" tabIndex={0} aria-label={armed ? `Rooms. Enter places ${hazardLabel(armed)}` : 'Rooms. Pick a hazard first'} aria-activedescendant={`${uid}-${zones[active].id}`} onKeyDown={onKeyDown}>
      {zones.map((zone, index) => {
        const inside = hazards.filter(item => item.zone_id === zone.id);
        return <li key={zone.id} id={`${uid}-${zone.id}`} role="option" aria-selected={index === active} className={index === active ? 'is-active' : undefined}
          onClick={() => { setActive(index); onPlaceInZone(zone.id); }}>
          <span>{zone.name}</span>
          <small>{inside.length ? inside.map(item => hazardLabel(item.type)).join(', ') : zone.initial_occupants ? `${zone.initial_occupants} people` : ''}</small>
        </li>;
      })}
    </ul>
  </details>;
}
