"""Authored source accounting. Release mode fails closed below the size floor."""

import argparse
import io
import json
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
SOURCE_EXTENSIONS = {".py", ".ts", ".tsx", ".css", ".sql"}
LOCKS = {"package-lock.json", "uv.lock", "poetry.lock"}


def python_loc(source: str) -> int:
    covered: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type in {
            tokenize.COMMENT,
            tokenize.ENCODING,
            tokenize.NL,
            tokenize.NEWLINE,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.ENDMARKER,
        }:
            continue
        # Exclude all standalone string statements, including module/class/function docstrings.
        if token.type == tokenize.STRING:
            continue
        covered.update(range(token.start[0], token.end[0] + 1))
    return len(covered)


def classify(relative: Path) -> str:
    if relative.parts[0] == "tests":
        return "tests"
    if relative.parts[0] == "backend":
        return "backend"
    if relative.parts[0] == "frontend":
        return "frontend"
    return "sql_tooling"


def collect() -> dict[str, object]:
    entries: list[dict[str, object]] = []
    totals: dict[str, int] = dict.fromkeys(["backend", "frontend", "tests", "sql_tooling"], 0)
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        reason = None
        if path.name in LOCKS:
            reason = "dependency lock"
        elif path.suffix not in SOURCE_EXTENSIONS:
            reason = "documentation/configuration/artifact, not authored source"
        if reason:
            entries.append({"file": relative.as_posix(), "excluded_reason": reason})
            continue
        source = path.read_text(encoding="utf-8")
        if "GENERATED FILE" in source[:200]:
            entries.append({"file": relative.as_posix(), "excluded_reason": "generated source"})
            continue
        count = (
            python_loc(source)
            if path.suffix == ".py"
            else sum(
                bool(line.strip()) and not line.lstrip().startswith(("//", "/*", "*", "--"))
                for line in source.splitlines()
            )
        )
        category = classify(relative)
        totals[category] += count
        entries.append({"file": relative.as_posix(), "category": category, "loc": count})
    total = sum(totals.values())
    return {
        "categories": totals,
        "total_authored_code_loc": total,
        "files": entries,
        "minimum": 5000,
        "size_gate": total >= 5000,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", action="store_true")
    args = parser.parse_args()
    result = collect()
    target = ROOT / "docs" / "LOC_MANIFEST.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "files"}))
    return 1 if args.release and not result["size_gate"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
