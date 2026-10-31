import { useState } from 'react';
import type { Event } from '../types';
import { Empty, Panel } from './primitives';

export function Timeline({ events }: { events: Event[] }) {
  const [onlyFailures, setOnlyFailures] = useState(false);
  const filtered = onlyFailures
    ? events.filter((e) => /fault|unavailable|not_confirmed/.test(e.event))
    : events;
  return (
    <Panel
      className="timeline-panel"
      title="Event timeline"
      subtitle="Append-only backend events, in persisted sequence order"
    >
      <label className="filter">
        <input
          type="checkbox"
          checked={onlyFailures}
          onChange={(e) => setOnlyFailures(e.target.checked)}
        />{' '}
        Faults and unconfirmed reads only
      </label>
      {!filtered.length && <Empty>No matching events.</Empty>}
      <ol className="timeline" data-testid="timeline">
        {filtered.map((e) => (
          <li key={e.sequence} className={e.component === 'fault_injection' ? 'fault' : ''}>
            <span className="sequence">{e.sequence}</span>
            <div>
              <div className="event-title">
                <b>{e.event.replaceAll('_', ' ')}</b>
                <time dateTime={e.timestamp}>
                  {new Date(e.timestamp).toISOString().slice(11, 23)} UTC
                </time>
              </div>
              <small>
                {e.component} {e.state && `→ ${e.state}`}
              </small>
              {Object.keys(e.details).length > 0 && (
                <details>
                  <summary>Structured details</summary>
                  <pre>{JSON.stringify(e.details, null, 2)}</pre>
                </details>
              )}
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
