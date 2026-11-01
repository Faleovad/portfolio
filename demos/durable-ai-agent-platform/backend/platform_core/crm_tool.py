from typing import Any

from .errors import ProofMismatch
from .proof import EffectIdentity
from .tool_contracts import CRMPayload


async def apply_crm(
    c: Any, identity: EffectIdentity, payload: dict[str, object]
) -> dict[str, object]:
    data = CRMPayload.model_validate(payload)
    key = data.entity_key or identity.external_identity
    await c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1,2))",
        str(identity.tenant_id) + ":crm:" + key,
    )
    previous = await c.fetchrow(
        "SELECT * FROM crm_entities WHERE tenant_id=$1 AND entity_key=$2 FOR UPDATE",
        identity.tenant_id,
        key,
    )
    if (data.operation == "create" and previous) or (data.operation == "update" and not previous):
        raise ProofMismatch("CRM create/update precondition rejected")
    row = await c.fetchrow(
        """INSERT INTO crm_entities(tenant_id,entity_key,name,intent_id) VALUES($1,$2,$3,$4)
           ON CONFLICT(tenant_id,entity_key) DO UPDATE SET name=excluded.name,
           revision=crm_entities.revision+1,intent_id=excluded.intent_id RETURNING revision""",
        identity.tenant_id,
        key,
        data.name,
        identity.intent_id,
    )
    return {
        "entity_key": key,
        "operation": data.operation,
        "name": data.name,
        "revision": row["revision"],
    }
