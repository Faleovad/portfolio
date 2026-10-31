import type { Inventory, Snapshot } from '../types';
import { Empty, Panel, Status } from './primitives';

export function Warehouse({ data }: { data: Snapshot }) {
  const owners: [string, Inventory[]][] = [
    ['ERP', data.inventory],
    ['Provider', data.external.inventory],
  ];
  return (
    <Panel
      className="wide"
      title="Warehouse & reservations"
      subtitle="Available = on hand − reserved. ERP settles deductions only after effect proof."
    >
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Owner</th>
              <th>SKU</th>
              <th>On hand</th>
              <th>Reserved</th>
              <th>Available</th>
              <th>Fulfilled</th>
            </tr>
          </thead>
          <tbody>
            {owners.flatMap(([owner, rows]) =>
              rows.map((row) => (
                <tr key={`${owner}-${row.sku}`}>
                  <td>{owner}</td>
                  <td>
                    <code>{row.sku}</code>
                  </td>
                  <td>{row.on_hand}</td>
                  <td>{row.reserved}</td>
                  <td>{row.available}</td>
                  <td>{row.fulfilled}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
      <div className="reservations">
        {data.reservations.length ? (
          data.reservations.map((r) => (
            <span key={r.sku}>
              <code>
                {r.sku} × {r.quantity}
              </code>{' '}
              <Status value={r.state} />
            </span>
          ))
        ) : (
          <Empty>No local component reservations.</Empty>
        )}
      </div>
    </Panel>
  );
}
