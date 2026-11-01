CREATE TABLE tenants (
 id uuid PRIMARY KEY, name text NOT NULL, auth_hash text NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE agents (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id uuid NOT NULL,
 name text NOT NULL, revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id)
);
CREATE TABLE agent_versions (
 tenant_id uuid NOT NULL, id uuid NOT NULL, agent_id uuid NOT NULL,
 version integer NOT NULL CHECK(version > 0), config jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,agent_id,version),
 FOREIGN KEY(tenant_id,agent_id) REFERENCES agents(tenant_id,id)
);
CREATE TABLE tasks (
 tenant_id uuid NOT NULL, id uuid NOT NULL, agent_version_id uuid NOT NULL,
 enqueue_key text NOT NULL, state text NOT NULL DEFAULT 'QUEUED',
 objective text NOT NULL, revision bigint NOT NULL DEFAULT 1,
 cancel_requested boolean NOT NULL DEFAULT false,
 model_limit integer NOT NULL DEFAULT 8 CHECK(model_limit >= 0),
 tool_limit integer NOT NULL DEFAULT 8 CHECK(tool_limit >= 0),
 step_limit integer NOT NULL DEFAULT 24 CHECK(step_limit >= 0),
 recovery_limit integer NOT NULL DEFAULT 12 CHECK(recovery_limit >= 0),
 model_used integer NOT NULL DEFAULT 0 CHECK(model_used >= 0),
 tool_used integer NOT NULL DEFAULT 0 CHECK(tool_used >= 0),
 step_used integer NOT NULL DEFAULT 0 CHECK(step_used >= 0),
 recovery_used integer NOT NULL DEFAULT 0 CHECK(recovery_used >= 0),
 deadline timestamptz NOT NULL DEFAULT (clock_timestamp() + interval '1 hour'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,enqueue_key),
 FOREIGN KEY(tenant_id,agent_version_id) REFERENCES agent_versions(tenant_id,id),
 CHECK(model_used <= model_limit AND tool_used <= tool_limit
       AND step_used <= step_limit AND recovery_used <= recovery_limit)
);
CREATE TABLE runs (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL,
 worker_id text NOT NULL, started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ended_at timestamptz, PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE TABLE steps (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL, run_id uuid,
 sequence integer NOT NULL CHECK(sequence >= 0), kind text NOT NULL,
 state text NOT NULL DEFAULT 'PENDING', attempt integer NOT NULL DEFAULT 0,
 input_fingerprint text NOT NULL, input jsonb NOT NULL,
 output_reference uuid, idempotency_key text NOT NULL,
 owner text, owner_token uuid, lease_until timestamptz,
 revision bigint NOT NULL DEFAULT 1, error_class text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,task_id,sequence),
 UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,run_id) REFERENCES runs(tenant_id,id)
);
CREATE INDEX steps_claim ON steps(state,lease_until,created_at);
CREATE TABLE model_calls (
 tenant_id uuid NOT NULL, id uuid NOT NULL, step_id uuid NOT NULL,
 attempt integer NOT NULL, provider text NOT NULL, state text NOT NULL,
 request_hash text NOT NULL, response jsonb, error_class text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,step_id,attempt),
 FOREIGN KEY(tenant_id,step_id) REFERENCES steps(tenant_id,id)
);
CREATE TABLE tool_intents (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL, step_id uuid NOT NULL,
 tool text NOT NULL, state text NOT NULL DEFAULT 'PREPARED',
 payload jsonb NOT NULL, payload_fingerprint text NOT NULL,
 external_identity text NOT NULL, idempotency_key text NOT NULL,
 owner_token uuid NOT NULL, revision bigint NOT NULL DEFAULT 1,
 sent_at timestamptz, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,step_id),
 UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,step_id) REFERENCES steps(tenant_id,id),
 CHECK(state IN ('PREPARED','SENT','UNKNOWN','CONFIRMED','PROVEN_NOT_APPLIED','MANUAL_REVIEW'))
);
CREATE TABLE tool_receipts (
 tenant_id uuid NOT NULL, id uuid NOT NULL, intent_id uuid NOT NULL,
 provider_revision bigint NOT NULL CHECK(provider_revision > 0),
 proof_hash text NOT NULL, identity jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES tool_intents(tenant_id,id)
);
CREATE TABLE recovery_tasks (
 tenant_id uuid NOT NULL, id uuid NOT NULL, intent_id uuid NOT NULL,
 state text NOT NULL DEFAULT 'PENDING', attempts integer NOT NULL DEFAULT 0,
 owner text, owner_token uuid, lease_until timestamptz,
 revision bigint NOT NULL DEFAULT 1, reason text, next_attempt_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES tool_intents(tenant_id,id)
);
CREATE INDEX recovery_claim ON recovery_tasks(state,next_attempt_at,lease_until);
CREATE TABLE documents (
 tenant_id uuid NOT NULL REFERENCES tenants(id), id uuid NOT NULL,
 name text NOT NULL, media_type text NOT NULL, content_hash text NOT NULL,
 content text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,content_hash)
);
CREATE TABLE chunks (
 tenant_id uuid NOT NULL, id uuid NOT NULL, document_id uuid NOT NULL,
 ordinal integer NOT NULL CHECK(ordinal >= 0), content text NOT NULL,
 embedding double precision[] NOT NULL,
 PRIMARY KEY(tenant_id,id), UNIQUE(tenant_id,document_id,ordinal),
 FOREIGN KEY(tenant_id,document_id) REFERENCES documents(tenant_id,id)
);
CREATE TABLE retrieval_hits (
 tenant_id uuid NOT NULL, id uuid NOT NULL, step_id uuid NOT NULL, chunk_id uuid NOT NULL,
 score double precision NOT NULL, query_hash text NOT NULL, supports text NOT NULL,
 PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,step_id) REFERENCES steps(tenant_id,id),
 FOREIGN KEY(tenant_id,chunk_id) REFERENCES chunks(tenant_id,id)
);
CREATE TABLE artifacts (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL,
 media_type text NOT NULL, content jsonb NOT NULL, content_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE TABLE evaluations (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL,
 evaluator text NOT NULL, passed boolean NOT NULL, details jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE TABLE events (
 ordinal bigint GENERATED ALWAYS AS IDENTITY,
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL,
 kind text NOT NULL, details jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,id), UNIQUE(ordinal),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE INDEX events_timeline ON events(tenant_id,task_id,ordinal);
CREATE TABLE fault_plans (
 tenant_id uuid NOT NULL, id uuid NOT NULL, task_id uuid NOT NULL,
 boundary text NOT NULL, mode text NOT NULL, remaining integer NOT NULL CHECK(remaining >= 0),
 parameters jsonb NOT NULL DEFAULT '{}', PRIMARY KEY(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id)
);
CREATE INDEX faults_active ON fault_plans(tenant_id,task_id,boundary) WHERE remaining > 0;

CREATE FUNCTION reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable/append-only record'; END;
$$;
CREATE TRIGGER version_immutable BEFORE UPDATE OR DELETE ON agent_versions
 FOR EACH ROW EXECUTE FUNCTION reject_change();
CREATE TRIGGER receipt_immutable BEFORE UPDATE OR DELETE ON tool_receipts
 FOR EACH ROW EXECUTE FUNCTION reject_change();
CREATE TRIGGER event_append_only BEFORE UPDATE OR DELETE ON events
 FOR EACH ROW EXECUTE FUNCTION reject_change();

CREATE FUNCTION protect_intent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'intent deletion prohibited'; END IF;
 IF NEW.payload_fingerprint <> OLD.payload_fingerprint OR NEW.payload <> OLD.payload
    OR NEW.idempotency_key <> OLD.idempotency_key OR NEW.tenant_id <> OLD.tenant_id
    OR NEW.external_identity <> OLD.external_identity THEN
   RAISE EXCEPTION 'effect identity immutable';
 END IF;
 IF OLD.state IN ('SENT','UNKNOWN','CONFIRMED','MANUAL_REVIEW','PROVEN_NOT_APPLIED')
    AND NEW.state = 'PREPARED' THEN RAISE EXCEPTION 'blind replay prohibited'; END IF;
 IF OLD.state = 'CONFIRMED' AND NEW.state <> OLD.state THEN
   RAISE EXCEPTION 'terminal receipt fence'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER intent_fence BEFORE UPDATE OR DELETE ON tool_intents
 FOR EACH ROW EXECUTE FUNCTION protect_intent();
