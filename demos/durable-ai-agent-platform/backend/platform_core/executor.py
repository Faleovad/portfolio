import argparse
import asyncio
import os
from typing import Any, cast
from uuid import UUID, uuid4

from pydantic import ValidationError

from .database import event, transaction
from .evaluators import evaluate
from .faults import FaultEngine, TransactionRollback, WorkerCrash
from .identity import fingerprint
from .models import DeterministicModel, ModelProvider, ModelRequest
from .policy import reserve
from .rag import RetrievalService
from .repository import Claim, Repository, advance_task, check_claim
from .schemas import AgentConfig, DocumentUpload, ModelOutput
from .search_tool import search_step
from .state import StepState, TaskState, step_transition
from .tool_contracts import ToolName


class Executor:
    def __init__(
        self, dsn: str, model: ModelProvider | None = None, reader_dsn: str | None = None
    ) -> None:
        self.dsn = dsn
        self.repository = Repository(dsn)
        self.model = model or DeterministicModel()
        self.retrieval = RetrievalService(dsn)
        self.faults = FaultEngine(dsn)
        self.reader_dsn = reader_dsn

    async def run_once(self, worker: str = "executor", task_id: UUID | None = None) -> bool:
        if task_id:
            async with transaction(self.dsn) as c:
                tenant = await c.fetchval("SELECT tenant_id FROM tasks WHERE id=$1", task_id)
            await self.faults.admission(tenant, task_id)
        claim = await self.repository.claim(
            worker, kinds=("retrieve", "model", "evaluate", "search"), task_id=task_id
        )
        if claim is None:
            return False
        async with transaction(self.dsn) as c:
            step = await check_claim(c, claim)
            kind = step["kind"]
        if kind == "retrieve":
            try:
                await self._retrieve(claim)
            except TransactionRollback:
                async with transaction(self.dsn) as c:
                    await check_claim(c, claim)
                    await c.execute(
                        "UPDATE steps SET lease_until=clock_timestamp() WHERE tenant_id=$1 AND id=$2",
                        claim.tenant_id,
                        claim.step_id,
                    )
                    await event(
                        c,
                        claim.tenant_id,
                        claim.task_id,
                        "transaction_rolled_back",
                        {"step_id": str(claim.step_id)},
                    )
        elif kind == "model":
            await self._model(claim)
        elif kind == "evaluate":
            await self._finalize(claim)
        elif kind == "search":
            if not self.reader_dsn:
                await self._review(claim, "search reader capability unavailable")
            else:
                await search_step(self, claim, self.reader_dsn)
        return True

    async def _complete_step(self, c: Any, claim: Claim, reference: UUID | None = None) -> None:
        row = await check_claim(c, claim)
        step_transition(StepState(row["state"]), StepState.COMPLETED)
        await c.execute(
            """UPDATE steps SET state='COMPLETED',output_reference=$3,revision=revision+1,
               updated_at=clock_timestamp() WHERE tenant_id=$1 AND id=$2""",
            claim.tenant_id,
            claim.step_id,
            reference,
        )
        await event(
            c, claim.tenant_id, claim.task_id, "step_completed", {"step_id": str(claim.step_id)}
        )
        await c.execute(
            "UPDATE runs SET ended_at=clock_timestamp() WHERE tenant_id=$1 AND id=$2",
            claim.tenant_id,
            claim.run_id,
        )

    async def _retrieve(self, claim: Claim) -> None:
        task = await self.repository.task(claim.tenant_id, claim.task_id)
        fault = await self.faults.consume(claim.tenant_id, claim.task_id, "retrieval")
        if fault.mode == "retrieval_outage":
            await self._review(claim, "retrieval unavailable")
            return
        hits = await self.retrieval.search(claim.tenant_id, task["objective"])
        if fault.mode == "malformed_retrieved_document":
            try:
                DocumentUpload(name="corrupt.txt", text="invalid\x00document")
            except ValidationError:
                await self._review(claim, "malformed retrieved document rejected")
                return
        await self.faults.checkpoint(claim.tenant_id, claim.task_id, "step_before_commit")
        rollback = await self.faults.consume(claim.tenant_id, claim.task_id, "step_transaction")
        async with transaction(self.dsn) as c:
            await check_claim(c, claim)
            for hit in hits:
                await c.execute(
                    """INSERT INTO retrieval_hits(tenant_id,id,step_id,chunk_id,score,query_hash,supports)
                       VALUES($1,$2,$3,$4,$5,$6,'answer evidence')
                       ON CONFLICT(tenant_id,step_id,chunk_id,query_hash) DO NOTHING""",
                    claim.tenant_id,
                    uuid4(),
                    claim.step_id,
                    UUID(str(hit["chunk_id"])),
                    hit["score"],
                    fingerprint({"query": task["objective"]}),
                )
            await event(
                c, claim.tenant_id, claim.task_id, "retrieval_completed", {"hits": len(hits)}
            )
            await self._complete_step(c, claim)
            if rollback.mode == "database_transaction_rollback":
                raise TransactionRollback()
        await self.faults.checkpoint(claim.tenant_id, claim.task_id, "step_after_commit")

    async def _context(
        self, claim: Claim
    ) -> tuple[dict[str, Any], AgentConfig, list[dict[str, Any]]]:
        async with transaction(self.dsn) as c:
            task = await c.fetchrow(
                """SELECT t.*,v.config FROM tasks t JOIN agent_versions v
                   ON v.tenant_id=t.tenant_id AND v.id=t.agent_version_id WHERE t.tenant_id=$1 AND t.id=$2""",
                claim.tenant_id,
                claim.task_id,
            )
            hits = await c.fetch(
                """SELECT h.*,ch.content,ch.document_id,d.name AS document_name FROM retrieval_hits h
                   JOIN steps s ON s.tenant_id=h.tenant_id AND s.id=h.step_id
                   JOIN chunks ch ON ch.tenant_id=h.tenant_id AND ch.id=h.chunk_id
                   JOIN documents d ON d.tenant_id=ch.tenant_id AND d.id=ch.document_id
                   WHERE h.tenant_id=$1 AND s.task_id=$2 ORDER BY h.score DESC,h.id""",
                claim.tenant_id,
                claim.task_id,
            )
        return dict(task), AgentConfig.model_validate(task["config"]), [dict(row) for row in hits]

    async def _model(self, claim: Claim) -> None:
        task, config, hits = await self._context(claim)
        async with transaction(self.dsn) as c:
            step = await check_claim(c, claim)
            requested = bool(step["input"].get("requested_tool"))
            requested_name = cast(ToolName, step["input"].get("requested_tool_name", "crm"))
            # A previously valid durable call is reusable after a crash before step completion.
            previous = await c.fetchrow(
                "SELECT id,response FROM model_calls WHERE tenant_id=$1 AND step_id=$2 AND state='VALID' ORDER BY attempt DESC LIMIT 1",
                claim.tenant_id,
                claim.step_id,
            )
            if previous:
                ModelOutput.model_validate(previous["response"])
                await self._complete_step(c, claim, previous["id"])
                return
        request = ModelRequest(
            config.instructions,
            task["objective"],
            tuple({"hit_id": str(hit["id"]), "content": hit["content"]} for hit in hits),
            requested,
            requested_name,
        )
        for _ in range(config.repair_limit + 1):
            async with transaction(self.dsn) as c:
                await check_claim(c, claim)
                current = await c.fetchrow(
                    "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                    claim.tenant_id,
                    claim.task_id,
                )
                if current["cancel_requested"]:
                    await advance_task(
                        c, claim.tenant_id, claim.task_id, TaskState.CANCEL_REQUESTED
                    )
                    await advance_task(c, claim.tenant_id, claim.task_id, TaskState.CANCELLED)
                    return
                estimate = (
                    len(request.instructions)
                    + len(request.objective)
                    + sum(len(str(h["content"])) for h in hits)
                    + 3
                ) // 4 + 512
                if not await reserve(
                    c,
                    claim.tenant_id,
                    claim.task_id,
                    {
                        "model_calls": 1,
                        "estimated_tokens": estimate,
                        "estimated_cost_micros": estimate * 2,
                    },
                ):
                    return
                attempt = await c.fetchval(
                    "SELECT coalesce(max(attempt),0)+1 FROM model_calls WHERE tenant_id=$1 AND step_id=$2",
                    claim.tenant_id,
                    claim.step_id,
                )
                if attempt > config.repair_limit + 1:
                    await self._review_tx(c, claim, "model repair policy exhausted")
                    return
                call = uuid4()
                await c.execute(
                    """INSERT INTO model_calls(tenant_id,id,step_id,attempt,provider,state,request_hash)
                       VALUES($1,$2,$3,$4,'deterministic','STARTED',$5)""",
                    claim.tenant_id,
                    call,
                    claim.step_id,
                    attempt,
                    fingerprint(
                        {"objective": request.objective, "hits": [str(h["id"]) for h in hits]}
                    ),
                )
                await advance_task(c, claim.tenant_id, claim.task_id, TaskState.WAITING_MODEL)
                await event(
                    c,
                    claim.tenant_id,
                    claim.task_id,
                    "model_called",
                    {"call_id": str(call), "attempt": attempt},
                )
            mode = await self.faults.consume(claim.tenant_id, claim.task_id, "model_response")
            raw = ""
            try:
                raw = await self.model.generate(request, mode.mode)
                output = ModelOutput.model_validate_json(raw)
                valid_ids = {str(hit["id"]) for hit in hits}
                if not {str(x) for x in output.citations} <= valid_ids:
                    raise ValueError("unknown citation")
                if not set(output.tool_requests) <= set(config.tools):
                    raise ValueError("forbidden model tool request")
                planned = [requested_name] if requested and output.decision == "continue" else []
                if output.tool_requests != planned:
                    raise ValueError("model cannot change the persisted tool plan")
            except (ValidationError, ValueError, TimeoutError) as error:
                async with transaction(self.dsn) as c:
                    await check_claim(c, claim)
                    await c.execute(
                        "UPDATE model_calls SET state='INVALID',response=$3,error_class=$4 WHERE tenant_id=$1 AND id=$2",
                        claim.tenant_id,
                        call,
                        {"raw": raw},
                        type(error).__name__,
                    )
                    await advance_task(c, claim.tenant_id, claim.task_id, TaskState.RUNNING)
                    await event(
                        c,
                        claim.tenant_id,
                        claim.task_id,
                        "model_output_invalid",
                        {"call_id": str(call)},
                    )
                continue
            async with transaction(self.dsn) as c:
                await check_claim(c, claim)
                await c.execute(
                    "UPDATE model_calls SET state='VALID',response=$3 WHERE tenant_id=$1 AND id=$2",
                    claim.tenant_id,
                    call,
                    output.model_dump(mode="json"),
                )
                if output.decision == "review":
                    await self._review_tx(c, claim, "model requested manual review")
                    return
                await advance_task(c, claim.tenant_id, claim.task_id, TaskState.RUNNING)
                await self._complete_step(c, claim, call)
            return
        await self._review(claim, "bounded model repair exhausted")

    async def _review_tx(self, c: Any, claim: Claim, reason: str) -> None:
        row = await check_claim(c, claim)
        await advance_task(c, claim.tenant_id, claim.task_id, TaskState.MANUAL_REVIEW)
        step_transition(StepState(row["state"]), StepState.FAILED_TERMINAL)
        await c.execute(
            "UPDATE steps SET state='FAILED_TERMINAL',error_class=$3 WHERE tenant_id=$1 AND id=$2",
            claim.tenant_id,
            claim.step_id,
            reason,
        )
        await event(c, claim.tenant_id, claim.task_id, "manual_review", {"reason": reason})

    async def _review(self, claim: Claim, reason: str) -> None:
        async with transaction(self.dsn) as c:
            await self._review_tx(c, claim, reason)

    async def _finalize(self, claim: Claim) -> None:
        task, config, hits = await self._context(claim)
        async with transaction(self.dsn) as c:
            await check_claim(c, claim)
            call = await c.fetchrow(
                """SELECT m.* FROM model_calls m JOIN steps s ON s.tenant_id=m.tenant_id AND s.id=m.step_id
                   WHERE m.tenant_id=$1 AND s.task_id=$2 AND m.state='VALID' ORDER BY m.attempt DESC LIMIT 1""",
                claim.tenant_id,
                claim.task_id,
            )
            if call is None:
                await self._review_tx(c, claim, "missing validated model output")
                return
            unresolved = await c.fetchval(
                "SELECT count(*) FROM tool_intents WHERE tenant_id=$1 AND task_id=$2 AND state<>'CONFIRMED'",
                claim.tenant_id,
                claim.task_id,
            )
            results = evaluate(
                call["response"],
                hits,
                list(config.tools),
                config.expected_keywords,
                int(unresolved),
            )
            for result in results:
                await c.execute(
                    """INSERT INTO evaluations(tenant_id,id,task_id,evaluator,passed,details)
                       VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(tenant_id,task_id,evaluator) DO NOTHING""",
                    claim.tenant_id,
                    uuid4(),
                    claim.task_id,
                    result.evaluator,
                    result.passed,
                    result.details,
                )
            if not all(result.passed for result in results):
                await self._review_tx(c, claim, "evaluation failed")
                return
            artifact = uuid4()
            provenance = [
                {
                    "hit_id": str(hit["id"]),
                    "retrieval_step_id": str(hit["step_id"]),
                    "chunk_id": str(hit["chunk_id"]),
                    "document_id": str(hit["document_id"]),
                    "document_name": hit["document_name"],
                    "score": hit["score"],
                    "supports": hit["supports"],
                    "answer_span": (
                        {
                            "start": call["response"]["answer"].find(hit["content"][:240]),
                            "end": call["response"]["answer"].find(hit["content"][:240])
                            + len(hit["content"][:240]),
                        }
                        if hit["content"][:240] in call["response"]["answer"]
                        else None
                    ),
                }
                for hit in hits
                if str(hit["id"]) in call["response"]["citations"]
            ]
            content = {
                "answer": call["response"]["answer"],
                "model_step_id": str(call["step_id"]),
                "agent_version_id": str(task["agent_version_id"]),
                "provenance": provenance,
            }
            observations = await c.fetch(
                "SELECT id,content FROM artifacts WHERE tenant_id=$1 AND task_id=$2 AND media_type='application/vnd.synthetic.search+json'",
                claim.tenant_id,
                claim.task_id,
            )
            if observations:
                content["tool_observations"] = [
                    {"artifact_id": str(row["id"]), "observation": row["content"]}
                    for row in observations
                ]
            await c.execute(
                """INSERT INTO artifacts(tenant_id,id,task_id,media_type,content,content_hash)
                   VALUES($1,$2,$3,'application/json',$4,$5)""",
                claim.tenant_id,
                artifact,
                claim.task_id,
                content,
                fingerprint(content),
            )
            await self._complete_step(c, claim, artifact)
            await advance_task(c, claim.tenant_id, claim.task_id, TaskState.COMPLETED)
            await event(
                c, claim.tenant_id, claim.task_id, "task_completed", {"artifact_id": str(artifact)}
            )


async def main() -> None:
    from .telemetry import configure_logging

    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--task-id", type=UUID)
    args = parser.parse_args()
    executor = Executor(
        os.environ["ORCHESTRATOR_DSN"], reader_dsn=os.environ.get("PROVIDER_READ_DSN")
    )
    while True:
        worked = await executor.run_once(task_id=args.task_id)
        if args.once:
            return
        if not worked:
            await asyncio.sleep(0.1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except WorkerCrash:
        raise SystemExit(86) from None
