from typing import Any
from uuid import UUID

from .application import ApplicationService
from .provider_reader import ProviderReader


async def snapshot(dsn: str, reader_dsn: str, tenant: UUID, task: UUID) -> dict[str, Any]:
    service = ApplicationService(dsn)
    result: dict[str, Any] = {"task": await service.get(tenant, "tasks", task)}
    for table in [
        "runs",
        "steps",
        "events",
        "model_calls",
        "tool_intents",
        "tool_receipts",
        "recovery_tasks",
        "artifacts",
        "evaluations",
        "retrieval_hits",
        "fault_plans",
    ]:
        result[table] = await service.list(tenant, table, task)
    result["steps"].sort(key=lambda row: row["sequence"])
    result["version"] = await service.get(
        tenant, "agent_versions", result["task"]["agent_version_id"]
    )
    result["provider"] = await ProviderReader(reader_dsn).actual(
        tenant, [row["id"] for row in result["tool_intents"]]
    )
    result["safe_actions"] = ["acknowledge", "reconcile"]
    return result
