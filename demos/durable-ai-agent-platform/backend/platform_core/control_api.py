"""Opt-in synthetic process controls; separate from the read-only product API composition."""

import os
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import event, transaction
from .errors import DomainError, TenantDenied
from .scenario_catalog import CATALOG, SCENARIOS
from .scenarios import ScenarioRunner


def from_environment() -> FastAPI:
    from .telemetry import configure_logging

    configure_logging()
    if os.environ.get("ENABLE_LAB_CONTROLS") != "1":
        raise RuntimeError("synthetic controls require explicit ENABLE_LAB_CONTROLS=1")
    runner = ScenarioRunner(
        os.environ["ORCHESTRATOR_DSN"],
        os.environ["PROVIDER_WRITE_DSN"],
        os.environ["PROVIDER_READ_DSN"],
    )
    app = FastAPI(title="Synthetic laboratory controls")
    bearer = HTTPBearer()

    async def scope(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]) -> UUID:
        try:
            return await runner.service.authenticate(credentials.credentials)
        except TenantDenied as error:
            raise HTTPException(401, "invalid tenant bearer") from error

    Tenant = Annotated[UUID, Depends(scope)]

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "synthetic control process"}

    @app.get("/catalog")
    async def catalog() -> Any:
        return [spec.public() for spec in CATALOG]

    @app.post("/sessions/{identifier}")
    async def setup(identifier: str, tenant: Tenant) -> Any:
        if identifier not in SCENARIOS:
            raise HTTPException(404, "unknown scenario")
        session = await runner.setup(SCENARIOS[identifier], tenant)
        return {"task_id": session.task, "scenario": identifier}

    @app.post("/tasks/{task}/actions/{action}")
    async def control(task: UUID, action: str, tenant: Tenant) -> Any:
        try:
            session = await runner.resume(tenant, task)
            # A task-scoped lock rejects concurrent controls; it never serializes provider IO
            # with a mutating transaction or changes the worker ownership protocol.
            async with transaction(runner.dsn) as c:
                locked = await c.fetchval(
                    "SELECT pg_try_advisory_xact_lock(hashtextextended($1,4))", str(task)
                )
                if not locked:
                    raise HTTPException(409, "another laboratory action is running")
                cursor = int(
                    await c.fetchval(
                        "SELECT count(*) FROM events WHERE tenant_id=$1 AND task_id=$2 AND kind='scenario_action_completed'",
                        tenant,
                        task,
                    )
                )
                if action in {"step", "run"}:
                    remaining = list(enumerate(session.scenario.execution_steps))[cursor:]
                    if action == "step":
                        remaining = remaining[:1]
                    for index, step in remaining:
                        await runner.action(session, step)
                        # Commit the FK-bearing event before the next action requests
                        # task FOR UPDATE on another connection. The outer connection
                        # retains only the advisory control lock while actions execute.
                        async with transaction(runner.dsn) as progress:
                            await event(
                                progress,
                                tenant,
                                task,
                                "scenario_action_completed",
                                {"index": index, "action": step},
                            )
                elif action == "recover":
                    await runner.action(session, "recover_process")
                elif action == "crash-worker":
                    if session.scenario.id != "S06" or cursor:
                        raise HTTPException(
                            409, "OS-kill control is available at the S06 initial boundary"
                        )
                    await runner.action(session, "kill_unknown")
                    await event(
                        c,
                        tenant,
                        task,
                        "scenario_action_completed",
                        {"index": 0, "action": "kill_unknown"},
                    )
                elif action == "restart-worker":
                    await runner.process(session, "worker")
                elif action == "cancel":
                    await runner.service.cancel(tenant, task)
                else:
                    raise HTTPException(400, "unsupported safe laboratory action")
                await event(
                    c,
                    tenant,
                    task,
                    "operator_decision",
                    {
                        "action": action,
                        "process_evidence": session.process_evidence,
                        "assertions": session.assertions,
                    },
                )
            return await runner.evidence(session, final=action == "run")
        except TenantDenied as error:
            raise HTTPException(404, str(error)) from error
        except (DomainError, AssertionError, ValueError) as error:
            raise HTTPException(409, str(error)) from error

    return app
