from .database import transaction
from .proof import EffectIdentity, Observation, ObservationState


class ProviderReader:
    """Composition root supplies a PostgreSQL role with SELECT only on effects."""

    def __init__(self, read_dsn: str) -> None:
        self._dsn = read_dsn

    async def search(self, query: str) -> list[dict[str, object]]:
        if not query or len(query) > 1000:
            raise ValueError("invalid search query")
        async with transaction(self._dsn) as c:
            rows = await c.fetch(
                "SELECT id,content FROM search_catalog WHERE content ILIKE ANY($1::text[]) ORDER BY id LIMIT 5",
                ["%" + word + "%" for word in query.split()[:20]],
            )
        return [dict(row) for row in rows]

    async def observe(self, identity: EffectIdentity) -> Observation:
        async with transaction(self._dsn) as c:
            row = await c.fetchrow(
                "SELECT * FROM effects WHERE tenant_id=$1 AND intent_id=$2 AND visible_at <= now()",
                identity.tenant_id,
                identity.intent_id,
            )
        if row is None:
            return Observation(ObservationState.NOT_FOUND)
        actual = EffectIdentity(
            row["tenant_id"],
            row["intent_id"],
            row["external_identity"],
            row["payload_fingerprint"],
            row["idempotency_key"],
            row["tool"],
        )
        return Observation(ObservationState.COMMITTED, actual, row["provider_revision"])

    async def actual(self, tenant: object, intents: list[object]) -> dict[str, object]:
        async with transaction(self._dsn) as c:
            committed = await c.fetchval(
                "SELECT count(*) FROM effects WHERE tenant_id=$1 AND intent_id=ANY($2::uuid[])",
                tenant,
                intents,
            )
            attempts = await c.fetchval(
                "SELECT count(*) FROM provider_attempts WHERE tenant_id=$1 AND intent_id=ANY($2::uuid[])",
                tenant,
                intents,
            )
            effects = await c.fetch(
                "SELECT intent_id,tool,external_identity,outcome FROM effects WHERE tenant_id=$1 AND intent_id=ANY($2::uuid[]) ORDER BY provider_revision",
                tenant,
                intents,
            )
            state: dict[str, object] = {}
            for tool, table in [
                ("crm", "crm_entities"),
                ("quota", "quota_accounts"),
                ("email", "email_deliveries"),
                ("http", "http_resources"),
            ]:
                rows = await c.fetch(
                    "SELECT * FROM " + table + " WHERE tenant_id=$1 AND intent_id=ANY($2::uuid[])",
                    tenant,
                    intents,
                )
                state[tool] = [dict(row) for row in rows]
        return {
            "state": "COMMITTED" if committed else "NO_EFFECT",
            "mutations": committed,
            "dispatch_attempts": attempts,
            "effects": [dict(row) for row in effects],
            "domain_state": state,
            "scope": "Synthetic provider inspection; independent of recovery visibility",
        }
