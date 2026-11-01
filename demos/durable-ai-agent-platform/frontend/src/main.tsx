import { useEffect, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import {
  request,
  value,
  type Row,
  type Scenario,
  type Snapshot,
} from "./client";
import "./style.css";

function Badge({ children }: { children: ReactNode }) {
  const text = String(children);
  const tone = /UNKNOWN|REVIEW|EXHAUSTED|CANCEL_REQUESTED/.test(text)
    ? "amber"
    : /COMPLETED|CONFIRMED|PRESENT|COMMITTED/.test(text)
      ? "green"
      : "neutral";
  return <span className={`badge ${tone}`}>{children}</span>;
}
function Panel({
  title,
  eyebrow,
  children,
  id,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
  id?: string;
}) {
  return (
    <section className="panel" id={id}>
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
      </div>
      {children}
    </section>
  );
}
function Json({ data }: { data: unknown }) {
  return <pre>{JSON.stringify(data, null, 2)}</pre>;
}
function Records({ rows, empty }: { rows: Row[]; empty: string }) {
  return rows.length ? (
    <div className="records">
      {rows.map((row, i) => (
        <details key={String(row.id || i)}>
          <summary>
            {String(
              row.kind ||
                row.evaluator ||
                row.state ||
                row.id ||
                `Record ${i + 1}`,
            )}
            {row.passed !== undefined && (
              <Badge>{row.passed ? "PASS" : "FAIL"}</Badge>
            )}
          </summary>
          <Json data={row} />
        </details>
      ))}
    </div>
  ) : (
    <p className="empty">{empty}</p>
  );
}

function App() {
  const [tenant, setTenant] = useState<{ id: string; token: string }>();
  const [catalog, setCatalog] = useState<Scenario[]>([]);
  const [selected, setSelected] = useState("S04");
  const [taskId, setTaskId] = useState("");
  const [tasks, setTasks] = useState<Row[]>([]);
  const [metrics, setMetrics] = useState<Record<string, number>>({});
  const [data, setData] = useState<Snapshot>();
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [note, setNote] = useState(
    "Inspected external observation; mutation fence preserved.",
  );
  const [foreign, setForeign] = useState("");
  const [denial, setDenial] = useState("");
  const [operation, setOperation] = useState("Connecting");

  async function refresh(current = tenant, identity = taskId) {
    if (!current) return;
    const [list, counts] = await Promise.all([
      request<Row[]>("/api/tasks", current.token),
      request<Record<string, number>>("/api/metrics", current.token),
    ]);
    setTasks(list);
    setMetrics(counts);
    if (identity)
      setData(
        await request<Snapshot>(
          `/api/tasks/${identity}/snapshot`,
          current.token,
        ),
      );
  }
  async function workspace() {
    const current = await request<{ id: string; token: string }>(
      "/api/tenants",
      "",
      { name: "Operations laboratory" },
    );
    setTenant(current);
    setTaskId("");
    setData(undefined);
    setTasks([]);
    setMetrics({});
    return current;
  }
  useEffect(() => {
    void (async () => {
      try {
        const scenarios = await request<Scenario[]>("/lab/catalog");
        setCatalog(scenarios);
        await workspace();
        setOperation("Ready");
      } catch (e) {
        setError(String(e));
      } finally {
        setBusy(false);
      }
    })();
  }, []);
  async function perform(label: string, action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setOperation(label);
    try {
      await action();
      setOperation("Ready");
    } catch (e) {
      setError(String(e));
      setOperation("Action rejected");
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    if (!tenant) return;
    const created = await request<{ task_id: string }>(
      `/lab/sessions/${selected}`,
      tenant.token,
      {},
    );
    setTaskId(created.task_id);
    setDenial("");
    await refresh(tenant, created.task_id);
  }
  async function control(action: string) {
    if (!tenant || !taskId) return;
    await request(`/lab/tasks/${taskId}/actions/${action}`, tenant.token, {});
    await refresh();
  }
  async function review(action: string) {
    if (!tenant) return;
    await request(`/api/manual-review/${taskId}/resolve`, tenant.token, {
      action,
      note,
    });
    await refresh();
  }
  const state = data ? value(data.task, "state") : "NO_TASK";
  const terminal = [
    "COMPLETED",
    "CANCELLED",
    "MANUAL_REVIEW",
    "BUDGET_EXHAUSTED",
  ].includes(state);
  const scenario = catalog.find((s) => s.id === selected);
  const budgetDimensions = [
    ["model", "Model calls"],
    ["tool", "Tool calls"],
    ["step", "Steps"],
    ["token", "Estimated tokens"],
    ["cost", "Estimated cost units"],
    ["recovery", "Recovery attempts"],
  ];
  const intent = data?.tool_intents[0];
  const recovery = data?.recovery_tasks[0];
  const proof = data?.tool_receipts.length ? "PRESENT" : "NONE";

  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#top">
          <span className="logo">D/</span>
          <span>
            DURABLE<small>AGENT OPERATIONS</small>
          </span>
        </a>
        <div className="nav-label">CONTROL PLANE</div>
        <nav>
          <a href="#top" className="active">
            ◈ &nbsp; Overview
          </a>
          <a href="#workflow">⇢ &nbsp; Workflow & ownership</a>
          <a href="#recovery">↻ &nbsp; Recovery & proof</a>
          <a href="#evidence">▤ &nbsp; Evidence & provenance</a>
          <a href="#timeline">≡ &nbsp; Event timeline</a>
        </nav>
        <div className="sidebar-note">
          <span className="live-dot" /> POSTGRESQL BACKED
          <p>
            Deterministic model
            <br />
            Independent provider database
            <br />
            No external AI key required
          </p>
        </div>
        <div className="workspace">
          <span className="eyebrow">TENANT WORKSPACE</span>
          <code data-testid="tenant-id">
            {tenant?.id.slice(0, 18) || "Connecting…"}
          </code>
          <small>
            Reset creates a new tenant.
            <br />
            Prior intent fences are retained.
          </small>
        </div>
      </aside>
      <main id="top">
        <header className="topbar">
          <span>
            LABORATORY <b>/</b> DURABLE EXECUTION
          </span>
          <span className="connection">
            <span className="live-dot" />
            {operation}
          </span>
        </header>
        <div className="page-title">
          <div>
            <span className="eyebrow">RELIABILITY IN THE OPEN</span>
            <h1>Agent operations</h1>
            <p>
              Inspect what the agent knows, what happened outside, and what can
              be proved.
            </p>
          </div>
          <span className="lab-tag">SYNTHETIC ENVIRONMENT</span>
        </div>
        <div className="metric-grid">
          {[
            "queued",
            "running",
            "unknown",
            "recovering",
            "manual_review",
            "completed",
            "budget_exhausted",
            "failed",
          ].map((key) => (
            <div className="metric" key={key}>
              <span>{key.replaceAll("_", " ")}</span>
              <strong>
                {key === "failed"
                  ? (metrics.failed_retryable || 0) +
                    (metrics.failed_terminal || 0)
                  : metrics[key] || 0}
              </strong>
            </div>
          ))}
        </div>
        <section className="controls" aria-label="Scenario controls">
          <div className="scenario-picker">
            <label htmlFor="scenario">EXECUTABLE SCENARIO</label>
            <select
              id="scenario"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              disabled={busy}
            >
              {catalog.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id} · {s.title}
                </option>
              ))}
            </select>
          </div>
          <button
            className="primary"
            disabled={busy || !tenant}
            onClick={() => void perform("Creating scenario", start)}
          >
            Create scenario
          </button>
          <button
            disabled={busy}
            onClick={() =>
              void perform("Resetting workspace", async () => {
                await workspace();
              })
            }
          >
            Reset
          </button>
          <div className="action-row">
            {[
              ["run", "Run"],
              ["step", "Step"],
              ["crash-worker", "Crash worker"],
              ["restart-worker", "Restart worker"],
              ["recover", "Recover"],
              ["cancel", "Cancel"],
            ].map(([action, label]) => (
              <button
                key={action}
                disabled={
                  busy ||
                  !taskId ||
                  (action === "crash-worker" && selected !== "S06") ||
                  (action === "run" && terminal)
                }
                onClick={() => void perform(label, () => control(action))}
              >
                {label}
              </button>
            ))}
            <span className="operation" data-testid="operation">
              {operation}
            </span>
          </div>
        </section>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {!data ? (
          <section className="welcome">
            <span className="eyebrow">START WITH S04</span>
            <h2>One effect. Two different states.</h2>
            <p>
              Create a scenario and press Step. The provider commits while the
              orchestrator remains UNKNOWN. Recover to establish proof without
              another mutation.
            </p>
            <div className="welcome-flow">
              COMMIT <span>→</span> LOST ACK <span>→</span> UNKNOWN{" "}
              <span>→</span> RECONCILE
            </div>
          </section>
        ) : (
          <>
            <div className="task-header">
              <div>
                <span className="eyebrow">TASK / {scenario?.id}</span>
                <code data-testid="task-id">{taskId}</code>
              </div>
              <Badge>{state}</Badge>
            </div>
            <div className="truth-grid">
              <section className="truth knowledge">
                <span className="eyebrow">01 / ORCHESTRATOR KNOWLEDGE</span>
                <h2 data-testid="orchestrator-state">{state}</h2>
                <dl>
                  <dt>ToolIntent</dt>
                  <dd data-testid="intent-state">
                    {intent ? value(intent, "state") : "NONE"}
                  </dd>
                  <dt>Recovery</dt>
                  <dd data-testid="recovery-state">
                    {recovery ? value(recovery, "state") : "NONE"}
                  </dd>
                </dl>
                <p>Local knowledge may lag behind the external commit.</p>
              </section>
              <section className="truth reality">
                <span className="eyebrow">02 / EXTERNAL PROVIDER REALITY</span>
                <h2 data-testid="provider-state">{data.provider.state}</h2>
                <dl>
                  <dt>External mutations</dt>
                  <dd data-testid="mutation-count">
                    {data.provider.mutations}
                  </dd>
                  <dt>Dispatch attempts</dt>
                  <dd data-testid="dispatch-count">
                    {data.provider.dispatch_attempts}
                  </dd>
                </dl>
                <p>
                  Independent inspection of the synthetic provider database.
                </p>
                <details>
                  <summary>
                    Inspect tool effects and provider domain state
                  </summary>
                  <Json
                    data={{
                      effects: data.provider.effects,
                      domain_state: data.provider.domain_state,
                    }}
                  />
                </details>
              </section>
              <section className="truth proof">
                <span className="eyebrow">03 / CONFIRMED PROOF</span>
                <h2 data-testid="receipt-state">{proof}</h2>
                <dl>
                  <dt>Terminal receipts</dt>
                  <dd>{data.tool_receipts.length}</dd>
                  <dt>Reconciliation</dt>
                  <dd>
                    {data.tool_receipts.length ? "CONFIRMED" : "UNPROVEN"}
                  </dd>
                </dl>
                <p>
                  Only identity-matched readback creates an immutable receipt.
                </p>
              </section>
            </div>
            <div className="section-grid" id="workflow">
              <Panel
                title="Persisted workflow"
                eyebrow="EXECUTION / PINNED PLAN"
              >
                <div className="workflow">
                  {data.steps.map((step, i) => (
                    <div className="workflow-node" key={value(step, "id")}>
                      <span className="node-index">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <b>{value(step, "kind")}</b>
                      <Badge>{value(step, "state")}</Badge>
                      <small>Attempt {value(step, "attempt")}</small>
                    </div>
                  ))}
                </div>
                <div className="metadata">
                  <span>Pinned AgentVersion</span>
                  <code data-testid="pinned-version">
                    {value(data.task, "agent_version_id")}
                  </code>
                  <span>Task revision</span>
                  <code>{value(data.task, "revision")}</code>
                  <span>Tenant</span>
                  <code>{value(data.task, "tenant_id")}</code>
                </div>
              </Panel>
              <Panel title="Budget usage" eyebrow="ATOMIC ADMISSION">
                <div className="budgets">
                  {budgetDimensions.map(([key, label]) => {
                    const used = Number(data.task[`${key}_used`]);
                    const limit = Number(data.task[`${key}_limit`]);
                    return (
                      <div key={key}>
                        <div>
                          <span>{label}</span>
                          <code>
                            {used} / {limit}
                          </code>
                        </div>
                        <progress value={used} max={Math.max(1, limit)} />
                      </div>
                    );
                  })}
                  <small>
                    Logical deadline: {value(data.task, "deadline")}
                    <br />
                    Tokens and cost are deterministic admission estimates, not
                    provider billing.
                  </small>
                </div>
              </Panel>
            </div>
            <div className="section-grid">
              <Panel
                title="Worker ownership"
                eyebrow="LEASE / REVISION / FENCING"
              >
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Step</th>
                        <th>Owner</th>
                        <th>Revision</th>
                        <th>Lease until</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.steps.map((step) => (
                        <tr key={value(step, "id")}>
                          <td>{value(step, "kind")}</td>
                          <td>{value(step, "owner")}</td>
                          <td>{value(step, "revision")}</td>
                          <td>{value(step, "lease_until")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Records
                  rows={data.events.filter(
                    (row) => row.kind === "stale_owner_rejected",
                  )}
                  empty="No rejected stale ownership attempts in this task."
                />
                <details>
                  <summary>Execution runs · {data.runs.length}</summary>
                  <Records rows={data.runs} empty="No runs yet." />
                </details>
              </Panel>
              <Panel
                title="Durable fault plan"
                eyebrow="DETERMINISTIC BOUNDARIES"
              >
                <Records
                  rows={data.fault_plans}
                  empty="No faults configured; normal execution."
                />
              </Panel>
            </div>
            <div className="section-grid" id="recovery">
              <Panel
                title="Recovery queue"
                eyebrow="OBSERVATION / NO MUTATING CAPABILITY"
              >
                <Records
                  rows={data.recovery_tasks}
                  empty="No recovery tasks."
                />
                <h3>External observations</h3>
                <Records
                  rows={data.events.filter(
                    (row) => row.kind === "external_observation",
                  )}
                  empty="No readback yet."
                />
              </Panel>
              <Panel
                title="Confirmed receipts"
                eyebrow="IMMUTABLE TERMINAL EVIDENCE"
              >
                <Records
                  rows={data.tool_receipts}
                  empty="No receipt. An ACK is not confirmation."
                />
                <h3>Tool intents</h3>
                <Records
                  rows={data.tool_intents}
                  empty="No mutation planned."
                />
              </Panel>
            </div>
            {state === "MANUAL_REVIEW" && (
              <Panel
                title="Manual review"
                eyebrow="OPERATOR DECISIONS ARE APPEND-ONLY"
              >
                <p>
                  Inspect the intent, external observation and recovery attempts
                  above. These actions preserve the mutation fence.
                </p>
                <label htmlFor="review-note">Decision note</label>
                <textarea
                  id="review-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
                <div className="button-row">
                  <button
                    disabled={busy || !note}
                    onClick={() =>
                      void perform("Acknowledging observation", () =>
                        review("acknowledge"),
                      )
                    }
                  >
                    Acknowledge observation
                  </button>
                  <button
                    disabled={busy || !note}
                    onClick={() =>
                      void perform("Read-only reconciliation", () =>
                        review("reconcile"),
                      )
                    }
                  >
                    Reconcile read-only
                  </button>
                </div>
              </Panel>
            )}
            <div className="section-grid" id="evidence">
              <Panel
                title="RAG provenance"
                eyebrow="ANSWER → HIT → CHUNK → DOCUMENT"
              >
                <Records rows={data.artifacts} empty="No final artifact." />
                <Records
                  rows={data.retrieval_hits}
                  empty="No retrieval hits."
                />
              </Panel>
              <Panel
                title="Model calls & evaluations"
                eyebrow="STRUCTURED OUTPUT / BOUNDED REPAIR"
              >
                <Records rows={data.model_calls} empty="No model call." />
                <h3>Evaluation results</h3>
                <Records
                  rows={data.evaluations}
                  empty="Evaluations have not run."
                />
              </Panel>
            </div>
            <Panel
              title="Event timeline"
              eyebrow="PERSISTED / ORDERED / APPEND-ONLY"
              id="timeline"
            >
              <ol className="timeline">
                {data.events.map((row) => (
                  <li key={value(row, "id")}>
                    <span className="event-dot" />
                    <div>
                      <b>{value(row, "kind")}</b>
                      <time>{value(row, "created_at")}</time>
                      <details>
                        <summary>Inspect event</summary>
                        <Json data={row.details} />
                      </details>
                    </div>
                  </li>
                ))}
              </ol>
            </Panel>
          </>
        )}
        <div className="section-grid">
          <Panel
            title="Tenant access probe"
            eyebrow="BACKEND ENFORCED BOUNDARY"
          >
            <label htmlFor="foreign-task">Task UUID from another tenant</label>
            <div className="button-row">
              <input
                id="foreign-task"
                value={foreign}
                onChange={(e) => setForeign(e.target.value)}
                placeholder="Paste a synthetic task UUID"
              />
              <button
                disabled={busy || !foreign || !tenant}
                onClick={() =>
                  void perform("Checking tenant boundary", async () => {
                    try {
                      await request(`/api/tasks/${foreign}`, tenant?.token);
                      setDenial("ACCESS GRANTED");
                    } catch (e) {
                      setDenial(String(e));
                    }
                  })
                }
              >
                Check access
              </button>
            </div>
            <p data-testid="tenant-denial">{denial}</p>
          </Panel>
          <Panel title="Workspace tasks" eyebrow="TENANT SCOPED">
            <div className="task-list">
              {tasks.map((task) => (
                <button
                  key={value(task, "id")}
                  disabled={busy}
                  onClick={() =>
                    void perform("Inspecting task", async () => {
                      const id = value(task, "id");
                      setTaskId(id);
                      await refresh(tenant, id);
                    })
                  }
                >
                  <code>{value(task, "id").slice(0, 18)}</code>
                  <Badge>{value(task, "state")}</Badge>
                </button>
              ))}
            </div>
          </Panel>
        </div>
        <footer>
          Durable Multi-Tenant AI Agent Platform{" "}
          <span>STAGE 1 · ENGINEERING LAB · UNPUBLISHED</span>
        </footer>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
