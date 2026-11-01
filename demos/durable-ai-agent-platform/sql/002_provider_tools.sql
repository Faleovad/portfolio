ALTER TABLE effects ADD COLUMN outcome jsonb NOT NULL DEFAULT '{}';
CREATE TABLE crm_entities (
 tenant_id uuid NOT NULL, entity_key text NOT NULL, name text NOT NULL,
 revision bigint NOT NULL DEFAULT 1, intent_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,entity_key),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES effects(tenant_id,intent_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE quota_accounts (
 tenant_id uuid NOT NULL, account text NOT NULL, balance bigint NOT NULL CHECK(balance>=0),
 revision bigint NOT NULL DEFAULT 1, intent_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,account),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES effects(tenant_id,intent_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE email_deliveries (
 tenant_id uuid NOT NULL, message_key text NOT NULL, recipient_id text NOT NULL,
 subject text NOT NULL, body text NOT NULL, intent_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,message_key), UNIQUE(tenant_id,intent_id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES effects(tenant_id,intent_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE http_resources (
 tenant_id uuid NOT NULL, path text NOT NULL, body text NOT NULL,
 revision bigint NOT NULL DEFAULT 1, intent_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,path),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES effects(tenant_id,intent_id) DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE search_catalog (id text PRIMARY KEY, content text NOT NULL);
INSERT INTO search_catalog VALUES
 ('refund','Refund policy: 30 days. Повернення: 30 днів. Возврат: 30 дней.'),
 ('quota','Synthetic quota is measured in integer units; it is not real money.'),
 ('privacy','Only synthetic fixtures are stored in this reference catalog.');
REVOKE ALL ON crm_entities,quota_accounts,email_deliveries,http_resources,search_catalog FROM PUBLIC;
