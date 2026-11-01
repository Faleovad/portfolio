# Backend / API / CRM / AI Automation Engineer

I build and extend integrations between business systems, CRMs, marketplaces, and online stores. My work includes tracing production failures, mapping data contracts, and making recovery safe when an external API response does not establish whether a change took effect.

## Areas of work

- **Backend & APIs:** Python, FastAPI, Django, PostgreSQL / SQL, REST APIs, webhooks, OAuth.
- **Business integrations:** CRM and ERP / OMS / WMS workflows; KeyCRM, Pipedrive, amoCRM.
- **Automation & data:** n8n, Make, AI / LLM integrations, Playwright, scraping.
- **E-commerce:** Shopify, WooCommerce, OpenCart, marketplace and inventory integrations.
- **Production reliability:** debugging, idempotency, reconciliation, failure testing, and controlled releases.

These are my working areas and stack. Each case below identifies the technologies and responsibilities specific to that engagement.

## Executable Engineering Labs

### Durable AI Agent Platform

**ENGINEERING LAB / CLEAN-ROOM REFERENCE IMPLEMENTATION**

[Durable AI Agent Platform](demos/durable-ai-agent-platform/README.md) is a published Stage 1 synthetic engineering lab for durable, tenant-scoped agent execution, tool mutations, read-only reconciliation and persisted recovery. **This is not a production or commercial case.**

**Stage 1 — RELEASE PASS.** The project and its evidence are published as the exact verified snapshot; snapshot documents retain the status recorded at verification.

- **9 794 authored LOC**.
- **519/519 tests PASS** and **53/53 executable scenarios PASS**.
- **13/13 browser flows PASS** in both native and Docker Compose environments.
- **Docker Compose runtime PASS** and **persisted restart/recovery PASS**.
- Verified recovery path: `commit → lost ACK → UNKNOWN → restart → recovery → receipt → COMPLETED`.
- Restart gate: **1 external mutation / 1 dispatch attempt / 1 receipt**, with an actual dispatcher process kill inside a container, a replacement dispatcher and a separate read-only recovery process.

[Canonical verification](demos/durable-ai-agent-platform/docs/VERIFICATION.json) · [Requirement audit](demos/durable-ai-agent-platform/docs/REQUIREMENT_AUDIT.md) · [Measured metrics](demos/durable-ai-agent-platform/docs/METRICS.json) · [A1–A8 architecture views](demos/durable-ai-agent-platform/docs/ARCHITECTURE_VIEWS.md) · [Real browser captures](demos/durable-ai-agent-platform/docs/SCREENSHOTS.json)

### Order Reliability Lab

[Order Reliability Lab](demos/order-reliability/README.md) — clean-room FastAPI / SQLite / React simulation with persisted journals, mutation fences, read-only recovery, deterministic failure scenarios, and automated backend/browser tests. This is independently runnable demo code, separate from the private commercial implementation.

## Featured Case Studies

| Case | Work | Read |
| --- | --- | --- |
| **eBay / KeyCRM — Production Order & Warehouse Reliability** | Reliability engineering around an existing ERP / OMS integration: bundles, reservations, fulfillment, durable recovery, and external side effects. | [Case study](cases/ebay-keycrm-erp/README.md) · [Evidence & limits](cases/ebay-keycrm-erp/architecture/evidence.md) |
| **CoinAsk — SaaS Product & Marketing Analytics Infrastructure** | Browser/server analytics integration with identity, attribution, consent and data-quality debugging. | [Case study](cases/coinask-analytics/README.md) · [Evidence & limits](cases/coinask-analytics/evidence.md) |

These cases describe real commercial work. They distinguish production observations from local implementation and test results. Client identities, customer data, credentials, and confidential infrastructure are omitted; private implementation and operational records are not published here.

For the flagship case, the evidence section explains what the retained reports establish, which regression gates passed, and what remained unresolved.

[GitHub profile](https://github.com/Faleovad)
