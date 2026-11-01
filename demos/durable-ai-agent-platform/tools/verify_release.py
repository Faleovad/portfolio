"""Source-bound phase receipts; canonical verification is written only on finalization."""

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from metrics import ROOT, collect, python_loc
from source_manifest import manifest, source_files

PYTHON = sys.executable
NPM = "npm.cmd" if os.name == "nt" else "npm"
PHASES = {
    "static": [
        ([PYTHON, "-m", "ruff", "check", "backend", "tests", "tools"], "."),
        ([PYTHON, "-m", "ruff", "format", "--check", "backend", "tests", "tools"], "."),
        ([PYTHON, "-m", "mypy", "backend"], "."),
        ([PYTHON, "-m", "pip", "wheel", "--no-deps", ".", "--wheel-dir", "build/wheels"], "."),
        ([NPM, "run", "lint"], "frontend"),
        ([NPM, "run", "build"], "frontend"),
        ([PYTHON, "tools/build_architecture.py", "--check"], "."),
    ],
    "python": [([PYTHON, "-m", "pytest", "-q", "--junitxml=docs/application-tests.xml"], ".")],
    "scenarios": [([PYTHON, "-m", "platform_core.scenarios", "run-all"], ".")],
    "browser": [([NPM, "test"], "frontend")],
    "compose": [
        (["docker", "compose", "up", "--build", "-d"], "."),
        ([PYTHON, "tools/verify_compose.py"], "."),
    ],
    "compose_restart": [([PYTHON, "tools/verify_compose_restart.py"], ".")],
    "compose_browser": [([NPM, "test"], "frontend")],
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def pattern_scan() -> list[str]:
    pattern = re.compile(
        r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|gh[pousr]_[A-Za-z0-9]{25,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)"
    )
    return [row["path"] for row in source_files() if pattern.search(row["content"])]


def broken_links() -> list[str]:
    broken = []
    for row in source_files():
        if not row["path"].endswith(".md"):
            continue
        # The original prompt is an input specification, not authored navigation.
        if row["path"].endswith("ORIGINAL_REQUIREMENTS.md"):
            continue
        for link in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", row["content"]):
            if "://" in link or link.startswith(("#", "mailto:")):
                continue
            target = link.split("#")[0]
            if target and not (ROOT.parents[1] / row["path"]).parent.joinpath(target).exists():
                broken.append(row["path"] + ": " + link)
    return broken


def snapshot() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "backend"))
    from platform_core.api import create_app
    from platform_core.evidence import runtime_fingerprint
    from platform_core.faults import FaultEngine
    from platform_core.scenario_catalog import CATALOG
    from platform_core.state import (
        INTENT_EDGES,
        RECOVERY_EDGES,
        STEP_EDGES,
        TASK_EDGES,
        IntentState,
        RecoveryState,
        StepState,
        TaskState,
    )
    from requirement_audit import build

    identity = manifest()
    digest = identity["source_sha256"]
    phases = {}
    for phase in PHASES:
        receipt = read_json(ROOT / "docs/check-results" / (phase + ".json"))
        phases[phase] = (
            receipt["status"]
            if receipt and receipt["source_sha256"] == digest
            else "NOT_RUN_CURRENT_SOURCE"
        )
    ci = read_json(ROOT / "docs/CI_RUN.json")
    phases["ci"] = (
        "PASS"
        if ci
        and ci.get("source_sha256") == digest
        and ci.get("conclusion") == "success"
        and ci.get("source_tree_parity") is True
        and ci.get("run_id")
        and ci.get("private_commit_sha")
        else "NOT_ATTESTED"
    )
    functions = {
        p.name: sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
            for node in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
        )
        for p in sorted((ROOT / "tests").glob("test_*.py"))
    }
    xml = (
        ET.parse(ROOT / "docs/application-tests.xml")
        if (ROOT / "docs/application-tests.xml").exists()
        else None
    )
    cases = list(xml.iter("testcase")) if xml else []
    passed_tests = {
        row.attrib["name"].split("[")[0]
        for row in cases
        if not any(row.find(kind) is not None for kind in ["failure", "error", "skipped"])
    }
    integration_files = {
        p.stem
        for p in (ROOT / "tests").glob("test_*.py")
        if "pytest.mark.integration" in p.read_text(encoding="utf-8")
    }
    scenarios = [read_json(p) for p in sorted((ROOT / "docs/scenario-results").glob("S*.json"))]
    current = [
        row
        for row in scenarios
        if row.get("runtime_source_sha256") == runtime_fingerprint() and row["status"] == "PASS"
    ]
    passed_scenarios = {row.get("scenario") for row in current}
    browser = read_json(ROOT / "frontend/test-results/browser.json") or {}
    accounting = collect()
    dataset = read_json(ROOT / "tests/data/evaluation_tasks.json")
    if isinstance(dataset, dict):
        dataset = dataset.get("tasks", dataset.get("cases", []))
    backend = list((ROOT / "backend/platform_core").glob("*.py"))
    scan = pattern_scan()
    result = {
        "status": "INCOMPLETE_UNPUBLISHED",
        "scope": "Original Stage 1 synthetic engineering lab only",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        **identity,
        "api_operations": sum(
            len(methods)
            for methods in create_app("postgresql://unused", "postgresql://unused")
            .openapi()["paths"]
            .values()
        ),
        "domain_tables": len(
            re.findall(r"CREATE TABLE \w+", (ROOT / "sql/001_orchestrator.sql").read_text())
        ),
        "provider_tables": sum(
            len(re.findall(r"CREATE TABLE (?:IF NOT EXISTS )?\w+", p.read_text()))
            for p in [ROOT / "sql/001_provider.sql", ROOT / "sql/002_provider_tools.sql"]
        ),
        "backend_modules": {
            "total_including_package_init": len(backend),
            "code_bearing": sum(python_loc(p.read_text(encoding="utf-8")) > 0 for p in backend),
        },
        "state_machines": {
            name: {"states": len(states), "edges": sum(len(x) for x in edges.values())}
            for name, states, edges in [
                ("task", TaskState, TASK_EDGES),
                ("step", StepState, STEP_EDGES),
                ("intent", IntentState, INTENT_EDGES),
                ("recovery", RecoveryState, RECOVERY_EDGES),
            ]
        },
        "fault_modes": list(FaultEngine.MODES),
        "fault_mode_count": len(FaultEngine.MODES),
        "executable_scenario_catalog": len(CATALOG),
        "scenario_results_current_runtime": len(current),
        "loc": {k: v for k, v in accounting.items() if k != "files"},
        "tests": {
            "functions_total": sum(functions.values()),
            "functions_by_file": functions,
            "collected_cases": len(cases),
            "parameterized_cases": sum("[" in row.attrib["name"] for row in cases),
            "integration_functions": sum(
                count for name, count in functions.items() if Path(name).stem in integration_files
            ),
            "integration_cases": sum(
                row.attrib["classname"].split(".")[-1] in integration_files for row in cases
            ),
            "failures": len(list(xml.iter("failure"))) if xml else None,
            "errors": len(list(xml.iter("error"))) if xml else None,
            "skipped": len(list(xml.iter("skipped"))) if xml else None,
            "scenario_pass": len(current),
            "browser": browser.get("stats", {}),
        },
        "evaluation_dataset": {
            "samples": len(dataset),
            "executable_tasks": sum(row.get("kind") != "reject_document" for row in dataset),
        },
        "evaluators": sum(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "EvaluationResult"
            for node in ast.walk(
                ast.parse(
                    (ROOT / "backend/platform_core/evaluators.py").read_text(encoding="utf-8")
                )
            )
        ),
        "invariants": len(read_json(ROOT / "docs/INVARIANTS.json")),
        "diagrams": len(list((ROOT / "docs/diagrams").glob("A*.svg"))),
        "screenshots": len(list((ROOT / "docs/screenshots").glob("*.png"))),
        "executed_phases": phases,
        "credential_PII_pattern_scan": "PASS" if not scan else "FAIL",
        "pattern_scan_files": scan,
        "broken_documentation_links": broken_links(),
        "restart_baseline": read_json(ROOT / "docs/BACKBONE_RESTART.json"),
        "compose_result": read_json(ROOT / "docs/COMPOSE_SMOKE.json"),
        "compose_restart": read_json(ROOT / "docs/COMPOSE_RESTART.json"),
        "ci": ci,
    }
    audit = build(result, phases, passed_tests, passed_scenarios)
    result["requirement_audit"] = {
        k: audit[k]
        for k in ["status", "sections_covered", "checklist_items_covered", "mandatory_open"]
    }
    result["red_gates"] = [name for name, status in phases.items() if status != "PASS"]
    if not accounting["size_gate"]:
        result["red_gates"].append("size_below_5000")
    if scan:
        result["red_gates"].append("credential_PII_pattern_scan")
    if result["broken_documentation_links"]:
        result["red_gates"].append("documentation_links")
    if audit["status"] != "PASS":
        result["red_gates"].append("original_requirement_audit")
    result["release"] = "PASS" if not result["red_gates"] else "FAIL"
    if result["release"] == "PASS":
        result["status"] = "STAGE1_READY_UNPUBLISHED"
    return result


def run_phase(phase: str) -> int:
    before = manifest()["source_sha256"]
    commands = []
    status = "PASS"
    env = {**os.environ, "PYTHONPATH": str(ROOT / "backend")}
    if phase == "compose_browser":
        env["BROWSER_EXTERNAL_SERVERS"] = "1"
    for command, directory in PHASES[phase]:
        completed = subprocess.run(
            command,
            cwd=ROOT / directory,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        commands.append(
            {
                "command": command[1:] if command[0] == PYTHON else command,
                "exit_code": completed.returncode,
            }
        )
        print(json.dumps(commands[-1]), flush=True)
        logs = ROOT / "docs/check-results" / (phase + ".log")
        logs.parent.mkdir(parents=True, exist_ok=True)
        with logs.open("a", encoding="utf-8") as stream:
            stream.write(completed.stdout + completed.stderr)
        if completed.returncode:
            print((completed.stdout + completed.stderr)[-9000:])
            status = "FAIL"
            break
    if (
        phase == "python"
        and status == "PASS"
        and list(ET.parse(ROOT / "docs/application-tests.xml").iter("skipped"))
    ):
        status = "FAIL_SKIPPED_TESTS"
    if before != manifest()["source_sha256"]:
        status = "FAIL_SOURCE_CHANGED_DURING_PHASE"
    write_json(
        ROOT / "docs/check-results" / (phase + ".json"),
        {"status": status, "source_sha256": before, "commands": commands},
    )
    return int(status != "PASS")


def main() -> int:
    sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--finalize", action="store_true")
    parser.add_argument("--release", action="store_true")
    parser.add_argument(
        "--payload-gate",
        action="store_true",
        help="CI payload checks excluding external run conclusion",
    )
    args = parser.parse_args()
    if args.phase:
        return run_phase(args.phase)
    result = snapshot()
    if args.finalize:
        from requirement_audit import build, write

        xml = ET.parse(ROOT / "docs/application-tests.xml")
        tests = {row.attrib["name"].split("[")[0] for row in xml.iter("testcase") if len(row) == 0}
        scenario_ids = {
            p.stem
            for p in (ROOT / "docs/scenario-results").glob("S*.json")
            if read_json(p).get("status") == "PASS"
        }
        write(build(result, result["executed_phases"], tests, scenario_ids))
        write_json(ROOT / "docs/LOC_MANIFEST.json", collect())
        write_json(ROOT / "docs/VERIFICATION.json", result)
    else:
        write_json(ROOT / "build/VERIFICATION_PREVIEW.json", result)
    print(
        json.dumps(
            {
                "source_sha256": result["source_sha256"],
                "phases": result["executed_phases"],
                "red_gates": result["red_gates"],
                "audit": result["requirement_audit"],
            }
        )
    )
    if args.payload_gate:
        return int(
            any(
                status != "PASS"
                for phase, status in result["executed_phases"].items()
                if phase != "ci"
            )
            or result["credential_PII_pattern_scan"] != "PASS"
            or bool(result["broken_documentation_links"])
            or any(
                x != "R39"
                and not x.startswith("R39.")
                and x != "R50"
                and not x.startswith("R50.")
                and x != "R54"
                and not x.startswith("R54.")
                for x in result["requirement_audit"]["mandatory_open"]
            )
        )
    return int(args.release and bool(result["red_gates"]))


if __name__ == "__main__":
    raise SystemExit(main())
