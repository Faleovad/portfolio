"""Portable candidate identity and lossless private-CI transfer. No credentials are exported."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
PREFIX = ROOT.relative_to(REPO).as_posix()
WORKFLOW = ".github/workflows/durable-agent-platform.yml"
GENERATED_FOLDERS = (
    "docs/check-results/",
    "docs/scenario-results/",
    "docs/screenshots/",
    "docs/ci-evidence/",
    "frontend/test-results/",
    "build/",
)
GENERATED_FILES = {
    "docs/VERIFICATION.json",
    "docs/LOC_MANIFEST.json",
    "docs/METRICS.json",
    "docs/BACKBONE_RESTART.json",
    "docs/APPLICATION_SMOKE.json",
    "docs/SCREENSHOTS.json",
    "docs/RELEASE_GATE.json",
    "docs/REQUIREMENT_AUDIT.json",
    "docs/REQUIREMENT_AUDIT.md",
    "docs/TOOL_REQUIREMENT_AUDIT.json",
    "docs/INVARIANT_AUDIT.json",
    "docs/COMPOSE_SMOKE.json",
    "docs/COMPOSE_RESTART.json",
    "docs/CI_RUN.json",
    "docs/diagrams/MANIFEST.json",
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
    ).hexdigest()


def source_files() -> list[dict[str, str]]:
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "--", PREFIX, WORKFLOW],
        cwd=REPO,
        text=True,
        encoding="utf-8",
    ).splitlines()
    records = []
    for name in sorted(set(names)):
        path = REPO / name
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT).as_posix() if name.startswith(PREFIX + "/") else None
        if relative and (
            relative in GENERATED_FILES
            or relative.startswith(GENERATED_FOLDERS)
            or relative.endswith(".xml")
        ):
            continue
        content = path.read_text(encoding="utf-8")
        data = content.encode("utf-8")
        records.append(
            {
                "path": name,
                "mode": "100644",
                "content": content,
                "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob_sha": git_blob(data),
            }
        )
    return records


def manifest() -> dict[str, Any]:
    entries = [{k: v for k, v in row.items() if k != "content"} for row in source_files()]
    digest = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "source_sha256": digest,
        "scope": "Exact project source/config/docs/SVG + its workflow; generated verification/run outputs are excluded",
        "encoding": "UTF-8/LF canonical Git blob bytes",
        "files": entries,
    }


def tree_sha(records: list[dict[str, str]]) -> str:
    tree: dict[str, Any] = {}
    for row in records:
        current = tree
        parts = row["path"].split("/")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = row["git_blob_sha"]

    def encode(node: dict[str, Any]) -> str:
        data = b""
        for name, value in sorted(
            node.items(),
            key=lambda item: (item[0] + ("/" if isinstance(item[1], dict) else "")).encode(),
        ):
            mode = "40000" if isinstance(value, dict) else "100644"
            sha = encode(value) if isinstance(value, dict) else value
            data += mode.encode() + b" " + name.encode() + b"\0" + bytes.fromhex(sha)
        return hashlib.sha1(
            b"tree " + str(len(data)).encode() + b"\0" + data, usedforsecurity=False
        ).hexdigest()

    return encode(tree)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="strict")
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int)
    parser.add_argument("--compare", type=Path)
    args = parser.parse_args()
    result = manifest()
    if args.compare:
        expected = json.loads(args.compare.read_text(encoding="utf-8"))
        if expected["source_sha256"] != result["source_sha256"]:
            print(
                json.dumps(
                    {
                        "status": "FAIL",
                        "expected": expected["source_sha256"],
                        "actual": result["source_sha256"],
                    }
                )
            )
            return 1
    if args.batch is not None:
        parts = []
        for record in source_files():
            count = max(1, (len(record["content"]) + 5999) // 6000)
            for i in range(count):
                parts.append(
                    {
                        "path": record["path"],
                        "part": i,
                        "parts": count,
                        "content": record["content"][i * 6000 : (i + 1) * 6000],
                    }
                )
        print(
            json.dumps(
                {
                    "source_sha256": result["source_sha256"],
                    "batches": (len(parts) + 1) // 2,
                    "fragments": parts[args.batch * 2 : (args.batch + 1) * 2],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
