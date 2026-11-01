# Deterministic model, retrieval and evaluation contract

The default ModelProvider is deterministic and uses no external API or credential.
It receives trusted agent instructions, a submitted objective and separately labelled
untrusted context. The fake provider summarizes data; it is not a production reasoning model.

ModelOutput is validated with Pydantic. Unknown fields/tools, malformed JSON, invalid
citations and changes to tool authority are rejected. Invalid attempts are persisted
and consume the model budget; bounded repair exhaustion enters MANUAL_REVIEW.
A valid review decision stops execution before an optional mutation.

## Evaluation records

Each finalization creates five tenant-scoped records:
- schema: validated structured output contract;
- citation: cited hit identities exist in this task's retrieved evidence;
- tool_use: requests stay inside pinned AgentVersion permissions;
- expected_result: explicit synthetic keyword assertions;
- invariant: no unresolved mutation before artifact completion.

An evaluation failure persists the results and enters manual review without an artifact.
The schema evaluator confirms the validated boundary; malformed raw outputs are stopped
earlier and remain visible in model_calls as INVALID attempts.

## Dataset

tests/data/evaluation_tasks.json contains 27 named samples: 26 executable tasks and one rejected upload.
The dataset includes refund, quota, security, retention and support facts in English,
Ukrainian and Russian, plus mixed-language and instruction-like documents.
The API integration test executes the full persisted research pipeline for each valid task,
checks five evaluation results and traces artifact provenance to the uploaded source.
The additional samples cover all five tools, irrelevant context and malformed ingestion.
Exact answer spans are retained where a retrieved excerpt occurs in the answer.

These are evaluation dataset cases, not the required 25 distributed failure scenarios.
Lexical hashing plus an explicit alias dictionary is not a semantic embedding benchmark.
The injection tests establish only the deterministic prompt/tool authority boundary.

## Executed evidence

- application-tests.xml: local pytest result (ignored transient test output).
- APPLICATION_SMOKE.json: real HTTP server plus three separate executor processes,
  pinned version and durable continuation.
- BACKBONE_RESTART.json: accepted lost-ACK/OS-kill/read-only recovery regression.
- VERIFICATION.json: consolidated snapshot with source hashes and unrun gates.

No paid-provider quality, latency, cost or adversarial robustness results are claimed.
