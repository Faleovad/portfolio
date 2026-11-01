import hashlib
import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from .database import event, transaction
from .errors import ReplayForbidden, TenantDenied
from .identity import fingerprint, idempotency_identity
from .repository import advance_task
from .schemas import AgentConfig, TaskCreate
from .state import TaskState


class ApplicationRepository:
    TABLES = frozenset(
        {
            "agents",
            "agent_versions",
            "tasks",
            "documents",
            "artifacts",
            "recovery_tasks",
            "steps",
            "model_calls",
            "tool_intents",
            "tool_receipts",
            "evaluations",
            "fault_plans",
            "retrieval_hits",
            "events",
            "runs",
        }
    )

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def create_tenant(self, name: str) -> dict[str, object]:
        tenant = uuid4()
        token = secrets.token_urlsafe(32)
        async with transaction(self.dsn) as c:
            await c.execute(
                "INSERT INTO tenants(id,name,auth_hash) VALUES($1,$2,$3)",
                tenant,
                name,
                hashlib.sha256(token.encode()).hexdigest(),
            )
        return {"id": tenant, "name": name, "token": token}

    async def authenticate(self, token: str) -> UUID:
        if not token or len(token) > 256:
            raise TenantDenied("invalid authentication")
        async with transaction(self.dsn) as c:
            tenant = await c.fetchval(
                "SELECT id FROM tenants WHERE auth_hash=$1",
                hashlib.sha256(token.encode()).hexdigest(),
            )
        if not tenant:
            raise TenantDenied("invalid authentication")
        return UUID(str(tenant))

    async def tenants(self, tenant: UUID) -> list[dict[str, Any]]:
        async with transaction(self.dsn) as c:
            return [
                dict(row)
                for row in await c.fetch(
                    "SELECT id,name,created_at FROM tenants WHERE id=$1", tenant
                )
            ]

    async def get(self, tenant: UUID, table: str, identity: UUID) -> dict[str, Any]:
        if table not in self.TABLES:
            raise ValueError("unsupported resource")
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                "SELECT * FROM " + table + " WHERE tenant_id=$1 AND id=$2", tenant, identity
            )
        if row is None:
            raise TenantDenied("resource unavailable")
        return dict(row)

    async def list(
        self, tenant: UUID, table: str, task: UUID | None = None
    ) -> list[dict[str, Any]]:
        if table not in self.TABLES:
            raise ValueError("unsupported resource")
        if task:
            await self.get(tenant, "tasks", task)
        async with transaction(self.dsn) as c:
            if task is not None:
                if table not in {
                    "steps",
                    "runs",
                    "model_calls",
                    "tool_intents",
                    "tool_receipts",
                    "events",
                    "artifacts",
                    "evaluations",
                    "fault_plans",
                    "retrieval_hits",
                    "recovery_tasks",
                }:
                    raise ValueError("resource has no task scope")
                if table in {"model_calls", "retrieval_hits"}:
                    rows = await c.fetch(
                        "SELECT x.* FROM "
                        + table
                        + " x JOIN steps s ON s.tenant_id=x.tenant_id AND s.id=x.step_id "
                        "WHERE x.tenant_id=$1 AND s.task_id=$2",
                        tenant,
                        task,
                    )
                elif table in {"tool_receipts", "recovery_tasks"}:
                    rows = await c.fetch(
                        "SELECT x.* FROM "
                        + table
                        + " x JOIN tool_intents i ON i.tenant_id=x.tenant_id AND i.id=x.intent_id "
                        "WHERE x.tenant_id=$1 AND i.task_id=$2",
                        tenant,
                        task,
                    )
                else:
                    order = "ordinal" if table == "events" else "id"
                    rows = await c.fetch(
                        "SELECT * FROM "
                        + table
                        + " WHERE tenant_id=$1 AND task_id=$2 ORDER BY "
                        + order
                        + " LIMIT 500",
                        tenant,
                        task,
                    )
            else:
                rows = await c.fetch(
                    "SELECT * FROM " + table + " WHERE tenant_id=$1 ORDER BY id LIMIT 500", tenant
                )
        return [dict(row) for row in rows]

    async def create_agent(self, tenant: UUID, name: str) -> UUID:
        agent = uuid4()
        async with transaction(self.dsn) as c:
            await c.execute(
                "INSERT INTO agents(tenant_id,id,name) VALUES($1,$2,$3)", tenant, agent, name
            )
        return agent

    async def publish(self, tenant: UUID, agent: UUID, config: AgentConfig) -> UUID:
        async with transaction(self.dsn) as c:
            owner = await c.fetchrow(
                "SELECT id FROM agents WHERE tenant_id=$1 AND id=$2 FOR UPDATE", tenant, agent
            )
            if not owner:
                raise TenantDenied("agent unavailable")
            number = await c.fetchval(
                "SELECT coalesce(max(version),0)+1 FROM agent_versions WHERE tenant_id=$1 AND agent_id=$2",
                tenant,
                agent,
            )
            version = uuid4()
            await c.execute(
                "INSERT INTO agent_versions(tenant_id,id,agent_id,version,config) VALUES($1,$2,$3,$4,$5)",
                tenant,
                version,
                agent,
                number,
                config.model_dump(),
            )
            return version

    async def create_task(self, tenant: UUID, request: TaskCreate) -> UUID:
        digest = fingerprint(request.model_dump(mode="json"))
        async with transaction(self.dsn) as c:
            await c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                str(tenant) + request.enqueue_key,
            )
            version = await c.fetchrow(
                "SELECT * FROM agent_versions WHERE tenant_id=$1 AND id=$2",
                tenant,
                request.agent_version_id,
            )
            if not version:
                raise TenantDenied("version unavailable")
            if request.tool_payload is not None and request.tool_name not in version["config"].get(
                "tools", []
            ):
                raise ReplayForbidden("pinned agent does not permit " + request.tool_name)
            previous = await c.fetchrow(
                "SELECT id,request_fingerprint FROM tasks WHERE tenant_id=$1 AND enqueue_key=$2",
                tenant,
                request.enqueue_key,
            )
            if previous:
                if previous["request_fingerprint"] != digest:
                    raise ReplayForbidden("enqueue payload conflict")
                return UUID(str(previous["id"]))
            task = uuid4()
            await c.execute(
                """INSERT INTO tasks(tenant_id,id,agent_version_id,enqueue_key,objective,request_fingerprint,
                   model_limit,tool_limit,recovery_limit) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)""",
                tenant,
                task,
                request.agent_version_id,
                request.enqueue_key,
                request.objective,
                digest,
                request.model_limit,
                request.tool_limit,
                request.recovery_limit,
            )
            await c.execute(
                """UPDATE tasks SET step_limit=$3,token_limit=$4,cost_limit=$5,
                   deadline=clock_timestamp()+$6::interval,lab_controlled=$7 WHERE tenant_id=$1 AND id=$2""",
                tenant,
                task,
                request.step_limit,
                request.token_limit,
                request.cost_limit,
                timedelta(seconds=request.duration_seconds),
                request.lab_controlled,
            )
            # The ordered rows are the durable Plan; no whole-workflow JSON blob.
            plan: list[tuple[str, dict[str, object]]] = [
                ("retrieve", {"query": request.objective}),
                (
                    "model",
                    {
                        "objective": request.objective,
                        "requested_tool": request.tool_payload is not None,
                        "requested_tool_name": request.tool_name,
                    },
                ),
            ]
            if request.tool_payload is not None:
                plan.append(
                    (
                        "search" if request.tool_name == "search" else "tool",
                        dict(request.tool_payload),
                    )
                )
            plan.append(("evaluate", {}))
            for sequence, (kind, payload) in enumerate(plan):
                await c.execute(
                    """INSERT INTO steps(tenant_id,id,task_id,sequence,kind,input_fingerprint,input,idempotency_key)
                       VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
                    tenant,
                    uuid4(),
                    task,
                    sequence,
                    kind,
                    fingerprint(payload),
                    payload,
                    idempotency_identity(tenant, task, sequence),
                )
            await c.execute(
                "UPDATE steps SET tool_name=$3 WHERE tenant_id=$1 AND task_id=$2",
                tenant,
                task,
                request.tool_name,
            )
            await event(
                c, tenant, task, "task_created", {"agent_version_id": str(request.agent_version_id)}
            )
            await event(c, tenant, task, "plan_persisted", {"steps": len(plan)})
            await advance_task(c, tenant, task, TaskState.QUEUED)
            return task

    async def continue_task(self, tenant: UUID, task: UUID) -> dict[str, Any]:
        current = await self.get(tenant, "tasks", task)
        if current["state"] == "FAILED_RETRYABLE":
            async with transaction(self.dsn) as c:
                await advance_task(c, tenant, task, TaskState.QUEUED)
                await event(c, tenant, task, "continuation_requested", {})
        # UNKNOWN/review/terminal never reopens a mutation via this endpoint.
        return await self.get(tenant, "tasks", task)

    async def cancel(self, tenant: UUID, task: UUID) -> dict[str, Any]:
        await self.get(tenant, "tasks", task)
        async with transaction(self.dsn) as c:
            current = await c.fetchrow(
                "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE", tenant, task
            )
            if current["state"] in {
                "COMPLETED",
                "CANCELLED",
                "FAILED_TERMINAL",
                "BUDGET_EXHAUSTED",
            }:
                return dict(current)
            await c.execute(
                "UPDATE tasks SET cancel_requested=true WHERE tenant_id=$1 AND id=$2", tenant, task
            )
            intents = await c.fetch(
                """SELECT * FROM tool_intents WHERE tenant_id=$1 AND task_id=$2
                   AND state IN ('PREPARED','SENT','UNKNOWN','MANUAL_REVIEW') FOR UPDATE""",
                tenant,
                task,
            )
            unresolved = [row for row in intents if row["state"] != "PREPARED"]
            if unresolved:
                await advance_task(c, tenant, task, TaskState.CANCEL_REQUESTED)
                for row in unresolved:
                    await c.execute(
                        """INSERT INTO recovery_tasks(tenant_id,id,intent_id) VALUES($1,$2,$3)
                           ON CONFLICT(tenant_id,intent_id) DO NOTHING""",
                        tenant,
                        uuid4(),
                        row["id"],
                    )
            else:
                source = TaskState(current["state"])
                if source not in {TaskState.CREATED, TaskState.QUEUED, TaskState.FAILED_RETRYABLE}:
                    await advance_task(c, tenant, task, TaskState.CANCEL_REQUESTED)
                await advance_task(c, tenant, task, TaskState.CANCELLED)
                await c.execute(
                    "UPDATE steps SET state='CANCELLED',revision=revision+1 WHERE tenant_id=$1 AND task_id=$2 AND state NOT IN ('COMPLETED','FAILED_TERMINAL','CANCELLED')",
                    tenant,
                    task,
                )
            await event(
                c, tenant, task, "cancellation_requested", {"unresolved_intents": len(unresolved)}
            )
        return await self.get(tenant, "tasks", task)

    async def metrics(self, tenant: UUID) -> dict[str, int]:
        async with transaction(self.dsn) as c:
            rows = await c.fetch(
                "SELECT state,count(*) AS count FROM tasks WHERE tenant_id=$1 GROUP BY state",
                tenant,
            )
            ambiguous = await c.fetchval(
                "SELECT count(*) FROM tool_intents WHERE tenant_id=$1 AND state IN ('UNKNOWN','MANUAL_REVIEW')",
                tenant,
            )
        result = {state.value.lower(): 0 for state in TaskState}
        result.update({row["state"].lower(): int(row["count"]) for row in rows})
        result["failed"] = result["failed_terminal"] + result["failed_retryable"]
        result["ambiguous_tool_outcomes"] = int(ambiguous)
        return result

    async def acknowledge_review(self, tenant: UUID, recovery_id: UUID, note: str) -> None:
        record = await self.get(tenant, "recovery_tasks", recovery_id)
        intent = await self.get(tenant, "tool_intents", record["intent_id"])
        async with transaction(self.dsn) as c:
            await event(c, tenant, intent["task_id"], "review_acknowledged", {"note": note})
        # No change to intent state, mutation fence, or dispatch eligibility.

    async def reopen_observation(self, tenant: UUID, recovery_id: UUID) -> None:
        from .state import RecoveryState, recovery_transition

        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                "SELECT state FROM recovery_tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                tenant,
                recovery_id,
            )
            if row is None:
                raise TenantDenied("recovery unavailable")
            if row["state"] == "MANUAL_REVIEW":
                recovery_transition(RecoveryState.MANUAL_REVIEW, RecoveryState.PENDING)
                await c.execute(
                    "UPDATE recovery_tasks SET state='PENDING',revision=revision+1,next_attempt_at=clock_timestamp() WHERE tenant_id=$1 AND id=$2",
                    tenant,
                    recovery_id,
                )

    async def review_note(self, tenant: UUID, task: UUID, note: str) -> None:
        await self.get(tenant, "tasks", task)
        async with transaction(self.dsn) as c:
            await event(c, tenant, task, "review_acknowledged", {"note": note})
