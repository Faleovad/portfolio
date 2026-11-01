import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from uuid import UUID

from .database import transaction
from .fault_reader import FaultReader
from .faults import WorkerCrash
from .recovery import RecoveryPolicy, RecoveryService
from .repository import Repository


async def run_once(
    dsn: str, reader_dsn: str, worker: str, task_id: UUID | None = None, seconds: float = 30
) -> bool:
    repository = Repository(dsn)
    await repository.rescue_expired_sent(task_id)
    recovery_id = None
    if task_id:
        async with transaction(dsn) as c:
            recovery_id = await c.fetchval(
                "SELECT r.id FROM recovery_tasks r JOIN tool_intents i ON i.tenant_id=r.tenant_id AND i.id=r.intent_id WHERE i.task_id=$1",
                task_id,
            )
        if recovery_id is None:
            return False
    recovery = await repository.claim_recovery(worker, seconds=seconds, recovery_id=recovery_id)
    if recovery is None:
        return False
    async with transaction(dsn) as c:
        task = await c.fetchval(
            "SELECT task_id FROM tool_intents WHERE tenant_id=$1 AND id=$2",
            recovery.identity.tenant_id,
            recovery.identity.intent_id,
        )
    service = RecoveryService(FaultReader(dsn, reader_dsn, task), recovery, RecoveryPolicy())
    outcome = await service.reconcile(recovery.identity)
    print(json.dumps({"event": "recovery_result", "outcome": outcome.value}), flush=True)
    return True


async def run(args: argparse.Namespace) -> None:
    # This process never reads a mutating provider DSN.
    dsn = os.environ["ORCHESTRATOR_DSN"]
    reader_dsn = os.environ["PROVIDER_READ_DSN"]
    while True:
        worked = await run_once(dsn, reader_dsn, args.worker_id, args.task_id, args.lease_seconds)
        if args.once:
            return
        if not worked:
            await asyncio.sleep(0.1)


def main(argv: Sequence[str] | None = None) -> None:
    from .telemetry import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--worker-id", default="recovery")
    parser.add_argument("--task-id", type=UUID)
    parser.add_argument("--lease-seconds", type=float, default=30)
    try:
        asyncio.run(run(parser.parse_args(argv)))
    except WorkerCrash:
        raise SystemExit(86) from None


if __name__ == "__main__":
    main()
