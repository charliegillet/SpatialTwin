import { ApiError, requestJson } from './client.ts';
import type { HazardType, PlacedHazard } from '../twin/types.ts';

/** Phone exit signs and phone hazard proposals, operator side (docs/plans/contracts/signs.md). Every route here is
 *  loopback only: the presenter laptop mints QR links and decides on proposals; a phone never gets operator authority. */

export type SignScope = 'sign:read' | 'hazard:propose';
export interface SignLink {
  token_id: string; scope: SignScope; venue_id: string; exit_id: string | null; exit_name: string | null; url: string; qr_svg: string;
  expires_at: string; lan: { base_url: string; source: string; listening_on_lan: boolean | null; warning: string | null };
}
export interface SignsStatus { sign_streams: number; by_sign: Record<string, number>; tokens_minted: number; pending_proposals: number; disabled_reason: string | null }
export interface PhoneProposal {
  proposal_id: string; type: HazardType; room: string; status: 'pending' | 'confirmed' | 'rejected' | 'expired'; created_at: string;
  venue_id: string; zone_id: string; phone: string;
  /** Where the judge tapped (metres), or null for a room-list proposal. */
  position: { x: number; y: number } | null;
}
export interface ProposalList { version: number; pending: PhoneProposal[]; recent: PhoneProposal[] }
export const PROPOSAL_EVENTS_URL = '/api/signs/proposals/events';

const isRecord = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
const bad = (what: string): never => { throw new ApiError(`Unexpected ${what} from the sign service`, 0); };

const SIGN_ERRORS: Record<string, string> = {
  sign_secret_too_short: 'Phone signs are off: SPATIALTWIN_SIGN_SECRET is shorter than 32 characters.',
  unknown_venue: 'That venue is not available any more.',
  unknown_exit: 'That exit is not in this venue.',
  loopback_only: 'Phone links can only be made on the presenter laptop.',
  proposal_not_pending: 'That proposal was already decided.',
  venue_not_active: 'The proposal is for another venue.',
  unknown_proposal: 'That proposal is gone.',
};
const describe = (_status: number, detail: string, code: string) => SIGN_ERRORS[code] ?? SIGN_ERRORS[detail] ?? '';

export function parseSignLink(raw: unknown): SignLink {
  if (!isRecord(raw) || typeof raw.url !== 'string' || typeof raw.qr_svg !== 'string' || !raw.qr_svg.startsWith('<svg') || !isRecord(raw.lan)) return bad('sign link');
  const lan = raw.lan;
  return {
    token_id: String(raw.token_id ?? ''), scope: raw.scope === 'hazard:propose' ? 'hazard:propose' : 'sign:read', venue_id: String(raw.venue_id ?? ''),
    exit_id: typeof raw.exit_id === 'string' ? raw.exit_id : null, exit_name: typeof raw.exit_name === 'string' ? raw.exit_name : null,
    url: raw.url, qr_svg: raw.qr_svg, expires_at: String(raw.expires_at ?? ''),
    lan: { base_url: String(lan.base_url ?? ''), source: String(lan.source ?? ''), listening_on_lan: typeof lan.listening_on_lan === 'boolean' ? lan.listening_on_lan : null,
      warning: typeof lan.warning === 'string' && lan.warning ? lan.warning : null },
  };
}

export function parseProposalList(raw: unknown): ProposalList {
  if (!isRecord(raw) || !Array.isArray(raw.pending) || !Array.isArray(raw.recent)) return bad('proposal list');
  const one = (item: unknown): PhoneProposal => {
    if (!isRecord(item) || typeof item.proposal_id !== 'string' || typeof item.type !== 'string' || typeof item.zone_id !== 'string') return bad('proposal');
    return { proposal_id: item.proposal_id, type: item.type as HazardType, room: String(item.room ?? item.zone_id), status: (item.status as PhoneProposal['status']) ?? 'pending',
      created_at: String(item.created_at ?? ''), venue_id: String(item.venue_id ?? ''), zone_id: item.zone_id, phone: String(item.phone ?? ''),
      position: isRecord(item.position) && Number.isFinite(item.position.x) && Number.isFinite(item.position.y) ? { x: item.position.x as number, y: item.position.y as number } : null };
  };
  return { version: Number(raw.version ?? 0), pending: raw.pending.map(one), recent: raw.recent.map(one) };
}

/** The confirmed hazard as a twin placement, labelled as a phone proposal the operator confirmed. */
export function proposalHazard(raw: unknown): PlacedHazard {
  const hazard = isRecord(raw) && isRecord(raw.hazard) ? raw.hazard : null;
  const position = hazard && isRecord(hazard.position) ? hazard.position : null;
  if (!hazard || !position || typeof hazard.id !== 'string' || typeof hazard.type !== 'string' || typeof hazard.zone_id !== 'string'
    || !Number.isFinite(position.x) || !Number.isFinite(position.y)) return bad('confirmed hazard');
  return { id: hazard.id, type: hazard.type as HazardType, x: position.x as number, y: position.y as number, zone_id: hazard.zone_id, untenable_s: null,
    source: 'simulated', proposal_id: typeof hazard.proposal_id === 'string' ? hazard.proposal_id : null };
}

export const mintSignLink = async (scope: SignScope, venueId: string, exitId?: string): Promise<SignLink> =>
  parseSignLink(await requestJson<unknown>('/api/signs/tokens', { method: 'POST', body: { scope, venue_id: venueId, ...(exitId ? { exit_id: exitId } : {}) },
    timeoutMs: 8_000, fallback: 'The phone link could not be made', describe }));
export const revokeSignLinks = () => requestJson<unknown>('/api/signs/revoke', { method: 'POST', body: {}, timeoutMs: 8_000, fallback: 'The phone links could not be revoked', describe });
export const fetchSignsStatus = async (signal?: AbortSignal): Promise<SignsStatus> => {
  const raw = await requestJson<unknown>('/api/signs/status', { signal, timeoutMs: 5_000, fallback: 'The sign service could not be read', describe });
  if (!isRecord(raw)) return bad('status');
  return { sign_streams: Number(raw.sign_streams ?? 0), by_sign: isRecord(raw.by_sign) ? raw.by_sign as Record<string, number> : {}, tokens_minted: Number(raw.tokens_minted ?? 0),
    pending_proposals: Number(raw.pending_proposals ?? 0), disabled_reason: typeof raw.disabled_reason === 'string' ? raw.disabled_reason : null };
};
export const fetchProposals = async (): Promise<ProposalList> =>
  parseProposalList(await requestJson<unknown>('/api/signs/proposals', { timeoutMs: 5_000, fallback: 'Proposals could not be read', describe }));
export const confirmProposal = async (id: string): Promise<PlacedHazard> =>
  proposalHazard(await requestJson<unknown>(`/api/signs/proposals/${encodeURIComponent(id)}/confirm`, { method: 'POST', body: {}, timeoutMs: 8_000, fallback: 'The proposal could not be confirmed', describe }));
export const rejectProposal = (id: string) =>
  requestJson<unknown>(`/api/signs/proposals/${encodeURIComponent(id)}/reject`, { method: 'POST', body: {}, timeoutMs: 8_000, fallback: 'The proposal could not be rejected', describe });
