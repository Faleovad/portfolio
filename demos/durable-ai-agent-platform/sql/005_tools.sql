ALTER TABLE steps ADD COLUMN tool_name text NOT NULL DEFAULT 'crm'
 CHECK(tool_name IN ('search','crm','quota','email','http'));
CREATE OR REPLACE FUNCTION protect_intent() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'intent deletion prohibited'; END IF;
 IF NEW.payload_fingerprint <> OLD.payload_fingerprint OR NEW.payload <> OLD.payload
    OR NEW.idempotency_key <> OLD.idempotency_key OR NEW.tenant_id <> OLD.tenant_id
    OR NEW.external_identity <> OLD.external_identity OR NEW.tool <> OLD.tool
    OR NEW.id <> OLD.id OR NEW.task_id <> OLD.task_id OR NEW.step_id <> OLD.step_id THEN
   RAISE EXCEPTION 'effect identity immutable';
 END IF;
 IF OLD.state IN ('SENT','UNKNOWN','CONFIRMED','MANUAL_REVIEW','PROVEN_NOT_APPLIED')
    AND NEW.state = 'PREPARED' THEN RAISE EXCEPTION 'blind replay prohibited'; END IF;
 IF OLD.state = 'CONFIRMED' AND NEW.state <> OLD.state THEN
   RAISE EXCEPTION 'terminal receipt fence'; END IF;
 RETURN NEW;
END;
$$;
