# Durable fault boundaries

FaultEngine owns stable identifiers, persisted configuration, named deterministic
boundaries, row-locked decrements and fault_consumed events. Runtime components consume
their named boundary; they do not switch on scenario IDs.

| Identifier | Trigger / verification |
| --- | --- |
| model_timeout | Persisted model reservation then timeout |
| malformed_model_output | Invalid structured JSON; bounded repair |
| worker_crash_before_step_commit | Process exit before retrieval commit |
| worker_crash_after_step_commit | Process exit after completed step commit |
| tool_timeout_before_commit | Attempt exists, no effect; conservative UNKNOWN |
| tool_commit_then_timeout | Independent effect commits, response lost |
| delayed_external_visibility | Actual provider visible_at delayed |
| stale_readback | Stale observation despite committed reality |
| readback_outage | Unavailable observation; no replay |
| lost_acknowledgement | Worker drops received ACK before persistence |
| worker_lease_expiry | Ownership expires before dispatch |
| stale_worker_write | Old owner CAS rejected after transfer |
| database_transaction_rollback | Inserts, completion and events actually roll back |
| duplicate_enqueue | Same enqueue identity returns same task |
| cancellation_during_unknown | Cancel request after ambiguous transport |
| retrieval_outage | Retrieval fails before model/tool authority |
| malformed_retrieved_document | Malformed content rejected by validation |
| budget_exhaustion | Model admission denied before invocation |
| competing_workers | Two concurrent claimers; one winner |
| manual_review_required | Structured model decision requires review |
| worker_pause_after_unknown | Parent terminates real OS worker at UNKNOWN |
| recovery_crash_after_observation | Process exits before receipt; fresh process reclaims |
| logical_duration_expiry | Persisted deadline denies admission |

Each mode is configured and consumed by an executable CLI specification. Contract tests
reject orphan modes. Results contain final assertions, exact counts and source fingerprints.
A missing/stale/unavailable read never proves non-application or authorizes redispatch.

The 53 CLI specifications, pytest cases and thirteen browser tests are counted separately.
Synthetic faults do not demonstrate production incidents, paid-model quality or absolute
prompt-injection security. Five distinct tools are covered by the tool requirement matrix.

Search outage and provider errors before/after commit are additional durable fault modes.
The per-tool matrix states exact tested coverage; it does not claim every possible
tool/fault combination was exercised.
