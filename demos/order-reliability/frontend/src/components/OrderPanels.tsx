import type { Snapshot } from '../types';
import { Empty, Field, Panel, Status } from './primitives';

export function OrderPanels({ data }: { data: Snapshot }) {
  const order = data.orders[0];
  const external = data.external.orders[0];
  return (
    <>
      <Panel title="Incoming order" subtitle="Synthetic marketplace input">
        <dl>
          <Field name="External identity" value={order.external_id} />
          <Field name="Warehouse" value={order.warehouse_id} />
        </dl>
        {order.lines.map((l) => (
          <div className="line-item" key={l.sku}>
            <code>{l.sku}</code>
            <b>× {l.quantity}</b>
          </div>
        ))}
      </Panel>
      <Panel title="Order state" subtitle="ERP-owned state machine">
        <div data-testid="order-state">
          <Status value={order.state} />
        </div>
        <dl>
          <Field
            name="Local / CRM identity"
            value={`${order.id} / ${order.crm_id ?? 'not confirmed'}`}
          />
          <Field name="Confirmation reads used" value={order.read_attempts} />
          <Field name="Persisted revision" value={order.version} />
        </dl>
        {order.error && <p className="callout">{order.error}</p>}
      </Panel>
      <Panel
        title="External CRM state"
        subtitle="Lab observer: actual provider state, not ERP proof"
      >
        {external ? (
          <>
            <Status value={external.status} />
            <dl>
              <Field name="Stock state" value={external.stock_status} />
              <Field name="Tracking" value={external.tracking} />
              <Field name="Reads until visible" value={external.hidden_reads} />
            </dl>
          </>
        ) : (
          <Empty>No provider order has committed.</Empty>
        )}
        <div className="counters">
          <span>
            CREATE calls{' '}
            <b data-testid="create-count">
              {data.external.calls.filter((c) => c.operation === 'CREATE').length}
            </b>
          </span>
          <span>
            FULFILL calls{' '}
            <b data-testid="fulfill-count">
              {data.external.calls.filter((c) => c.operation === 'FULFILL').length}
            </b>
          </span>
        </div>
      </Panel>
      <Panel
        title="Bundle resolution"
        subtitle="Recursive expansion, canonical component aggregation"
      >
        {order.components.length ? (
          order.components.map((l) => (
            <div className="line-item" key={l.sku}>
              <code>{l.sku}</code>
              <b>× {l.quantity}</b>
            </div>
          ))
        ) : (
          <Empty>Awaiting complete validation. Invalid plans are not partially admitted.</Empty>
        )}
      </Panel>
    </>
  );
}
