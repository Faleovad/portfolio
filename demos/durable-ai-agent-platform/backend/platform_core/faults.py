from dataclasses import dataclass
from typing import ClassVar
from uuid import UUID, uuid4

from .database import event, transaction


class WorkerCrash(Exception):
    """The CLI exits without completing the current step/receipt transaction."""


class TransactionRollback(Exception):
    pass


@dataclass(frozen=True)
class FaultDecision:
    mode: str = "none"
    parameters: dict[str, object] | None = None


class FaultEngine:
    """Every fault is consumed transactionally once at its named boundary."""

    MODES: ClassVar[dict[str, str]] = {
        "tool_commit_then_timeout": "tool_response",
        "worker_pause_after_unknown": "worker_after_unknown",
        "model_timeout": "model_response",
        "malformed_model_output": "model_response",
        "retrieval_outage": "retrieval",
        "worker_crash_before_step_commit": "step_before_commit",
        "worker_crash_after_step_commit": "step_after_commit",
        "tool_timeout_before_commit": "tool_response",
        "delayed_external_visibility": "tool_response",
        "stale_readback": "readback",
        "readback_outage": "readback",
        "lost_acknowledgement": "tool_ack",
        "worker_lease_expiry": "worker_claim",
        "stale_worker_write": "ownership_experiment",
        "database_transaction_rollback": "step_transaction",
        "duplicate_enqueue": "enqueue_experiment",
        "cancellation_during_unknown": "worker_after_unknown",
        "malformed_retrieved_document": "retrieval",
        "budget_exhaustion": "admission",
        "competing_workers": "claim_experiment",
        "manual_review_required": "model_response",
        "recovery_crash_after_observation": "recovery_observed",
        "logical_duration_expiry": "admission",
        "tool_error_before_commit": "tool_response",
        "tool_error_after_commit": "tool_response",
        "search_outage": "search_response",
    }

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def configure(self, tenant: UUID, task: UUID, mode: str, remaining: int = 1) -> None:
        if mode not in self.MODES or remaining < 1:
            raise ValueError("unsupported fault or invalid count")
        async with transaction(self.dsn) as c:
            if not await c.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tasks WHERE tenant_id=$1 AND id=$2)", tenant, task
            ):
                raise ValueError("task unavailable")
            await c.execute(
                "INSERT INTO fault_plans(tenant_id,id,task_id,boundary,mode,remaining) VALUES($1,$2,$3,$4,$5,$6)",
                tenant,
                uuid4(),
                task,
                self.MODES[mode],
                mode,
                remaining,
            )

    async def consume(self, tenant: UUID, task: UUID, boundary: str) -> FaultDecision:
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                """SELECT * FROM fault_plans WHERE tenant_id=$1 AND task_id=$2
                   AND boundary=$3 AND remaining > 0 ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",
                tenant,
                task,
                boundary,
            )
            if row is None:
                return FaultDecision()
            await c.execute(
                "UPDATE fault_plans SET remaining=remaining-1 WHERE tenant_id=$1 AND id=$2",
                tenant,
                row["id"],
            )
            await event(
                c, tenant, task, "fault_consumed", {"boundary": boundary, "mode": row["mode"]}
            )
            return FaultDecision(row["mode"], row["parameters"])

    async def checkpoint(self, tenant: UUID, task: UUID, boundary: str) -> None:
        decision = await self.consume(tenant, task, boundary)
        if decision.mode in {
            "worker_crash_before_step_commit",
            "worker_crash_after_step_commit",
            "recovery_crash_after_observation",
        }:
            raise WorkerCrash(decision.mode)

    async def admission(self, tenant: UUID, task: UUID) -> None:
        decision = await self.consume(tenant, task, "admission")
        async with transaction(self.dsn) as c:
            if decision.mode == "budget_exhaustion":
                await c.execute(
                    "UPDATE tasks SET model_limit=model_used WHERE tenant_id=$1 AND id=$2",
                    tenant,
                    task,
                )
            elif decision.mode == "logical_duration_expiry":
                await c.execute(
                    "UPDATE tasks SET deadline=clock_timestamp() WHERE tenant_id=$1 AND id=$2",
                    tenant,
                    task,
                )
