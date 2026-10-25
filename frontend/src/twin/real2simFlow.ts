import { ApiError } from '../api/client.ts';
import { MAX_CONTROLLABLE_DOORS, REAL2SIM_ERRORS, parseDraftEvent, pipelineErrorMessage } from '../api/real2sim.ts';
import type {
  AcceptRequest, AcceptResponse, CreateDraftRequest, CreateDraftResponse, CritiqueRound, DraftChecks, DraftCounts, DraftEvent, DraftStatus, DraftView, Provenance,
} from '../api/real2sim.ts';
import type { Real2SimStage } from './real2simView.ts';

/** One draft session, pure and testable: idle -> uploading -> extracting -> checking -> [critiquing] -> ready ->
 *  accepting -> accepted | failed. Progress comes from the draft's SSE stream; if the stream fails the flow polls the
 *  draft view every 1.5 s instead. No React in here: the hook only subscribes to `onState`.
 *
 *  Request identity (DESIGN.md: "Clearing a workflow invalidates outstanding UI request identities"): every start and
 *  every reset bumps `epoch`. Each async continuation, SSE listener and poll timer captures the epoch it was born in and
 *  does nothing when it no longer matches, so a late stream event or response after "Start over" cannot repopulate the
 *  cleared panel. A closed EventSource may still deliver events already queued; the epoch check drops them. */

export const MAX_THOUGHTS = 120;
export const MAX_THOUGHT_CHARS = 1500;
export const POLL_MS = 1500;
const MAX_POLL_FAILURES = 5;

export interface FlowThought { id: string; phase: string; text: string; recorded: boolean }

export interface Real2SimState {
  stage: Real2SimStage;
  /** Increases with every start/reset; a UI keyed on it drops stale local state (selection, form text). */
  epoch: number;
  draftId: string | null;
  revision: number | null;
  startedAt: number | null;
  finishedAt: number | null;
  provenance: Provenance | null;
  /** The server's wording, shown verbatim wherever the draft is shown. */
  provenanceLabel: string | null;
  name: string | null;
  thoughts: FlowThought[];
  counts: DraftCounts | null;
  unreadable: string[];
  dropped: string[];
  repaired: string[];
  checks: DraftChecks | null;
  rounds: CritiqueRound[];
  critiqueNote: string | null;
  /** The last full view; set at done/failed and by polling. Carries candidates, blockers and receipts. */
  view: DraftView | null;
  transport: 'sse' | 'polling' | null;
  /** Why the draft failed (stage "failed"): judge-readable copy and the machine code. */
  error: string | null;
  errorCode: string | null;
  /** A refused Accept (stage stays "ready"). */
  acceptError: string | null;
  /** A refreshed-after-conflict notice (stage stays "ready"). */
  acceptNotice: string | null;
  accepted: AcceptResponse | null;
}

export const idleState = (epoch = 0): Real2SimState => ({
  stage: 'idle', epoch, draftId: null, revision: null, startedAt: null, finishedAt: null, provenance: null, provenanceLabel: null, name: null,
  thoughts: [], counts: null, unreadable: [], dropped: [], repaired: [], checks: null, rounds: [], critiqueNote: null, view: null, transport: null,
  error: null, errorCode: null, acceptError: null, acceptNotice: null, accepted: null,
});

/** The subset of EventSource the flow uses; the real one and test fakes both satisfy it. */
export interface EventSourceLike {
  addEventListener(type: string, listener: (event: { data?: unknown }) => void): void;
  close(): void;
}

export interface Real2SimDeps {
  createDraft: (request: CreateDraftRequest) => Promise<CreateDraftResponse>;
  fetchDraft: (draftId: string) => Promise<DraftView>;
  acceptDraft: (draftId: string, request: AcceptRequest) => Promise<AcceptResponse>;
  openEvents: (draftId: string) => EventSourceLike;
  onState: (state: Real2SimState) => void;
  now?: () => number;
  pollMs?: number;
}

export interface AcceptOptions { controllableDoors: string[]; headcount?: number; buildingWidthM?: number; makeActive?: boolean; leftOutRooms?: string[] }

const STREAM_EVENTS = ['status', 'thought', 'draft', 'checks', 'round', 'done', 'error'] as const;
const RANK: Record<Real2SimStage, number> = { idle: 0, uploading: 1, extracting: 2, checking: 3, critiquing: 4, ready: 5, accepting: 6, accepted: 7, failed: 7 };
const RUNNING: readonly Real2SimStage[] = ['uploading', 'extracting', 'checking', 'critiquing'];
export const isRunning = (stage: Real2SimStage) => RUNNING.includes(stage);

const errorOf = (error: unknown, fallback: string): { message: string; code: string; status: number } =>
  error instanceof ApiError ? { message: error.message, code: error.detail, status: error.status } : { message: fallback, code: '', status: 0 };

/** The view's counts when the stream's `draft` event was missed (polling): count the draft's own lists. */
function countsFromDraft(draft: Record<string, unknown> | null): DraftCounts | null {
  if (!draft) return null;
  const size = (key: string) => Array.isArray(draft[key]) ? (draft[key] as unknown[]).length : null;
  const rooms = size('rooms'), doors = size('doors'), exits = size('exits');
  return rooms == null || doors == null || exits == null ? null : { rooms, doors, exits };
}

export function createReal2SimFlow(deps: Real2SimDeps) {
  const now = deps.now ?? Date.now;
  const pollMs = deps.pollMs ?? POLL_MS;
  let epoch = 0;
  let state = idleState(0);
  let source: EventSourceLike | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const publish = (patch: Partial<Real2SimState>) => { state = { ...state, ...patch }; deps.onState(state); };
  const closeTransport = () => {
    source?.close(); source = null;
    if (timer) { clearTimeout(timer); timer = null; }
  };
  /** Stage only moves forward while a draft is running; terminal stages are set explicitly. */
  const advance = (stage: Real2SimStage): Partial<Real2SimState> => RANK[stage] >= RANK[state.stage] && !['ready', 'accepting', 'accepted', 'failed'].includes(state.stage) ? { stage } : {};
  const stageOf = (status: DraftStatus): Real2SimStage => status;

  function appendThought(thought: { phase: string; index?: number; text: string; recorded: boolean }) {
    const id = `${thought.phase}:${thought.index ?? state.thoughts.length}`;
    // A replayed or re-delivered event (SSE reconnect, poll merge) carries the same phase:index: keep one copy.
    if (thought.index !== undefined && state.thoughts.some(item => item.id === id)) return {};
    const next = [...state.thoughts, { id, phase: thought.phase, text: thought.text.slice(0, MAX_THOUGHT_CHARS), recorded: thought.recorded }];
    return { thoughts: next.slice(-MAX_THOUGHTS) };
  }

  /** Folds a full view into state. `terminal` decides whether the stage follows the view's status. */
  function applyView(view: DraftView): Partial<Real2SimState> {
    const patch: Partial<Real2SimState> = {
      view, revision: view.revision, provenance: view.provenance, provenanceLabel: view.provenance_label, name: view.name ?? state.name,
      rounds: view.rounds.length >= state.rounds.length ? view.rounds : state.rounds, critiqueNote: view.critique_note ?? state.critiqueNote,
    };
    if (view.checks) patch.checks = view.checks;
    if (view.draft) {
      patch.unreadable = view.unreadable; patch.dropped = view.dropped; patch.repaired = view.repaired;
      patch.counts = countsFromDraft(view.draft) ?? state.counts;
    }
    if (view.thoughts.length >= state.thoughts.length) {
      patch.thoughts = view.thoughts.slice(-MAX_THOUGHTS).map((thought, position) => ({
        id: `${thought.phase}:${thought.index ?? position}`, phase: thought.phase, text: thought.text.slice(0, MAX_THOUGHT_CHARS), recorded: thought.recorded,
      }));
    }
    return patch;
  }

  function failWith(code: string, extra: Partial<Real2SimState> = {}) {
    closeTransport();
    publish({ ...extra, stage: 'failed', errorCode: code, error: extra.error ?? pipelineErrorMessage(code), finishedAt: now() });
  }

  /** Settles a draft from its view (end of stream, or a poll): the stage follows the server's status. */
  function settle(view: DraftView) {
    const patch = applyView(view);
    if (view.status === 'ready') { closeTransport(); publish({ ...patch, stage: 'ready', finishedAt: now(), error: null, errorCode: null }); }
    else if (view.status === 'accepted') { closeTransport(); publish({ ...patch, stage: 'accepted', finishedAt: now() }); }
    else if (view.status === 'failed') failWith(view.errors[view.errors.length - 1] ?? 'unknown', patch);
    else publish({ ...patch, ...advance(stageOf(view.status)) });
  }

  async function finish(myEpoch: number, draftId: string, event: Extract<DraftEvent, { name: 'done' | 'error' }>) {
    closeTransport();
    try {
      const view = await deps.fetchDraft(draftId);
      if (myEpoch !== epoch) return;
      // A server `error` event is authoritative even if the view were somehow still in progress.
      if (event.name === 'error' && view.status !== 'failed') failWith(event.code, applyView(view));
      else settle(view);
    } catch (error) {
      if (myEpoch !== epoch) return;
      if (event.name === 'error') failWith(event.code);
      else failWith('view_unavailable', { error: errorOf(error, 'The finished draft could not be loaded.').message });
    }
  }

  function onEvent(myEpoch: number, draftId: string, event: DraftEvent) {
    if (myEpoch !== epoch) return;
    switch (event.name) {
      case 'status': publish({ ...(isRunning(stageOf(event.status)) ? advance(stageOf(event.status)) : {}), revision: event.revision, provenance: event.provenance ?? state.provenance }); break;
      case 'thought': publish(appendThought(event.thought)); break;
      case 'draft': publish({ counts: event.counts ?? state.counts, unreadable: event.unreadable, dropped: event.dropped, repaired: event.repaired }); break;
      case 'checks': publish({ checks: event.checks }); break;
      case 'round': publish({ rounds: [...state.rounds.filter(round => round.round !== event.round.round), event.round].sort((a, b) => a.round - b.round) }); break;
      case 'done': case 'error': void finish(myEpoch, draftId, event); break;
    }
  }

  function startPolling(myEpoch: number, draftId: string) {
    closeTransport();
    publish({ transport: 'polling' });
    let failures = 0;
    const tick = async () => {
      timer = null;
      try {
        const view = await deps.fetchDraft(draftId);
        if (myEpoch !== epoch) return;
        failures = 0;
        settle(view);
        if (!['ready', 'accepted', 'failed'].includes(view.status)) timer = setTimeout(tick, pollMs);
      } catch (error) {
        if (myEpoch !== epoch) return;
        const info = errorOf(error, '');
        failures += 1;
        if (info.status === 404 || failures >= MAX_POLL_FAILURES) {
          failWith(info.status === 404 ? 'unknown_draft' : 'view_unavailable', { error: info.status === 404 ? REAL2SIM_ERRORS.unknown_draft : 'Lost contact with the server while reading. Start over.' });
          return;
        }
        timer = setTimeout(tick, pollMs);
      }
    };
    timer = setTimeout(tick, pollMs);
  }

  function openStream(myEpoch: number, draftId: string) {
    let stream: EventSourceLike;
    try { stream = deps.openEvents(draftId); } catch { startPolling(myEpoch, draftId); return; }
    source = stream;
    publish({ transport: 'sse' });
    for (const name of STREAM_EVENTS) {
      stream.addEventListener(name, raw => {
        if (myEpoch !== epoch || source !== stream) return;
        // The browser fires a data-less `error` Event for connection trouble and a MessageEvent for the server's own
        // `error` event: only the latter carries data. Connection trouble means: stop streaming, poll instead.
        if (typeof raw.data !== 'string') {
          if (name === 'error') startPolling(myEpoch, draftId);
          return;
        }
        const parsed = parseDraftEvent(name, raw.data);
        if (parsed) onEvent(myEpoch, draftId, parsed);
      });
    }
  }

  /** After create: pick up the server's provenance label and name right away (events carry only the provenance code). */
  async function loadLabel(myEpoch: number, draftId: string) {
    try {
      const view = await deps.fetchDraft(draftId);
      if (myEpoch !== epoch || RANK[state.stage] >= RANK.ready) return;
      publish({ provenance: view.provenance, provenanceLabel: view.provenance_label, name: view.name ?? state.name });
    } catch { /* The label is also set from the final view; a missed early fetch changes nothing. */ }
  }

  async function begin(makeRequest: () => Promise<CreateDraftRequest>) {
    closeTransport();
    const myEpoch = ++epoch;
    state = { ...idleState(myEpoch), stage: 'uploading', startedAt: now() };
    deps.onState(state);
    try {
      const response = await deps.createDraft(await makeRequest());
      if (myEpoch !== epoch) return;
      publish({ draftId: response.draft_id, revision: response.revision, ...advance(stageOf(response.status)) });
      void loadLabel(myEpoch, response.draft_id);
      openStream(myEpoch, response.draft_id);
    } catch (error) {
      if (myEpoch !== epoch) return;
      const info = errorOf(error, 'The drawing could not be sent. Try again.');
      publish({ stage: 'failed', error: info.message, errorCode: info.code || 'request_failed', finishedAt: now() });
    }
  }

  return {
    getState: () => state,
    /** `prepare` runs inside the "uploading" stage (file read, downscale, base64) so the panel shows progress at once. */
    startLive: (prepare: () => Promise<CreateDraftRequest>) => begin(prepare),
    startSaved: (fixtureId: string, name?: string) => begin(async () => ({ mode: 'fixture', fixture_id: fixtureId, ...(name ? { name } : {}) })),

    async accept(options: AcceptOptions) {
      const myEpoch = epoch;
      if (state.stage !== 'ready' || !state.draftId || state.revision === null) return;
      const max = state.view?.max_controllable_doors ?? MAX_CONTROLLABLE_DOORS;
      if (options.controllableDoors.length > max) { publish({ acceptError: REAL2SIM_ERRORS.too_many_controllable_doors }); return; }
      const draftId = state.draftId;
      const request: AcceptRequest = {
        expected_revision: state.revision, controllable_doors: options.controllableDoors, make_active: options.makeActive ?? true,
        ...(options.headcount !== undefined ? { headcount: options.headcount } : {}),
        ...(options.buildingWidthM !== undefined ? { building_width_m: options.buildingWidthM } : {}),
        ...(options.leftOutRooms?.length ? { left_out_rooms: options.leftOutRooms } : {}),
      };
      publish({ stage: 'accepting', acceptError: null, acceptNotice: null });
      try {
        const accepted = await deps.acceptDraft(draftId, request);
        if (myEpoch !== epoch) return;
        publish({ stage: 'accepted', accepted, finishedAt: now(), revision: accepted.draft_revision });
      } catch (error) {
        if (myEpoch !== epoch) return;
        const info = errorOf(error, 'The building could not be accepted. Try again.');
        if (info.status === 409) {
          // Stale revision (or the draft moved on): refetch so the next Accept carries the current revision.
          try {
            const view = await deps.fetchDraft(draftId);
            if (myEpoch !== epoch) return;
            if (view.status === 'ready') publish({ ...applyView(view), stage: 'ready', acceptNotice: info.message });
            else settle(view);
          } catch (refreshError) {
            if (myEpoch !== epoch) return;
            publish({ stage: 'ready', acceptError: errorOf(refreshError, info.message).message });
          }
          return;
        }
        publish({ stage: 'ready', acceptError: info.message });
      }
    },

    /** Re-reads a ready draft after a change made outside the flow (a furniture edit): new revision and preview. */
    async refresh() {
      const myEpoch = epoch;
      if (state.stage !== 'ready' || !state.draftId) return;
      try {
        const view = await deps.fetchDraft(state.draftId);
        if (myEpoch !== epoch || state.stage !== 'ready') return;
        publish({ ...applyView(view), acceptError: null, acceptNotice: null });
      } catch (error) {
        if (myEpoch !== epoch) return;
        publish({ acceptError: errorOf(error, 'The draft could not be refreshed.').message });
      }
    },

    /** "Start over" / unmount: invalidates every outstanding request, stream and timer. */
    reset() {
      closeTransport();
      epoch += 1;
      state = idleState(epoch);
      deps.onState(state);
    },
    dispose() { closeTransport(); epoch += 1; },
  };
}

export type Real2SimFlow = ReturnType<typeof createReal2SimFlow>;
