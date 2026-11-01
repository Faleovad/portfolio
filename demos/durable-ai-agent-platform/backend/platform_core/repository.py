from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from .database import event, transaction
from .errors import BudgetExceeded, OwnershipLost, ReplayForbidden, TenantDenied
from .identity import fingerprint, idempotency_identity
from .policy import reserve
from .proof import EffectIdentity, Receipt
from .state import (
    IntentState,
    StepState,
    TaskState,
    intent_transition,
    step_transition,
    task_transition,
)
from .tool_contracts import TOOLS, ToolName, validate_payload


@dataclass(frozen=True)
class Claim:
    tenant_id: UUID
    task_id: UUID
    step_id: UUID
    run_id: UUID
    token: UUID
    revision: int
    worker: str


async def advance_task(c: Any, tenant: UUID, task: UUID, target: TaskState) -> None:
    source = await c.fetchval(
        "SELECT state FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
        tenant,
        task,
    )
    if source is None:
        raise TenantDenied("task unavailable")
    if source != target.value:
        task_transition(TaskState(source), target)
        await c.execute(
            "UPDATE tasks SET state=$3,revision=revision+1 WHERE tenant_id=$1 AND id=$2",
            tenant,
            task,
            target.value,
        )
        await event(c, tenant, task, "state_transition", {"from": source, "to": target.value})


def effect(row: Any) -> EffectIdentity:
    return EffectIdentity(
        row["tenant_id"],
        row["id"],
        row["external_identity"],
        row["payload_fingerprint"],
        row["idempotency_key"],
        row["tool"],
    )


async def transport_state(c: Any, tenant: UUID, task: UUID, target: TaskState) -> None:
    cancel = await c.fetchval(
        "SELECT cancel_requested FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
        tenant,
        task,
    )
    await advance_task(c, tenant, task, TaskState.CANCEL_REQUESTED if cancel else target)


async def check_claim(c: Any, claim: Claim) -> Any:
    row = await c.fetchrow(
        """SELECT *, lease_until > clock_timestamp() AS live FROM steps
           WHERE tenant_id=$1 AND id=$2 FOR UPDATE""",
        claim.tenant_id,
        claim.step_id,
    )
    if (
        not row
        or not row["live"]
        or row["owner_token"] != claim.token
        or row["revision"] != claim.revision
    ):
        raise OwnershipLost("stale worker cannot persist")
    return row


class Repository:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    async def seed_task(
        self,
        tenant: UUID,
        key: str,
        payload: dict[str, object],
        lab_controlled: bool = False,
        tool: ToolName = "crm",
    ) -> UUID:
        """Synthetic provisioning; service/API auth is a subsequent boundary."""
        async with transaction(self.dsn) as c:
            await c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1,0))",
                str(tenant) + ":" + key,
            )
            await c.execute(
                "INSERT INTO tenants(id,name,auth_hash) VALUES($1,'Synthetic tenant',$2) ON CONFLICT DO NOTHING",
                tenant,
                fingerprint({"tenant": str(tenant)}),
            )
            previous = await c.fetchval(
                "SELECT id FROM tasks WHERE tenant_id=$1 AND enqueue_key=$2",
                tenant,
                key,
            )
            if previous:
                stored = await c.fetchrow(
                    "SELECT input_fingerprint,tool_name FROM steps WHERE tenant_id=$1 AND task_id=$2 AND sequence=0",
                    tenant,
                    previous,
                )
                if (
                    stored["input_fingerprint"] != fingerprint(payload)
                    or stored["tool_name"] != tool
                ):
                    raise ReplayForbidden("enqueue key reused with different payload")
                return UUID(str(previous))
            agent, version, task, step = uuid4(), uuid4(), uuid4(), uuid4()
            await c.execute(
                "INSERT INTO agents(tenant_id,id,name) VALUES($1,$2,'Reference agent')",
                tenant,
                agent,
            )
            await c.execute(
                "INSERT INTO agent_versions(tenant_id,id,agent_id,version,config) VALUES($1,$2,$3,1,$4)",
                tenant,
                version,
                agent,
                {"tools": [tool], "model": "deterministic"},
            )
            await c.execute(
                """INSERT INTO tasks(tenant_id,id,agent_version_id,enqueue_key,objective)
                   VALUES($1,$2,$3,$4,$5)""",
                tenant,
                task,
                version,
                key,
                "Execute one synthetic " + tool + " operation",
            )
            await c.execute(
                "UPDATE tasks SET lab_controlled=$3 WHERE tenant_id=$1 AND id=$2",
                tenant,
                task,
                lab_controlled,
            )
            await c.execute(
                """INSERT INTO steps(tenant_id,id,task_id,sequence,kind,input_fingerprint,input,idempotency_key)
                   VALUES($1,$2,$3,0,$7,$4,$5,$6)""",
                tenant,
                step,
                task,
                fingerprint(payload),
                payload,
                idempotency_identity(tenant, task, 0),
                "search" if TOOLS[tool].read_only else "tool",
            )
            await c.execute(
                "UPDATE steps SET tool_name=$3 WHERE tenant_id=$1 AND id=$2", tenant, step, tool
            )
            await event(c, tenant, task, "task_created", {})
            await advance_task(c, tenant, task, TaskState.QUEUED)
            return task

    async def task(self, tenant: UUID, task_id: UUID) -> dict[str, Any]:
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2", tenant, task_id
            )
            if not row:
                raise TenantDenied("resource unavailable")
            return dict(row)

    async def claim(
        self,
        worker: str,
        lease_seconds: float = 30,
        kinds: tuple[str, ...] = ("tool",),
        task_id: UUID | None = None,
    ) -> Claim | None:
        if lease_seconds <= 0:
            raise ValueError("positive lease required")
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                """SELECT s.* FROM steps s JOIN tasks t ON t.tenant_id=s.tenant_id AND t.id=s.task_id
                     WHERE s.state IN ('PENDING','RUNNING','CLAIMED','FAILED_RETRYABLE')
                     AND s.kind = ANY($1::text[])
                     AND ($2::uuid IS NULL OR t.id=$2)
                     AND (NOT t.lab_controlled OR $2::uuid IS NOT NULL)
                     AND NOT EXISTS(SELECT 1 FROM steps previous
                         WHERE previous.tenant_id=s.tenant_id AND previous.task_id=s.task_id
                         AND previous.sequence<s.sequence AND previous.state<>'COMPLETED')
                     AND (s.lease_until IS NULL OR s.lease_until <= clock_timestamp())
                     AND t.state IN ('QUEUED','RUNNING','FAILED_RETRYABLE','WAITING_MODEL')
                     AND NOT EXISTS(SELECT 1 FROM tool_intents i WHERE i.tenant_id=s.tenant_id
                                    AND i.step_id=s.id AND i.state <> 'PREPARED')
                   ORDER BY s.created_at FOR UPDATE OF s SKIP LOCKED LIMIT 1""",
                list(kinds),
                task_id,
            )
            if not row:
                return None
            tenant, task, step = row["tenant_id"], row["task_id"], row["id"]
            token, run = uuid4(), uuid4()
            await c.execute(
                "INSERT INTO runs(tenant_id,id,task_id,worker_id) VALUES($1,$2,$3,$4)",
                tenant,
                run,
                task,
                worker,
            )
            source_step = StepState(row["state"])
            if source_step in {StepState.PENDING, StepState.FAILED_RETRYABLE}:
                step_transition(source_step, StepState.CLAIMED)
                step_transition(StepState.CLAIMED, StepState.RUNNING)
            elif source_step == StepState.CLAIMED:
                step_transition(source_step, StepState.RUNNING)
            # Reclaiming an expired RUNNING lease transfers ownership, not execution state.
            current = await c.fetchrow(
                """UPDATE steps SET state='RUNNING',attempt=attempt+1,owner=$3,owner_token=$4,
                   lease_until=clock_timestamp()+$5::interval,revision=revision+1,run_id=$6
                   WHERE tenant_id=$1 AND id=$2 RETURNING revision""",
                tenant,
                step,
                worker,
                token,
                timedelta(seconds=lease_seconds),
                run,
            )
            task_state = await c.fetchval(
                "SELECT state FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE", tenant, task
            )
            if task_state == "FAILED_RETRYABLE":
                await advance_task(c, tenant, task, TaskState.QUEUED)
                task_state = "QUEUED"
            if task_state != "RUNNING":
                task_transition(TaskState(task_state), TaskState.RUNNING)
            await c.execute(
                "UPDATE tasks SET state='RUNNING',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                tenant,
                task,
            )
            if task_state != "RUNNING":
                await event(
                    c, tenant, task, "state_transition", {"from": task_state, "to": "RUNNING"}
                )
            if not await reserve(c, tenant, task, {"steps": 1}):
                return None
            await event(
                c,
                tenant,
                task,
                "worker_claimed",
                {"worker_id": worker, "step_id": str(step), "run_id": str(run)},
            )
            return Claim(tenant, task, step, run, token, current["revision"], worker)

    async def heartbeat(self, claim: Claim, seconds: float = 30) -> None:
        if seconds <= 0:
            raise ValueError("positive lease required")
        async with transaction(self.dsn) as c:
            await check_claim(c, claim)
            await c.execute(
                "UPDATE steps SET lease_until=clock_timestamp()+$3::interval WHERE tenant_id=$1 AND id=$2",
                claim.tenant_id,
                claim.step_id,
                timedelta(seconds=seconds),
            )

    async def exhaust_before_dispatch(self, claim: Claim, dimension: str) -> None:
        async with transaction(self.dsn) as c:
            row = await check_claim(c, claim)
            unresolved = await c.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tool_intents WHERE tenant_id=$1 AND step_id=$2 AND state<>'PREPARED')",
                claim.tenant_id,
                claim.step_id,
            )
            if unresolved:
                raise ReplayForbidden("budget terminalization cannot erase an unresolved effect")
            await advance_task(c, claim.tenant_id, claim.task_id, TaskState.BUDGET_EXHAUSTED)
            step_transition(StepState(row["state"]), StepState.FAILED_TERMINAL)
            await c.execute(
                "UPDATE steps SET state='FAILED_TERMINAL',revision=revision+1,error_class=$3 WHERE tenant_id=$1 AND id=$2",
                claim.tenant_id,
                claim.step_id,
                dimension,
            )
            await event(
                c, claim.tenant_id, claim.task_id, "budget_exhausted", {"dimension": dimension}
            )

    async def prepare(self, claim: Claim) -> tuple[EffectIdentity, dict[str, object]]:
        async with transaction(self.dsn) as c:
            step = await check_claim(c, claim)
            task = await c.fetchrow(
                """SELECT t.*,v.config FROM tasks t JOIN agent_versions v
                   ON v.tenant_id=t.tenant_id AND v.id=t.agent_version_id
                   WHERE t.tenant_id=$1 AND t.id=$2 FOR UPDATE OF t""",
                claim.tenant_id,
                claim.task_id,
            )
            if task["cancel_requested"]:
                raise ReplayForbidden("cancel requested before mutation")
            tool = step["tool_name"]
            if tool not in task["config"].get("tools", []) or TOOLS[tool].read_only:
                raise ReplayForbidden("tool not in pinned version allowlist")
            try:
                validate_payload(tool, dict(step["input"]))
            except ValueError as error:
                raise ReplayForbidden(str(error)) from error
            row = await c.fetchrow(
                "SELECT * FROM tool_intents WHERE tenant_id=$1 AND step_id=$2 FOR UPDATE",
                claim.tenant_id,
                claim.step_id,
            )
            if row:
                if row["state"] != "PREPARED":
                    raise ReplayForbidden("sent/unknown/terminal intent cannot dispatch")
                return effect(row), dict(row["payload"])
            intent = uuid4()
            row = await c.fetchrow(
                """INSERT INTO tool_intents(tenant_id,id,task_id,step_id,tool,payload,payload_fingerprint,
                   external_identity,idempotency_key,owner_token)
                   VALUES($1,$2,$3,$4,$10,$5,$6,$7,$8,$9) RETURNING *""",
                claim.tenant_id,
                intent,
                claim.task_id,
                claim.step_id,
                step["input"],
                step["input_fingerprint"],
                "synthetic-" + tool + ":" + str(intent),
                step["idempotency_key"],
                claim.token,
                tool,
            )
            await event(
                c,
                claim.tenant_id,
                claim.task_id,
                "tool_intent_prepared",
                {"intent_id": str(intent)},
            )
            return effect(row), dict(row["payload"])

    async def sent(self, claim: Claim, identity: EffectIdentity) -> None:
        async with transaction(self.dsn) as c:
            step = await check_claim(c, claim)
            step_transition(StepState(step["state"]), StepState.WAITING)
            task = await c.fetchrow(
                "SELECT * FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                claim.tenant_id,
                claim.task_id,
            )
            if task["cancel_requested"]:
                raise ReplayForbidden("cancel before dispatch")
            if task["tool_used"] >= task["tool_limit"]:
                raise BudgetExceeded("tool_calls")
            if task["deadline"] <= await c.fetchval("SELECT clock_timestamp()"):
                raise BudgetExceeded("logical_duration")
            intent_transition(IntentState.PREPARED, IntentState.SENT)
            result = await c.execute(
                """UPDATE tool_intents SET state='SENT',sent_at=clock_timestamp(),revision=revision+1,
                   owner_token=$3 WHERE tenant_id=$1 AND id=$2 AND state='PREPARED'""",
                claim.tenant_id,
                identity.intent_id,
                claim.token,
            )
            if result != "UPDATE 1":
                raise ReplayForbidden("intent dispatch fence")
            task_transition(TaskState(task["state"]), TaskState.WAITING_TOOL)
            await c.execute(
                "UPDATE tasks SET state='WAITING_TOOL',tool_used=tool_used+1 WHERE tenant_id=$1 AND id=$2",
                claim.tenant_id,
                claim.task_id,
            )
            await c.execute(
                "UPDATE steps SET state='WAITING' WHERE tenant_id=$1 AND id=$2",
                claim.tenant_id,
                claim.step_id,
            )
            await event(
                c,
                claim.tenant_id,
                claim.task_id,
                "tool_dispatched",
                {"intent_id": str(identity.intent_id)},
            )
            await event(
                c,
                claim.tenant_id,
                claim.task_id,
                "state_transition",
                {"from": task["state"], "to": "WAITING_TOOL"},
            )

    async def schedule_readback(self, claim: Claim, identity: EffectIdentity) -> None:
        async with transaction(self.dsn) as c:
            await check_claim(c, claim)
            row = await c.fetchrow(
                "SELECT * FROM tool_intents WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                claim.tenant_id,
                identity.intent_id,
            )
            if row is None or row["state"] != "SENT" or effect(row) != identity:
                raise ReplayForbidden("readback requires the sent intent")
            await transport_state(c, claim.tenant_id, claim.task_id, TaskState.WAITING_READBACK)
            await c.execute(
                "INSERT INTO recovery_tasks(tenant_id,id,intent_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                claim.tenant_id,
                uuid4(),
                identity.intent_id,
            )
            await event(c, claim.tenant_id, claim.task_id, "readback_scheduled", {})

    async def unknown(self, claim: Claim, identity: EffectIdentity) -> None:
        async with transaction(self.dsn) as c:
            await check_claim(c, claim)
            intent_transition(IntentState.SENT, IntentState.UNKNOWN)
            changed = await c.execute(
                "UPDATE tool_intents SET state='UNKNOWN',revision=revision+1 WHERE tenant_id=$1 AND id=$2 AND state='SENT'",
                claim.tenant_id,
                identity.intent_id,
            )
            if changed != "UPDATE 1":
                raise ReplayForbidden("outcome already finalized")
            await transport_state(c, claim.tenant_id, claim.task_id, TaskState.UNKNOWN)
            await c.execute(
                "INSERT INTO recovery_tasks(tenant_id,id,intent_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                claim.tenant_id,
                uuid4(),
                identity.intent_id,
            )
            await event(
                c,
                claim.tenant_id,
                claim.task_id,
                "state_unknown",
                {"intent_id": str(identity.intent_id)},
            )

    async def rescue_expired_sent(self, task_id: UUID | None = None) -> int:
        """A dispatcher may die after SENT, before recording any outcome."""
        async with transaction(self.dsn) as c:
            rows = await c.fetch(
                """SELECT i.* FROM tool_intents i JOIN steps s
                   ON s.tenant_id=i.tenant_id AND s.id=i.step_id
                   WHERE i.state='SENT' AND s.lease_until <= clock_timestamp()
                   AND ($1::uuid IS NULL OR i.task_id=$1)
                   FOR UPDATE OF i SKIP LOCKED""",
                task_id,
            )
            for row in rows:
                await c.execute(
                    "UPDATE tool_intents SET state='UNKNOWN',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                    row["tenant_id"],
                    row["id"],
                )
                await transport_state(c, row["tenant_id"], row["task_id"], TaskState.UNKNOWN)
                await c.execute(
                    "INSERT INTO recovery_tasks(tenant_id,id,intent_id) VALUES($1,$2,$3) ON CONFLICT DO NOTHING",
                    row["tenant_id"],
                    uuid4(),
                    row["id"],
                )
                await event(
                    c,
                    row["tenant_id"],
                    row["task_id"],
                    "expired_sent_quarantined",
                    {"intent_id": str(row["id"])},
                )
            return len(rows)

    async def claim_recovery(
        self,
        worker: str,
        seconds: float = 30,
        tenant: UUID | None = None,
        recovery_id: UUID | None = None,
    ) -> "SQLRecovery | None":
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                """SELECT r.* FROM recovery_tasks r WHERE
                   ((r.state IN ('PENDING','WAITING') AND r.next_attempt_at <= clock_timestamp())
                    OR (r.state='CLAIMED' AND r.lease_until <= clock_timestamp()))
                   AND ($1::uuid IS NULL OR r.tenant_id=$1)
                   AND ($2::uuid IS NULL OR r.id=$2)
                   AND EXISTS(SELECT 1 FROM tool_intents i JOIN tasks t ON t.tenant_id=i.tenant_id AND t.id=i.task_id
                       WHERE i.tenant_id=r.tenant_id AND i.id=r.intent_id AND t.state NOT IN ('BUDGET_EXHAUSTED','CANCELLED','COMPLETED')
                       AND (NOT t.lab_controlled OR $2::uuid IS NOT NULL))
                   ORDER BY r.created_at FOR UPDATE SKIP LOCKED LIMIT 1""",
                tenant,
                recovery_id,
            )
            if not row:
                return None
            token = uuid4()
            revision = await c.fetchval(
                """UPDATE recovery_tasks SET state='CLAIMED',owner=$3,owner_token=$4,
                   lease_until=clock_timestamp()+$5::interval,revision=revision+1
                   WHERE tenant_id=$1 AND id=$2 RETURNING revision""",
                row["tenant_id"],
                row["id"],
                worker,
                token,
                timedelta(seconds=seconds),
            )
            intent = await c.fetchrow(
                "SELECT * FROM tool_intents WHERE tenant_id=$1 AND id=$2",
                row["tenant_id"],
                row["intent_id"],
            )
            await advance_task(c, row["tenant_id"], intent["task_id"], TaskState.RECOVERING)
            await event(
                c, row["tenant_id"], intent["task_id"], "recovery_claimed", {"worker_id": worker}
            )
            return SQLRecovery(self.dsn, row["id"], token, revision, effect(intent))


class SQLRecovery:
    def __init__(
        self, dsn: str, recovery_id: UUID, token: UUID, revision: int, identity: EffectIdentity
    ) -> None:
        self.dsn, self.recovery_id, self.token, self.revision, self.identity = (
            dsn,
            recovery_id,
            token,
            revision,
            identity,
        )

    async def _lock(self, c: Any, identity: EffectIdentity) -> Any:
        if identity != self.identity:
            raise TenantDenied("recovery identity unavailable")
        row = await c.fetchrow(
            """SELECT *,lease_until > clock_timestamp() AS live FROM recovery_tasks
               WHERE tenant_id=$1 AND id=$2 FOR UPDATE""",
            identity.tenant_id,
            self.recovery_id,
        )
        if (
            not row
            or not row["live"]
            or row["owner_token"] != self.token
            or row["revision"] != self.revision
            or row["state"] != "CLAIMED"
        ):
            raise OwnershipLost("recovery ownership lost")
        return row

    async def receipt(self, identity: EffectIdentity) -> Receipt | None:
        if identity != self.identity:
            raise TenantDenied("receipt unavailable")
        async with transaction(self.dsn) as c:
            row = await c.fetchrow(
                "SELECT * FROM tool_receipts WHERE tenant_id=$1 AND intent_id=$2",
                identity.tenant_id,
                identity.intent_id,
            )
            if not row:
                return None
            return Receipt(identity, row["provider_revision"], row["proof_hash"])

    async def record_attempt(self, identity: EffectIdentity) -> int:
        async with transaction(self.dsn) as c:
            row = await self._lock(c, identity)
            task = await c.fetchrow(
                """SELECT t.* FROM tasks t JOIN tool_intents i
                   ON i.tenant_id=t.tenant_id AND i.task_id=t.id
                   WHERE i.tenant_id=$1 AND i.id=$2 FOR UPDATE OF t""",
                identity.tenant_id,
                identity.intent_id,
            )
            if task["recovery_used"] >= task["recovery_limit"]:
                raise BudgetExceeded("recovery_attempts")
            if task["deadline"] <= await c.fetchval("SELECT clock_timestamp()"):
                raise BudgetExceeded("logical_duration")
            await c.execute(
                "UPDATE tasks SET recovery_used=recovery_used+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                task["id"],
            )
            await c.execute(
                "UPDATE recovery_tasks SET attempts=attempts+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                self.recovery_id,
            )
            return int(row["attempts"]) + 1

    async def confirm(self, identity: EffectIdentity, receipt: Receipt) -> None:
        if identity != receipt.identity:
            raise ReplayForbidden("receipt does not match effect")
        async with transaction(self.dsn) as c:
            await self._lock(c, identity)
            intent = await c.fetchrow(
                "SELECT * FROM tool_intents WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                identity.tenant_id,
                identity.intent_id,
            )
            if effect(intent) != identity:
                raise ReplayForbidden("persisted effect identity mismatch")
            intent_transition(IntentState(intent["state"]), IntentState.CONFIRMED)
            encoded = {key: str(value) for key, value in asdict(identity).items()}
            await c.execute(
                """INSERT INTO tool_receipts(tenant_id,id,intent_id,provider_revision,proof_hash,identity)
                   VALUES($1,$2,$3,$4,$5,$6)""",
                identity.tenant_id,
                uuid4(),
                identity.intent_id,
                receipt.provider_revision,
                receipt.observation_fingerprint,
                encoded,
            )
            await c.execute(
                "UPDATE tool_intents SET state='CONFIRMED',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                identity.intent_id,
            )
            step_state = await c.fetchval(
                "SELECT state FROM steps WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                identity.tenant_id,
                intent["step_id"],
            )
            step_transition(StepState(step_state), StepState.COMPLETED)
            await c.execute(
                "UPDATE steps SET state='COMPLETED',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                intent["step_id"],
            )
            remaining = await c.fetchval(
                "SELECT count(*) FROM steps WHERE tenant_id=$1 AND task_id=$2 AND state<>'COMPLETED'",
                identity.tenant_id,
                intent["task_id"],
            )
            cancelled = await c.fetchval(
                "SELECT cancel_requested FROM tasks WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                identity.tenant_id,
                intent["task_id"],
            )
            state = "CANCELLED" if cancelled else "COMPLETED"
            intermediate = TaskState.CANCEL_REQUESTED if cancelled else TaskState.RUNNING
            await advance_task(c, identity.tenant_id, intent["task_id"], intermediate)
            if cancelled or remaining == 0:
                await advance_task(c, identity.tenant_id, intent["task_id"], TaskState(state))
            if cancelled:
                await c.execute(
                    "UPDATE steps SET state='CANCELLED',revision=revision+1 WHERE tenant_id=$1 AND task_id=$2 AND state NOT IN ('COMPLETED','CANCELLED')",
                    identity.tenant_id,
                    intent["task_id"],
                )
            await c.execute(
                "UPDATE recovery_tasks SET state='CONFIRMED',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                self.recovery_id,
            )
            await event(
                c,
                identity.tenant_id,
                intent["task_id"],
                "effect_confirmed",
                {"intent_id": str(identity.intent_id)},
            )
            kind = "task_" + state.lower() if cancelled or remaining == 0 else "step_completed"
            await event(c, identity.tenant_id, intent["task_id"], kind, {})

    async def defer(self, identity: EffectIdentity, reason: str) -> None:
        async with transaction(self.dsn) as c:
            await self._lock(c, identity)
            await c.execute(
                """UPDATE recovery_tasks SET state='WAITING',reason=$3,
                   next_attempt_at=clock_timestamp()+interval '0.1 seconds',revision=revision+1
                   WHERE tenant_id=$1 AND id=$2""",
                identity.tenant_id,
                self.recovery_id,
                reason,
            )
            task = await c.fetchval(
                "SELECT task_id FROM tool_intents WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                identity.intent_id,
            )
            await transport_state(c, identity.tenant_id, task, TaskState.UNKNOWN)

    async def review(self, identity: EffectIdentity, reason: str) -> None:
        async with transaction(self.dsn) as c:
            await self._lock(c, identity)
            await c.execute(
                "UPDATE recovery_tasks SET state='MANUAL_REVIEW',reason=$3,revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                self.recovery_id,
                reason,
            )
            intent = await c.fetchrow(
                "SELECT state FROM tool_intents WHERE tenant_id=$1 AND id=$2 FOR UPDATE",
                identity.tenant_id,
                identity.intent_id,
            )
            source = IntentState(intent["state"])
            if source == IntentState.SENT:
                intent_transition(source, IntentState.UNKNOWN)
                source = IntentState.UNKNOWN
            if source != IntentState.MANUAL_REVIEW:
                intent_transition(source, IntentState.MANUAL_REVIEW)
            await c.execute(
                "UPDATE tool_intents SET state='MANUAL_REVIEW',revision=revision+1 WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                identity.intent_id,
            )
            task = await c.fetchval(
                "SELECT task_id FROM tool_intents WHERE tenant_id=$1 AND id=$2",
                identity.tenant_id,
                identity.intent_id,
            )
            if reason.startswith("recovery budget exhausted"):
                from .policy import exhaust

                await exhaust(c, identity.tenant_id, task, "recovery_attempts_or_duration")
            else:
                await advance_task(c, identity.tenant_id, task, TaskState.MANUAL_REVIEW)
            await event(c, identity.tenant_id, task, "manual_review", {"reason": reason})
