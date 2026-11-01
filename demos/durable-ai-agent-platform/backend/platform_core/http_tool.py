from typing import Any

from .errors import ProofMismatch
from .proof import EffectIdentity
from .tool_contracts import HTTPPayload


async def apply_http(
    c: Any, identity: EffectIdentity, payload: dict[str, object]
) -> dict[str, object]:
    data = HTTPPayload.model_validate(payload)
    await c.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended($1,2))",
        str(identity.tenant_id) + ":http:" + data.path,
    )
    previous = await c.fetchrow(
        "SELECT revision FROM http_resources WHERE tenant_id=$1 AND path=$2 FOR UPDATE",
        identity.tenant_id,
        data.path,
    )
    if data.method == "POST" and previous:
        raise ProofMismatch("synthetic resource already exists")
    row = await c.fetchrow(
        """INSERT INTO http_resources(tenant_id,path,body,intent_id) VALUES($1,$2,$3,$4)
           ON CONFLICT(tenant_id,path) DO UPDATE SET body=excluded.body,
           revision=http_resources.revision+1,intent_id=excluded.intent_id RETURNING revision""",
        identity.tenant_id,
        data.path,
        data.body,
        identity.intent_id,
    )
    return {
        "method": data.method,
        "path": data.path,
        "body": data.body,
        "status": 200 if previous else 201,
        "revision": row["revision"],
        "network": "synthetic provider only",
    }
