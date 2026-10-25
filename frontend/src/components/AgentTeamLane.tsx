import { useEffect, useRef } from 'react';
import { Check, DoorClosed, DoorOpen, TriangleAlert, X } from 'lucide-react';
import { NO_THOUGHTS_NOTE, type ClaimRow, type LaneCard, type TraceRow } from '../twin/agentTeamView';

/** A claim the checker did or did not reproduce. The mark carries a word as well as a colour, so it never relies on colour alone. */
function ClaimsTable({ rows, line }: { rows: ClaimRow[]; line: string | null }) {
  return <div className="agent-claims">
    {rows.length > 0 && <table>
      <caption className="sr-only">Agent claimed versus checker verified, in modeled crossings</caption>
      <thead><tr><th scope="col">Scenario</th><th scope="col">Agent claimed</th><th scope="col">Checker verified</th></tr></thead>
      <tbody>{rows.map(row => <tr key={row.key} className={row.reproduced ? 'is-ok' : 'is-mismatch'}>
        <th scope="row"><code>{row.scenario}</code><small>{row.appliesTo}</small></th>
        <td>{row.claimed}{row.sandboxEstimate && <small className="agent-estimate">sandbox estimate</small>}</td>
        <td>{row.verified}<span className="agent-verdict">{row.reproduced ? <Check size={12} aria-hidden="true" /> : <X size={12} aria-hidden="true" />}{row.reproduced ? 'reproduced' : 'not reproduced'}</span>
          {row.reason && <small>{row.reason}</small>}</td>
      </tr>)}</tbody>
    </table>}
    {line && <p className="twin-quiet">{line}</p>}
  </div>;
}

function TraceItem({ row }: { row: TraceRow }) {
  const classes = `agent-trace-line is-${row.kind}${row.isError ? ' is-error' : ''}${row.partial ? ' is-partial' : ''}`;
  const label = <span className="agent-trace-label">{row.label}</span>;
  if (!row.body) return <li className={classes}>{label}<span className="agent-trace-text">{row.head}</span></li>;
  // Code cells and results are collapsed to their first line; the native disclosure keeps keyboard and screen-reader behaviour for free.
  return <li className={classes}><details><summary>{label}<span className="agent-trace-text">{row.head}</span></summary><pre>{row.body}</pre></details></li>;
}

/** Newest line last. Follows the end of the list unless the reader scrolled up to read something. */
function Trace({ rows, dropped, title }: { rows: TraceRow[]; dropped: number; title: string }) {
  const ref = useRef<HTMLOListElement>(null);
  const pinned = useRef(true);
  useEffect(() => {
    const list = ref.current;
    if (list && pinned.current) list.scrollTop = list.scrollHeight;
  }, [rows]);
  if (rows.length === 0) return null;
  return <details className="agent-trace" open>
    <summary>Trace <span>({rows.length}{dropped ? ` shown, ${dropped} older hidden` : ''})</span></summary>
    {/* Not a live region: announcing every line would bury the status changes. Focusable so the keyboard can scroll it. */}
    <ol ref={ref} tabIndex={0} aria-label={`${title} trace`} onScroll={event => {
      const list = event.currentTarget;
      pinned.current = list.scrollHeight - list.scrollTop - list.clientHeight < 24;
    }}>{rows.map(row => <TraceItem key={row.key} row={row} />)}</ol>
    <p className="twin-quiet">{NO_THOUGHTS_NOTE}</p>
  </details>;
}

const DoorChips = ({ doors, label }: { doors: LaneCard['doors']; label: string }) => doors.length === 0 ? null : <div className="agent-doors">
  <small>{label}</small>
  <ul>{doors.map(door => <li key={door.id} className={`is-${door.state}`}>{door.state === 'open' ? <DoorOpen size={12} aria-hidden="true" /> : <DoorClosed size={12} aria-hidden="true" />}<strong>{door.id}</strong> {door.state}</li>)}</ul>
</div>;

/** One lane of the team: who it is, its provenance and cost, what it recommended, and what the checker made of its claims. */
export function AgentTeamLane({ card }: { card: LaneCard }) {
  return <article className={`agent-lane is-${card.lane} is-phase-${card.phase}`} aria-label={`${card.title} lane`}>
    <header>
      <h4>{card.title}</h4>
      <span className={`agent-chip is-${card.chip.tone}`}>{card.chip.text}</span>
      {card.countdown && <span className="agent-countdown" aria-label={`Deadline: ${card.countdown}`}>{card.countdown}</span>}
    </header>
    <p className="twin-quiet">{card.role}</p>
    <div className="agent-chips">
      <span className={`agent-chip agent-prov is-${card.provenance.tone}`}>{card.provenance.text}{card.provenance.reason ? `: ${card.provenance.reason}` : ''}</span>
      {card.tokens && <span className="agent-chip">{card.tokens}</span>}
      {card.cost && <span className="agent-chip">{card.cost}</span>}
      {card.elapsed && <span className="agent-chip">{card.elapsed}</span>}
    </div>
    {card.liveFailure && <p className="agent-failure"><TriangleAlert size={13} aria-hidden="true" />{card.liveFailure}</p>}
    {card.error && <p className="agent-failure" role="alert"><TriangleAlert size={13} aria-hidden="true" />{card.error}</p>}
    <Trace rows={card.trace} dropped={card.droppedLines} title={card.title} />
    {(card.doors.length > 0 || card.summary) && <div className="agent-recommendation">
      <DoorChips doors={card.doors} label="Recommended" />
      <DoorChips doors={card.fallbackDoors} label="If an opened door jams" />
      {card.summary && <p>{card.summary}</p>}
      {card.recommendationNote && <p className="twin-quiet">{card.recommendationNote}</p>}
    </div>}
    <ClaimsTable rows={card.claims} line={card.claimsLine} />
  </article>;
}
