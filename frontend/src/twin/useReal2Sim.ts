import { useCallback, useEffect, useRef, useState } from 'react';
import { acceptDraft, createDraft, eventsUrl, fetchDraft, fetchSavedRuns, prepareSource } from '../api/real2sim.ts';
import type { AcceptResponse, SavedRun, SourceKind } from '../api/real2sim.ts';
import { createReal2SimFlow, idleState, type AcceptOptions, type EventSourceLike, type Real2SimFlow, type Real2SimState } from './real2simFlow.ts';

export interface Real2SimController {
  state: Real2SimState;
  /** `null` while loading; `[]` with `savedEnabled` false means saved runs are switched off on this server. */
  saved: SavedRun[] | null;
  savedEnabled: boolean;
  savedError: string | null;
  /** Reads the picked file (downscaling big photos), uploads it and starts the live reading. */
  startFile: (file: File, kind: SourceKind, name?: string) => void;
  startSaved: (fixtureId: string) => void;
  accept: (options: AcceptOptions) => void;
  /** "Start over": drops the draft and every outstanding stream, timer and response. */
  reset: () => void;
  reloadSaved: () => void;
}

/** React shell over the pure Real2Sim flow. `onAccepted` fires once per accepted draft with the new venue id so the host
 *  can switch the twin to it; the panel touches nothing else global. */
export function useReal2Sim(onAccepted?: (venueId: string, accepted: AcceptResponse) => void): Real2SimController {
  const [state, setState] = useState<Real2SimState>(() => idleState());
  const [saved, setSaved] = useState<SavedRun[] | null>(null);
  const [savedEnabled, setSavedEnabled] = useState(true);
  const [savedError, setSavedError] = useState<string | null>(null);
  const flowRef = useRef<Real2SimFlow | null>(null);
  if (!flowRef.current) {
    flowRef.current = createReal2SimFlow({
      createDraft: request => createDraft(request),
      fetchDraft: id => fetchDraft(id),
      acceptDraft: (id, request) => acceptDraft(id, request),
      openEvents: id => new EventSource(eventsUrl(id)) as unknown as EventSourceLike,
      onState: setState,
    });
  }
  const flow = flowRef.current;

  const notified = useRef<string | null>(null);
  const onAcceptedRef = useRef(onAccepted);
  onAcceptedRef.current = onAccepted;
  useEffect(() => {
    if (state.stage !== 'accepted' || !state.accepted || notified.current === state.accepted.venue_id) return;
    notified.current = state.accepted.venue_id;
    onAcceptedRef.current?.(state.accepted.venue_id, state.accepted);
  }, [state.stage, state.accepted]);

  const loadSaved = useCallback(() => {
    const controller = new AbortController();
    setSavedError(null);
    fetchSavedRuns(controller.signal)
      .then(result => { setSaved(result.saved); setSavedEnabled(result.fixtures_enabled); })
      .catch(error => { if (!controller.signal.aborted) { setSaved([]); setSavedError(error instanceof Error ? error.message : 'Saved runs could not be listed.'); } });
    return () => controller.abort();
  }, []);
  useEffect(() => loadSaved(), [loadSaved]);
  // Unmount ("Next judge", mode switch): drop the stream and any pending response.
  useEffect(() => () => flow.dispose(), [flow]);

  const startFile = useCallback((file: File, kind: SourceKind, name?: string) => {
    void flow.startLive(async () => {
      const prepared = await prepareSource(file, kind);
      return { mode: 'live', image_base64: prepared.image_base64, mime_type: prepared.mime_type, source_kind: prepared.source_kind, ...(name ? { name } : {}) };
    });
  }, [flow]);
  const startSaved = useCallback((fixtureId: string) => { void flow.startSaved(fixtureId); }, [flow]);
  const accept = useCallback((options: AcceptOptions) => { void flow.accept(options); }, [flow]);
  const reset = useCallback(() => flow.reset(), [flow]);

  return { state, saved, savedEnabled, savedError, startFile, startSaved, accept, reset, reloadSaved: () => { loadSaved(); } };
}
