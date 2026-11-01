# Defects found while executing the milestone

These are defects in the synthetic project/harness, not historical production incidents.

| Trigger | Finding | Fix / verification |
| --- | --- | --- |
| Recovery budget exhausted with unresolved effect | UPDATE FROM used an ambiguous revision column | Qualified recovery revision; S38 persists the terminal budget and retains review/fence |
| State-path assertion after tool dispatch | Task changed to WAITING_TOOL without a transition event | Emit the transition in the same dispatch transaction; ordered scenario paths are asserted |
| UI Run combines stale-owner action and recovery | An uncommitted progress event held an FK key-share lock; next action requested task FOR UPDATE on another connection | Progress events now commit between actions while the separate advisory control lock remains held |
| Repeated manual reconcile after budget terminal | Metadata reopen could move the recovery record back to pending even though no further attempt was allowed | Refuse reopening at the service boundary; counter, manual state and dispatch fence remain unchanged |
| Scenario recovery child used a 150ms lease | Harness startup/storage latency exhausted ownership before an attempt | Use a normal lease; expire only a dead synthetic recovery child's ownership before restart |
| Delayed visibility shorter than the first observation path | Harness could observe the effect already visible | Delay actual provider visible_at and explicitly verify the initial unconfirmed observation |
| Failed phase output on a Windows CP1251 stream | Unicode diagnostics could prevent writing a failure receipt | Backslash-replace unrepresentable diagnostics; command exit status is preserved |
| Parent killed worker immediately after UNKNOWN | Pause-fault consumption could lose a race with termination | Wait for both persisted UNKNOWN and the committed pause-consumption marker before OS kill; retain the all-faults-consumed assertion |

Permanent regression additions include test_control_multi_action_events_do_not_block_recovery
(S08/S09) and test_operator_reconcile_cannot_reopen_budget_terminal. Browser flows also
exercise the real multi-action control HTTP boundary. Scenario evidence records source
fingerprints and final assertions; rerunning an old JSON file is not verification.

The accepted OS-kill baseline remains mandatory and separate: provider commit, lost ACK,
persisted UNKNOWN, actual dispatcher termination, a new read-only recovery process,
one immutable receipt and COMPLETED, with one mutation and one dispatch attempt.

Five-tool completion also exposed two accounting/transition defects: retryable steps
needed the CLAIMED transition and retryable tasks needed QUEUED before RUNNING;
state metrics initially counted only graph keys, omitting terminal states. The current
metrics derive state totals from the enums and edge totals from the transition maps.
Code-bearing module totals exclude the package docstring. Committed-log tests also
verify that a rolled-back event cannot appear as a committed structured log.

The first private CI run passed every runtime phase but failed the documentation-link
gate because generated historical checkpoint targets were absent from the private copy.
The copy now retains those explicitly historical files; source fingerprint parity still
excludes generated evidence and every candidate is verified by a full new runtime run.
