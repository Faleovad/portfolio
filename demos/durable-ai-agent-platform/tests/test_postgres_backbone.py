import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio


async def test_normal_ack_still_requires_readback():
    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "normal", {"name": "Normal"})
    dispatcher = process("platform_core.worker")
    stdout, stderr = await asyncio.to_thread(dispatcher.communicate, timeout=15)
    assert dispatcher.returncode == 0, (stdout, stderr)
    await wait_state(repository, tenant, task, "WAITING_READBACK")
    async with transaction(DSN) as c:
        assert await c.fetchval("SELECT state FROM tool_intents") == "SENT"
        assert await c.fetchval("SELECT count(*) FROM tool_receipts") == 0
    recovery = process("platform_core.recovery_worker")
    stdout, stderr = await asyncio.to_thread(recovery.communicate, timeout=15)
    assert recovery.returncode == 0, (stdout, stderr)
    await wait_state(repository, tenant, task, "COMPLETED")


async def test_unknown_database_fence_blocks_reprepare():
    import asyncpg

    repository = Repository(DSN)
    tenant = uuid4()
    await repository.seed_task(tenant, "fence", {"name": "Fence"})
    claim = await repository.claim("fence-worker")
    identity, _ = await repository.prepare(claim)
    await repository.sent(claim, identity)
    await repository.unknown(claim, identity)
    async with transaction(DSN) as c:
        with pytest.raises(asyncpg.RaiseError):
            await c.execute("UPDATE tool_intents SET state='PREPARED'")


async def test_intent_payload_is_immutable():
    import asyncpg

    repository = Repository(DSN)
    await repository.seed_task(uuid4(), "payload", {"name": "Original"})
    claim = await repository.claim("payload-worker")
    await repository.prepare(claim)
    async with transaction(DSN) as c:
        with pytest.raises(asyncpg.RaiseError):
            await c.execute("UPDATE tool_intents SET payload='{}'")


async def test_events_are_append_only():
    import asyncpg

    repository = Repository(DSN)
    await repository.seed_task(uuid4(), "events", {"name": "Event"})
    async with transaction(DSN) as c:
        with pytest.raises(asyncpg.RaiseError):
            await c.execute("DELETE FROM events")


async def test_running_task_keeps_published_version():
    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "version", {"name": "Pinned"})
    original = await repository.task(tenant, task)
    await repository.claim("version-worker")
    async with transaction(DSN) as c:
        agent = await c.fetchval("SELECT agent_id FROM agent_versions WHERE tenant_id=$1", tenant)
        await c.execute(
            "UPDATE agents SET name='Updated',revision=revision+1 WHERE tenant_id=$1", tenant
        )
        await c.execute(
            "INSERT INTO agent_versions(tenant_id,id,agent_id,version,config) VALUES($1,$2,$3,2,$4)",
            tenant,
            uuid4(),
            agent,
            {"tools": []},
        )
    current = await repository.task(tenant, task)
    assert current["agent_version_id"] == original["agent_version_id"]


async def test_recovery_worker_has_no_mutating_provider_import():
    import ast

    tree = ast.parse((ROOT / "backend/platform_core/recovery_worker.py").read_text())
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    assert not any(node.module == "provider" for node in imports)
    assert (
        "PROVIDER_WRITE_DSN" not in (ROOT / "backend/platform_core/recovery_worker.py").read_text()
    )


from platform_core.database import transaction
from platform_core.errors import OwnershipLost, TenantDenied
from platform_core.faults import FaultEngine
from platform_core.repository import Repository

ROOT = Path(__file__).resolve().parents[1]
DSN = os.environ.get("ORCHESTRATOR_DSN")
ORCHESTRATOR_ADMIN = os.environ.get("ORCHESTRATOR_ADMIN_DSN")
PROVIDER_ADMIN = os.environ.get("PROVIDER_ADMIN_DSN")
WRITE_DSN = os.environ.get("PROVIDER_WRITE_DSN")
READ_DSN = os.environ.get("PROVIDER_READ_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not all([DSN, ORCHESTRATOR_ADMIN, PROVIDER_ADMIN, WRITE_DSN, READ_DSN]),
        reason="dedicated PostgreSQL DSNs required",
    ),
]


@pytest_asyncio.fixture(autouse=True)
async def clean_database():
    assert DSN and PROVIDER_ADMIN
    async with transaction(ORCHESTRATOR_ADMIN) as c:
        await c.execute("TRUNCATE tenants CASCADE")
    async with transaction(PROVIDER_ADMIN) as c:
        await c.execute("TRUNCATE effects,provider_attempts RESTART IDENTITY CASCADE")
    yield


def process(module, **environment):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "backend"))
    env.update(environment)
    if module.endswith("recovery_worker"):
        env.pop("PROVIDER_WRITE_DSN", None)
        env.pop("PROVIDER_ADMIN_DSN", None)
        env.pop("LAB_ADMIN_DSN", None)
        env.pop("ORCHESTRATOR_ADMIN_DSN", None)
    return subprocess.Popen(
        [sys.executable, "-m", module, "--once"],
        env=env,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


async def wait_state(repository, tenant, task, state):
    for _ in range(200):
        value = await repository.task(tenant, task)
        if value["state"] == state:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"task never reached {state}")


async def test_real_process_death_unknown_readonly_recovery_one_effect():
    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "restart-proof", {"name": "Synthetic entity"})
    faults = FaultEngine(DSN)
    await faults.configure(tenant, task, "tool_commit_then_timeout")
    await faults.configure(tenant, task, "worker_pause_after_unknown")
    worker = process("platform_core.worker")
    try:
        await wait_state(repository, tenant, task, "UNKNOWN")
        assert worker.poll() is None
        async with transaction(PROVIDER_ADMIN) as c:
            assert await c.fetchval("SELECT count(*) FROM effects") == 1
        # This is an actual OS process termination, not object recreation.
        worker.kill()
        await asyncio.to_thread(worker.wait, timeout=10)
        recovery = process("platform_core.recovery_worker")
        stdout, stderr = await asyncio.to_thread(recovery.communicate, timeout=15)
        assert recovery.returncode == 0, (stdout, stderr)
        assert "CONFIRMED" in stdout
        await wait_state(repository, tenant, task, "COMPLETED")
        async with transaction(DSN) as c:
            assert await c.fetchval("SELECT count(*) FROM tool_receipts") == 1
            assert await c.fetchval("SELECT state FROM tool_intents") == "CONFIRMED"
            events = await c.fetch("SELECT kind FROM events ORDER BY ordinal")
            assert [r["kind"] for r in events][-2:] == ["effect_confirmed", "task_completed"]
        again = process("platform_core.recovery_worker")
        stdout, stderr = await asyncio.to_thread(again.communicate, timeout=15)
        assert again.returncode == 0, (stdout, stderr)
        async with transaction(PROVIDER_ADMIN) as c:
            assert await c.fetchval("SELECT count(*) FROM effects") == 1
            assert await c.fetchval("SELECT count(*) FROM provider_attempts") == 1
            mutations = await c.fetchval("SELECT count(*) FROM effects")
            attempts = await c.fetchval("SELECT count(*) FROM provider_attempts")
        import json

        (ROOT / "docs/BACKBONE_RESTART.json").write_text(
            json.dumps(
                {
                    "scope": "single-tool PostgreSQL backbone, not complete AI platform",
                    "status": "PASS",
                    "dispatcher_pid": worker.pid,
                    "dispatcher_termination_code": worker.returncode,
                    "recovery_pid": recovery.pid,
                    "recovery_exit_code": recovery.returncode,
                    "persisted_unknown_before_termination": True,
                    "task_after_recovery": "COMPLETED",
                    "external_mutations": mutations,
                    "dispatch_attempts": attempts,
                    "terminal_receipt_count": 1,
                    "recovery_writer_credentials": False,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    finally:
        if worker.poll() is None:
            worker.kill()
            await asyncio.to_thread(worker.wait, timeout=10)


async def test_competing_claims_have_one_owner():
    repository = Repository(DSN)
    await repository.seed_task(uuid4(), "race", {"name": "Race"})
    claims = await asyncio.gather(*(repository.claim(f"worker-{i}") for i in range(12)))
    assert sum(c is not None for c in claims) == 1


async def test_expired_owner_cannot_prepare_or_heartbeat():
    repository = Repository(DSN)
    await repository.seed_task(uuid4(), "stale", {"name": "Stale"})
    old = await repository.claim("old", 0.05)
    await asyncio.sleep(0.1)
    current = await repository.claim("new")
    assert current and old
    with pytest.raises(OwnershipLost):
        await repository.prepare(old)
    with pytest.raises(OwnershipLost):
        await repository.heartbeat(old)
    assert current.token != old.token


async def test_foreign_tenant_task_hidden():
    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "private", {"name": "Private"})
    with pytest.raises(TenantDenied):
        await repository.task(uuid4(), task)


async def test_duplicate_enqueue_returns_original_task():
    repository = Repository(DSN)
    tenant = uuid4()
    first = await repository.seed_task(tenant, "same", {"name": "One"})
    second = await repository.seed_task(tenant, "same", {"name": "One"})
    assert first == second
    async with transaction(DSN) as c:
        assert await c.fetchval("SELECT count(*) FROM steps") == 1


async def test_cross_tenant_foreign_keys_reject_version_reference():
    import asyncpg

    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "fk", {"name": "Source"})
    original = await repository.task(tenant, task)
    async with transaction(DSN) as c:
        other = uuid4()
        await c.execute("INSERT INTO tenants VALUES($1,'Other',$2,now())", other, str(other))
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await c.execute(
                "INSERT INTO tasks(tenant_id,id,agent_version_id,enqueue_key,objective) VALUES($1,$2,$3,'bad','bad')",
                other,
                uuid4(),
                original["agent_version_id"],
            )


async def test_published_version_database_immutable():
    import asyncpg

    repository = Repository(DSN)
    tenant = uuid4()
    task = await repository.seed_task(tenant, "immutable", {"name": "One"})
    value = await repository.task(tenant, task)
    async with transaction(DSN) as c:
        with pytest.raises(asyncpg.RaiseError):
            await c.execute(
                "UPDATE agent_versions SET config='{}' WHERE tenant_id=$1 AND id=$2",
                tenant,
                value["agent_version_id"],
            )


async def test_provider_reader_database_role_cannot_insert():
    import asyncpg

    async with transaction(READ_DSN) as c:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await c.execute(
                """INSERT INTO effects(tenant_id,intent_id,external_identity,payload_fingerprint,
                   idempotency_key,tool,payload) VALUES($1,$2,'x','x','x','crm','{}')""",
                uuid4(),
                uuid4(),
            )


async def test_sent_intent_never_claimed_as_dispatchable_after_expiry():
    repository = Repository(DSN)
    tenant = uuid4()
    await repository.seed_task(tenant, "sent", {"name": "Sent"})
    claim = await repository.claim("old", 30)
    assert claim
    identity, _ = await repository.prepare(claim)
    await repository.sent(claim, identity)
    async with transaction(DSN) as c:
        await c.execute("UPDATE steps SET lease_until=clock_timestamp()-interval '1 second'")
    assert await repository.claim("new") is None
    assert await repository.rescue_expired_sent() == 1
    async with transaction(DSN) as c:
        assert await c.fetchval("SELECT state FROM tool_intents") == "UNKNOWN"
        assert await c.fetchval("SELECT count(*) FROM recovery_tasks") == 1


async def test_concurrent_duplicate_enqueue_creates_one_task():
    repository = Repository(DSN)
    tenant = uuid4()
    results = await asyncio.gather(
        *(repository.seed_task(tenant, "concurrent", {"name": "One"}) for _ in range(8))
    )
    assert len(set(results)) == 1
    async with transaction(DSN) as c:
        assert await c.fetchval("SELECT count(*) FROM tasks") == 1
        assert await c.fetchval("SELECT count(*) FROM agent_versions") == 1


async def test_enqueue_payload_conflict_rejected():
    from platform_core.errors import ReplayForbidden

    repository = Repository(DSN)
    tenant = uuid4()
    await repository.seed_task(tenant, "conflict", {"name": "One"})
    with pytest.raises(ReplayForbidden):
        await repository.seed_task(tenant, "conflict", {"name": "Two"})


async def test_provider_duplicate_is_idempotent_but_identity_conflict_rejected():
    from dataclasses import replace

    from platform_core.errors import ProofMismatch
    from platform_core.identity import fingerprint
    from platform_core.proof import EffectIdentity
    from platform_core.provider import ProviderWriter

    payload = {"name": "One"}
    identity = EffectIdentity(uuid4(), uuid4(), "crm:one", fingerprint(payload), "key")
    provider = ProviderWriter(WRITE_DSN)
    first = await provider.dispatch(identity, payload)
    second = await provider.dispatch(identity, payload)
    assert first == second
    with pytest.raises(ProofMismatch):
        await provider.dispatch(replace(identity, intent_id=uuid4()), payload)
    async with transaction(PROVIDER_ADMIN) as c:
        assert await c.fetchval("SELECT count(*) FROM effects") == 1
