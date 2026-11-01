# State boundaries

Task, Step, ToolIntent and Recovery transition rules are in platform_core/state.py.
Ownership validation is in ownership.py; persisted CAS/locking is in repository.py.

UNKNOWN ToolIntent cannot return to PREPARED. CONFIRMED has no outgoing transition.
SQL also rejects PREPARED reset from a sent/unknown/review/terminal intent and protects
its effect identity. Immutable receipt/version and append-only event triggers are active.

The backbone exercises:
CREATED → QUEUED → RUNNING → WAITING_TOOL → UNKNOWN → RECOVERING → RUNNING → COMPLETED.

Normal ACK:
WAITING_TOOL → WAITING_READBACK → RECOVERING → RUNNING → COMPLETED.

The research executor persists retrieve → model → optional tool → evaluate steps.
WAITING_MODEL is exercised with durable call reservations, bounded repair and lease
reclaim. AgentVersion is pinned at task creation; continuation reuses the stored plan.

Cancellation before dispatch closes the plan without an external effect. Cancellation
after SENT preserves CANCEL_REQUESTED through ACK or lost ACK; reconciliation must
establish the external outcome before final CANCELLED. Acknowledging manual review
changes observation metadata only and never releases the mutation fence.

All seven budget dimensions now gate execution. Retries/repair/reclaims reserve durable
usage; exact limits succeed and exceeding admission persists BUDGET_EXHAUSTED plus an
event. Unresolved mutation fences remain intact. Unprovable cancellation requires manual
review. Token/cost units are explicit synthetic estimates, not provider billing measures.

CREATED → QUEUED and plan publication commit atomically. A retryable failed task
returns through QUEUED before RUNNING; a retryable Step must pass CLAIMED. The full
Task graph, including cancellation and terminal states, is generated in diagrams/A2.svg.
