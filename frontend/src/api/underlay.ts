// GET /api/venues/{venue_id}/underlay: where the accepted venue's source photo lies, in venue metres (local only).
import { ApiError, requestJson } from './client.ts';
import { NO_PHOTO_VENUES, parseUnderlay, type UnderlayAnswer } from '../twin/underlay.ts';

/** Never throws: a missing route (an older server), an unknown venue or a network failure all mean "no photo". */
export async function fetchUnderlay(venueId: string, signal?: AbortSignal): Promise<UnderlayAnswer> {
  if (NO_PHOTO_VENUES.has(venueId)) return { available: false, reason: 'no_source_image' };
  try {
    const raw = await requestJson<unknown>(`/api/venues/${encodeURIComponent(venueId)}/underlay`, {
      signal, timeoutMs: 10_000, fallback: 'The map photo could not be loaded',
    });
    return parseUnderlay(raw, venueId);
  } catch (error) {
    if (signal?.aborted) throw error;
    return { available: false, reason: error instanceof ApiError ? `http_${error.status}` : 'network_error' };
  }
}
