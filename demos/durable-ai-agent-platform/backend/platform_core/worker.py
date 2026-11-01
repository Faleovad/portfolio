import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from uuid import UUID

from .database import transaction
from .errors import BudgetExceeded
from .faults import FaultEngine, WorkerCrash
from .provider import ProviderResponseLost, ProviderWriter
from .provider_http import HTTPProviderWriter
from .repository import Claim, Repository


async def dispatch_once(
    repository: Repository,
    provider: ProviderWriter,
    worker_id: str,
    task_id: UUID | None = None,
    claimed: Claim | None = None,
) -> bool:
    if task_id:
        await FaultEngine(repository.dsn).admission(await _tenant(repository, task_id), task_id)
    claim = claimed or await repository.claim(worker_id, task_id=task_id)
    if claim is None:
        return False
    faults = FaultEngine(repository.dsn)
    lease_fault = await faults.consume(claim.tenant_id, claim.task_id, "worker_claim")
    if lease_fault.mode == "worker_lease_expiry":
        async with transaction(repository.dsn) as c:
            await c.execute(
                "UPDATE steps SET lease_until=clock_timestamp() WHERE tenant_id=$1 AND id=$2",
                claim.tenant_id,
                claim.step_id,
            )
        return True
    identity, payload = await repository.prepare(claim)
    try:
        await repository.sent(claim, identity)
    except BudgetExceeded as error:
        await repository.exhaust_before_dispatch(claim, str(error))
        return True
    fault = await faults.consume(claim.tenant_id, claim.task_id, "tool_response")
    try:
        await provider.dispatch(
            identity,
            payload,
            tool=identity.tool,
            response_lost=fault.mode == "tool_commit_then_timeout",
            timeout_before_commit=fault.mode == "tool_timeout_before_commit",
            visibility_delay=5 if fault.mode == "delayed_external_visibility" else 0,
            error_before_commit=fault.mode == "tool_error_before_commit",
            error_after_commit=fault.mode == "tool_error_after_commit",
        )
    except ProviderResponseLost:
        await repository.unknown(claim, identity)
        print(json.dumps({"event": "persisted_unknown", "task_id": str(claim.task_id)}), flush=True)
        pause = await faults.consume(claim.tenant_id, claim.task_id, "worker_after_unknown")
        if pause.mode == "worker_pause_after_unknown":
            # Executable crash boundary: the parent terminates this OS process here.
            await asyncio.Event().wait()
        if pause.mode == "cancellation_during_unknown":
            from .application_repository import ApplicationRepository

            await ApplicationRepository(repository.dsn).cancel(claim.tenant_id, claim.task_id)
        return True
    ack = await faults.consume(claim.tenant_id, claim.task_id, "tool_ack")
    if ack.mode == "lost_acknowledgement":
        await repository.unknown(claim, identity)
        return True
    # Even an ACK requires independent readback before final confirmation.
    await repository.schedule_readback(claim, identity)
    return True


async def _tenant(repository: Repository, task: UUID) -> UUID:
    async with transaction(repository.dsn) as c:
        return UUID(str(await c.fetchval("SELECT tenant_id FROM tasks WHERE id=$1", task)))


async def run(args: argparse.Namespace) -> None:
    repository = Repository(os.environ["ORCHESTRATOR_DSN"])
    provider = (
        HTTPProviderWriter(os.environ["PROVIDER_URL"])
        if os.environ.get("PROVIDER_URL")
        else ProviderWriter(os.environ["PROVIDER_WRITE_DSN"])
    )
    while True:
        worked = await dispatch_once(repository, provider, args.worker_id, args.task_id)
        if args.once:
            return
        if not worked:
            await asyncio.sleep(0.1)


def main(argv: Sequence[str] | None = None) -> None:
    from .telemetry import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default="dispatcher")
    parser.add_argument("--task-id", type=UUID)
    args = parser.parse_args(argv)
    try:
        asyncio.run(run(args))
    except WorkerCrash:
        raise SystemExit(86) from None


if __name__ == "__main__":
    main()
