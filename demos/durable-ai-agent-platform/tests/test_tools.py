import asyncio
from uuid import uuid4

import asyncpg
import httpx
import pytest
from platform_core.database import transaction
from platform_core.errors import ProofMismatch
from platform_core.executor import Executor
from platform_core.faults import FaultEngine
from platform_core.identity import fingerprint
from platform_core.models import ModelRequest
from platform_core.proof import EffectIdentity
from platform_core.provider import ProviderWriter
from platform_core.provider_api import create_app
from platform_core.provider_http import HTTPProviderWriter
from platform_core.recovery_worker import run_once
from platform_core.repository import Repository
from platform_core.schemas import ModelOutput
from platform_core.worker import dispatch_once
from test_application_api import (
    DSN,
    READ,
    WRITE,
    agent,
    create_task,
    tenant,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not all([DSN, READ, WRITE]), reason="dedicated PostgreSQL required"),
]
PAYLOADS = {
    "search": {"query": "refund"},
    "crm": {"name": "Synthetic entity"},
    "quota": {"account": "test-account", "delta": "100"},
    "email": {
        "recipient_id": "demo-inbox",
        "subject": "Synthetic notice",
        "body": "Synthetic message",
    },
    "http": {"method": "POST", "path": "/synthetic/test-resource", "body": "created"},
}


def identity(owner, tool, payload):
    return EffectIdentity(
        owner, uuid4(), "synthetic:" + str(uuid4()), fingerprint(dict(payload)), str(uuid4()), tool
    )


async def dispatch_task(tool, payload=None, fault=None):
    owner = uuid4()
    repo = Repository(DSN)
    task = await repo.seed_task(owner, str(uuid4()), dict(payload or PAYLOADS[tool]), tool=tool)
    if fault:
        await FaultEngine(DSN).configure(owner, task, fault)
    await dispatch_once(repo, ProviderWriter(WRITE), "tool-test", task)
    return owner, task


@pytest.mark.parametrize("tool", list(PAYLOADS))
async def test_tool_permission_denied_before_any_intent(client, tool):
    headers = await tenant(client)
    _, version = await agent(client, headers)
    response = await client.post(
        "/tasks",
        headers=headers,
        json={
            "agent_version_id": version,
            "enqueue_key": str(uuid4()),
            "objective": "Forbidden tool",
            "tool_name": tool,
            "tool_payload": PAYLOADS[tool],
        },
    )
    assert response.status_code == 409
    async with transaction(DSN) as c:
        assert await c.fetchval("SELECT count(*) FROM tool_intents") == 0


async def test_external_search_observation_and_final_artifact(client):
    headers = await tenant(client)
    _, version = await agent(client, headers, tools=["search"])
    task = await create_task(
        client, headers, version, tool_name="search", tool_payload=PAYLOADS["search"]
    )
    executor = Executor(DSN, reader_dsn=READ)
    for _ in range(4):
        assert await executor.run_once()
    data = (await client.get(f"/tasks/{task}/snapshot", headers=headers)).json()
    assert data["task"]["state"] == "COMPLETED" and data["task"]["tool_used"] == 1
    observation = next(
        x for x in data["artifacts"] if x["media_type"] == "application/vnd.synthetic.search+json"
    )
    final = next(x for x in data["artifacts"] if x["media_type"] == "application/json")
    assert (
        observation["content"]["read_only"] and observation["content"]["hits"][0]["id"] == "refund"
    )
    assert final["content"]["tool_observations"][0]["artifact_id"] == observation["id"]
    assert data["tool_intents"] == data["tool_receipts"] == []
    assert data["provider"]["mutations"] == data["provider"]["dispatch_attempts"] == 0


async def test_external_search_outage_retains_no_mutation_authority(client):
    repo = Repository(DSN)
    owner = uuid4()
    task = await repo.seed_task(owner, str(uuid4()), PAYLOADS["search"], tool="search")
    await FaultEngine(DSN).configure(owner, task, "search_outage")
    await Executor(DSN, reader_dsn=READ).run_once(task_id=task)
    assert (await repo.task(owner, task))["state"] == "MANUAL_REVIEW"
    async with transaction(WRITE) as c:
        assert await c.fetchval("SELECT count(*) FROM effects") == 0


async def test_quota_credit_then_debit_exact_balance(client):
    owner = uuid4()
    writer = ProviderWriter(WRITE)
    for delta in ["100", "-25"]:
        payload = {"account": "balance", "delta": delta}
        await writer.dispatch(identity(owner, "quota", payload), payload, tool="quota")
    async with transaction(WRITE) as c:
        assert (
            await c.fetchval("SELECT balance FROM quota_accounts WHERE tenant_id=$1", owner) == 75
        )
        assert await c.fetchval("SELECT count(*) FROM effects WHERE tenant_id=$1", owner) == 2


async def test_quota_idempotency_does_not_apply_delta_twice(client):
    owner = uuid4()
    payload = PAYLOADS["quota"]
    effect = identity(owner, "quota", payload)
    writer = ProviderWriter(WRITE)
    first = await writer.dispatch(effect, payload, tool="quota")
    assert await writer.dispatch(effect, payload, tool="quota") == first
    async with transaction(WRITE) as c:
        assert (
            await c.fetchval("SELECT balance FROM quota_accounts WHERE tenant_id=$1", owner) == 100
        )
        assert (
            await c.fetchval("SELECT count(*) FROM provider_attempts WHERE tenant_id=$1", owner)
            == 2
        )
        assert await c.fetchval("SELECT count(*) FROM effects WHERE tenant_id=$1", owner) == 1


async def test_concurrent_quota_adjustments_are_atomic(client):
    owner = uuid4()
    payload = {"account": "concurrent", "delta": "10"}
    writer = ProviderWriter(WRITE)
    await asyncio.gather(
        *(
            writer.dispatch(identity(owner, "quota", payload), payload, tool="quota")
            for _ in range(8)
        )
    )
    async with transaction(WRITE) as c:
        assert (
            await c.fetchval("SELECT balance FROM quota_accounts WHERE tenant_id=$1", owner) == 80
        )
        assert (
            await c.fetchval("SELECT revision FROM quota_accounts WHERE tenant_id=$1", owner) == 8
        )


async def test_insufficient_quota_rolls_back_domain_and_effect(client):
    owner = uuid4()
    writer = ProviderWriter(WRITE)
    credit = {"account": "limited", "delta": "5"}
    debit = {"account": "limited", "delta": "-6"}
    await writer.dispatch(identity(owner, "quota", credit), credit, tool="quota")
    with pytest.raises(ProofMismatch):
        await writer.dispatch(identity(owner, "quota", debit), debit, tool="quota")
    async with transaction(WRITE) as c:
        assert await c.fetchval("SELECT balance FROM quota_accounts WHERE tenant_id=$1", owner) == 5
        assert await c.fetchval("SELECT count(*) FROM effects WHERE tenant_id=$1", owner) == 1


async def test_email_message_key_cannot_be_sent_by_another_intent(client):
    owner = uuid4()
    payload = {**PAYLOADS["email"], "message_key": "one-message"}
    writer = ProviderWriter(WRITE)
    await writer.dispatch(identity(owner, "email", payload), payload, tool="email")
    with pytest.raises(ProofMismatch):
        await writer.dispatch(identity(owner, "email", payload), payload, tool="email")
    async with transaction(WRITE) as c:
        assert (
            await c.fetchval("SELECT count(*) FROM email_deliveries WHERE tenant_id=$1", owner) == 1
        )
        assert await c.fetchval("SELECT count(*) FROM effects WHERE tenant_id=$1", owner) == 1


async def test_email_lost_response_recovery_creates_receipt_not_another_delivery(client):
    owner, task = await dispatch_task("email", fault="tool_commit_then_timeout")
    assert (await Repository(DSN).task(owner, task))["state"] == "UNKNOWN"
    await run_once(DSN, READ, "read-only-email-recovery", task)
    assert (await Repository(DSN).task(owner, task))["state"] == "COMPLETED"
    async with transaction(WRITE) as c:
        assert (
            await c.fetchval("SELECT count(*) FROM email_deliveries WHERE tenant_id=$1", owner) == 1
        )
    async with transaction(DSN) as c:
        assert (
            await c.fetchval(
                "SELECT identity->>'tool' FROM tool_receipts WHERE tenant_id=$1", owner
            )
            == "email"
        )


async def test_crm_update_changes_existing_entity_once(client):
    owner = uuid4()
    writer = ProviderWriter(WRITE)
    for operation, name in [("create", "initial"), ("update", "updated")]:
        payload = {"entity_key": "one-entity", "operation": operation, "name": name}
        await writer.dispatch(identity(owner, "crm", payload), payload)
    async with transaction(WRITE) as c:
        row = await c.fetchrow("SELECT name,revision FROM crm_entities WHERE tenant_id=$1", owner)
        assert dict(row) == {"name": "updated", "revision": 2}


async def test_generic_HTTP_POST_then_PUT_updates_virtual_resource(client):
    owner = uuid4()
    writer = ProviderWriter(WRITE)
    for method, body in [("POST", "initial"), ("PUT", "updated")]:
        payload = {"method": method, "path": "/synthetic/virtual", "body": body}
        await writer.dispatch(identity(owner, "http", payload), payload, tool="http")
    async with transaction(WRITE) as c:
        assert dict(
            await c.fetchrow("SELECT body,revision FROM http_resources WHERE tenant_id=$1", owner)
        ) == {"body": "updated", "revision": 2}
        assert [
            x["outcome"]["status"]
            for x in await c.fetch(
                "SELECT outcome FROM effects WHERE tenant_id=$1 ORDER BY provider_revision", owner
            )
        ] == [201, 200]


@pytest.mark.parametrize(
    "path", ["https://invalid", "/synthetic/../escape", "/bin/sh", "/synthetic/x?execute=1"]
)
async def test_HTTP_tool_rejects_real_URL_or_arbitrary_route_before_dispatch(client, path):
    headers = await tenant(client)
    _, version = await agent(client, headers, tools=["http"])
    response = await client.post(
        "/tasks",
        headers=headers,
        json={
            "agent_version_id": version,
            "enqueue_key": str(uuid4()),
            "objective": "Route denial",
            "tool_name": "http",
            "tool_payload": {"method": "POST", "path": path, "body": "ignored"},
        },
    )
    assert response.status_code == 422


async def test_intent_tool_identity_is_immutable(client):
    owner = uuid4()
    repo = Repository(DSN)
    task = await repo.seed_task(owner, str(uuid4()), PAYLOADS["crm"])
    claim = await repo.claim("owner", task_id=task)
    await repo.prepare(claim)
    async with transaction(DSN) as c:
        with pytest.raises(asyncpg.RaiseError):
            await c.execute("UPDATE tool_intents SET tool='email' WHERE tenant_id=$1", owner)


@pytest.mark.parametrize(
    "table", ["crm_entities", "quota_accounts", "email_deliveries", "http_resources"]
)
async def test_provider_reader_role_has_no_domain_mutation_permission(client, table):
    async with transaction(READ) as c:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await c.execute("DELETE FROM " + table)


async def test_model_cannot_switch_to_another_allowed_but_unplanned_tool(client):
    class WrongChoice:
        async def generate(self, request: ModelRequest, mode="none"):
            return ModelOutput(
                decision="continue",
                confidence=1,
                answer="Unplanned operation",
                citations=[],
                tool_requests=["quota"],
                reason_codes=[],
            ).model_dump_json()

    headers = await tenant(client)
    _, version = await agent(client, headers, tools=["email", "quota"], repair=0)
    task = await create_task(
        client, headers, version, tool_name="email", tool_payload=PAYLOADS["email"]
    )
    executor = Executor(DSN, model=WrongChoice())
    await executor.run_once()
    await executor.run_once()
    assert (await client.get("/tasks/" + task, headers=headers)).json()["state"] == "MANUAL_REVIEW"
    assert (await client.get(f"/tasks/{task}/intents", headers=headers)).json() == []


@pytest.mark.parametrize("tool", ["crm", "quota", "email", "http"])
@pytest.mark.parametrize("fault", ["tool_error_after_commit", "tool_timeout_before_commit"])
async def test_each_tool_HTTP_fault_and_readonly_recovery(client, tool, fault):
    owner = uuid4()
    repo = Repository(DSN)
    task = await repo.seed_task(owner, str(uuid4()), PAYLOADS[tool], tool=tool)
    await FaultEngine(DSN).configure(owner, task, fault)
    writer = HTTPProviderWriter("http://provider", httpx.ASGITransport(app=create_app(WRITE, READ)))
    await dispatch_once(repo, writer, "HTTP-owner", task)
    assert (await repo.task(owner, task))["state"] == "UNKNOWN"
    assert await repo.claim("blind-retry", task_id=task) is None
    await run_once(DSN, READ, "recovery", task)
    assert (await repo.task(owner, task))["state"] == (
        "COMPLETED" if fault == "tool_error_after_commit" else "UNKNOWN"
    )
    async with transaction(WRITE) as c:
        assert await c.fetchval("SELECT count(*) FROM effects WHERE tenant_id=$1", owner) == int(
            fault == "tool_error_after_commit"
        )
        assert (
            await c.fetchval("SELECT count(*) FROM provider_attempts WHERE tenant_id=$1", owner)
            == 1
        )


async def test_search_cannot_enter_mutating_port(client):
    owner = uuid4()
    payload = PAYLOADS["search"]
    with pytest.raises(ProofMismatch):
        await ProviderWriter(WRITE).dispatch(
            identity(owner, "search", payload), payload, tool="search"
        )
    async with transaction(WRITE) as c:
        assert await c.fetchval("SELECT count(*) FROM provider_attempts") == 0
