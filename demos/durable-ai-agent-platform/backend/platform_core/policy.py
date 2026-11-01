"""Atomic reservations. Synthetic token/cost estimates are admission units, not billing."""

from typing import Any
from uuid import UUID

from .database import event
from .state import TaskState

COLUMNS = {
    "model_calls": ("model_used", "model_limit"),
    "tool_calls": ("tool_used", "tool_limit"),
    "steps": ("step_used", "step_limit"),
    "estimated_tokens": ("token_used", "token_limit"),
    "estimated_cost_micros": ("cost_used", "cost_limit"),
    "recovery_attempts": ("recovery_used", "recovery_limit"),
}


async def exhaust(c: Any, tenant: UUID, task: UUID, dimension: str) -> None:
    from .repository import advance_task

    row = await c.fetchrow(
        "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE", tenant, task
    )
    unresolved = await c.fetchval(
        "SELECT EXISTS(SELECT 1 FROM tool_intents WHERE tenant_id=$1 AND task_id=$2 AND state IN ('SENT','UNKNOWN','MANUAL_REVIEW'))",
        tenant,
        task,
    )
    target = (
        TaskState.MANUAL_REVIEW
        if row["cancel_requested"] and unresolved
        else TaskState.BUDGET_EXHAUSTED
    )
    await advance_task(c, tenant, task, target)
    if unresolved:
        await c.execute(
            "UPDATE recovery_tasks r SET state='MANUAL_REVIEW',reason=$3,revision=r.revision+1 FROM tool_intents i WHERE r.tenant_id=$1 AND i.tenant_id=r.tenant_id AND i.id=r.intent_id AND i.task_id=$2 AND r.state<>'CONFIRMED'",
            tenant,
            task,
            "budget exhausted: " + dimension,
        )
    else:
        await c.execute(
            "UPDATE steps SET state=CASE WHEN state='PENDING' THEN 'CANCELLED' ELSE 'FAILED_TERMINAL' END,error_class=$3,revision=revision+1 WHERE tenant_id=$1 AND task_id=$2 AND state NOT IN ('COMPLETED','CANCELLED','FAILED_TERMINAL')",
            tenant,
            task,
            "budget exhausted: " + dimension,
        )
    await event(
        c,
        tenant,
        task,
        "budget_exhausted",
        {"dimension": dimension, "unresolved_fence_retained": bool(unresolved)},
    )


async def reserve(c: Any, tenant: UUID, task: UUID, amounts: dict[str, int]) -> bool:
    row = await c.fetchrow(
        "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE", tenant, task
    )
    if row["deadline"] <= await c.fetchval("SELECT clock_timestamp()"):
        await exhaust(c, tenant, task, "logical_duration")
        return False
    for dimension, amount in amounts.items():
        if dimension not in COLUMNS or amount < 0:
            raise ValueError("invalid reservation")
        used, limit = COLUMNS[dimension]
        if row[used] + amount > row[limit]:
            await exhaust(c, tenant, task, dimension)
            return False
    for dimension, amount in amounts.items():
        used, _ = COLUMNS[dimension]
        await c.execute(
            "UPDATE tasks SET " + used + "=" + used + "+$3 WHERE tenant_id=$1 AND id=$2",
            tenant,
            task,
            amount,
        )
    await event(c, tenant, task, "budget_reserved", dict(amounts))
    return True
