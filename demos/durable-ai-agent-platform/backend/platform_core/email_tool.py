from typing import Any

from .errors import ProofMismatch
from .proof import EffectIdentity
from .tool_contracts import EmailPayload


async def apply_email(
    c: Any, identity: EffectIdentity, payload: dict[str, object]
) -> dict[str, object]:
    data = EmailPayload.model_validate(payload)
    key = data.message_key or identity.external_identity
    row = await c.fetchrow(
        """INSERT INTO email_deliveries(tenant_id,message_key,recipient_id,subject,body,intent_id)
           VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(tenant_id,message_key) DO NOTHING RETURNING message_key""",
        identity.tenant_id,
        key,
        data.recipient_id,
        data.subject,
        data.body,
        identity.intent_id,
    )
    if row is None:
        raise ProofMismatch("message identity already delivered by a different intent")
    return {
        "message_key": key,
        "recipient_id": data.recipient_id,
        "state": "DELIVERED_TO_SYNTHETIC_INBOX",
        "transport": "database simulator; no SMTP",
    }
