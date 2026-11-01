[← Case study](README.md) · [← Portfolio](../../README.md)

# Evidence ledger & limits

Public summary of a private forensic review completed November 1, 2026. Source files, correspondence, browser history and production configuration are not published. IDs below map to the private source index and allow the owner to trace each statement.

## Evidence labels

| Label | Meaning here |
|---|---|
| VERIFIED ARTIFACT | Retained document, vendor notice, download record or code diff was inspected. A specification proves requirements only. |
| CONVERSATION / SPEC EVIDENCE | A specification, team message or historical audit states the fact. Historical AI audit text is not a newly inspected source export. |
| RUNTIME OBSERVATION | Concrete historical request/debug details survive in conversation. This is not a fresh production capture. |
| IMPLEMENTED | Actual code/configuration changes survive in local diff records. Deployment is a separate question. |
| IMPLEMENTED + VERIFIED | The particular implementation behavior also has a retained observation; scope and environment must be named. |
| STRONG INFERENCE | Multiple traces support a conclusion, without direct proof of every step. |
| UNKNOWN | Evidence cannot establish the claim. |

Labels are not an automatic promotion ladder. No claim in this case implies complete production acceptance.

## Source register

| Source IDs | Retained material | What it establishes |
|---|---|---|
| D01–D06 | April event maps, integrator brief, UTM convention, seven-page specification and handoff | Intended architecture, event contract and responsibility boundaries |
| C01–C10 | April–June team correspondence preserved in notification emails | Creation/installation reports, loader regression, endpoint diagnosis, lifecycle checks, consent work and corrected dedup assumptions |
| C11–C13 | Stape and CMP operational notifications | Actual service usage and operational configuration issues; not business outcomes |
| H01 | Selected browser download metadata | 24 GTM JSON download records, July 16–August 18; original target files are currently absent |
| D10 | Four untruncated JSON change records; three fix-pack document records | Actual local implementation and import/Preview/rollback planning |
| D11/D12 | Partial original audit record and historical redaction manifest | Additional audit provenance; partial record is explicitly incomplete |
| R01 | July 19 CTA request details pasted from Tag Assistant | Debug CTA request through first-party server collection, parameters and decorated destination |
| R02 | August 3 backend input/output details | Correct outgoing client field, incorrect session field, HTTP 204 |
| R03 | June 8 consent debugging context | Clean Preview reject report; live still needed publication and accept-all verification |
| A01–A08 | July–August historical technical audits | Local fixes, version/workspace differences, later routing inventory and unresolved gates |

Private material was summarized, not copied wholesale. Customer infrastructure IDs, keys, domain-specific endpoints, online identifiers, email addresses and access links are omitted.

## Claim ledger

| Claim | Label | Source / practical limit |
|---|---|---|
| Separate Web and Server GTM containers existed | VERIFIED ARTIFACT + CONVERSATION / SPEC EVIDENCE | H01 filenames, D03 and C01/A01. Not a proof of every version serving |
| Stape hosted a receiving collection service | VERIFIED ARTIFACT + CONVERSATION / SPEC EVIDENCE | C11 vendor usage notice; C02/C06 endpoint reports |
| Browser CTA reached first-party GA4 collection | IMPLEMENTED + VERIFIED, Preview scope | D10 listener/tag changes and R01 debug request; not a production conversion KPI |
| Backend traffic reached GA4/Mixpanel | CONVERSATION / SPEC EVIDENCE; GA4 request RUNTIME OBSERVATION | C06/C07 and R02 |
| Mixpanel lifecycle naming/payload changes were checked live | CONVERSATION / SPEC EVIDENCE | May 26 author report specifically names payment_failed, renewed/refunded and fields; raw provider export unavailable |
| PostHog browser/base and backend tags were configured | CONVERSATION / SPEC EVIDENCE | A08 configuration audit. Independent PostHog receipt UNKNOWN |
| Meta browser + CAPI Primary/Backup scheme existed in later configuration | CONVERSATION / SPEC EVIDENCE | A04/A05/A08. No achieved EMQ or dedup percentage |
| Attribution capture and link decoration existed | VERIFIED ARTIFACT / RUNTIME OBSERVATION / CONVERSATION / SPEC EVIDENCE, scoped | D10 listener fields, R01 decorated destination, C09 contract and C12 cookie names |
| Canonical event source fallback was implemented locally | IMPLEMENTED | D10 server patches; final deployment not inferred |
| Session transformations were present in later configuration | CONVERSATION / SPEC EVIDENCE | A08; after-fix network request UNKNOWN |
| Cross-domain identifiers survived end to end | UNKNOWN | Decoration is observed, but no retained before/after collect pair establishes equal cid/sid |
| Complete consent behavior was accepted in production | UNKNOWN | Reject Preview evidence does not prove accept/revoke/reload on every host |
| Unified client-provided architecture guided implementation | STRONG INFERENCE | Specifications plus implementation, correspondence and audits. Actual paths include direct browser destinations |

## Retained code changes

These are short, manually sanitized excerpts of D10 local change records, not importable GTM exports. Symbolic names replace client-specific variable names. No source URL, dataset ID or credential is included.

**Server record 1 — separate destination settings and canonical source fallback**

```text
destination URL: literal credential → destination/token variable references
event_source_url default: disabled → enabled
fallback: landing_url
```

**Server record 2 — event context in three Meta request bodies**

```diff
- "event_source_url": "{{landing_url}}"
+ "event_source_url": "{{event_source_url}}"
  "event_id": "{{event_id}}"
```

Matching-field variable references remained present in the retained bodies. This proves a local payload edit, not verified match quality.

**Web record 3 — CTA listener correction**

```diff
- href.indexOf('/signup') !== -1
+ href.indexOf('/sign-up') !== -1
```

The retained listener includes installation protection, text normalization, event identifier generation, and a one-second repeated-click guard. Those controls do not establish backend exactly-once delivery.

**Web record 4 — GA4 CTA tag**

```text
event: cta_click
parameters: event_id, cta_text, destination_url, page_location
firing: once per event
consent requirements: analytics_storage, ad_storage,
                      ad_user_data, ad_personalization
```

The local candidate used an event-source variable for page_location; the later manual checkpoint describes Page URL. These snapshots are not merged into a fictional exact latest export.

## Runtime observations

**R01 · July 19 · Preview**

```text
destination: first-party GA4 collection
event: cta_click
client and session fields: present
CTA text / destination / page location: populated
destination link: linker and attribution parameters present
debug flag: enabled
```

This supports the particular debug path. It does not show a matching destination cid/sid after navigation.

**R02 · August 3 · backend request**

```text
input: client_id, session_id, subscription_started
output: cid matches input client_id
output: ep.session_id present; standard sid absent
response: HTTP 204
```

Later configuration added ga_session_id and excluded raw session_id for four core events in the GA4 backend tag (A08). No retained after-fix request establishes final serialization.

## Evolution and release boundaries

| Date | Evidence | Meaning |
|---|---|---|
| April–May | Specifications, creation and base tracking reports | Intended architecture followed by actual implementation/debugging activity |
| May 26–29 | Lifecycle payload checks; withdrawn dual-path Mixpanel concern | Canonical naming and actual event ownership mattered more than a generic dedup fix |
| June | CMP crawler/domain notices and consent Preview investigation | Operational use, with consent gates still requiring work |
| July 16 | Local fix pack; published/workspace audit | Concrete code edits; explicit no-publish boundary |
| July 19 | CTA Preview request | Scoped routing observation |
| July 24–27 | Destination version history and stale workspace audit | Duplicate-tag cleanup and prevention of configuration regression |
| August 3 | Backend session serialization defect | Transport success did not establish semantic correctness |
| August 18 | Later workspace audit, including PostHog | Expanded destination/configuration view with open acceptance gaps |

Download metadata corroborates this period; chronology does not imply 24 releases or uninterrupted production operation.

## Event counts and deduplication

- **22** rows in retained event-map specifications, including one dynamic quiz-step family.
- **9** subscription lifecycle names in the expanded contract.
- **4** core backend names in the later routing audit.
- **24** GTM JSON download records and **4** retained local JSON diff records.

There is no defensible total of production-verified events. The event table in the case selects concrete examples rather than claiming complete implementation.

May 29 correspondence explicitly removes the proposed Mixpanel dual-path fix: signup and account-connection events were backend-only. Meta Primary and Backup are separate destinations; one delivery to each is not a duplicate within one dataset. A historical duplicate Third-tag configuration is a separate issue. Actual duplicate volume and achieved dedup rate are UNKNOWN.

## Open gates and claims excluded

| Item | Retained state |
|---|---|
| Final launch-ready acceptance | UNKNOWN |
| Cross-domain client/session/source continuity | UNKNOWN; link decoration alone is insufficient |
| Final backend sid after transformations | UNKNOWN |
| BigQuery export / datasets / jobs | UNKNOWN; specified, not independently evidenced as deployed |
| Customer.io, Looker, Google Ads delivery | UNKNOWN; excluded from implemented architecture |
| PostHog accepted-event receipt | UNKNOWN |
| Complete consent matrix / legal compliance | UNKNOWN; no legal guarantee claimed |
| Global production hostname filter | Open in latest retained audit for several analytics tags |
| Onboarding event routing | Absent in latest retained audit |
| Meta revenue value/currency/custom_data | Absent from latest audited request bodies |
| Revenue/conversion/ROAS uplift, real paid-user count | UNKNOWN |
| Durable backend retries / exactly-once | UNKNOWN; specification is not implementation proof |

No raw credentials, historical customer identifiers, original exports, private correspondence or browser profile files are included. All diagrams are reconstructed public illustrations, not production screenshots.
