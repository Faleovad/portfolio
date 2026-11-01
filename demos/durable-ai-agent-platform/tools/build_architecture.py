"""Render the eight Stage 1 architecture views; lifecycle edges come from actual code."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from platform_core.state import TASK_EDGES, TaskState

STYLE = """graph [bgcolor="#0b1120",pad="0.45",nodesep="0.55",ranksep="0.9",fontname="Arial",fontsize=22,fontcolor="#e3ecf7",labelloc=t];
node [shape=box,style="rounded,filled",fillcolor="#15253b",color="#4d6786",fontname="Arial",fontcolor="#dce7f5",fontsize=15,margin="0.20,0.14"];
edge [color="#8ba4be",fontname="Arial",fontcolor="#a4b9cf",fontsize=12,arrowsize=0.75];"""

SPECS = {
    "A1": (
        "System topology",
        """rankdir=LR;
ui[label="React operational console\\nKnowledge / Reality / Proof"];
api[label="Tenant API\\nread-only provider inspection"];
ctl[label="Opt-in synthetic controller\\nscoped process controls"];
db[label="Orchestrator PostgreSQL\\n17 normalized domain tables",shape=cylinder];
exe[label="Executor\\nretrieve / model / search / evaluate"];
worker[label="Dispatcher\\nPREPARED → SENT"];
model[label="Deterministic ModelProvider\\nno API key"];
rag[label="Tenant RAG\\ndocuments / chunks / hits"];
provider[label="Independent provider service\\nCRM / quota / Email / HTTP"];
pdb[label="Provider PostgreSQL\\neffects + domain state",shape=cylinder];
reader[label="Read-only recovery process\\nSELECT capability only",color="#8ebfa4"];
ui->api[label="authenticated snapshots"];ui->ctl[label="laboratory actions"];
api->db;api->pdb[label="SELECT inspection"];ctl->exe;ctl->worker;ctl->reader;
exe->db;exe->model;exe->rag;exe->pdb[label="Search: SELECT only"];
rag->db;worker->db;worker->provider[label="Compose HTTP dispatch"];
worker->pdb[label="native / scenario reference port",style=dashed];
provider->pdb[label="independent commit"];reader->pdb[label="observe, never mutate",color="#8ebfa4"];reader->db[label="receipt / recovery metadata"];
""",
        [
            "api.py",
            "control_api.py",
            "executor.py",
            "worker.py",
            "recovery_worker.py",
            "provider_api.py",
        ],
    ),
    "A3": (
        "Ambiguous tool mutation",
        """rankdir=LR;
prepared[label="PREPARED\\nidentity + payload fingerprint"];
sent[label="SENT\\ndurable dispatch fence"];
commit[label="External COMMITTED\\nindependent provider transaction",color="#91c6a3"];
lost[label="Response lost",color="#e0b06b"];
unknown[label="UNKNOWN\\nno permission to replay",color="#e0b06b"];
observe[label="Read-only reconciliation\\nmatch tenant / tool / intent / payload"];
receipt[label="Immutable receipt\\nCONFIRMED",color="#91c6a3"];
prepared->sent[label="persist before request"];sent->commit[label="non-atomic boundary"];
commit->lost;lost->unknown;unknown->observe[label="fresh observation"];
observe->receipt[label="exact committed proof"];
review[label="MANUAL_REVIEW\\nfence retained",color="#e0b06b"];
observe->review[label="stale / missing / unavailable beyond bounds"];
""",
        ["repository.py", "provider.py", "recovery.py", "proof.py"],
    ),
    "A4": (
        "Worker ownership",
        """rankdir=LR;
pending[label="Eligible persisted Step"];
claim[label="Claim transaction\\nFOR UPDATE SKIP LOCKED"];
owner[label="Owner A\\ntoken A / revision r / lease"];
renew[label="Heartbeat\\ncheck token + revision + live lease"];
expire[label="Lease expires"];
new[label="Owner B\\nnew token / revision r+1"];
reject[label="Owner A persistence rejected\\nOwnershipLost",color="#e0b06b"];
fence[label="SENT / UNKNOWN intent\\nnever eligible for redispatch",color="#e0b06b"];
pending->claim;claim->owner;owner->renew;renew->owner[label="extend lease"];
owner->expire;expire->new[label="safe unmutated step reclaim"];
new->reject[label="old token / revision invalid"];
expire->fence[label="ambiguous mutation → recovery only"];
""",
        ["repository.py", "ownership.py", "state.py"],
    ),
    "A5": (
        "Read-only recovery architecture",
        """rankdir=LR;
queue[label="Persisted recovery queue\\npending / waiting / claimed"];
claim[label="Recovery ownership\\nlease + token + revision"];
budget[label="Durable attempt / deadline admission"];
read[label="ReadOnlyToolPort\\nobserve(identity)",color="#91c6a3"];
external[label="Provider DB\\nSELECT-only role",shape=cylinder,color="#91c6a3"];
proof[label="Identity-matched committed observation"];
receipt[label="Atomic local confirmation\\nreceipt + intent + step + task"];
manual[label="Manual review / budget terminal\\nunresolved fence retained",color="#e0b06b"];
queue->claim;claim->budget;budget->read;read->external[label="SELECT"];
external->proof;proof->receipt;read->manual[label="unprovable beyond policy"];
budget->manual[label="exhausted; no extra observation"];
none[label="No writer DSN\\nNo dispatch method\\nNo mutating provider port",shape=note,color="#e0b06b"];
none->read[style=dashed,arrowhead=none];
""",
        ["ports.py", "recovery.py", "recovery_worker.py", "provider_reader.py"],
    ),
    "A6": (
        "Tenant isolation",
        """rankdir=LR;
tokenA[label="Tenant A bearer"];
auth[label="API authentication\\nSHA256 lookup → tenant scope"];
service[label="Tenant-scoped service"];
repo[label="Repository predicates / joins\\ntenant_id + resource ID"];
tenantA[label="A: tasks / versions / documents\\nartifacts / events / recovery",color="#91c6a3"];
tenantB[label="B: private resources",color="#e0b06b"];
deny[label="Foreign UUID → 404\\nforeign lists remain empty",color="#e0b06b"];
tokenA->auth;auth->service;service->repo;repo->tenantA[label="authorized"];
repo->deny[label="scope mismatch"];deny->tenantB[arrowhead=tee,style=dashed];
fk[label="Composite tenant foreign keys\\nprevent cross-tenant references",shape=note];fk->repo[arrowhead=none,style=dashed];
catalog[label="Public synthetic Search catalog\\nfixed shared reference facts\\nnot tenant-private RAG documents",shape=note];
service->catalog[label="explicit read-only external tool"];
""",
        ["api.py", "application_repository.py", "rag.py", "inspection.py"],
    ),
    "A7": (
        "RAG provenance",
        """rankdir=LR;
artifact[label="Final Artifact\\nanswer + pinned version"];
model[label="Validated ModelCall\\nmodel step ID / citations"];
hit[label="RetrievalHit\\nquery hash / score / supports"];
retrieve[label="Retrieval Step\\ntenant / task identity"];
chunk[label="Chunk\\ncontent / embedding / ordinal"];
doc[label="Document\\nname / content hash / tenant"];
span[label="Exact answer span when present\\notherwise explicitly null",shape=note];
artifact->model[label="model_step_id"];artifact->hit[label="provenance / citation ID"];
artifact->span[style=dashed,arrowhead=none];hit->retrieve[label="step_id"];
hit->chunk[label="chunk_id"];chunk->doc[label="document_id"];
""",
        ["executor.py", "rag.py", "evaluators.py"],
    ),
    "A8": (
        "Cancellation during UNKNOWN",
        """rankdir=LR;
request[label="Cancel requested"];
safe[label="No dispatched intent"];
unresolved[label="SENT / UNKNOWN intent",color="#e0b06b"];
pending[label="CANCEL_REQUESTED\\nretain payload / identity / fence",color="#e0b06b"];
read[label="Budgeted read-only reconciliation"];
receipt[label="Committed effect confirmed\\nimmutable receipt",color="#91c6a3"];
cancel[label="CANCELLED\\nremaining plan steps cancelled",color="#91c6a3"];
review[label="MANUAL_REVIEW\\nunprovable after bounds",color="#e0b06b"];
request->safe;safe->cancel;request->unresolved;unresolved->pending;pending->read;
read->receipt[label="fresh exact proof"];receipt->cancel;
read->review[label="missing / stale / outage / exhausted budget"];
note[label="NOT_FOUND is not authoritative absence\\nCancellation never authorizes redispatch",shape=note];note->read[style=dashed,arrowhead=none];
""",
        ["application_repository.py", "repository.py", "recovery.py", "policy.py"],
    ),
}


def lifecycle() -> str:
    rows = ["rankdir=LR;"]
    for state in TaskState:
        color = (
            "#e0b06b"
            if state.value in {"UNKNOWN", "MANUAL_REVIEW", "CANCEL_REQUESTED", "BUDGET_EXHAUSTED"}
            else "#91c6a3"
            if state.value in {"COMPLETED", "CANCELLED"}
            else "#4d6786"
        )
        rows.append(f'{state.value}[label="{state.value}",color="{color}"];')
    for source, targets in TASK_EDGES.items():
        rows.extend(
            f"{source.value}->{target.value};" for target in sorted(targets, key=lambda x: x.value)
        )
    rows.append(
        'note[label="All actual TaskState edges from state.py\\nCREATED → QUEUED publishes the persisted plan atomically\\nTerminal budget/receipt states do not reopen execution",shape=note];'
    )
    return "\n".join(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    specs = {
        **SPECS,
        "A2": (
            "Task lifecycle — complete durable state machine",
            lifecycle(),
            ["state.py", "repository.py", "application_repository.py"],
        ),
    }
    target = ROOT / "docs/diagrams"
    target.mkdir(parents=True, exist_ok=True)
    renderer = """import {instance} from '@viz-js/viz'; const viz=await instance(); let input=''; for await (const chunk of process.stdin) input+=chunk; const rows=JSON.parse(input); const out=rows.map(r=>({...r,svg:viz.renderString(r.dot,{format:'svg',engine:'dot'})})); process.stdout.write(JSON.stringify(out));"""
    inputs = [
        {
            "id": key,
            "dot": "digraph "
            + key
            + " {\n"
            + STYLE
            + '\nlabel="'
            + key
            + " · "
            + title
            + '";\n'
            + body
            + "\n}",
        }
        for key, (title, body, _) in sorted(specs.items())
    ]
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", renderer],
        cwd=ROOT / "frontend",
        input=json.dumps(inputs),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    manifest = []
    for item in json.loads(completed.stdout):
        key = item["id"]
        for suffix, content in [("dot", item["dot"]), ("svg", item["svg"])]:
            path = target / (key + "." + suffix)
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    raise SystemExit("Architecture artifact differs: " + path.name)
            else:
                path.write_text(content, encoding="utf-8")
        manifest.append(
            {
                "id": key,
                "title": specs[key][0],
                "sources": specs[key][2],
                "svg_sha256": hashlib.sha256(item["svg"].encode()).hexdigest(),
            }
        )
    if not args.check:
        (target / "MANIFEST.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "architecture_views": len(manifest),
                "complete_task_states": len(TaskState),
                "task_edges": sum(len(x) for x in TASK_EDGES.values()),
                "status": "PASS",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
