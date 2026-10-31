[← Case study](../README.md) · [Architecture index](full-system-map.md) · [Evidence labels](evidence.md)

# 50 critical end-to-end boundary chains

Exactly **50 selected chains** from the reviewed source/state census. Selection favors side-effect boundaries, source coverage, business postconditions and recoverability. They are reference/control chains, not 50 observed production executions. Validation-only paths deliberately end without an external effect.

**Path classes:** 14 failure · 16 normal · 13 recovery · 7 release/operations.

Evidence references T01–T14 identify source-backed runtime traces in the private inventory. Their relationship rows are indexed in the [sanitized public graph](full-forensic-graph.md); [SG IDs](safeguards.md) identify protection boundaries. A missing terminal proof means held/review, not invented success.

## Discovery / CREATE

### CC01 — Freeze source coverage

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

scheduled source read → frozen modified-time window → paginated source IDs → durable capture ACK → acknowledged prefix → cursor checkpoint.

- Safeguard: SG01 SG02. Final authority: Source/capture receipts, not business completion.
- Evidence: T01 T05. Scope: RC continuation differs from retained serving.

### CC02 — Discovery starvation

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

source order → repeated capped first pages → candidate never selected → no CREATE journal → no CRM identity/warehouse work → local continuation correction and reread coverage.

- Safeguard: SG02. Final authority: Source coverage and capture ACK.
- Evidence: T05. Scope: Conditional reproduction, not a proven lost live order.

### CC03 — Later-page failure

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

page one succeeds → next page fails → successful prefix may be discarded → downstream work delayed → local partial-prefix preservation → persist only acknowledged work.

- Safeguard: SG01 SG02. Final authority: Persisted prefix.
- Evidence: T05. Scope: Retained defect/local tested correction.

### CC04 — Old due retry ages out

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

source revision changes → rolling creation floor excludes due retry → no admission → fixed cutoff distinguishes creation from modification → existing retry reconsidered → capture receipt.

- Safeguard: SG02. Final authority: Approved cutoff and exact source revision.
- Evidence: T01 T05. Scope: Local correction; no global fairness guarantee.

### CC05 — Exact source identity

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

source order/selected lines → normalize → strict source correlation lookup → existing exact CRM match → existing-order path → identity retained without new POST.

- Safeguard: SG03. Final authority: Exact marketplace/CRM identity.
- Evidence: T01. Scope: Retained production flow; implementation variants remain.

### CC06 — Serialized duplicate prevention

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

same source identity → outer exact lookup → source-identity actor → repeated lookup under serialization → existing journal/result blocks second CREATE → exact identity receipt.

- Safeguard: SG03 SG04. Final authority: CREATE actor plus positive identity.
- Evidence: T01 T03. Scope: Not a tenant-global lock.

### CC07 — Persist before CREATE

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

validated payload → preparing → pending with phase=in_flight before transport → one POST → exact positive identity readback → completed identity journal.

- Safeguard: SG04 SG05. Final authority: create_state; reserve remains separate.
- Evidence: T01 T03. Scope: Independent post-CREATE GET is current RC behavior, not whole-serving parity.

### CC08 — CREATE committed, response lost

**recovery · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

CREATE dispatch → provider may commit → response/RPC loss → ambiguous journal → no blind recreate → exact identity lookup may reconcile completed result.

- Safeguard: SG04 SG14. Final authority: Positive exact identity; negative search is insufficient.
- Evidence: T03. Scope: Failure protocol/test path; not a new observed incident.

### CC09 — Possible-send flags lost

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

actor may dispatch → caller error aggregation drops flags → ordinary-looking retry receipt → durable actor still fences → read actor before report → retain ambiguity until exact match.

- Safeguard: SG04 SG16. Final authority: Actor journal over caller report.
- Evidence: T03. Scope: Conditional retained-code flag propagation defect.

### CC10 — Trusted preflight retry

**recovery · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

prepare → proven pre-dispatch failure → retryable_preflight → retry computation under existing identity guard → possible-send journal if admitted → exact identity result.

- Safeguard: SG15. Final authority: Trusted no-send boundary.
- Evidence: T03. Scope: Local RC distinction; timeout text is not no-send proof.

## Status / fulfillment / tracking

### CC11 — Capture existing status work

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

maintenance scan/hot-tail → capture existing_status revisions → durable ACK → own task lease → fresh source/CRM policy → guarded existing-order result.

- Safeguard: SG07 SG17. Final authority: Typed delivery ownership plus independent fence.
- Evidence: T02. Scope: Status task never authorizes CREATE.

### CC12 — Refresh eligibility

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

status task → fresh payment/refund/fulfillment/tracking → fresh CRM lines → existing policy decision → eligible guarded update or no-op/review → independently verified result.

- Safeguard: SG26. Final authority: Source facts and current exact CRM state.
- Evidence: T02. Scope: Not an invented universal AND-only policy.

### CC13 — One guarded fulfillment PUT

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

eligible exact order → root RUN/epoch → CRM-ID fence and fresh reserve checks → persist pending/dispatch marker → one PUT → exact fulfilled/tracking proof and receipt.

- Safeguard: SG08 SG09 SG10 SG11 SG12. Final authority: Mutation actor and root receipt.
- Evidence: T02. Scope: Retained bridge architecture; current full RC differs.

### CC14 — Tracking readback

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

source shipment/tracking → shipping delta → guarded existing-order update → pending evidence → fresh CRM shipping readback → verified sync summary.

- Safeguard: SG09 SG11 SG26. Final authority: Exact tracking correlation.
- Evidence: T02. Scope: Label printing alone is not warehouse fulfillment.

### CC15 — PUT committed then timeout

**failure · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

one PUT → provider may commit stock effect → response unavailable → mutation_pending/held unknown → fence prevents second PUT → bounded read-only confirmation or retained review.

- Safeguard: SG09 SG10 SG14. Final authority: Exact effect plus operation-specific settlement.
- Evidence: T04. Scope: No generic automatic resolver for every sent/unknown.

### CC16 — Stale accepted response

**failure · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

identified 200/202 acceptance → readback still stale → no terminal completion → bounded GET rereads → exact match or unknown → receipt only for confirmed effect.

- Safeguard: SG11 SG14. Final authority: Fresh identity/status/stock/tracking evidence.
- Evidence: T02 T04. Scope: Polling deadline is not remote cancellation proof.

### CC17 — Lost unlock metadata

**recovery · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

effect exactly confirmed → unlock/settlement reply lost → caller receives uncertainty → preserve confirmed-vs-settlement flags → reconcile own metadata → no extra PUT.

- Safeguard: SG13 SG14. Final authority: Completion tombstone and epoch receipt.
- Evidence: T04. Scope: Local flag preservation corrections differ from retained code.

### CC18 — Date-only disagreement

**recovery · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

status/tracking/stock independently confirmed → planned/actual shipping date differ → warning retained → verified summary reused → existing completion path settles → no corrective PUT for date alone.

- Safeguard: SG11 SG12. Final authority: Independent exact business/warehouse proof.
- Evidence: T02 T04. Scope: Serving incident fix; not all date mismatches are harmless.

## Warehouse / reserves / bundles

### CC19 — Active bundle meaning

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

source parent SKU → active effective rule version/hash → component expansion → catalog identity resolution → warehouse-specific exact component lines → distinct reserve/fulfilled checks.

- Safeguard: SG18 SG19. Final authority: Designated active rules and KeyCRM line evidence.
- Evidence: T07. Scope: Local malformed-input corrections are not all deployed.

### CC20 — Aggregate exact components

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

source quantities → canonical expansion → aggregate repeated SKU quantities → validate whole plan → exact CRM quantities → warehouse proof without parent-SKU inference.

- Safeguard: SG18 SG06. Final authority: Exact aggregate expected lines.
- Evidence: T07. Scope: Current inspected code; not a live stock test.

### CC21 — Partial bundle validation

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

parent expansion → invalid/unresolved component → partial map risk → local fail-closed full-rule validation → block whole plan before reserve → corrected authoritative input required.

- Safeguard: SG18. Final authority: Complete validated component plan.
- Evidence: T07. Scope: Conditional code defect; no actual wrong composition inferred.

### CC22 — Quantity overflow

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

safe-looking inputs → multiplication/aggregation overflow → wrong downstream quantity risk → local safe-integer checks → reject plan → no terminal warehouse claim.

- Safeguard: SG18. Final authority: Bounded validated quantities.
- Evidence: T07. Scope: Local test/candidate correction.

### CC23 — Reserve is separate from identity

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

CREATE identity completed → fresh CRM product detail → numeric warehouse and exact SKU quantities → reserved_valid check → reserve receipt → fulfillment still requires separate proof.

- Safeguard: SG05 SG06. Final authority: Current exact reserved lines.
- Evidence: T01 T07. Scope: More stringent validator fixes local.

### CC24 — Fulfilled warehouse proof

**normal · VERIFIED PRODUCTION** · Systems: eBay / Cloudflare / KeyCRM.

guarded status transition → CRM readback → exact identity/status/warehouse/fulfilled quantities → tracking check → verified completion → tombstone and task settlement.

- Safeguard: SG11 SG12 SG13. Final authority: Fresh line-level stock evidence.
- Evidence: T02. Scope: Current balance alone is not a linked movement ledger.

### CC25 — Warehouse aliases conflict

**failure · OBSERVED DEFECT** · Systems: eBay / Cloudflare / KeyCRM.

name/alias projection → numeric warehouse conflict hidden → false reserve/eligibility risk → local numeric-only conflict rejection → preserve hold/alert → no guessed stock correction.

- Safeguard: SG06 SG12. Final authority: Numeric warehouse and stock_status.
- Evidence: T07. Scope: Retained code risks; serving already blocks one distinct unsafe completion.

### CC26 — Historical reserve is not history

**recovery · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

current order appears reserved/DONE → old mutation/movement receipt absent → historical deduction unknown → retain legacy hold → linked provider/ledger reconciliation required → no generic completion proof.

- Safeguard: SG14 SG26. Final authority: Linked historical request and stock evidence.
- Evidence: T06 T14. Scope: Historical business acceptance remains incomplete.

## Recovery / reconciliation

### CC27 — Task ownership

**normal · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

captured revision → due index → transactional claim → owned lease → independent operation check → own finish/last_finished_lease receipt.

- Safeguard: SG07 SG17. Final authority: Delivery actor, not provider mutation authority.
- Evidence: T05. Scope: Full importer recovery consumer is RC-only.

### CC28 — Worker stops after possible side effect

**failure · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

persisted intent/dispatch → provider may apply → Worker stops → journal/fence survives → persisted task/read-only reconciliation → exact proof or retained review without replay.

- Safeguard: SG04 SG10 SG14. Final authority: Operation journal plus exact readback.
- Evidence: T03 T04 T05. Scope: Source/fault/restart evidence, not a claimed new production crash.

### CC29 — Lost task finish acknowledgement

**recovery · IMPLEMENTED + TESTED** · Systems: eBay / Cloudflare / KeyCRM.

business effect confirmed → task finish reply lost → delivery appears unsettled → consult last_finished_lease/tombstone → reconcile own finish only → no external mutation replay.

- Safeguard: SG13 SG17. Final authority: Own lease finish receipt.
- Evidence: T04 T05. Scope: Finish metadata and stock finality differ.

### CC30 — Source revision during lease

**recovery · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

leased older revision → new source revision captured → pending_revision retained → finish old ownership → newer work remains pending → fresh policy evaluation.

- Safeguard: SG07 SG17. Final authority: Revision-scoped task state.
- Evidence: T05. Scope: A newer revision cannot erase an unknown fence.

### CC31 — Expired processing KV

**failure · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

progress TTL expires → KV value absent → historical send not disproved → consult durable journal/fence → read exact CRM state → keep uncertainty when proof absent.

- Safeguard: SG14 SG16. Final authority: Durable operation evidence over KV absence.
- Evidence: T06 T14. Scope: Absence is not permission for CREATE.

### CC32 — Manual-review source changes

**failure · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

unknown/manual_review → new source timestamp or current DONE → apparent retry opportunity → persistent hold blocks reopen → operation-specific evidence review → no generic release.

- Safeguard: SG14. Final authority: Each owning hold/journal.
- Evidence: T06. Scope: Healthy metrics do not settle quarantine.

### CC33 — Budget deferral

**recovery · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

insufficient admission budget → no new dispatch → retain capture/due/checkpoint → later invocation reads owned work → resume computation under budget → finish only acknowledged prefix.

- Safeguard: SG01 SG25. Final authority: Capture and task receipts.
- Evidence: T05. Scope: Application budget is not platform quota.

### CC34 — Provider cooldown

**recovery · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

provider Retry-After → origin-specific maximum pause → persist selective cooldown → time eligibility rechecked → source reads resume → safe checkpoint/finish.

- Safeguard: SG25. Final authority: Provider-specific pause and deadline.
- Evidence: T05. Scope: No tenant-global admission guarantee.

### CC35 — Identity reconciliation index

**recovery · IMPLEMENTED** · Systems: eBay / Cloudflare / KeyCRM.

scheduled reconcile → source and exact CRM index reads → missing/existing classification → delegate to original mutation owner → independent journal/fence gates → verified result or review.

- Safeguard: SG03 SG14 SG26. Final authority: Exact source/CRM identity and mutation owner.
- Evidence: T01 T14. Scope: Reconcile is not an alternate unguarded writer.

### CC36 — Mixed-version recovery

**recovery · CANDIDATE** · Systems: eBay / Cloudflare / KeyCRM.

legacy record/typed state → identify actual producer/schema → compatibility reader retains uncertainty → guarded forward handling → exact readback → no bare-legacy rewind.

- Safeguard: SG14 SG16 SG28. Final authority: Producer-aware durable state contracts.
- Evidence: T14. Scope: Staged repair/full RC not a live replacement.

## Catalog / Yellow

### CC37 — Workbook publication

**normal · IMPLEMENTED + TESTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

XLSX/OOXML input → staging → validation/hash/SUCCESS → validated run outputs → atomic CURRENT_RUN pointer → local presentation checkpoint.

- Safeguard: SG20 SG21. Final authority: Local run/hash chain.
- Evidence: T08. Scope: Selected source only; installed client UNKNOWN.

### CC38 — Complete catalog snapshot

**normal · VERIFIED PRODUCTION** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

independent schedule → bounded KeyCRM offer pages → sanitize/sort/hash complete candidate → one cache publication → authenticated client wire verification → catalog observation.

- Safeguard: SG24 SG19. Final authority: Complete wire snapshot, not stock authority.
- Evidence: T12. Scope: Client installed identity remains UNKNOWN.

### CC39 — Catalog refresh page fails

**failure · IMPLEMENTED + TESTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

refresh starts → later page unavailable → incomplete candidate rejected → prior complete snapshot retained → next bounded refresh → client verifies complete version/hash.

- Safeguard: SG24. Final authority: Last complete published snapshot.
- Evidence: T12. Scope: No new live failure invocation asserted.

### CC40 — Yellow APPLY ACK lost

**failure · IMPLEMENTED + TESTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

verified proposal → persist exact command → remote authority may commit → ACK unavailable → pending remains unknown → receipt/version reconciliation or continued hold, never new blind APPLY.

- Safeguard: SG22 SG14. Final authority: Exact remote command proof.
- Evidence: T09 T10. Scope: Legacy KV lacks transactional command receipt; installed client UNKNOWN.

### CC41 — Positive APPLY, cache repair pending

**recovery · IMPLEMENTED + TESTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

positive settings version/hash ACK → separate cache-recovery receipt → local cache update fails/restart → receipt-first continuation → repair matching local cache → retire evidence without APPLY.

- Safeguard: SG22. Final authority: Positive remote receipt and local ownership.
- Evidence: T10. Scope: Selected local client code/test evidence.

### CC42 — Replenishment report chain

**normal · IMPLEMENTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

active min/target policy + actual warehouse quantities → attention decision → full report/outbox enqueue → independent delivery dedupe → provider ACK/finish → alert history.

- Safeguard: SG19 SG23. Final authority: Stock observation, policy and delivery receipts separately.
- Evidence: T11. Scope: Local full-attention correction is not deployed; human receipt unproven.

### CC43 — Pending product observation

**recovery · IMPLEMENTED + TESTED** · Systems: Yellow / Cloudflare / KeyCRM / Snapshot.

local proposal → newer unique catalog observation → compare original/current/desired lineage → reference confirmation → preserve settings-owned columns → local marker/report.

- Safeguard: SG19 SG20. Final authority: Product observation and separate settings ownership.
- Evidence: T08 T10 T12. Scope: No product CREATE implied; installed package UNKNOWN.

## Release / operations

### CC44 — Exact artifact scope

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

serving identity/resources → pinned exact inputs → scoped transform → reverse diff/source manifest → compatible artifact candidate → no deployment inferred from build.

- Safeguard: SG27. Final authority: Exact artifact/config provenance.
- Evidence: T13. Scope: Candidate still NO-GO without current protocol gates.

### CC45 — Checkpoint before STOP

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

reviewed scope → fresh encrypted checkpoint → independent verification/native continuity → recovery review → selective STOP readiness → separate finality gate.

- Safeguard: SG27 SG28. Final authority: Reviewed checkpoint plus independent finality.
- Evidence: T13. Scope: Native continuity is not catastrophic restore.

### CC46 — Stale writer after cutover

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

older participating writer → stale expected epoch → root admission rejects → no new guarded dispatch → current compatible epoch retained → existing unknowns still held.

- Safeguard: SG08 SG28. Final authority: Current server controller.
- Evidence: T13 T04. Scope: STOP does not cancel provider-preaccepted work.

### CC47 — Upload is not serving

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

exclusive upload intent → upload reply/version → exact resource/config proof → separate traffic activation → serving attestation → DRAINED/RUN and natural verification.

- Safeguard: SG28. Final authority: Actual version/resources/traffic receipts.
- Evidence: T13. Scope: Reference order, not a ready release command.

### CC48 — Unknown management mutation

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

upload/activation may commit → technical response lost → local exclusive intent retained → read version/deployment evidence → reconcile same operation → no blind repeated management POST.

- Safeguard: SG27 SG28. Final authority: Operation-specific journal and platform readback.
- Evidence: T13. Scope: No production operation performed for this portfolio task.

### CC49 — Preserve state on forward recovery

**release/operations · IMPLEMENTED** · Systems: Cloudflare / operator / build.

new typed state/fence exists → rollback candidate considered → compatibility gate → reject bare legacy/stale KV rewind → guarded forward recovery → retain unknown/terminal receipts.

- Safeguard: SG14 SG28. Final authority: Durable state reader compatibility.
- Evidence: T13 T14. Scope: Code rollback cannot undo stock effects.

### CC50 — Release remains blocked

**release/operations · CANDIDATE** · Systems: Cloudflare / operator / build.

local scoped tests pass → full aggregate EXIT1/compatibility or fresh-proof gaps → no release GO → minimal compatible recipe separately prepared → authentic protocol/publisher evidence still required → NO-GO retained.

- Safeguard: SG27 SG28. Final authority: Release acceptance evidence, not local test color.
- Evidence: T13. Scope: Full RC and later minimal patch have distinct remaining blockers.
