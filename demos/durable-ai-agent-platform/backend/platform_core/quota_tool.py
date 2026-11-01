from typing import Any

from .errors import ProofMismatch
from .proof import EffectIdentity
from .tool_contracts import QuotaPayload


async def apply_quota(
    c: Any, identity: EffectIdentity, payload: dict[str, object]
) -> dict[str, object]:
    data = QuotaPayload.model_validate(payload)
    await c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1,2))",
        str(identity.tenant_id) + ":quota:" + data.account,
    )
    previous = await c.fetchrow(
        "SELECT balance,revision FROM quota_accounts WHERE tenant_id=$1 AND account=$2 FOR UPDATE",
        identity.tenant_id,
        data.account,
    )
    balance = (int(previous["balance"]) if previous else 0) + int(data.delta)
    if balance < 0:
        raise ProofMismatch("insufficient synthetic quota")
    row = await c.fetchrow(
        """INSERT INTO quota_accounts(tenant_id,account,balance,intent_id) VALUES($1,$2,$3,$4)
           ON CONFLICT(tenant_id,account) DO UPDATE SET balance=excluded.balance,
           revision=quota_accounts.revision+1,intent_id=excluded.intent_id RETURNING revision""",
        identity.tenant_id,
        data.account,
        balance,
        identity.intent_id,
    )
    return {
        "account": data.account,
        "delta": int(data.delta),
        "balance": balance,
        "revision": row["revision"],
        "unit": "synthetic integer quota; not real payment",
    }
