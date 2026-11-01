Нужно спроектировать и реализовать с нуля отдельный публичный engineering showcase.

Это НЕ коммерческий кейс.

Позиционирование:

# Durable Multi-Tenant AI Agent Platform

Clean-room reference implementation production-oriented AI backend, где AI-задачи могут выполняться долго, падать, перезапускаться, вызывать инструменты, использовать retrieval, ждать внешних результатов и безопасно продолжаться после restart без потери состояния или повторного выполнения опасных side effects.

Главная цель:

показать серьёзную backend / AI / distributed-systems инженерную работу, а не очередной чат с OpenAI API.

# 1. Жёсткий размер проекта

Это обязательный acceptance criterion.

Финальная система должна содержать **НЕ МЕНЕЕ 5 000 authored code LOC суммарно**.

В LOC можно учитывать:

- backend Python;
- frontend TypeScript / TSX / CSS;
- automated tests;
- SQL schemas / migrations;
- собственные CLI / verification / tooling scripts.

НЕ учитывать:

- Markdown/docs;
- JSON verification receipts;
- generated code;
- `package-lock.json`;
- dependency lock files;
- vendored libraries;
- build output;
- node_modules;
- virtual environments;
- generated OpenAPI;
- generated migrations без ручной логики;
- screenshots/SVG;
- fixtures, состоящие в основном из больших данных;
- пустые/искусственно размноженные файлы.

Минимум 5 000 LOC должен быть достигнут **реальной функциональностью**.

Предпочтительная естественная структура:

- backend: примерно 2 500-4 000+ LOC;
- frontend: примерно 1 000-2 000+ LOC;
- tests: примерно 1 000-2 000+ LOC;
- SQL/tools: дополнительный объём.

Это не квоты по слоям, но проект не должен получить 5 000 LOC за счёт одного огромного тестового fixture или UI boilerplate.

Если после реализации architecture/system requirements получилось меньше 5 000 authored LOC:

**НЕ публикуй проект.**

Продолжай развивать реальные части системы:

- recovery;
- concurrency;
- evaluations;
- scenarios;
- observability;
- RAG;
- authorization;
- frontend operational tooling;
- tests;

пока meaningful authored code LOC не станет >= 5 000.

Никакого padding.

В финальном verification автоматически посчитать LOC по категориям и сохранить список учитываемых файлов.

---

# 2. Основная задача

Платформа должна позволять нескольким изолированным пользователям создавать AI tasks.

Пример:

`Research → retrieve documents → reason → call tools → validate output → produce structured result`

Execution состоит из durable steps.

Если процесс умер после шага 7 из 12:

- состояние не теряется;
- завершённые expensive steps не выполняются заново без причины;
- external tool side effects не повторяются вслепую;
- task продолжается с безопасной точки;
- ambiguous tool result переводится в reconciliation/UNKNOWN.

---

# 3. Стек

Backend:

- Python 3.12+
- FastAPI
- PostgreSQL
- Pydantic v2
- asyncio/httpx
- SQLAlchemy async или другой слой только если оправдан архитектурно

Worker:

- отдельный worker process;
- durable execution;
- несколько конкурентных workers;
- собственная state/ownership semantics.

Frontend:

- React + TypeScript;
- Vite или Next.js;
- полноценная operational console.

Infra:

- Docker Compose;
- PostgreSQL;
- backend;
- worker;
- frontend;
- Redis только если реально нужен.

Tests:

- pytest;
- Playwright.

CI:

- GitHub Actions.

Не добавлять технологии только ради списка.

---

# 4. Масштаб

Ориентир:

- >= 5 000 authored code LOC - ОБЯЗАТЕЛЬНО;
- 40-80 meaningful backend modules;
- 100+ meaningful automated tests;
- 15-30+ API endpoints;
- 20-30+ executable scenarios;
- несколько state machines;
- полноценная persistence model;
- полноценный frontend.

Не искусственно раздувать число файлов.

---

# 5. Domain model

Минимум:

### Tenant
Изолированный пользователь/organization.

### Agent
Логическое определение агента.

### AgentVersion
Immutable published configuration.

### Task
End-to-end execution.

### Run
Конкретная execution/continuation attempt.

### Step
Durable execution unit.

### ModelCall
LLM invocation.

### ToolIntent
Намерение выполнить внешний side effect.

### ToolReceipt
Immutable proof результата.

### RecoveryTask
Durable recovery/reconciliation item.

### Artifact
Результат исполнения.

### Event
Append-only operational history.

### Evaluation
Проверка качества/invariants.

### Document
RAG source.

### RetrievalChunk
Retrieval unit.

### RetrievalHit
Provenance конкретного поиска.

---

# 6. Multi-tenancy

Tenant isolation - настоящий invariant.

Нельзя:

- получить чужой Task;
- увидеть чужой Artifact;
- читать чужие documents;
- использовать чужой AgentVersion;
- выполнять чужой RecoveryTask;
- читать чужой Event timeline.

Isolation проверять:

- API;
- service layer;
- repository layer;
- tests.

Не только UI.

---

# 7. Durable workflow engine

Не делать обычную async-функцию из последовательности вызовов.

Нужна state machine:

CREATED
→ QUEUED
→ RUNNING
→ WAITING_MODEL
→ WAITING_TOOL
→ WAITING_READBACK
→ RECOVERING
→ COMPLETED

Дополнительные:

UNKNOWN  
FAILED_RETRYABLE  
FAILED_TERMINAL  
MANUAL_REVIEW  
CANCEL_REQUESTED  
CANCELLED  
BUDGET_EXHAUSTED

Каждый Step:

- id;
- task_id;
- run_id;
- sequence;
- type;
- state;
- attempt;
- input fingerprint;
- output reference;
- owner;
- lease;
- revision;
- idempotency key;
- timestamps;
- error class.

Все transitions валидировать.

---

# 8. Worker ownership

Несколько workers должны безопасно конкурировать.

Реализовать:

- claim;
- lease;
- heartbeat;
- ownership token;
- revision;
- compare-and-set;
- lease expiry;
- stale writer protection.

Критически:

**lease expiry != permission to repeat an unknown side effect.**

---

# 9. Synthetic external tools

Минимум:

### Search Tool
read-only.

### CRM Tool
создание/изменение synthetic CRM entity.

### Quota/Payment Tool
изменение synthetic balance/quota.

### Email Tool
synthetic send.

### HTTP Tool
generic synthetic provider.

External state должен существовать отдельно от orchestrator state.

---

# 10. Fault semantics

Tool provider должен моделировать:

- success;
- timeout before commit;
- commit then timeout;
- error before commit;
- ambiguous error after commit;
- delayed visibility;
- stale reads;
- read outage;
- duplicate request;
- lost acknowledgement.

---

# 11. Tool mutation safety

Перед внешней mutation persist:

- intent;
- payload fingerprint;
- external identity;
- idempotency identity;
- mutation type;
- owner;
- dispatch state.

Lifecycle:

PREPARED
→ SENT
→ CONFIRMED

или:

PREPARED
→ SENT
→ UNKNOWN

UNKNOWN автоматически обратно в PREPARED не переводится.

Blind replay запрещён.

---

# 12. Read-only recovery

RecoveryService не должен иметь mutating tool port.

Он может:

- читать external state;
- читать intents;
- сверять identities/fingerprints;
- подтверждать effect;
- записывать receipt;
- создавать manual review;
- завершать recovery metadata.

Архитектурно невозможно сделать mutating call из recovery path.

---

# 13. LLM abstraction

`ModelProvider` interface.

Минимум:

- deterministic fake provider для CI;
- optional OpenAI-compatible adapter.

CI не требует платного API.

---

# 14. Structured model outputs

Использовать schema-based outputs.

Например:

```json
{
  "decision": "continue",
  "confidence": 0.82,
  "tool_requests": [],
  "reason_codes": []
}
```

Pydantic validation.

Malformed output:

- bounded repair;
- retry policy;
- terminal/manual-review при исчерпании.

---

# 15. Planner / Executor

Архитектура:

Planner
→ persisted Plan
→ Step Executor
→ Model
→ Tool
→ Observation
→ Evaluator
→ Finalizer

Plan сохраняется durable.

Restart не должен беспричинно строить новый plan.

---

# 16. Agent versioning

AgentVersion immutable.

Task хранит:

`agent_version_id`

Изменение текущего Agent не меняет уже выполняющийся Task.

Обязательно протестировать.

---

# 17. RAG

Настоящий retrieval pipeline:

- document upload;
- validation;
- parsing;
- chunking;
- embeddings abstraction;
- storage;
- search;
- tenant isolation;
- retrieval provenance.

Для CI deterministic local embedding.

PostgreSQL/pgvector использовать только если это реально оправдано.

---

# 18. Retrieval provenance

Final artifact должен позволять понять:

- какой Document;
- какой Chunk;
- score;
- на каком Step использован;
- какую часть результата поддерживал.

---

# 19. Prompt injection boundary

Synthetic malicious documents.

Retrieved content = untrusted data.

Проверить, что инструкции из документа не получают system authority.

Не заявлять абсолютную защиту от prompt injection.

---

# 20. Tool permissions

AgentVersion содержит explicit allowlist.

Попытка вызвать запрещённый tool блокируется до создания side effect.

---

# 21. Budgets

Task budgets:

- model calls;
- tool calls;
- steps;
- estimated tokens/cost;
- recovery attempts;
- logical execution duration.

Retry не должен обходить budget.

---

# 22. Cancellation

Cancellation до external mutation:

→ CANCELLED.

Cancellation при `SENT/UNKNOWN`:

CANCEL_REQUESTED
→ reconciliation
→ CANCELLED

или:

→ MANUAL_REVIEW.

Нельзя удалить unresolved intent.

---

# 23. Manual review

Operational queue.

Показывать:

- task;
- step;
- intent;
- reason;
- external observations;
- available safe actions.

Не делать unrestricted `Force retry`.

---

# 24. Event history

Append-only event log.

Примеры:

task_created  
worker_claimed  
step_started  
model_called  
model_output_invalid  
tool_intent_prepared  
tool_dispatched  
tool_response_lost  
state_unknown  
recovery_claimed  
effect_confirmed  
manual_review  
task_completed

Frontend timeline строить по фактическим persisted events.

---

# 25. Observability

Structured logs:

- correlation ID;
- tenant ID;
- task ID;
- run ID;
- step ID;
- tool intent ID;
- worker ID.

Metrics endpoint:

- queued;
- running;
- recovering;
- unknown;
- manual review;
- completed;
- failed;
- ambiguous tool outcomes.

---

# 26. Central fault injection

Один durable Fault Engine.

Не делать разбросанные:

`if scenario == ...`

Минимум 20 fault modes:

1. model timeout
2. malformed model output
3. worker crash before commit
4. worker crash after commit
5. tool timeout before commit
6. tool commit then timeout
7. delayed visibility
8. stale readback
9. readback outage
10. lost acknowledgement
11. lease expiry
12. stale worker write
13. DB rollback
14. duplicate enqueue
15. cancellation during UNKNOWN
16. retrieval outage
17. malformed document
18. budget exhaustion
19. competing workers
20. manual review escalation

Можно расширять.

---

# 27. Executable scenarios

Минимум 25:

S01 Normal research  
S02 RAG + citations  
S03 Tool mutation normal  
S04 Commit then timeout  
S05 Timeout before commit  
S06 Restart recovery  
S07 Duplicate enqueue  
S08 Worker race  
S09 Stale worker  
S10 Lost tool ACK  
S11 Malformed model output  
S12 Model outage  
S13 Retrieval outage  
S14 Prompt injection document  
S15 Tenant isolation violation  
S16 Tool permission violation  
S17 Budget exhaustion  
S18 Cancel before mutation  
S19 Cancel during UNKNOWN  
S20 Agent version changed mid-run  
S21 Unprovable effect → manual review  
S22 Delayed visibility  
S23 Stale visibility beyond policy  
S24 Restart during recovery  
S25 Terminal receipt replay

Добавлять дополнительные, если архитектура даёт полезные failure boundaries.

---

# 28. Critical invariants

Минимум:

INV01 - one logical step cannot have two valid owners.

INV02 - stale worker cannot commit after ownership transfer.

INV03 - UNKNOWN side effect never blindly replayed.

INV04 - recovery cannot mutate provider.

INV05 - terminal receipt blocks replay.

INV06 - tenant isolation.

INV07 - pinned AgentVersion.

INV08 - tool allowlist before dispatch.

INV09 - retries cannot bypass budgets.

INV10 - cancellation cannot erase unresolved intent.

INV11 - malformed model output cannot advance execution.

INV12 - retrieval provenance retained.

INV13 - duplicate enqueue does not duplicate execution.

INV14 - commit-before-ack represented explicitly.

INV15 - manual review does not release mutation safety.

---

# 29. Database

Нормализованные tables.

Минимум:

tenants  
agents  
agent_versions  
tasks  
runs  
steps  
model_calls  
tool_intents  
tool_receipts  
recovery_tasks  
documents  
chunks  
retrieval_hits  
artifacts  
evaluations  
events  
fault_plans

Использовать constraints/indexes для invariants.

Не хранить весь workflow одним JSON blob.

---

# 30. Transaction boundaries

Документировать:

- что persisted до external request;
- что после request;
- где находится non-atomic boundary;
- какие outcomes ambiguous;
- что является proof;
- что является observation.

---

# 31. API

Tenant:
- create/list

Agents:
- create
- publish version
- inspect

Tasks:
- create
- list
- get
- run/continue
- cancel
- events
- artifacts

Documents:
- upload
- list
- inspect
- retrieval search

Recovery:
- list
- inspect
- reconcile

Manual review:
- list
- inspect
- resolve metadata-safe actions

Faults:
- configure
- inspect

System:
- health
- metrics
- synthetic reset

---

# 32. Frontend

Operational console, не generic CRUD admin.

Панели:

### Task overview
### Workflow graph
### Worker ownership / lease
### Model calls
### Tool intents
### External provider state
### Recovery queue
### Manual review
### Retrieval provenance
### Event timeline
### Budget usage
### Evaluations

---

# 33. Truth layers

В UI явно разделять:

**Orchestrator knowledge**

**External actual state**

**Confirmed proof**

Главный пример:

Provider:
`COMMITTED`

Orchestrator:
`UNKNOWN`

ToolIntent:
`UNKNOWN`

Recovery:
`PENDING`

---

# 34. Scenario controls

- Select scenario
- Reset
- Run
- Step
- Crash worker
- Restart worker
- Recover
- Cancel

---

# 35. Frontend quality

Responsive.

Нормальные:

- tables;
- timelines;
- badges;
- state visualization;
- loading states;
- error states;
- mobile layout.

Без fake animations.

---

# 36. Testing

Цель - 100+ meaningful automated tests.

Проверять:

- state machines;
- repositories;
- tenant isolation;
- concurrency;
- leases;
- stale workers;
- tool intents;
- receipts;
- recovery;
- cancellation;
- budgets;
- RAG;
- injection boundary;
- AgentVersion;
- API;
- scenarios;
- restart persistence;
- UI/browser flows.

---

# 37. Real restart

Обязательно реальный process/container restart.

Сценарий:

task
→ external tool commit
→ response lost
→ UNKNOWN
→ worker termination
→ new worker
→ read-only recovery
→ external observation
→ confirmation
→ receipt
→ completion

Проверить:

**ровно один external mutation.**

---

# 38. Docker Compose

Запускает:

- PostgreSQL;
- backend;
- worker;
- frontend;
- optional Redis.

Persistent volume.

CI должен реально запускать Compose.

---

# 39. CI

GitHub Actions:

- lint;
- formatting;
- typing;
- backend tests;
- frontend checks;
- TS build;
- Playwright;
- Compose config;
- Compose runtime;
- restart smoke;
- tenant isolation smoke;
- recovery smoke;
- LOC verification;
- metrics;
- secret scan.

---

# 40. Security

Минимум:

- synthetic auth;
- tenant authorization;
- payload validation;
- upload limits;
- safe filenames;
- no secrets in logs;
- tool permissions;
- no arbitrary shell execution;
- prompt/tool boundary.

---

# 41. Evaluations

Evaluation subsystem как persisted entity.

Минимум:

### Schema evaluator

### Citation evaluator

### Tool-use evaluator

### Expected-result evaluator

### Invariant evaluator

---

# 42. AI evaluation dataset

20-30+ synthetic tasks.

Проверять:

- correctness;
- citations;
- tool choice;
- structured output;
- irrelevant context;
- malformed docs;
- mixed-language retrieval.

---

# 43. Cross-language

Documents на:

- украинском;
- русском;
- английском.

Query на одном языке может ссылаться на source на другом.

CI implementation deterministic.

Не выдавать fake embedding за benchmark semantic model.

---

# 44. Demo data

Только synthetic.

Никаких реальных клиентов/данных.

---

# 45. Documentation

`demos/durable-ai-agent-platform/README.md`

`docs/ARCHITECTURE.md`

`docs/STATE_MACHINES.md`

`docs/FAILURE_MODEL.md`

`docs/SECURITY_MODEL.md`

`docs/EVALUATIONS.md`

`docs/VERIFICATION.json`

Не создавать сотни markdown-файлов.

---

# 46. Architecture diagrams

Минимум:

A1 System topology  
A2 Task lifecycle  
A3 Ambiguous tool mutation  
A4 Worker ownership  
A5 Recovery architecture  
A6 Tenant isolation  
A7 RAG provenance  
A8 Cancellation during UNKNOWN

---

# 47. Screenshots

Реальные captures:

1. Normal task
2. Commit then timeout
3. Recovery after restart
4. Tenant isolation denial
5. RAG provenance
6. Manual review
7. Worker race/stale owner

---

# 48. Automatic metrics

Создать metrics script.

Считать:

- backend LOC;
- frontend LOC;
- test LOC;
- SQL/tooling LOC;
- total authored code LOC;
- modules;
- tests;
- API endpoints;
- tables;
- state entities;
- fault modes;
- scenarios;
- invariants;
- diagrams.

### HARD ASSERTION

Если:

`total_authored_code_loc < 5000`

metrics command должен завершаться с non-zero exit code для release verification.

CI также должен падать.

То есть 5 000 LOC - не пожелание в README, а автоматический release gate.

---

# 49. LOC integrity

Metrics script должен сохранить:

- каждый учитываемый файл;
- category;
- LOC;
- excluded reason для generated/vendor/lock/artifact files.

Создать, например:

`docs/LOC_MANIFEST.json`

Никакого ручного написания числа `5000`.

Число вычисляется из source tree.

---

# 50. Verification receipt

`docs/VERIFICATION.json`

Включить:

- commit SHA;
- source hashes;
- LOC metrics;
- >=5000 LOC gate;
- backend tests;
- browser tests;
- Compose;
- restart;
- recovery;
- scenario count;
- invariant count.

PASS только для реально выполненных checks.

---

# 51. Portfolio integration

После полной готовности добавить:

# Durable AI Agent Platform

`ENGINEERING LAB / CLEAN-ROOM REFERENCE IMPLEMENTATION`

Описание:

`Multi-tenant AI orchestration reference implementation with durable workflows, tool-side-effect safety, read-only recovery, RAG provenance, evaluations and deterministic fault injection.`

Не выдавать за коммерческий проект.

---

# 52. Не использовать buzzword complexity

Не добавлять Kafka/Kubernetes/LangChain/Temporal только ради впечатления.

Сложность должна идти из correctness problem:

- durable state;
- ownership;
- side effects;
- recovery;
- tenant isolation;
- AI uncertainty;
- evaluation.

---

# 53. Центральный принцип

Проект должен доказывать:

> AI orchestration is a distributed state problem, not just a sequence of model calls.

Пользователь должен руками воспроизвести:

`tool committed`
→ `response lost`
→ `orchestrator UNKNOWN`
→ `worker crash`
→ `restart`
→ `read-only recovery`
→ `effect confirmed`
→ `terminal receipt`
→ `no duplicate side effect`

Плюс:

`Agent updated`
→ old task uses pinned AgentVersion

и:

`Tenant B requests Tenant A data`
→ backend denies access.

---

# 54. Release gate

НЕ ПУБЛИКОВАТЬ проект, пока одновременно не выполнены:

- total authored code LOC >= **5 000**;
- backend tests green;
- frontend/browser tests green;
- typing/lint green;
- Docker Compose green;
- real restart scenario green;
- UNKNOWN recovery green;
- external mutation count verified;
- tenant isolation green;
- RAG/provenance green;
- screenshots generated;
- documentation links valid;
- secret scan clean;
- PII scan clean;
- verification receipt generated.

Если хотя бы один обязательный gate красный:

проект остаётся unpublished/incomplete.

---

# Финальный отчёт

После публикации сообщи:

### Size
- total authored LOC;
- backend LOC;
- frontend LOC;
- tests LOC;
- SQL/tooling LOC;
- LOC manifest.

### Architecture
- components;
- DB entities;
- state machines;
- transaction boundaries.

### Verification
- test count;
- browser count;
- CI;
- Compose;
- restart recovery.

### Reliability
- fault modes;
- executable scenarios;
- invariants.

### AI
- model abstraction;
- RAG;
- tools;
- evaluations.

### Security
- tenant isolation;
- permissions;
- prompt/tool boundaries.

### Visuals
- diagrams;
- screenshots.

### Changed files

### Commit SHA

### Links

Главный критерий:

**После просмотра сильный backend/AI инженер должен увидеть полноценную durable orchestration system, а не LLM-wrapper.**

И дополнительный жёсткий критерий:

**финальная опубликованная система должна содержать минимум 5 000 автоматически подсчитанных authored code LOC без искусственного padding.**