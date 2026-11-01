# Architecture views

Generated from the implemented boundaries and the actual Task transition map using
`python tools/build_architecture.py`. `--check` compares all DOT and SVG bytes.

- [A1 — topology](diagrams/A1.svg): Compose HTTP provider and native reference port.
- [A2 — lifecycle](diagrams/A2.svg): every Task state and permitted transition.
- [A3 — ambiguous mutation](diagrams/A3.svg): independent commit and lost response.
- [A4 — ownership](diagrams/A4.svg): leases, tokens and stale-owner rejection.
- [A5 — recovery](diagrams/A5.svg): SELECT capability and identity-bound proof.
- [A6 — tenancy](diagrams/A6.svg): scoped API, repository and relational constraints.
- [A7 — provenance](diagrams/A7.svg): sources, retrieval, output spans and evaluations.
- [A8 — cancellation](diagrams/A8.svg): preserve unknown intents until reconciliation.

The editable DOT files and generator reference concrete implementation modules.
These are laboratory architecture views, not production deployment evidence.
