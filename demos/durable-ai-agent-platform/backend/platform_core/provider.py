from datetime import timedelta

from .crm_tool import apply_crm
from .database import transaction
from .email_tool import apply_email
from .errors import ProofMismatch
from .http_tool import apply_http
from .identity import fingerprint
from .proof import EffectIdentity, Observation, ObservationState
from .quota_tool import apply_quota
from .tool_contracts import TOOLS, validate_payload

APPLY = {"crm": apply_crm, "quota": apply_quota, "email": apply_email, "http": apply_http}


class ProviderResponseLost(Exception):
    pass


class ProviderWriter:
    """Synthetic side effects commit in a separate database transaction."""

    def __init__(self, write_dsn: str) -> None:
        self._dsn = write_dsn

    async def dispatch(
        self,
        identity: EffectIdentity,
        payload: dict[str, object],
        tool: str = "crm",
        response_lost: bool = False,
        timeout_before_commit: bool = False,
        visibility_delay: float = 0,
        error_before_commit: bool = False,
        error_after_commit: bool = False,
    ) -> Observation:
        if tool != identity.tool or tool not in TOOLS or TOOLS[tool].read_only:
            raise ProofMismatch("mutating port/tool identity mismatch")
        try:
            validate_payload(tool, payload)
        except ValueError as error:
            raise ProofMismatch(str(error)) from error
        if fingerprint(payload) != identity.payload_fingerprint:
            raise ProofMismatch("payload differs from persisted intent fingerprint")
        async with transaction(self._dsn) as c:
            await c.execute(
                "INSERT INTO provider_attempts(tenant_id,intent_id) VALUES($1,$2)",
                identity.tenant_id,
                identity.intent_id,
            )
            if timeout_before_commit or error_before_commit:
                # Attempt audit commits; no effects INSERT has been issued.
                row = None
            else:
                row = True
        if row is None:
            raise ProviderResponseLost(
                "synthetic error before commit"
                if error_before_commit
                else "timeout before synthetic provider commit"
            )
        async with transaction(self._dsn) as c:
            await c.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1,1))",
                str(identity.tenant_id) + ":" + identity.idempotency_key,
            )
            existing = await c.fetchrow(
                "SELECT * FROM effects WHERE tenant_id=$1 AND idempotency_key=$2",
                identity.tenant_id,
                identity.idempotency_key,
            )
            if existing:
                actual = EffectIdentity(
                    existing["tenant_id"],
                    existing["intent_id"],
                    existing["external_identity"],
                    existing["payload_fingerprint"],
                    existing["idempotency_key"],
                    existing["tool"],
                )
                if actual != identity or existing["payload"] != payload:
                    raise ProofMismatch("provider idempotency conflict")
                revision = existing["provider_revision"]
            else:
                outcome = await APPLY[tool](c, identity, payload)
                row = await c.fetchrow(
                    """INSERT INTO effects(tenant_id,intent_id,external_identity,payload_fingerprint,
                   idempotency_key,tool,payload,visible_at,outcome) VALUES($1,$2,$3,$4,$5,$6,$7,clock_timestamp()+$8::interval,$9)
                   RETURNING provider_revision""",
                    identity.tenant_id,
                    identity.intent_id,
                    identity.external_identity,
                    identity.payload_fingerprint,
                    identity.idempotency_key,
                    tool,
                    payload,
                    timedelta(seconds=visibility_delay),
                    outcome,
                )
                revision = row["provider_revision"]
        if response_lost or error_after_commit:
            raise ProviderResponseLost(
                "synthetic ambiguous error after commit"
                if error_after_commit
                else "provider committed; acknowledgement lost"
            )
        return Observation(ObservationState.COMMITTED, identity, revision)
