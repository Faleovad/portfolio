# Stage 1 verified handoff

Stage 1 READY / RELEASE PASS; unpublished. Stage 2 has not started.

The authoritative source candidate is local bec110ab875d39ff3cb5c3f1975b02e5cb5ec12e,
private 73717f1abb7046a1be9f496244bb29e2004ae6e9, Actions run 41341505800.
Canonical source fingerprint (119 UTF-8/LF Git blobs, project + workflow):
64b76eb3a327b592a653f7f97fa35d2844cb92f5d95a10098ccf2f75410f38cf.
Downloaded artifact integrity and every source-manifest entry were compared.

All seven runtime/static phases plus external CI attestation PASS. 519 Python cases,
53 CLI scenarios, 13 native browser and 13 Compose browser cases pass. Container
restart evidence is an actual dispatcher OS-process kill inside the control container,
replacement dispatcher and new SELECT-only recovery process; effect/dispatch/receipt=1.
This does not claim a database-container restart or catastrophe restore.

The private immutable source snapshot carries historical generated checkpoint files
only to preserve documentation links. Current verification is the successful run's
artifact plus the finalized local docs/VERIFICATION.json, CI_RUN.json and audit outputs.
Generated outputs are excluded from authored-source identity and LOC.

No public repository push, main merge, public navigation or Stage 2 work was performed.
Before any eventual public publication, compare the exact committed authored Git blobs
with this manifest (python tools/source_manifest.py --compare docs/CI_RUN.json for the
working tree). Changed authored source/config/docs/workflow/SVG invalidates verification
and requires the corresponding runtime gates again. Public publication remains deferred.
