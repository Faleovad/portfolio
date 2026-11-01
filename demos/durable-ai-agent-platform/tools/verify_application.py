"""Real HTTP + separate executor processes; requires the dedicated synthetic PostgreSQL lab."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def child_environment() -> dict[str, str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT / "backend"))
    for key in (
        "PROVIDER_WRITE_DSN",
        "PROVIDER_ADMIN_DSN",
        "ORCHESTRATOR_ADMIN_DSN",
        "LAB_ADMIN_DSN",
    ):
        env.pop(key, None)
    return env


async def main() -> None:
    env = child_environment()
    server = await asyncio.create_subprocess_exec(
        *[
            sys.executable,
            "-m",
            "uvicorn",
            "platform_core.api:from_environment",
            "--factory",
            "--host",
            "127.0.0.1",
            "--port",
            "58041",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:58041", timeout=10) as client:
            for _ in range(100):
                try:
                    response = await client.get("/health")
                    if response.status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(0.1)
            else:
                raise RuntimeError("HTTP server did not become ready")
            created = await client.post("/tenants", json={"name": "HTTP verification tenant"})
            created.raise_for_status()
            headers = {"Authorization": "Bearer " + created.json()["token"]}
            agent = await client.post(
                "/agents", headers=headers, json={"name": "Version pinned research"}
            )
            agent.raise_for_status()
            identity = agent.json()["id"]
            version = await client.post(
                f"/agents/{identity}/versions", headers=headers, json={"expected_keywords": ["14"]}
            )
            version.raise_for_status()
            v1 = version.json()["id"]
            document = await client.post(
                "/documents",
                headers=headers,
                json={"name": "policy-uk.txt", "text": "Політика повернення: 14 днів."},
            )
            document.raise_for_status()
            task_response = await client.post(
                "/tasks",
                headers=headers,
                json={
                    "agent_version_id": v1,
                    "objective": "refund policy",
                    "enqueue_key": "process-research",
                },
            )
            task_response.raise_for_status()
            task = task_response.json()["id"]
            executor_pids: list[int] = []
            for sequence in range(3):
                process = await asyncio.create_subprocess_exec(
                    *[sys.executable, "-m", "platform_core.executor", "--once"],
                    cwd=ROOT,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                _stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
                if process.returncode != 0:
                    raise RuntimeError(f"executor failed: {stderr.decode(errors='replace')}")
                executor_pids.append(process.pid)
                if sequence == 0:
                    new = await client.post(
                        f"/agents/{identity}/versions",
                        headers=headers,
                        json={"expected_keywords": ["must-not-affect-existing-task"]},
                    )
                    new.raise_for_status()
            current = (await client.get(f"/tasks/{task}", headers=headers)).json()
            artifacts = (await client.get(f"/tasks/{task}/artifacts", headers=headers)).json()
            calls = (await client.get(f"/tasks/{task}/model-calls", headers=headers)).json()
            steps = (await client.get(f"/tasks/{task}/steps", headers=headers)).json()
            checks = {
                "task_completed": current["state"] == "COMPLETED",
                "pinned_v1": current["agent_version_id"] == v1,
                "one_model_call": len(calls) == 1,
                "one_artifact": len(artifacts) == 1,
                "steps_not_rebuilt": len(steps) == 3 and all(x["attempt"] == 1 for x in steps),
                "source_document_matches": artifacts[0]["content"]["provenance"][0]["document_id"]
                == document.json()["id"],
                "cross_language_evidence": "14" in artifacts[0]["content"]["answer"],
            }
            if not all(checks.values()):
                raise AssertionError(checks)
            receipt = {
                "status": "PASS",
                "transport": "real HTTP loopback",
                "api_pid": server.pid,
                "executor_pids": executor_pids,
                "checks": checks,
                "model": "deterministic lexical reference; not a semantic benchmark",
                "paid_api_required": False,
            }
            (ROOT / "docs/APPLICATION_SMOKE.json").write_text(
                json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
            )
            print(json.dumps(receipt))
    finally:
        server.terminate()
        try:
            await asyncio.wait_for(server.wait(), timeout=10)
        except TimeoutError:
            server.kill()
            await asyncio.wait_for(server.wait(), timeout=10)


if __name__ == "__main__":
    asyncio.run(main())
