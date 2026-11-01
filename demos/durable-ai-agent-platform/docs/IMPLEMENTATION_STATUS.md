# Stage 1 implementation status

This is an unpublished synthetic engineering lab. Canonical, source-bound results are
in VERIFICATION.json after finalization. Intermediate phase receipts are stored under
check-results; changing authored source/configuration/docs invalidates them.

All five tools have distinct implemented semantics: read-only Search observations,
versioned CRM entities, atomic integer quota adjustments, synthetic inbox delivery and
constrained HTTP resource operations. Mutating tools share immutable intent, dispatch
fence, readback and receipt protocols. They do not perform real payments, SMTP or
arbitrary network requests. TOOL_REQUIREMENTS.json identifies the actual per-tool
checks; shared protocol tests are not represented as an exhaustive Cartesian matrix.

Task creation publishes CREATED → QUEUED and the plan atomically. Execution persists
retrieval, model calls, tool observations and evaluations. Events produce identifier-only
structured logs after transaction commit. The evaluation dataset distinguishes executed
tasks from a rejected ingestion example. Metrics report measured counts, including
code-bearing modules separately from package files; no files are added to pad counts.

Native, container, browser and remote CI outcomes are separate gates. A running GitHub
job cannot attest to its own eventual successful conclusion. CI_RUN.json must record
the observed run, private commit and exact source parity before release can pass.
The temporary private CI repository is Faleovad/portfolio-verification. Public portfolio
integration is deferred by owner instruction until all Stage 1 release gates pass.
Stage 2 is outside scope.
