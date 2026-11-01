"""Real compose smoke; the running background dispatcher must use the HTTP provider."""

import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    running = subprocess.check_output(
        ["docker", "compose", "ps", "--services", "--status", "running"], cwd=root, text=True
    ).splitlines()
    assert {
        "postgres",
        "backend",
        "executor",
        "worker",
        "recovery",
        "provider",
        "control",
        "frontend",
    } <= set(running)
    migrations = {}
    for database, expected in [("agent_orchestrator", 6), ("agent_provider", 2)]:
        versions = subprocess.check_output(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "lab_admin",
                "-d",
                database,
                "-Atc",
                "SELECT version FROM schema_versions ORDER BY version",
            ],
            cwd=root,
            text=True,
        ).splitlines()
        assert len(versions) == expected
        migrations[database] = versions
    subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "provider",
            "python",
            "-c",
            "import httpx; c=httpx.Client(base_url='http://127.0.0.1:8002'); assert c.get('/health').is_success; assert c.get('/search',params={'query':'refund'},headers={'x-lab-service':'synthetic-only-lab'}).is_success",
        ],
        cwd=root,
        check=True,
    )
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
        for _ in range(90):
            try:
                if client.get("/health").is_success:
                    break
            except httpx.TransportError:
                pass
            time.sleep(1)
        else:
            raise AssertionError("compose API never became healthy")
        tenant = client.post("/tenants", json={"name": "Compose smoke"}).json()
        headers = {"Authorization": "Bearer " + tenant["token"]}
        agent = client.post("/agents", headers=headers, json={"name": "Compose agent"}).json()["id"]
        version = client.post(
            f"/agents/{agent}/versions", headers=headers, json={"tools": ["crm"]}
        ).json()["id"]
        document = client.post(
            "/documents",
            headers=headers,
            json={"name": "compose.txt", "text": "Refund policy: 30 days."},
        ).json()["id"]
        task = client.post(
            "/tasks",
            headers=headers,
            json={
                "agent_version_id": version,
                "enqueue_key": str(uuid4()),
                "objective": "refund policy",
                "tool_payload": {"name": "compose synthetic"},
            },
        ).json()["id"]
        for _ in range(90):
            snapshot = client.get(f"/tasks/{task}/snapshot", headers=headers).json()
            if snapshot["task"]["state"] == "COMPLETED":
                break
            time.sleep(1)
        else:
            raise AssertionError("automatic compose task did not complete")
        assert snapshot["provider"]["mutations"] == snapshot["provider"]["dispatch_attempts"] == 1
        assert len(snapshot["tool_receipts"]) == 1
        assert snapshot["artifacts"][0]["content"]["provenance"][0]["document_id"] == document
        stranger = client.post("/tenants", json={"name": "Compose stranger"}).json()
        assert (
            client.get(
                f"/tasks/{task}/snapshot", headers={"Authorization": "Bearer " + stranger["token"]}
            ).status_code
            == 404
        )
        assert httpx.get("http://127.0.0.1:58045").status_code == 200
    evidence = {
        "status": "PASS",
        "running_services": running,
        "migration_versions": migrations,
        "automatic_HTTP_provider_task": task,
        "provider_mutation_count": snapshot["provider"]["mutations"],
        "dispatch_attempts": snapshot["provider"]["dispatch_attempts"],
        "receipts": len(snapshot["tool_receipts"]),
        "RAG_provenance": "PASS",
        "tenant_denial": "PASS",
        "frontend_HTTP": "PASS",
        "provider_health_and_search": "PASS",
    }
    (root / "docs/COMPOSE_SMOKE.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
