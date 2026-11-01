# Yaroslav — Backend / Systems / AI Automation Engineer

I build verifiable backend and integration systems — from investigation and architecture to implementation, recovery and operational verification.

**Python · FastAPI · PostgreSQL · Distributed State · API Integrations · CRM / ERP · AI Systems · Reliability Engineering**

Production ERP / OMS reliability · SaaS analytics infrastructure · Durable AI platform · Failure recovery & reconciliation · Multi-tenant backend systems

[Engineering Labs](#engineering-labs) · [Commercial Cases](#commercial-case-studies) · [Architecture & Evidence](#evidence-first-engineering)

## Featured Engineering Work

| Project | Type | Key proof |
| --- | --- | --- |
| **[Durable AI Agent Platform](demos/durable-ai-agent-platform/README.md)** | Engineering Lab | 9,794 authored LOC · 519 tests · 53 scenarios · persisted restart/recovery |
| **[eBay → KeyCRM ERP/OMS Reliability](cases/ebay-keycrm-erp/README.md)** | Commercial Case | Production reliability · bundles · reservations · reconciliation |
| **[CoinAsk Analytics Infrastructure](cases/coinask-analytics/README.md)** | Commercial Case | Browser/server analytics · identity · attribution · consent |

**Durable · Verified Stage 1 — RELEASE PASS**

519/519 tests · 53/53 scenarios · 13/13 browser flows in each of native and Compose. Docker Compose runtime **PASS** · persisted restart/recovery **PASS** · **1 mutation / 1 dispatch / 1 receipt**.

[Verification](demos/durable-ai-agent-platform/docs/VERIFICATION.json) · [Requirement audit](demos/durable-ai-agent-platform/docs/REQUIREMENT_AUDIT.md) · [Architecture A1–A8](demos/durable-ai-agent-platform/docs/ARCHITECTURE_VIEWS.md)

## What I do

- **Backend & Distributed Systems:** FastAPI, PostgreSQL, durable workflows, concurrency, state machines and idempotency.
- **Integrations & Automation:** CRM / ERP, marketplaces, APIs, webhooks, OAuth, n8n and Make.
- **Reliability Engineering:** failure reconstruction, ambiguous external state, reconciliation, recovery and release verification.
- **AI Systems:** LLM orchestration, tools, RAG, evaluations and multi-tenant agent infrastructure.

## Commercial Case Studies

Real engagements, with scoped production observations and explicit evidence limits.

- **[eBay / KeyCRM](cases/ebay-keycrm-erp/README.md)** — ERP / OMS / warehouse reliability. [Evidence & limits](cases/ebay-keycrm-erp/architecture/evidence.md).
- **[CoinAsk](cases/coinask-analytics/README.md)** — SaaS product and marketing analytics infrastructure. [Evidence & limits](cases/coinask-analytics/evidence.md).

## Engineering Labs

**ENGINEERING LAB / CLEAN-ROOM REFERENCE IMPLEMENTATION** — synthetic, independently reproducible projects. These are not production or commercial cases.

- **[Durable AI Agent Platform](demos/durable-ai-agent-platform/README.md)** — published Stage 1: tenant-scoped execution, tool mutations, persisted workflows, RAG and read-only recovery. [Metrics](demos/durable-ai-agent-platform/docs/METRICS.json) · [Browser captures](demos/durable-ai-agent-platform/docs/SCREENSHOTS.json).
- **[Order Reliability Lab](demos/order-reliability/README.md)** — FastAPI / SQLite / React simulation with persisted journals, mutation fences and deterministic failure scenarios.

## How I work

Investigate → model state and ownership → identify failure modes → define invariants → implement → test failure paths → verify runtime behavior.

## Evidence-first engineering

Each case distinguishes **production observations**, **implemented behavior**, **tested behavior**, **verified runtime evidence** and **unknowns**. Claims link to retained evidence where available; each result names its scope and environment.

Client identities, customer data, credentials and confidential infrastructure are omitted from commercial cases. Lab data is synthetic.

---

[GitHub profile](https://github.com/Faleovad)
