# Persisted admission and operator policies

Reservations lock the task row. All dimensions are durable and bounded:

| Dimension | Charged boundary |
| --- | --- |
| Model calls | Before every provider invocation, including timeout and repair |
| Tool calls | Before PREPARED becomes SENT; a failed transport keeps the charge |
| Steps | Every acquired/reclaimed execution claim, including retries |
| Estimated tokens | Before model invocation, together with call reservation |
| Estimated cost | Before model invocation, together with token reservation |
| Recovery attempts | Before every independent readback attempt |
| Logical duration | Persisted deadline checked at claim/model/dispatch/recovery admission |

Token estimates are ceil((instruction + objective + retrieved character lengths)/4) + 512
output allowance. Cost units are twice that estimate. They are deterministic synthetic
admission accounting; no actual tokenizer, paid-provider cost or billing accuracy is claimed.
Reservations are never refunded after an ambiguous outcome or process death.

The exact limit is allowed; an operation that would exceed a limit is denied. Exhaustion
persists BUDGET_EXHAUSTED and a budget_exhausted event. It never deletes an intent, resets
PREPARED or grants another dispatch. Unresolved recovery is retained for review. Ordinary
continuation cannot reopen a budget terminal. Cancellation with an unprovable effect uses
MANUAL_REVIEW rather than claiming the requested cancellation has completed.

Cancellation before dispatch closes remaining steps and persists CANCELLED. Once an
intent is SENT/UNKNOWN, cancellation records CANCEL_REQUESTED and retains the intent.
ACK/lost-ACK handlers preserve that request. Reconciliation must establish the effect
before final cancellation. Missing/stale/unavailable observations eventually require
manual review. NOT_FOUND is not authoritative proof of non-application in this simulator.

Manual review inspection includes the task, step, pinned version, intent, external
observation, reason, receipts, recovery attempts and event history. Safe actions are an
append-only acknowledgment and budgeted read-only reconciliation. They do not reset
attempt counters, clear fences, change tool authority or force another mutation.
After the readback/attempt policy is exhausted, another reconciliation request can remain
in review without obtaining additional observation authority.

Regression evidence includes exact successful model/step boundaries, all admission
dimensions, repair consuming the last model call, recovery attempt exhaustion, denied
tool retry, cancellation before mutation, cancellation after committed UNKNOWN and
unprovable cancellation. See S17–S19 and S33–S41 plus API integration tests.
