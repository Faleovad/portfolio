[← Case study](../README.md) · [Architecture index](full-system-map.md) · [Evidence labels](evidence.md)

# Full forensic relationship census — safe public projection

**805 nodes / 1,208 normalized relationships**, reconstructed from a selected 31 October 2026 source/state snapshot. This is an architectural census, not runtime calls, request telemetry, throughput, services, production executions, or evidence that every relationship is simultaneously active in production.

## Explore without a hairball

- [Download the offline HTML explorer](graph-explorer.html) (GitHub shows source; save/open locally). It embeds the sanitized graph and works without a server or network. Search and select one node, filter subsystem/path class, inspect a bounded directional neighborhood, zoom and pan.
- [Full sanitized JSON](data/relationships.json) — all 805 opaque nodes and 1,208 relationships.
- [Normalized CSV](data/relationships.csv) — the same relationship rows and source-record references.
- [Measured census / chain counts](data/visual-summary.json).
- [System topology](full-system-map.md), [failure/recovery view](failure-recovery-map.md), and [state authority view](state-authority-map.md) provide readable derived views.

## Exact denominators

| Metric | Count | Meaning |
| --- | --- | --- |
| Components | 54 | Logical catalog areas including support/history/unknown; not services |
| Modeled state entities | 40 | 30 state families + 10 actor identity families; not stored row count |
| Authority relationships | 24 | Designated authority per fact |
| Safeguards | 28 | Evidence-indexed implemented boundaries, deployment scope varies |
| Failure descriptors | 157 | Modeled failure continuations, not observed incidents |
| Recovery edges | 65 | Source/reference continuations, not recovery executions |
| Normal edges | 981 | Includes declarations/reference paths |
| Release/operations path-class edges | 5 | Additional disjoint path class; 981 + 157 + 65 + 5 = 1,208 |
| Release/operations semantic subset | 134 | Overlapping node-family filter, not another additive path class |
| Dangling edges | 0 | Referential closure only, not correctness or release acceptance |

The normalized private key used source, target, relationship type, operation, involved state and path class. The public projection has stable opaque IDs and retains one row per source relationship. It deliberately withholds route paths (264 declaration nodes), source/code locations, resource and actor identifiers, security predicates and operational payloads. Collapsing labels does not merge identities. Thus the complete topology census is available, but this is **not the raw private forensic graph** or an access map.

All source relationship rows carry IMPLEMENTED, a structural existence label. It must not be read as VERIFIED PRODUCTION. Source scopes include retained bridge, current RC, baseline, demo, selected client, support/history and staged code. Local evidence pointers are represented by semantic record IDs, not broken private filesystem links.
