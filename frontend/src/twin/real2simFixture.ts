/** Test fixtures for the Real2Sim client and flow (shape follows docs/plans/contracts/real2sim-api.md). Not a test file. */
export const DRAFT_ID = 'r2s-b3a96db303b7a09e08bd3357';

export const makeView = (over: Record<string, unknown> = {}) => ({
  draft_id: DRAFT_ID, revision: 3, status: 'ready', mode: 'live', name: 'Meridian level 1',
  provenance: 'live', provenance_label: 'Live Gemini 4 Argon reading (proposal; checked locally, accepted by an operator)',
  draft: { rooms: [{}, {}], doors: [{}], exits: [{}] },
  unreadable: ['smudged label top left'], dropped: ['door KD9: joins unknown or identical room ATTIC'], repaired: ['room LIVING: name shortened'],
  checks: { issues: [{ code: 'door_narrow', severity: 'warning', message: 'Door is narrow', element_ids: ['D1'] }], errors: 0, warnings: 1, compile_error: null, geometry_revision: 'geom-1' },
  rounds: [], critique_note: null,
  thoughts: [{ phase: 'extract', text: '**Reading the walls** ...', recorded: false }],
  receipts: [{ phase: 'extract', status: 'completed', provenance: 'live', provider_model: 'gemini-4-argon', interaction_id_hash: 'a1b2c3d4e5f60718', token_usage: { total_tokens: 23000 }, latency_ms: 28740.1, thinking_level: 'medium', streamed: true, errors: [] }],
  errors: [], overlay_available: true, topdown_available: true, accepted: null,
  controllable_door_candidates: [
    { key: 'KD1', between: ['LIVING', 'HALL'], room_names: ['Living', 'Hall'], symbol: 'swing', confidence: 0.9, venue_door_id: 'D1' },
    { key: 'KD2', between: ['HALL', 'BATH'], room_names: ['Hall', 'Bath'], symbol: 'swing', confidence: 0.8, venue_door_id: 'D2' },
  ],
  max_controllable_doors: 3, accept_blockers: [], last_event_id: 14, ...over,
});

export const acceptResponse = (over: Record<string, unknown> = {}) => ({
  venue_id: 'meridian-level-1-24a745', venue_revision: 1, draft_revision: 4, active_revision: 7, geometry_revision: 'geom-e6e3', provenance: 'live', warnings: [], defaults: [], ...over,
});

/** A recorded live event sequence, as the server emits it (data already JSON strings). */
export const LIVE_EVENTS: [string, Record<string, unknown>][] = [
  ['status', { draft_id: DRAFT_ID, status: 'extracting', phase: 'read', revision: 1, provenance: 'live' }],
  ['thought', { phase: 'extract', index: 0, text: '**Reading the walls** first.', recorded: false }],
  ['thought', { phase: 'extract', index: 1, text: 'Found three exits.', recorded: false }],
  ['draft', { phase: 'extract', draft: {}, unreadable: ['smudge'], dropped: ['door KD9'], repaired: [], counts: { rooms: 9, doors: 10, exits: 4 } }],
  ['status', { draft_id: DRAFT_ID, status: 'checking', phase: 'check', revision: 2, provenance: 'live' }],
  ['checks', { phase: 'extract', issues: [{ code: 'room_unreachable', severity: 'error', message: 'Bath unreachable', element_ids: ['BATH'] }], errors: 1, warnings: 0, compile_error: null, geometry_revision: 'g1' }],
  ['status', { draft_id: DRAFT_ID, status: 'critiquing', phase: 'critique-1', revision: 3, provenance: 'live' }],
  ['thought', { phase: 'critique-1', index: 0, text: 'Add a door to the bath.', recorded: false }],
  ['round', { round: 1, issues_before: { errors: 1, warnings: 0, compile_failed: false }, issues_after: { errors: 0, warnings: 0, compile_failed: false }, accepted: true, note: 'round 1: kept' }],
  ['draft', { phase: 'critique-1', draft: {}, unreadable: [], dropped: [], repaired: [], counts: { rooms: 9, doors: 11, exits: 4 } }],
  ['checks', { phase: 'critique-1', issues: [], errors: 0, warnings: 0, compile_error: null, geometry_revision: 'g2' }],
  ['status', { draft_id: DRAFT_ID, status: 'ready', phase: 'done', revision: 4, provenance: 'live' }],
  ['done', { draft_id: DRAFT_ID, status: 'ready', revision: 4, errors: 0, warnings: 0, provenance: 'live' }],
];
