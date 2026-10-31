import type { Snapshot } from '../types';
import { Empty, Field, Panel, Status } from './primitives';

export function Reliability({ data }: { data: Snapshot }) {
  const journal = data.journals[0];
  const fence = data.fences[0];
  return (
    <>
      <Panel title="CREATE journal" subtitle="Persisted external identity and exact intent">
        {journal ? (
          <>
            <Status value={journal.state} />
            <dl>
              <Field name="Intent" value={<code>{journal.intent_id}</code>} />
              <Field name="Resulting CRM identity" value={journal.crm_id} />
            </dl>
          </>
        ) : (
          <Empty>No CREATE intent yet.</Empty>
        )}
      </Panel>
      <Panel title="Mutation fence" subtitle="Lease expiry never reopens a possible send">
        {fence ? (
          <>
            <Status value={fence.state} />
            <dl>
              <Field
                name="Resource / operation"
                value={`${fence.resource_id} / ${fence.mutation_type}`}
              />
              <Field name="Intent" value={<code>{fence.intent_id}</code>} />
              <Field
                name="Ownership"
                value={fence.owner ? 'Persisted dispatch owner' : 'Prepared, not dispatched'}
              />
            </dl>
          </>
        ) : (
          <Empty>No fulfillment intent yet.</Empty>
        )}
      </Panel>
      <Panel title="Recovery queue" subtitle="Read-only reconciliation with bounded attempts">
        {data.tasks.length ? (
          data.tasks.map((t) => (
            <div className="task" key={t.id}>
              <b>{t.kind}</b> <Status value={t.state} />
              <p>{t.reason}</p>
              <small>Read attempts: {t.attempts}</small>
            </div>
          ))
        ) : (
          <Empty>No unresolved recovery tasks.</Empty>
        )}
      </Panel>
      <Panel title="Terminal receipts" subtitle="Positive proof retained independently of delivery">
        {data.receipts.length ? (
          data.receipts.map((r) => (
            <details key={r.intent_id}>
              <summary>{r.kind} · confirmed effect</summary>
              <pre>{JSON.stringify(JSON.parse(r.proof), null, 2)}</pre>
            </details>
          ))
        ) : (
          <Empty>No terminal proof yet.</Empty>
        )}
      </Panel>
    </>
  );
}
