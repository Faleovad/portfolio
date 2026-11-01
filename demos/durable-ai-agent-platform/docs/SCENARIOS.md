# Executable scenario layer

Source: backend/platform_core/scenario_catalog.py and scenarios.py.
This is a standalone CLI layer, not a relabelled parameterized test matrix.

Run one specification with `python -m platform_core.scenarios run S04` or the whole
catalog with `python -m platform_core.scenarios run-all`.
The `list` command emits the full machine-readable contracts, including setup, faults,
execution steps, expected ordered state subsequence and final provider/receipt assertions.

The original S01–S25 cover research, citations, mutation, commit/timeout, timeout before
commit, OS worker termination, enqueue idempotency, competing claims, stale ownership,
lost acknowledgement, invalid model output, outages, injection, tenant denial, permission
denial, budgets, cancellation, pinned versions, manual review, delayed/stale visibility,
recovery restart and terminal receipt reuse.

S26–S41 add process exits on both sides of a step commit, actual database rollback,
lease expiry, malformed retrieved content, model review, read outage, logical duration,
token/cost admission, exact successful budget boundary, repair near a model budget,
recovery exhaustion, denied tool retry, unprovable cancellation and step exhaustion.

Each result in scenario-results/ contains the actual state path, exact provider mutation
and dispatch counts, receipt count, recovery state/attempts/reason, invariant assertions,
process PIDs/exit codes where relevant, and a runtime source fingerprint.
Generated results are excluded from authored LOC.

Fault consumption commits independently of the injected failure. A rollback fault therefore
does not rearm itself when the step transaction rolls back. Consumption is row-locked,
decremented exactly once and recorded as fault_consumed. A contract test requires every
registered mode to appear in an executable specification.

S06 waits for persisted UNKNOWN before terminating an actual OS dispatcher process.
Its new recovery process has no provider writer or admin DSN. S24 exits a recovery
process after a persisted observation and before confirmation, then reclaims the expired
claim with a different process. The harness expires only synthetic ownership leases after
the child has exited; it never clears mutation fences or rewinds an intent.

S22 delays the provider's actual visible_at timestamp. Its first observation must be
unconfirmed; only a later visible committed result can generate a receipt. S23 injects
stale observations beyond the readback policy while independent provider inspection still
shows one committed effect. Neither absence, stale data nor outage permits redispatch.

S14 retrieves all five malicious documents: instruction override, tool escalation,
cross-tenant request, prompt disclosure request and fake admin authority. Assertions cover
the deterministic model/tool boundary, not absolute prompt-injection security.

CLI runs preserve previous histories by creating new synthetic tenants. UI sessions use
their authenticated workspace and task-scoped claims. Database-reset pytest fixtures
must run separately from this layer and browser flows.

S42–S53 execute external Search, CRM update, quota credit/debit, Email delivery, HTTP
POST/PUT, lost acknowledgements, provider errors on either side of commit and Search
outage. S06 also starts a replacement dispatcher before read-only recovery; the fenced
UNKNOWN intent must survive that replacement without another dispatch.
