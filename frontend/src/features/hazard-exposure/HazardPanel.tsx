import { useId } from 'react';
import { buildDisplayModel } from './hazard';
import type { HazardResultView } from './hazard';
import './HazardPanel.css';

interface HazardPanelProps {
  result: HazardResultView | null;
  isCurrent: boolean;
}

export function HazardPanel({ result, isCurrent }: HazardPanelProps) {
  const uid = useId();
  const model = buildDisplayModel(result, isCurrent);
  const titleId = `${uid}-title`;
  return (
    <section className="hazard-panel" aria-labelledby={titleId}>
      <h2 id={titleId}>Hazard exposure</h2>
      {model.kind !== 'result' || !model.summary || !model.check ? (
        <p className={`hazard-empty${model.kind === 'stale' ? ' is-stale' : ''}`} role="status">{model.message}</p>
      ) : (
        <>
          <p className="hazard-label">{model.label}</p>
          <p className="hazard-scenario">{model.scenario_label}</p>
          <div className={`hazard-check is-${model.check.status}`} role="status">
            <strong>Checker {model.check.status}</strong>
            {model.check.reasons.length > 0 && (
              <ul>{model.check.reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ul>
            )}
          </div>
          <h3>Closure events</h3>
          {model.events.length === 0 ? <p className="hazard-note">No closure events.</p> : (
            <ul className="hazard-events">
              {model.events.map((event, index) => (
                <li key={`${event.element_id}-${index}`}><span className="hazard-mono">{event.element_id}</span> closes at <span className="hazard-mono">{event.close_at_s} s</span></li>
              ))}
            </ul>
          )}
          <div className="hazard-table-wrap" tabIndex={0} role="region" aria-label="Alternatives">
            <table className="hazard-table">
              <caption>{model.label}</caption>
              <thead><tr><th scope="col">Alternative</th><th scope="col">Completed crossings</th><th scope="col">Exposure (people-seconds)</th></tr></thead>
              <tbody>
                {model.summary.rows.map(row => (
                  <tr key={row.alternative_id}>
                    <th scope="row">{row.alternative_id}</th>
                    <td>{row.completed_crossings}</td>
                    <td>{row.exposure_people_seconds}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
