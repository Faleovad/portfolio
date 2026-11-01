import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from .telemetry import committed_logs, pending_logs

ROOT = Path(__file__).resolve().parents[2]


async def connect(dsn: str) -> Any:
    connection = await asyncpg.connect(dsn)
    await connection.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    return connection


@asynccontextmanager
async def transaction(dsn: str) -> AsyncIterator[Any]:
    connection = await connect(dsn)
    events: list[dict[str, object]] = []
    context_token = pending_logs.set(events)
    try:
        async with connection.transaction():
            yield connection
        committed_logs(events)
    finally:
        pending_logs.reset(context_token)
        await connection.close()


async def migrate(dsn: str, component: str) -> None:
    if component not in {"orchestrator", "provider"}:
        raise ValueError("unknown component")
    async with transaction(dsn) as c:
        await c.execute("SELECT pg_advisory_xact_lock(7001801)")
        await c.execute("CREATE TABLE IF NOT EXISTS schema_versions(version text PRIMARY KEY)")
        versions = ["001_" + component]
        if component == "orchestrator":
            versions.extend(
                [
                    "002_application",
                    "003_policies",
                    "004_laboratory",
                    "005_tools",
                    "006_task_bootstrap",
                ]
            )
        else:
            versions.append("002_provider_tools")
        for version in versions:
            if not await c.fetchval(
                "SELECT EXISTS(SELECT 1 FROM schema_versions WHERE version=$1)", version
            ):
                await c.execute((ROOT / "sql" / (version + ".sql")).read_text(encoding="utf-8"))
                await c.execute("INSERT INTO schema_versions VALUES($1)", version)


async def event(c: Any, tenant: UUID, task: UUID, kind: str, details: dict[str, object]) -> None:
    from uuid import uuid4

    await c.execute(
        "INSERT INTO events(tenant_id,id,task_id,kind,details) VALUES($1,$2,$3,$4,$5)",
        tenant,
        uuid4(),
        task,
        kind,
        details,
    )
    queue = pending_logs.get()
    if queue is not None:
        current = await c.fetchrow(
            """SELECT s.id,s.run_id,coalesce(r.owner,s.owner) AS owner,i.id AS intent_id FROM steps s
               LEFT JOIN tool_intents i ON i.tenant_id=s.tenant_id AND i.step_id=s.id
               LEFT JOIN recovery_tasks r ON r.tenant_id=i.tenant_id AND r.intent_id=i.id AND r.state='CLAIMED'
               WHERE s.tenant_id=$1 AND s.task_id=$2 AND (s.id=$3::uuid OR s.state IN ('RUNNING','WAITING','CLAIMED'))
               ORDER BY (s.id=$3::uuid) DESC NULLS LAST,s.sequence LIMIT 1""",
            tenant,
            task,
            UUID(str(details["step_id"])) if details.get("step_id") else None,
        )
        queue.append(
            {
                "event": kind,
                "correlation_id": str(task),
                "tenant_id": str(tenant),
                "task_id": str(task),
                "run_id": str(details.get("run_id") or current["run_id"])
                if details.get("run_id") or (current and current["run_id"])
                else None,
                "step_id": str(details.get("step_id") or current["id"])
                if details.get("step_id") or current
                else None,
                "tool_intent_id": str(details.get("intent_id") or current["intent_id"])
                if details.get("intent_id") or (current and current["intent_id"])
                else None,
                "worker_id": details.get("worker_id") or (current["owner"] if current else None),
            }
        )
