from typing import Any
from uuid import UUID

from .application_repository import ApplicationRepository
from .fault_reader import FaultReader
from .recovery import RecoveryPolicy, RecoveryService
from .repository import Repository
from .schemas import AgentConfig, TaskCreate


class ApplicationService:
    """Authenticated tenant operations; SQL access belongs to repository adapters."""

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.repository = ApplicationRepository(dsn)

    async def create_tenant(self, name: str) -> dict[str, object]:
        return await self.repository.create_tenant(name)

    async def authenticate(self, token: str) -> UUID:
        return await self.repository.authenticate(token)

    async def tenants(self, tenant: UUID) -> list[dict[str, Any]]:
        return await self.repository.tenants(tenant)

    async def get(self, tenant: UUID, table: str, identity: UUID) -> dict[str, Any]:
        return await self.repository.get(tenant, table, identity)

    async def list(
        self, tenant: UUID, table: str, task: UUID | None = None
    ) -> list[dict[str, Any]]:
        return await self.repository.list(tenant, table, task)

    async def create_agent(self, tenant: UUID, name: str) -> UUID:
        return await self.repository.create_agent(tenant, name)

    async def publish(self, tenant: UUID, agent: UUID, config: AgentConfig) -> UUID:
        return await self.repository.publish(tenant, agent, config)

    async def create_task(self, tenant: UUID, request: TaskCreate) -> UUID:
        return await self.repository.create_task(tenant, request)

    async def continue_task(self, tenant: UUID, task: UUID) -> dict[str, Any]:
        return await self.repository.continue_task(tenant, task)

    async def cancel(self, tenant: UUID, task: UUID) -> dict[str, Any]:
        return await self.repository.cancel(tenant, task)

    async def metrics(self, tenant: UUID) -> dict[str, int]:
        return await self.repository.metrics(tenant)

    async def reconcile(self, tenant: UUID, recovery_id: UUID, reader_dsn: str) -> dict[str, str]:
        current = await self.get(tenant, "recovery_tasks", recovery_id)
        intent = await self.get(tenant, "tool_intents", current["intent_id"])
        task = await self.get(tenant, "tasks", intent["task_id"])
        if task["state"] == "BUDGET_EXHAUSTED":
            return {"status": "BUDGET_EXHAUSTED"}
        if current["state"] == "MANUAL_REVIEW":
            await self.repository.reopen_observation(tenant, recovery_id)
        claimed = await Repository(self.dsn).claim_recovery(
            "api-readonly", tenant=tenant, recovery_id=recovery_id
        )
        if claimed is None:
            return {"status": "not_claimed"}
        result = await RecoveryService(
            FaultReader(
                self.dsn,
                reader_dsn,
                intent["task_id"],
            ),
            claimed,
            RecoveryPolicy(),
        ).reconcile(claimed.identity)
        return {"status": result.value}

    async def resolve_review(
        self,
        tenant: UUID,
        task: UUID,
        action: str,
        note: str,
        reader_dsn: str,
    ) -> dict[str, object]:
        await self.get(tenant, "tasks", task)
        await self.repository.review_note(tenant, task, note)
        if action == "reconcile":
            for row in await self.list(tenant, "recovery_tasks", task):
                await self.reconcile(tenant, row["id"], reader_dsn)
        return {"status": "metadata_action_recorded", "mutation_fence_preserved": True}
