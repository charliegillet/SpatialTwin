import { useEffect, useRef, useState } from 'react';
import { Hand, Lock, RotateCcw, ShieldAlert, ShieldCheck, TriangleAlert } from 'lucide-react';
import type { GateFault } from '../api/incident';
import { approvalSummary, FAILSAFE_RULE, FAILSAFE_WINDOWS, FAULT_COPY, planSummary, SIM_LABEL, type GateView } from '../twin/incidentFlow';
import type { IncidentController } from '../twin/useIncident';
import './Incident.css';

const OTHER_FAULTS: GateFault[] = ['switch_disagreement', 'dropped_ack', 'heartbeat_timeout'];
const CONNECTION_COPY = { connecting: 'connecting', live: 'live', polling: 'polling (stream down)', offline: 'offline' } as const;
const seconds = (ms: number) => `${(ms / 1000).toFixed(1)} s`;

/** Act 3: approve the checked door plan and watch the simulated doors answer. A door counts as open only when its endpoint switch says so. */
export function IncidentPanel({ incident }: { incident: IncidentController }) {
  const { state, busy, error } = incident;
  const { plan, availability, banner, approval, gates } = state;
  const summary = planSummary(plan);
  const approvalLine = approvalSummary(approval);
  const reasonId = 'incident-approve-reason';
  const failed = approval?.status === 'failed';
  const held = plan?.held_doors ?? [];

  return <section className="incident" aria-label="Approval and door controller" aria-busy={busy !== null}>
    <header className="incident-head">
      <h3>Approve &amp; doors</h3>
      <span className="chip chip-data incident-sim" title={state.label}>{SIM_LABEL}</span>
      <span className={`chip incident-conn is-${state.connection}`} role="status">{CONNECTION_COPY[state.connection]}</span>
    </header>

    {banner && <div className="incident-banner" role="alert">
      <TriangleAlert size={16} aria-hidden="true" />
      <div><strong>{banner.headline}</strong>{banner.reason && <small>{banner.reason}</small>}</div>
    </div>}

    <div className={`incident-plan${plan?.label === 'fallback' ? ' is-fallback' : ''}`}>
      {plan ? <>
        <div className="incident-plan-top">
          <span className={`chip ${plan.label === 'fallback' || held.length ? 'chip-warn' : 'chip-ok'}`}>{plan.label === 'fallback' ? 'FALLBACK plan' : held.length ? 'Fail-safe plan' : 'Primary plan'}</span>
          <span className="chip chip-data">r{plan.plan_revision}</span>
          {plan.note && <span className="chip chip-warn">{plan.note}</span>}
        </div>
        {summary ? <p className="incident-count"><strong>{summary}</strong><small> · modeled, not survival</small></p>
          : <p className="twin-quiet">No numbers: the checker did not accept this plan.</p>}
        {plan.reason && <p className="twin-quiet">{plan.reason}</p>}
        <ul className="incident-doors" aria-label="Door states this plan asks for">
          {Object.entries(plan.door_states).sort(([a], [b]) => a.localeCompare(b)).map(([id, doorState]) =>
            <li key={id} className={`chip chip-data${plan.stuck_doors.includes(id) || held.includes(id) ? ' chip-warn' : ''}`}>{id} {doorState}{plan.stuck_doors.includes(id) ? ' · stuck' : held.includes(id) ? ' · held' : ''}</li>)}
        </ul>
      </> : <p className="twin-quiet">{state.incident ? 'No plan yet. Place a hazard and the checker plans the doors.' : 'Connecting to the door controller…'}</p>}
      <button type="button" className="btn btn-primary incident-approve" disabled={!availability.allowed || busy !== null} aria-describedby={reasonId} onClick={() => void incident.approve()}>
        <ShieldCheck size={16} aria-hidden="true" />{plan?.label === 'fallback' ? 'Approve fallback' : 'Approve plan'}
      </button>
      <p id={reasonId} className="twin-quiet incident-reason">{availability.allowed ? 'Sends the doors this plan asks for. You approve exactly r' + (plan?.plan_revision ?? '') + '.' : availability.reason}</p>
      {approvalLine && <p className={`incident-approval is-${approval?.status}`} role="status">{approvalLine}</p>}
      {failed && !banner && <p className="door-advisory">The plan did not complete. Re-planning…</p>}
    </div>

    <FailSafeCard incident={incident} />

    {error && <p className="incident-error" role="alert">{error}<button type="button" className="btn btn-quiet btn-ghost" onClick={incident.dismissError}>Dismiss</button></p>}

    {gates.length === 0 && state.incident && <p className="twin-quiet">This venue has no motorized doors. Doors are signs and follow the plan.</p>}
    <div className="incident-gates">
      {gates.map(gate => <GateCard key={gate.id} gate={gate} incident={incident} />)}
    </div>

    <div className="incident-actions">
      <button type="button" className="btn" disabled={busy !== null} onClick={() => void incident.reset()}><RotateCcw size={14} aria-hidden="true" />Reset devices</button>
      <small className="twin-quiet">Clears hazards, faults and stuck doors, then resends the twin's hazards.</small>
    </div>

    <IncidentConsole lines={incident.console} />
  </section>;
}

/** The unattended fail-safe: off by default; armed, it acts only when nobody approves a checked plan in its window. */
function FailSafeCard({ incident }: { incident: IncidentController }) {
  const display = incident.state.failsafe;
  const [seconds, setSeconds] = useState(15);
  const busy = incident.busy !== null;
  const disabled = busy || !incident.state.incident;
  return <section className={`incident-failsafe is-${display.tone}`} aria-label="Unattended fail-safe">
    <header>
      <ShieldAlert size={16} aria-hidden="true" />
      <strong>Unattended fail-safe</strong>
      <span className={`chip ${display.armed ? 'chip-warn' : 'chip-data'}`}>{display.armed ? 'Armed' : 'Off'}</span>
    </header>
    <p className="incident-failsafe-line" aria-hidden="true">{display.headline}</p>
    <p className="sr-only" role="status">{display.status}</p>
    {display.tone === 'counting' && <div className="incident-transit incident-failsafe-bar" role="progressbar" aria-label="Fail-safe window" aria-valuemin={0}
      aria-valuemax={100} aria-valuenow={Math.round((display.fraction ?? 0) * 100)} aria-valuetext={`${display.secondsLeft ?? 0} s left`}>
      <i style={{ width: `${Math.round((display.fraction ?? 0) * 100)}%` }} />
      <small>{display.secondsLeft ?? 0} s left for a person to approve</small>
    </div>}
    {display.detail && <p className="twin-quiet incident-failsafe-detail">{display.detail}</p>}
    <div className="incident-failsafe-actions">
      {display.armed
        ? <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => void incident.setFailsafe(false)}><Hand size={14} aria-hidden="true" />I'm here · take over</button>
        : <>
          <button type="button" className="btn" disabled={disabled} onClick={() => void incident.setFailsafe(true, seconds)}><ShieldAlert size={14} aria-hidden="true" />Arm fail-safe</button>
          <label className="incident-failsafe-window">Window<select aria-label="Fail-safe window" value={seconds} disabled={disabled} onChange={event => setSeconds(Number(event.target.value))}>
            {FAILSAFE_WINDOWS.map(item => <option key={item} value={item}>{item} s</option>)}
          </select></label>
        </>}
    </div>
    <small className="twin-quiet">{FAILSAFE_RULE}</small>
  </section>;
}

function GateCard({ gate, incident }: { gate: GateView; incident: IncidentController }) {
  const busy = incident.busy !== null;
  const [other, setOther] = useState('');
  return <article className={`incident-gate is-${gate.draw}${gate.warn ? ' is-warn' : ''}`} aria-label={`Door ${gate.id}: ${gate.label}`}>
    <header>
      <strong>{gate.id}</strong>
      <span className="incident-gate-state">{gate.state}</span>
      <span className="chip chip-data incident-sim">{SIM_LABEL}</span>
    </header>
    <p className="incident-gate-label">{gate.warn && <TriangleAlert size={14} aria-hidden="true" />}{gate.label}{gate.target ? ` · target ${gate.target.toLowerCase()}` : ''}</p>

    {gate.moving && <div className="incident-transit" role="progressbar" aria-label={`${gate.id} transit`} aria-valuemin={0} aria-valuemax={100}
      aria-valuenow={Math.round((gate.transitFraction ?? 0) * 100)} aria-valuetext={gate.overdue ? 'Endpoint switch is late' : 'Moving'}>
      <i className={gate.overdue ? 'is-overdue' : ''} style={{ width: `${Math.round((gate.transitFraction ?? 0) * 100)}%` }} />
      <small>{gate.overdue ? 'No endpoint switch yet' : 'In transit'} · {seconds(gate.elapsedMs ?? 0)} since command</small>
    </div>}

    <ul className="incident-chips" aria-label={`${gate.id} signals`}>
      <li className={`chip chip-data incident-switch${gate.openSwitch ? ' is-lit' : ''}`}><i aria-hidden="true" />OPEN switch {gate.openSwitch ? 'on' : 'off'}</li>
      <li className={`chip chip-data incident-switch${gate.closedSwitch ? ' is-lit' : ''}`}><i aria-hidden="true" />CLOSED switch {gate.closedSwitch ? 'on' : 'off'}</li>
      <li className={`chip chip-data${gate.ack.heard ? ' incident-ack' : ''}`} title="The device heard the command. That is not arrival.">{gate.ack.label}</li>
      <li className="chip chip-data">epoch {gate.epoch}</li>
      {gate.stuck && <li className="chip chip-warn"><Lock size={12} aria-hidden="true" />stuck closed</li>}
      {gate.armedFault && <li className="chip chip-warn" title={FAULT_COPY[gate.armedFault]}>armed: {gate.armedFault.replace('_', ' ')}</li>}
    </ul>
    {gate.detail && <p className="twin-quiet incident-detail">{gate.detail}</p>}

    <div className="incident-gate-actions">
      <button type="button" className="btn btn-stop" disabled={busy} onClick={() => void incident.jam(gate.id, 'stall')} title={FAULT_COPY.stall} aria-label={`Jam ${gate.id} (stall)`}>Jam the gate</button>
      <select aria-label={`Other fault for ${gate.id}`} value={other} disabled={busy} onChange={event => {
        const fault = event.target.value as GateFault;
        setOther('');
        if (fault) void incident.jam(gate.id, fault);
      }}>
        <option value="">Other fault…</option>
        {OTHER_FAULTS.map(fault => <option key={fault} value={fault}>{FAULT_COPY[fault]}</option>)}
      </select>
      <button type="button" className="btn" disabled={busy || (!gate.armedFault && !gate.warn)} onClick={() => void incident.clearFault(gate.id)} aria-label={`Clear fault on ${gate.id}`}>Clear fault</button>
    </div>
  </article>;
}

/** Serial-style log of what the device said, newest last. Announcements to screen readers are opt-in: the stream is fast. */
function IncidentConsole({ lines }: { lines: IncidentController['console'] }) {
  const [announce, setAnnounce] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const last = lines[lines.length - 1]?.seq;
  useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [last]);
  return <div className="incident-console">
    <div className="incident-console-head">
      <strong>Device console</strong>
      <button type="button" className="btn btn-quiet btn-ghost" aria-pressed={announce} onClick={() => setAnnounce(value => !value)}>Announce events</button>
    </div>
    <div className="incident-log" ref={ref} role="log" tabIndex={0} aria-label="Simulated device events" aria-live={announce ? 'polite' : 'off'} aria-relevant="additions">
      {lines.length ? lines.map(line => <div key={`${line.seq}-${line.text}`} className={`incident-line is-${line.tone}`}><span>{line.seq}</span>{line.text}</div>)
        : <div className="incident-line">Waiting for the device…</div>}
    </div>
  </div>;
}
