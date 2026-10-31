import { Controls } from './components/Controls';
import { OrderPanels } from './components/OrderPanels';
import { Reliability } from './components/Reliability';
import { Timeline } from './components/Timeline';
import { Warehouse } from './components/Warehouse';
import { useLab } from './useLab';

export default function App() {
  const lab = useLab();
  const data = lab.snapshot;
  return (
    <>
      <header className="masthead">
        <div className="brand-mark">OR</div>
        <div>
          <span className="eyebrow">ENGINEERING LAB / 01</span>
          <h1>Order Reliability</h1>
        </div>
        <span className="lab-badge">SYNTHETIC · LOCAL ONLY</span>
      </header>
      <main>
        <div className="intro">
          <div>
            <span className="eyebrow">OBSERVE THE FAILURE BOUNDARY</span>
            <h2>Accepted is not confirmed.</h2>
            <p>
              Trace an order across independent stores. Inject failures, inspect the evidence, and
              recover without repeating a side effect.
            </p>
          </div>
          <aside>
            Two SQLite databases. One observable history.
            <br />
            No live credentials. No production data.
          </aside>
        </div>
        {lab.error && (
          <div role="alert" className="error">
            <b>Execution paused</b>
            <p>{lab.error}</p>
            <span>Persisted state is retained. Resume or inspect before resetting.</span>
          </div>
        )}
        {!data ? (
          <div className="loading" role="status">
            {lab.error ? (
              <button onClick={() => void lab.reconnect()}>Retry connection</button>
            ) : (
              'Connecting to local backend…'
            )}
          </div>
        ) : (
          <>
            <Controls
              scenarios={lab.scenarios}
              selected={lab.selected}
              active={data.orders[0].scenario}
              busy={lab.busy}
              onSelect={lab.setSelected}
              onAction={(kind) => void lab.act(kind)}
            />
            <div className="workspace">
              <div className="panel-grid">
                <OrderPanels data={data} />
                <Warehouse data={data} />
                <Reliability data={data} />
              </div>
              <Timeline events={data.events} />
            </div>
            <footer>
              Clean-room distributed-state simulation. The provider observer exposes lab truth;
              recovery uses only bounded readback API evidence.
            </footer>
          </>
        )}
      </main>
    </>
  );
}
