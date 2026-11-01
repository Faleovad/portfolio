"""Kill a dispatcher OS process inside the control container, then recover from DB."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "control",
            "python",
            "-m",
            "platform_core.scenarios",
            "run",
            "S06",
        ],
        cwd=ROOT,
        check=True,
    )
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "control",
            "cat",
            "/app/docs/scenario-results/S06.json",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "PASS" and result["state"] == "COMPLETED"
    assert (
        result["provider_mutation_count"] == result["dispatch_attempts"] == result["receipts"] == 1
    )
    assert all(result["invariant_assertions"].values())
    assert any("replacement" in key for key in result["invariant_assertions"])
    assert "UNKNOWN" in result["state_path"] and "RECOVERING" in result["state_path"]
    result["boundary"] = (
        "OS process kill inside running Docker Compose control container; persisted PostgreSQL state; replacement dispatcher and SELECT-only recovery subprocess"
    )
    (ROOT / "docs/COMPOSE_RESTART.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                k: result[k]
                for k in [
                    "status",
                    "provider_mutation_count",
                    "dispatch_attempts",
                    "receipts",
                    "boundary",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
