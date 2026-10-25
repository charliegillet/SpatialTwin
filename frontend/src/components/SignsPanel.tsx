import { useEffect, useState } from 'react';
import { Check, QrCode, Smartphone, X } from 'lucide-react';
import {
  confirmProposal, fetchSignsStatus, mintSignLink, parseProposalList, PROPOSAL_EVENTS_URL, rejectProposal, revokeSignLinks,
  type PhoneProposal, type SignLink, type SignsStatus,
} from '../api/signs';
import type { PlacedHazard, VenueV2 } from '../twin/types';
import './Signs.css';

const message = (error: unknown, fallback: string) => error instanceof Error && error.message ? error.message : fallback;
const qrSrc = (svg: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;

/** Judges' phones become the exit signs: one QR per exit of this venue plus one for proposing a hazard. Signs follow the
 *  incident's checked plan; a phone proposal joins the twin only when the operator confirms it here. */
export function SignsPanel({ venue, onConfirmed }: { venue: VenueV2; onConfirmed: (hazard: PlacedHazard) => void }) {
  const [open, setOpen] = useState(false);
  const [links, setLinks] = useState<SignLink[]>([]);
  const [status, setStatus] = useState<SignsStatus | null>(null);
  const [pending, setPending] = useState<PhoneProposal[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Links belong to one venue: after a switch the old QR codes would show an idle sign, so they are dropped.
  useEffect(() => { setLinks([]); }, [venue.venue_id]);

  // Connected phones, polled only while the panel is open.
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    const read = () => fetchSignsStatus(controller.signal).then(setStatus).catch(() => undefined);
    read();
    const timer = setInterval(read, 5000);
    return () => { controller.abort(); clearInterval(timer); };
  }, [open]);

  // Phone proposals arrive whether or not the panel is open: a judge may propose at any time.
  useEffect(() => {
    const source = new EventSource(PROPOSAL_EVENTS_URL);
    source.addEventListener('proposals', event => {
      try { setPending(parseProposalList(JSON.parse((event as MessageEvent).data)).pending.filter(item => item.venue_id === venue.venue_id)); }
      catch { /* a malformed frame is ignored; the next one replaces the list */ }
    });
    return () => source.close();
  }, [venue.venue_id]);

  const mint = async () => {
    setBusy(true); setError(null);
    try {
      const signs = await Promise.all(venue.exits.map(exit => mintSignLink('sign:read', venue.venue_id, exit.id)));
      const propose = await mintSignLink('hazard:propose', venue.venue_id);
      setLinks([...signs, propose]);
    } catch (cause) { setError(message(cause, 'The phone links could not be made')); } finally { setBusy(false); }
  };
  const revoke = async () => {
    setBusy(true); setError(null);
    try { await revokeSignLinks(); setLinks([]); } catch (cause) { setError(message(cause, 'The phone links could not be revoked')); } finally { setBusy(false); }
  };
  const decide = async (proposal: PhoneProposal, accept: boolean) => {
    setError(null);
    try {
      if (accept) onConfirmed(await confirmProposal(proposal.proposal_id)); else await rejectProposal(proposal.proposal_id);
    } catch (cause) { setError(message(cause, 'The proposal could not be decided')); }
  };

  const warning = links.find(link => link.lan.warning)?.lan.warning ?? null;
  const phones = status?.sign_streams ?? 0;
  return <details className="signs twin-card" open={open} onToggle={event => setOpen((event.currentTarget as HTMLDetailsElement).open)}>
    <summary><Smartphone size={15} aria-hidden="true" /><strong>Phone exit signs</strong>
      <span className="chip chip-data">{phones} {phones === 1 ? 'phone' : 'phones'} live</span>
      {pending.length > 0 && <span className="chip chip-warn">{pending.length} proposal{pending.length === 1 ? '' : 's'}</span>}</summary>

    {pending.length > 0 && <ul className="signs-proposals" aria-label="Hazards proposed from phones">
      {pending.map(item => <li key={item.proposal_id}>
        <span><strong>{item.type}</strong> · {item.room}<small> · phone {item.phone.slice(-4)}</small></span>
        <button type="button" className="btn btn-primary" onClick={() => void decide(item, true)} aria-label={`Confirm ${item.type} in ${item.room}`}><Check size={14} aria-hidden="true" />Confirm</button>
        <button type="button" className="btn" onClick={() => void decide(item, false)} aria-label={`Reject ${item.type} in ${item.room}`}><X size={14} aria-hidden="true" />Reject</button>
      </li>)}
    </ul>}

    <p className="twin-quiet">Scan to turn a phone into an exit sign of {venue.exits.length === 1 ? 'the' : 'this'} venue. Signs follow the checked plan; a phone can propose a hazard, never set one. Simulated signs, not certified exit signs.</p>
    <div className="signs-actions">
      <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void mint()}><QrCode size={14} aria-hidden="true" />{links.length ? 'Make new QR codes' : 'Show QR codes'}</button>
      <button type="button" className="btn" disabled={busy} onClick={() => void revoke()}>Revoke all phone links</button>
      <a className="btn btn-ghost" href={`/sign.html?venue=${encodeURIComponent(venue.venue_id)}`} target="_blank" rel="noreferrer">Signs on this laptop</a>
    </div>
    {warning && <p className="door-advisory" role="alert">{warning}</p>}
    {error && <p className="incident-error" role="alert">{error}</p>}
    {links.length > 0 && <div className="signs-grid">
      {links.map(link => <figure key={link.token_id || link.url}>
        <img src={qrSrc(link.qr_svg)} alt={link.scope === 'hazard:propose' ? 'QR to propose a hazard' : `QR for exit ${link.exit_id}`} width={240} height={240} />
        <figcaption>{link.scope === 'hazard:propose' ? <strong>Propose a hazard</strong> : <><strong>{link.exit_id}</strong> {link.exit_name}</>}
          {status && link.exit_id && <small> · {status.by_sign[`${venue.venue_id}/${link.exit_id}`] ?? 0} live</small>}</figcaption>
      </figure>)}
    </div>}
  </details>;
}
