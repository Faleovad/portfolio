"""Internal synthetic provider service. Recovery never receives this mutating port."""

import os
from dataclasses import asdict
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import Field

from .errors import ProofMismatch
from .proof import EffectIdentity
from .provider import ProviderResponseLost, ProviderWriter
from .provider_reader import ProviderReader
from .schemas import StrictModel
from .tool_contracts import ToolName


class Dispatch(StrictModel):
    tenant_id: UUID
    intent_id: UUID
    external_identity: str = Field(max_length=200)
    payload_fingerprint: str = Field(max_length=100)
    idempotency_key: str = Field(max_length=200)
    payload: dict[str, str]
    tool: ToolName = "crm"
    response_lost: bool = False
    timeout_before_commit: bool = False
    visibility_delay: float = Field(default=0, ge=0, le=30)
    error_before_commit: bool = False
    error_after_commit: bool = False


def create_app(writer_dsn: str, reader_dsn: str | None = None) -> FastAPI:
    app = FastAPI(title="Independent synthetic tool provider")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "boundary": "separate provider database"}

    @app.post("/dispatch")
    async def dispatch(body: Dispatch, x_lab_service: str = Header(default="")) -> object:
        if x_lab_service != "synthetic-only-lab":
            raise HTTPException(403, "synthetic service boundary")
        identity = EffectIdentity(
            body.tenant_id,
            body.intent_id,
            body.external_identity,
            body.payload_fingerprint,
            body.idempotency_key,
            body.tool,
        )
        try:
            result = await ProviderWriter(writer_dsn).dispatch(
                identity,
                dict(body.payload),
                tool=body.tool,
                response_lost=body.response_lost,
                timeout_before_commit=body.timeout_before_commit,
                visibility_delay=body.visibility_delay,
                error_before_commit=body.error_before_commit,
                error_after_commit=body.error_after_commit,
            )
        except ProviderResponseLost as error:
            raise HTTPException(504, "unconfirmed synthetic transport outcome") from error
        except ProofMismatch as error:
            raise HTTPException(409, str(error)) from error
        return asdict(result)

    @app.get("/search")
    async def search(query: str, x_lab_service: str = Header(default="")) -> object:
        if x_lab_service != "synthetic-only-lab":
            raise HTTPException(403, "synthetic service boundary")
        try:
            return await ProviderReader(reader_dsn or writer_dsn).search(query)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    return app


def from_environment() -> FastAPI:
    return create_app(os.environ["PROVIDER_WRITE_DSN"], os.environ.get("PROVIDER_READ_DSN"))
