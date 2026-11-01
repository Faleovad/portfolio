CREATE TABLE effects (
 tenant_id uuid NOT NULL, intent_id uuid NOT NULL, external_identity text NOT NULL,
 payload_fingerprint text NOT NULL, idempotency_key text NOT NULL,
 tool text NOT NULL, payload jsonb NOT NULL,
 provider_revision bigint GENERATED ALWAYS AS IDENTITY,
 visible_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,intent_id), UNIQUE(tenant_id,idempotency_key)
);
CREATE TABLE provider_attempts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL, intent_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON effects,provider_attempts FROM PUBLIC;
