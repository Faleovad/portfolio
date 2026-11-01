import os
from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .application import ApplicationService
from .database import transaction
from .errors import DomainError, TenantDenied
from .faults import FaultEngine
from .inspection import snapshot
from .provider_reader import ProviderReader
from .rag import RetrievalService
from .repository import effect
from .schemas import (
    AgentConfig,
    AgentCreate,
    DocumentUpload,
    FaultRequest,
    ReviewAction,
    SearchQuery,
    TaskCreate,
    TenantCreate,
)


def create_app(dsn: str, provider_read_dsn: str, allow_reset: bool = False) -> FastAPI:
    app = FastAPI(title="Durable AI Agent Platform", version="0.2.0")
    service = ApplicationService(dsn)
    retrieval = RetrievalService(dsn)
    bearer = HTTPBearer(auto_error=False)

    async def scope(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> UUID:
        if credentials is None:
            raise HTTPException(401, "tenant bearer token required")
        try:
            return await service.authenticate(credentials.credentials)
        except TenantDenied as error:
            raise HTTPException(401, "invalid authentication") from error

    Tenant = Annotated[UUID, Depends(scope)]

    @app.middleware("http")
    async def body_limit(request: Request, call_next: Any) -> Any:
        if request.method in {"POST", "PUT", "PATCH"}:
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 100000:
                    return JSONResponse({"detail": "request body too large"}, status_code=413)
            request._body = bytes(body)
        return await call_next(request)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        code = 404 if isinstance(error, TenantDenied) else 409
        return JSONResponse({"detail": str(error)}, status_code=code)

    @app.get("/health")
    async def health() -> dict[str, object]:
        async with transaction(dsn) as c:
            await c.fetchval("SELECT 1")
        return {"status": "ok", "mode": "synthetic", "model": "deterministic"}

    @app.post("/tenants", status_code=201)
    async def tenants_create(body: TenantCreate) -> Any:
        return await service.create_tenant(body.name)

    @app.get("/tenants")
    async def tenants_list(tenant: Tenant) -> Any:
        return await service.tenants(tenant)

    @app.post("/agents", status_code=201)
    async def agent_create(body: AgentCreate, tenant: Tenant) -> Any:
        return {"id": await service.create_agent(tenant, body.name)}

    @app.get("/agents")
    async def agents_list(tenant: Tenant) -> Any:
        return await service.list(tenant, "agents")

    @app.get("/agents/{identity}")
    async def agent_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "agents", identity)

    @app.post("/agents/{identity}/versions", status_code=201)
    async def version_publish(identity: UUID, body: AgentConfig, tenant: Tenant) -> Any:
        return {"id": await service.publish(tenant, identity, body)}

    @app.get("/versions/{identity}")
    async def version_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "agent_versions", identity)

    @app.post("/tasks", status_code=201)
    async def task_create(body: TaskCreate, tenant: Tenant) -> Any:
        return {"id": await service.create_task(tenant, body)}

    @app.get("/tasks")
    async def tasks_list(tenant: Tenant) -> Any:
        return await service.list(tenant, "tasks")

    @app.get("/tasks/{identity}")
    async def task_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "tasks", identity)

    @app.post("/tasks/{identity}/run")
    async def task_continue(identity: UUID, tenant: Tenant) -> Any:
        return await service.continue_task(tenant, identity)

    @app.post("/tasks/{identity}/cancel")
    async def task_cancel(identity: UUID, tenant: Tenant) -> Any:
        return await service.cancel(tenant, identity)

    @app.get("/tasks/{identity}/events")
    async def task_events(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "events", identity)

    @app.get("/tasks/{identity}/snapshot")
    async def task_snapshot(identity: UUID, tenant: Tenant) -> Any:
        return await snapshot(dsn, provider_read_dsn, tenant, identity)

    @app.get("/tasks/{identity}/steps")
    async def task_steps(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "steps", identity)

    @app.get("/tasks/{identity}/runs")
    async def task_runs(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "runs", identity)

    @app.get("/tasks/{identity}/model-calls")
    async def model_calls(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "model_calls", identity)

    @app.get("/tasks/{identity}/intents")
    async def intents(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "tool_intents", identity)

    @app.get("/tasks/{identity}/receipts")
    async def receipts(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "tool_receipts", identity)

    @app.get("/tasks/{identity}/evaluations")
    async def evaluations(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "evaluations", identity)

    @app.get("/tasks/{identity}/artifacts")
    async def artifacts(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "artifacts", identity)

    @app.get("/tasks/{identity}/provenance")
    async def provenance(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "retrieval_hits", identity)

    @app.get("/artifacts/{identity}")
    async def artifact_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "artifacts", identity)

    @app.get("/tasks/{identity}/provider")
    async def provider_state(identity: UUID, tenant: Tenant) -> Any:
        rows = await service.list(tenant, "tool_intents", identity)
        reader = ProviderReader(provider_read_dsn)
        return [asdict(await reader.observe(effect(row))) for row in rows]

    @app.post("/documents", status_code=201)
    async def document_upload(body: DocumentUpload, tenant: Tenant) -> Any:
        return {"id": await retrieval.upload(tenant, body.name, body.text)}

    @app.get("/documents")
    async def documents_list(tenant: Tenant) -> Any:
        return await service.list(tenant, "documents")

    @app.get("/documents/{identity}")
    async def document_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "documents", identity)

    @app.post("/retrieval/search")
    async def search(body: SearchQuery, tenant: Tenant) -> Any:
        return await retrieval.search(tenant, body.query, body.limit)

    @app.post("/documents/{identity}/search")
    async def document_search(identity: UUID, body: SearchQuery, tenant: Tenant) -> Any:
        return await retrieval.search(tenant, body.query, body.limit, identity)

    @app.get("/recovery")
    async def recoveries(tenant: Tenant) -> Any:
        return await service.list(tenant, "recovery_tasks")

    @app.get("/recovery/{identity}")
    async def recovery_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "recovery_tasks", identity)

    @app.post("/recovery/{identity}/reconcile")
    async def reconcile(identity: UUID, tenant: Tenant) -> Any:
        return await service.reconcile(tenant, identity, provider_read_dsn)

    @app.get("/manual-review")
    async def review_list(tenant: Tenant) -> Any:
        return [
            row for row in await service.list(tenant, "tasks") if row["state"] == "MANUAL_REVIEW"
        ]

    @app.get("/manual-review/{identity}")
    async def review_get(identity: UUID, tenant: Tenant) -> Any:
        return await service.get(tenant, "tasks", identity)

    @app.post("/manual-review/{identity}/resolve")
    async def review_resolve(identity: UUID, body: ReviewAction, tenant: Tenant) -> Any:
        return await service.resolve_review(
            tenant, identity, body.action, body.note, provider_read_dsn
        )

    @app.post("/tasks/{identity}/faults", status_code=201)
    async def configure_fault(identity: UUID, body: FaultRequest, tenant: Tenant) -> Any:
        await service.get(tenant, "tasks", identity)
        try:
            await FaultEngine(dsn).configure(tenant, identity, body.mode, body.remaining)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        return {"status": "configured"}

    @app.get("/tasks/{identity}/faults")
    async def inspect_faults(identity: UUID, tenant: Tenant) -> Any:
        return await service.list(tenant, "fault_plans", identity)

    @app.get("/metrics")
    async def metrics(tenant: Tenant) -> Any:
        return await service.metrics(tenant)

    @app.post("/synthetic/reset", status_code=201)
    async def synthetic_reset(tenant: Tenant) -> Any:
        if not allow_reset:
            raise HTTPException(403, "synthetic reset disabled")
        # Rotate to a new empty workspace; unresolved history is never deleted.
        return await service.create_tenant("Fresh synthetic workspace")

    return app


def from_environment() -> FastAPI:
    from .telemetry import configure_logging

    configure_logging()
    return create_app(
        os.environ["ORCHESTRATOR_DSN"],
        os.environ["PROVIDER_READ_DSN"],
        os.environ.get("ALLOW_SYNTHETIC_RESET") == "1",
    )
