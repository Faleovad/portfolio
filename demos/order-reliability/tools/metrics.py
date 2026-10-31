"""Measure the final lab, collecting tests rather than guessing test counts."""

import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.container import Lab  # noqa: E402
from app.domain.models import FaultMode  # noqa: E402
from app.main import create_app  # noqa: E402
from app.scenarios.catalog import SCENARIOS  # noqa: E402


def measure(paths: list[Path]) -> dict:
    return {
        "files": len(paths),
        "physical_loc": sum(len(p.read_text(encoding="utf-8").splitlines()) for p in paths),
    }


def main() -> None:
    backend = sorted((ROOT / "backend/app").rglob("*.py")) + sorted(
        (ROOT / "backend/app").rglob("*.sql")
    )
    frontend = [
        p for p in sorted((ROOT / "frontend/src").rglob("*")) if p.suffix in {".tsx", ".ts", ".css"}
    ]
    frontend.append(ROOT / "frontend/index.html")
    tests = sorted((ROOT / "backend/tests").glob("*.py")) + sorted(
        (ROOT / "frontend/tests").glob("*.ts")
    )
    collection = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT / "backend",
        text=True,
        capture_output=True,
        check=True,
    )
    nodes = [
        line
        for line in collection.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    with tempfile.TemporaryDirectory() as temporary:
        app = create_app(Path(temporary))
        lab: Lab = app.state.lab
        endpoints = sum(
            method in {"get", "post"} for item in app.openapi()["paths"].values() for method in item
        )
        tables = {}
        for owner, db in (("erp", lab.db), ("provider", lab.provider_db)):
            tables[owner] = [
                r["name"]
                for r in db.rows(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
    browser_path = ROOT / "frontend/test-results/browser.json"
    browser = json.loads(browser_path.read_text()) if browser_path.exists() else None
    xml_path = ROOT / "backend/test-results/backend.xml"
    executed = None
    if xml_path.exists():
        suites = ET.parse(xml_path).getroot().iter("testsuite")
        executed = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
        for suite in suites:
            for key in executed:
                executed[key] += int(suite.get(key, "0"))
    report = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "backend": measure(backend),
        "frontend": measure(frontend),
        "tests": measure(tests),
        "meaningful_backend_modules": sum(
            p.name != "__init__.py" for p in backend if p.suffix == ".py"
        ),
        "backend_test_modules": len(list((ROOT / "backend/tests").glob("test_*.py"))),
        "pytest_collected_cases": len(nodes),
        "backend_executed": executed,
        "browser_executed": browser["stats"] if browser else None,
        "api_endpoints": endpoints,
        "persisted_entity_types": sum(map(len, tables.values())),
        "persisted_tables": tables,
        "fault_modes": len(FaultMode),
        "executable_scenarios": len(SCENARIOS),
    }
    print(json.dumps(report, indent=2))
    (ROOT / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if "--write-report" in sys.argv:
        if (
            not executed
            or executed["tests"] != len(nodes)
            or executed["failures"]
            or executed["errors"]
            or executed["skipped"]
            or not browser
            or browser["stats"]["unexpected"]
            or browser["stats"]["skipped"]
        ):
            raise RuntimeError("A passing executed backend/browser receipt is required")
        report["source_sha256"] = {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(backend + frontend + tests)
        }
        destination = ROOT / "docs/VERIFICATION.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
