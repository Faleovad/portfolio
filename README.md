# Backend / API / CRM / AI Automation Engineer

I build and extend integrations between business systems, CRMs, marketplaces, and online stores. My work includes tracing production failures, mapping data contracts, and making recovery safe when an external API response does not establish whether a change took effect.

## Areas of work

- **Backend & APIs:** Python, FastAPI, Django, PostgreSQL / SQL, REST APIs, webhooks, OAuth.
- **Business integrations:** CRM and ERP / OMS / WMS workflows; KeyCRM, Pipedrive, amoCRM.
- **Automation & data:** n8n, Make, AI / LLM integrations, Playwright, scraping.
- **E-commerce:** Shopify, WooCommerce, OpenCart, marketplace and inventory integrations.
- **Production reliability:** debugging, idempotency, reconciliation, failure testing, and controlled releases.

These are my working areas and stack. Each case below identifies the technologies and responsibilities specific to that engagement.

## Executable Engineering Lab

[Order Reliability Lab](demos/order-reliability/README.md) — clean-room FastAPI / SQLite / React simulation with persisted journals, mutation fences, read-only recovery, deterministic failure scenarios, and automated backend/browser tests. This is independently runnable demo code, separate from the private commercial implementation.

## Featured Case Studies

| Case | Work | Read |
| --- | --- | --- |
| **eBay / KeyCRM — Production Order & Warehouse Reliability** | Reliability engineering around an existing ERP / OMS integration: bundles, reservations, fulfillment, durable recovery, and external side effects. | [Case study](cases/ebay-keycrm-erp/README.md) · [Evidence & limits](cases/ebay-keycrm-erp/architecture/evidence.md) |
| **CoinAsk — SaaS Product & Marketing Analytics Infrastructure** | Browser/server analytics integration with identity, attribution, consent and data-quality debugging. | [Case study](cases/coinask-analytics/README.md) · [Evidence & limits](cases/coinask-analytics/evidence.md) |

These cases describe real commercial work. They distinguish production observations from local implementation and test results. Client identities, customer data, credentials, and confidential infrastructure are omitted; private implementation and operational records are not published here.

For the flagship case, the evidence section explains what the retained reports establish, which regression gates passed, and what remained unresolved.

[GitHub profile](https://github.com/Faleovad)
