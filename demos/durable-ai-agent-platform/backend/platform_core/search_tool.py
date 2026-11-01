"""Read-only external Search. The artifact is an observation, not a mutation receipt."""

from typing import Any
from uuid import uuid4

from .database import event, transaction
from .identity import fingerprint
from .policy import reserve
from .provider_reader import ProviderReader
from .repository import Claim, check_claim
from .tool_contracts import SearchPayload


async def search_step(executor: Any, claim: Claim, reader_dsn: str) -> None:
    async with transaction(executor.dsn) as c:
        step = await check_claim(c, claim)
        config = await c.fetchval(
            "SELECT v.config FROM tasks t JOIN agent_versions v ON v.tenant_id=t.tenant_id AND v.id=t.agent_version_id WHERE t.tenant_id=$1 AND t.id=$2",
            claim.tenant_id,
            claim.task_id,
        )
        if "search" not in config.get("tools", []):
            await executor._review_tx(c, claim, "search permission denied")
            return
        if not await reserve(c, claim.tenant_id, claim.task_id, {"tool_calls": 1}):
            return
        payload = SearchPayload.model_validate(step["input"])
        await event(
            c,
            claim.tenant_id,
            claim.task_id,
            "search_called",
            {"step_id": str(claim.step_id), "read_only": True},
        )
    fault = await executor.faults.consume(claim.tenant_id, claim.task_id, "search_response")
    if fault.mode == "search_outage":
        await executor._review(claim, "external search unavailable")
        return
    hits = await ProviderReader(reader_dsn).search(payload.query)
    content = {
        "tool": "search",
        "read_only": True,
        "step_id": str(claim.step_id),
        "query": payload.query,
        "query_hash": fingerprint({"query": payload.query}),
        "hits": hits,
        "source": "public immutable synthetic provider catalog",
    }
    async with transaction(executor.dsn) as c:
        await check_claim(c, claim)
        artifact = uuid4()
        await c.execute(
            "INSERT INTO artifacts(tenant_id,id,task_id,media_type,content,content_hash) VALUES($1,$2,$3,'application/vnd.synthetic.search+json',$4,$5)",
            claim.tenant_id,
            artifact,
            claim.task_id,
            content,
            fingerprint(content),
        )
        await executor._complete_step(c, claim, artifact)
        await event(
            c,
            claim.tenant_id,
            claim.task_id,
            "search_observation_persisted",
            {"artifact_id": str(artifact), "hits": len(hits), "mutation_intent": False},
        )
