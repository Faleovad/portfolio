# Stage 1 architecture checkpoint

This is an unpublished clean-room synthetic reference implementation. Source-bound
release status is recorded in VERIFICATION.json.

## Runnable components

- PostgreSQL orchestrator: 17 normalized domain tables, composite tenant foreign keys,
  unique step/intent/receipt identities, immutable versions/receipts, append-only events.
- Separate provider database and roles: dispatcher receives write capability; recovery
  and API receive SELECT-only provider access.
- FastAPI: synthetic tenant authentication, scoped resources and operations.
- ApplicationService delegates entity persistence to ApplicationRepository.
- RetrievalService validates text, chunks it and stores deterministic embeddings.
- Executor process claims retrieve/model/evaluate steps.
- Dispatcher process claims only tool steps whose predecessors completed.
- Recovery process reconciles sent/unknown effects without mutation capability.

API handlers validate DTOs and delegate operations. They do not implement workflow
state transitions. Generic resource repository queries whitelist table names and
always bind authenticated tenant scope. Tenant listing returns only the caller's tenant.

## Persisted plan

Task creation atomically pins AgentVersion and inserts ordered Step rows:
retrieve → model → optional explicitly authorized tool → evaluate/finalize.

The plan is deterministic, persisted once, and bounded by the submitted task contract.
It is not an open-ended autonomous planner. Retrieved documents cannot expand tool authority.
Version publication does not rewrite existing tasks.

Completed steps are not claimed again. Model attempts are persisted before invocation,
consume budget even on invalid output, and have a durable repair-attempt bound.
A waiting-model lease may be reclaimed after process loss. Stale owners cannot persist.

## Transaction boundaries

1. Step claim atomically changes token/revision/lease under SKIP LOCKED.
2. Model call/budget reservation commits before provider invocation.
3. Validated model result and step completion commit together.
4. Tool intent PREPARED and then SENT commit before the independent provider transaction.
5. Lost response persists UNKNOWN; lease expiry never authorizes replay.
6. Recovery reads external state and requires exact identity/fingerprint matching.
7. Receipt, confirmed effect and tool step completion commit together.
8. A multi-step task resumes RUNNING after tool recovery; only its finalizer may produce
   the research artifact and complete it.
9. Evaluation rows and final artifact/provenance are persisted before task completion.

The accepted legacy single-tool restart scenario remains a regression test. It still
requires one external mutation and one dispatch attempt across an actual OS process kill.

## RAG and evaluations

All formerly schema-only entities now have application paths:
documents, chunks, retrieval_hits, model_calls, evaluations and artifacts.

Artifacts link answer → model step → retrieval hit → retrieval step/chunk/document,
with score and support relationship. Search and every join carry tenant scope.
Embeddings are lexical hashing with a tiny explicit multilingual dictionary, not a
semantic-model benchmark. Context is untrusted data; only the submitted plan and pinned
allowlist authorize tool activity.

Five evaluators check schema, citations, tool use, expected result and unresolved-effect
invariants. Twenty-six executable synthetic evaluation tasks and one rejected ingestion sample exercise English, Ukrainian, Russian and
mixed-language inputs, including instruction-like document text.

## Operational boundaries

Normal ACK still requires readback. Cancellation during SENT/UNKNOWN retains intent and
reconciles before final cancellation. Manual review supports acknowledgement/read-only
reconciliation, never unrestricted force retry. Synthetic reset creates a new workspace;
it does not delete old events, receipts or unresolved intents.

The React console reads local state, independent SELECT-only provider inspection and
immutable receipts as separate truth panels. A separate opt-in synthetic control process
holds lab writer authority and starts scoped subprocesses. The product API has no mutating
provider dependency. The dispatcher can use the independent HTTP provider service.

Laboratory-controlled tasks are marked atomically at creation. Background workers skip
them; scoped CLI/control commands use the same repository claims and mutation fences.
This lets reproducible Step/Crash/Recover controls coexist with automatic API tasks.

Central faults and 53 CLI specifications exercise process exits, real rollback, lease/CAS,
observation failure and admission. See SCENARIOS.md, POLICIES.md and CONSOLE.md.
Compose now includes the controller, provider and frontend. Docker/remote CI execution,
and the final release audit remain separate gates.

All five tool implementations and their actual tested semantics are described in
TOOL_REQUIREMENTS.json. Search is read-only; CRM, quota, synthetic Email and constrained
HTTP each maintain distinct provider domain state. See ARCHITECTURE_VIEWS.md for A1–A8.
