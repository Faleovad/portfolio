# Durable Multi-Tenant AI Agent Platform

**ENGINEERING LAB / CLEAN-ROOM REFERENCE IMPLEMENTATION**

**STAGE 1 — RELEASE PASS · PUBLICLY PUBLISHED**

A synthetic engineering lab, not a production or commercial case.

| Verified Stage 1 gate | Result |
| --- | --- |
| Private GitHub Actions [run #7](https://github.com/Faleovad/portfolio-verification/actions/runs/41341505800) | **SUCCESS** |
| Python tests | **519/519 PASS** |
| Executable CLI scenarios | **53/53 PASS** |
| Native browser flows | **13/13 PASS** |
| Compose browser flows | **13/13 PASS** |
| Docker Compose runtime | **PASS** |
| Persisted restart/recovery | **PASS** |
| External mutation / dispatch attempt / receipt in the restart gate | **1 / 1 / 1** |
| Mandatory FAIL/PARTIAL gates for the verified candidate | **None** |

The private run requires repository access. Its retained results are available in
[CI evidence](docs/CI_RUN.json), [canonical verification](docs/VERIFICATION.json) and
[the requirement audit](docs/REQUIREMENT_AUDIT.md). [Measured size: 9,794 authored LOC](docs/METRICS.json).

> Executable source remains unchanged from the verified release candidate. This post-release commit only updates public documentation/presentation.

The canonical `VERIFICATION.json` is unchanged, point-in-time evidence for the exact
verified candidate, before publication. Its recorded fingerprint includes that
candidate's README; it does not identify this later documentation revision.
This docs-only update is not a new verified executable candidate.

A synthetic durable orchestration system. Current runnable flows cover a tenant-scoped
research pipeline and side-effect-safe tool recovery. No commercial provenance or
production-readiness is claimed.

## Persisted research flow

```text
pinned AgentVersion
  → ordered durable Plan/Step rows
  → retrieval + persisted source hits
  → validated ModelCall with bounded repair
  → optional explicitly authorized tool
  → read-only reconciliation if needed
  → five persisted evaluations
  → artifact with citation provenance
```

Completed steps are not rebuilt on continuation. Agent publication never changes an
existing task's pinned version. Retrieved text is untrusted data, not tool authority.
The default deterministic provider uses no external API or credential.

## Accepted reliability baseline

```text
independent provider commit → lost ACK → persisted UNKNOWN
→ dispatcher OS process killed → new recovery process
→ SELECT-only readback → terminal receipt → completion
```

The subprocess regression asserts **one external mutation and one dispatch attempt**.
Normal acknowledgements also require readback. Cancellation retains unresolved intents;
manual review never offers an unrestricted force retry.

## Implemented API

Synthetic tenant creation/authentication; agent publication/version inspection; tasks,
continuation, cancellation, events, steps, model calls, intents, receipts, artifacts,
provenance and evaluations; text document upload/search; recovery and manual review;
fault configuration; tenant-scoped metrics; health and non-destructive workspace reset.

The OpenAPI schema is served by the API. Cross-tenant UUID access is denied at the API
and scoped repository boundaries. This is synthetic authentication for a local lab,
not a production identity platform.

## Development / verification

Python 3.12+ and dedicated synthetic PostgreSQL databases are required for native tests.

```sh
python -m venv .venv
# Activate the environment for your operating system.
pip install -e ".[dev]"
pytest -q
ruff check backend tests tools
ruff format --check backend tests tools
mypy backend
python tools/metrics.py --release
```

Database integration tests require explicit ORCHESTRATOR_DSN,
ORCHESTRATOR_ADMIN_DSN, PROVIDER_ADMIN_DSN, PROVIDER_WRITE_DSN and PROVIDER_READ_DSN.
Use dedicated disposable lab databases only. tools/bootstrap_local.py provisions the
synthetic schema/roles from LAB_ADMIN_DSN. A run without those test DSNs skips integration
tests and is not complete verification.

Run an API process with ORCHESTRATOR_DSN and PROVIDER_READ_DSN:

```sh
uvicorn platform_core.api:from_environment --factory --host 127.0.0.1 --port 8000
python -m platform_core.executor
```

The native dispatcher uses PROVIDER_WRITE_DSN, or PROVIDER_URL for the separate HTTP
provider service. Recovery receives only the reader DSN. tools/verify_application.py exercises a real local HTTP server
and separate executor processes. Do not run it concurrently with database-reset tests.

compose.yaml includes PostgreSQL with a persistent volume, initialization, API, executor,
dispatcher, read-only recovery, independent HTTP provider, synthetic control service and
React console. **Docker Compose runtime PASS** was established in private GitHub
Actions run #7. Public credentials named synthetic-only are intentionally synthetic
defaults, never client credentials.

## Executable reliability scenarios

The scenario layer is separate from pytest. Each specification has setup, durable faults,
execution steps, expected state path, provider/receipt expectations and final assertions.
Every invocation creates new synthetic state; it never truncates another run's history.

```sh
python -m platform_core.scenarios list
python -m platform_core.scenarios run S04
python -m platform_core.scenarios run-all
```

Provide ORCHESTRATOR_DSN, PROVIDER_WRITE_DSN and PROVIDER_READ_DSN as above.
Results are written to docs/scenario-results/Sxx.json. Generated evidence does not count
as authored LOC. There are 53 specifications, including the original S01–S25 and distinct
step-crash, rollback, visibility, admission and recovery-budget flows.

## Operational console

The console inspects three independent layers: orchestrator knowledge, actual synthetic
provider state and confirmed receipts. It exposes the persisted workflow, leases/revisions,
model calls, recovery attempts, manual review, provenance, evaluations, budgets and events.
No business state is synthesized in the browser.

For native development, start these processes in separate shells with the lab DSNs:

```sh
uvicorn platform_core.api:from_environment --factory --host 127.0.0.1 --port 58042
# The next process additionally requires PROVIDER_WRITE_DSN and ENABLE_LAB_CONTROLS=1.
uvicorn platform_core.control_api:from_environment --factory --host 127.0.0.1 --port 58043
cd frontend
npm ci
npm run dev -- --port 58045
```

Open http://127.0.0.1:58045. Create S04 and press Step: provider COMMITTED, orchestrator
UNKNOWN, recovery PENDING, receipt NONE. Recover runs a separate read-only process;
the receipt appears while mutation and dispatch counts remain one. S06 supports actual
worker termination and restart. OS-kill controls are restricted to its defined boundary.

Scenarios are marked lab_controlled atomically at creation. Background workers skip
them; scoped laboratory commands execute their stored steps. Ordinary API tasks continue
to execute automatically. Reset creates a new tenant; prior histories/fences remain.

```sh
cd frontend
npx playwright install chromium
npm test
```

Playwright starts the real API/control/UI processes and uses PostgreSQL. It makes no API
mocks. Never run browser/scenario flows concurrently with pytest's database-reset fixtures.
Seven actual browser captures are in docs/screenshots/.

## Verification and Compose

All seven executed phases below passed in the verified Stage 1 run. The commands are
provided for independent reproduction; use the dedicated synthetic databases described
above. Run pytest separately from scenarios and browser flows because its fixtures reset
lab databases.

```sh
python tools/verify_release.py --phase static
python tools/verify_release.py --phase python
python tools/verify_release.py --phase scenarios
python tools/verify_release.py --phase browser
# Docker is required for these three phases:
python tools/verify_release.py --phase compose
python tools/verify_release.py --phase compose_restart
python tools/verify_release.py --phase compose_browser
```

Each phase records commands, exit codes and the full authored snapshot fingerprint,
including documentation. Missing or stale receipts fail closed. This documentation-only
revision changes that full fingerprint; the retained receipts and canonical verification
continue to describe the exact released executable candidate. They have not been
rewritten or presented as a new verification run for this documentation commit.
Python test functions, parameterized cases, PostgreSQL cases, scenarios and browser
flows are counted separately.

For container startup:

```sh
docker compose up --build -d
# Open http://127.0.0.1:58045
```

The Compose smoke verified automatic background dispatch through the HTTP provider,
read-only reconciliation, one effect, one dispatch, RAG and tenant denial. The separate
restart gate executed S06 inside the control container: an actual dispatcher OS-process
kill after persisted UNKNOWN, a replacement dispatcher and a new SELECT-only recovery
process. It finished with one external mutation, one dispatch attempt and one receipt.
This proves the recorded process-restart boundary; it is not a database-container
restart or catastrophe-restore result.

The GitHub Actions workflow executed these gates and uploaded the evidence. Private
run #7 completed successfully; Docker runtime and persisted restart/recovery are **PASS**.

## Evidence and limits

- [Implementation checkpoint](docs/IMPLEMENTATION_STATUS.md)
- [Architecture and transaction boundaries](docs/ARCHITECTURE.md)
- [State machines](docs/STATE_MACHINES.md)
- [Failure model](docs/FAILURE_MODEL.md)
- [Model/RAG/evaluation contract](docs/EVALUATIONS.md)
- [Verification snapshot](docs/VERIFICATION.json)
- [Process restart proof](docs/BACKBONE_RESTART.json)
- [Real HTTP/research continuation proof](docs/APPLICATION_SMOKE.json)
- [Authored LOC manifest](docs/LOC_MANIFEST.json)
- [Scenario catalog and failure contracts](docs/SCENARIOS.md)
- [Budget/cancellation/manual-review policy](docs/POLICIES.md)
- [Operational console and real captures](docs/CONSOLE.md)
- [Defects found and fixed during this milestone](docs/MILESTONE_FIXES.md)

The 27 evaluation samples (26 executable tasks and one rejected upload) are not the required 25 failure scenarios.
Lexical hashing plus a small alias dictionary is not a semantic retrieval benchmark.
The centralized fault engine has 26 executable durable modes, covered by the scenario
catalog. Native, Docker and external CI results are retained in VERIFICATION.json
and CI_RUN.json. All mandatory gates for the verified Stage 1 candidate passed.
The size gate fails below 5,000 meaningful authored code LOC. No padding is permitted,
and passing the size gate alone does not authorize release.

## Implemented tool boundaries and architecture

Search persists read-only catalog observations; CRM creates/updates entities; quota
atomically adjusts integer units; Email delivers to a synthetic inbox; HTTP operates
on constrained synthetic resource paths. No real money, SMTP or arbitrary outbound
URL is used. See [tool matrix](docs/TOOL_REQUIREMENTS.json),
[security model](docs/SECURITY_MODEL.md) and [eight architecture views](docs/ARCHITECTURE_VIEWS.md).

For reproducible container startup: `docker compose up --build -d`, then open
http://127.0.0.1:58045. Run `python tools/verify_compose.py` for runtime smoke and
`python tools/verify_compose_restart.py` for the in-container process-restart gate.
The verified private CI snapshot was compared before and after execution. The
retained manifest identifies that exact snapshot; the README change in this docs-only
revision is intentional. Generated results are excluded from authored-source accounting.
