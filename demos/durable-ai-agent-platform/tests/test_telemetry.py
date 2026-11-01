import json
import logging
import os
from uuid import uuid4

import pytest
from platform_core.database import event, transaction
from platform_core.repository import Repository

DSN = os.environ.get("ORCHESTRATOR_DSN")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DSN, reason="dedicated PostgreSQL required"),
]


async def test_structured_logs_correlate_real_claim_ids_without_payload(client, caplog):
    caplog.set_level(logging.INFO, logger="platform.events")
    owner = uuid4()
    repo = Repository(DSN)
    task = await repo.seed_task(owner, str(uuid4()), {"name": "UNTRUSTED_PAYLOAD_NOT_FOR_LOGS"})
    claim = await repo.claim("trace-owner", task_id=task)
    logs = [
        json.loads(record.message) for record in caplog.records if record.name == "platform.events"
    ]
    claimed = next(row for row in logs if row["event"] == "worker_claimed")
    assert claimed["correlation_id"] == claimed["task_id"] == str(task)
    assert claimed["tenant_id"] == str(owner) and claimed["run_id"] == str(claim.run_id)
    assert claimed["step_id"] == str(claim.step_id) and claimed["worker_id"] == "trace-owner"
    assert "UNTRUSTED_PAYLOAD_NOT_FOR_LOGS" not in caplog.text


async def test_rolled_back_event_is_not_emitted_as_committed_log(client, caplog):
    caplog.set_level(logging.INFO, logger="platform.events")
    owner = uuid4()
    task = await Repository(DSN).seed_task(owner, str(uuid4()), {"name": "Rollback log"})
    caplog.clear()
    with pytest.raises(RuntimeError):
        async with transaction(DSN) as c:
            await event(c, owner, task, "must_rollback", {"note": "never log raw notes"})
            raise RuntimeError("force rollback")
    assert "must_rollback" not in caplog.text
    async with transaction(DSN) as c:
        assert (
            await c.fetchval(
                "SELECT count(*) FROM events WHERE task_id=$1 AND kind='must_rollback'", task
            )
            == 0
        )


async def test_metrics_exposes_zero_states_and_failed_aggregate(client):
    from test_application_api import tenant

    headers = await tenant(client)
    metrics = (await client.get("/metrics", headers=headers)).json()
    for key in [
        "queued",
        "running",
        "recovering",
        "unknown",
        "manual_review",
        "completed",
        "failed",
        "ambiguous_tool_outcomes",
    ]:
        assert key in metrics and metrics[key] == 0
