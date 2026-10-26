import { BUILTIN_VENUE_ID } from '../api/twin.ts';

/** The demo venue: where "Next judge" returns. The presenter's pick in the menu, kept in this browser (it is the
 *  presenter laptop's setting); without one, the venue the server had active when this screen opened. A judge's own
 *  accepted building is never the home: the next judge starts on the prepared venue again. */
export const HOME_VENUE_KEY = 'spatialtwin.homeVenue';

interface StorageLike { getItem(key: string): string | null; setItem(key: string, value: string): void }

const storage = (): StorageLike | null => {
  try { return typeof localStorage === 'undefined' ? null : localStorage; } catch { return null; }
};

export function readHomeVenue(store: StorageLike | null = storage()): string | null {
  try { return store?.getItem(HOME_VENUE_KEY) || null; } catch { return null; }
}

export function writeHomeVenue(venueId: string, store: StorageLike | null = storage()): void {
  try { store?.setItem(HOME_VENUE_KEY, venueId); } catch { /* private window: the load-time venue still applies */ }
}

/** Where Next judge goes: the chosen home if it still exists, else the venue active at load, else the built-in. */
export function nextJudgeVenue(home: string | null, loaded: string | null, known: readonly string[]): string {
  if (home && known.includes(home)) return home;
  if (loaded && known.includes(loaded)) return loaded;
  return BUILTIN_VENUE_ID;
}
