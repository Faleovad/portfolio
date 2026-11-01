# Operational console

React/TypeScript, real API state, no mocked frontend workflow.

The three central panels deliberately use independent sources:

- Orchestrator knowledge: tasks, tool_intents and recovery_tasks in the orchestrator DB.
- External provider reality: SELECT-only inspection of the independent provider DB,
  separate from the visibility/fault policy applied to recovery observations.
- Confirmed proof: immutable tool_receipts, produced by identity-matched readback.

The console exposes dashboard counts, task/version identity, ordered steps, owner/lease/
revision, execution runs, model calls and repairs, intents, receipts, observations,
recovery/manual review, artifact provenance, evaluations, ordered events and budget usage.
The tenant UUID probe calls the authenticated backend and displays its actual response.

The product API composition has no mutating provider dependency. An explicitly enabled
synthetic control service holds the lab writer capability and starts scoped subprocesses.
It is separate from the read-only API, and is not a production process manager.
Task-scoped advisory locks reject concurrent operator controls. Core worker claims and
mutation fences remain the actual execution authority.

Run/Step executes specification actions, not browser-local state transitions. S06's Crash
worker control terminates an OS process after persisted UNKNOWN; Restart worker starts
a new dispatcher which cannot reclaim that fenced mutation. Recover starts a separate
read-only recovery process. Every operator command is recorded in the event history.
Reset switches to a new tenant workspace and retains old histories.

Thirteen Playwright flows use real PostgreSQL/API/control/Vite processes. They assert both
rendered state and the actual snapshot response used to render it. There are no route
fulfill mocks. The flows cover normal completion, committed UNKNOWN, OS kill/recovery,
foreign UUID denial, provenance, manual review, stale owner, budgets, cancellation and
AgentVersion pinning.

Actual captures produced by those tests:

1. [Normal task](screenshots/01-normal-task.png)
2. [Committed effect / UNKNOWN](screenshots/02-commit-then-timeout.png)
3. [Recovery after restart](screenshots/03-recovery-after-restart.png)
4. [Tenant denial](screenshots/04-tenant-access-denial.png)
5. [RAG provenance](screenshots/05-rag-provenance.png)
6. [Manual review](screenshots/06-manual-review.png)
7. [Stale owner](screenshots/07-stale-worker-ownership.png)

Current execution counts and source-bound phase receipts are in VERIFICATION.json.
Compose and remote CI verification are independent of a successful native browser run.
