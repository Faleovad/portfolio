ALTER TABLE tasks ADD COLUMN request_fingerprint text;
CREATE UNIQUE INDEX retrieval_hit_identity ON retrieval_hits(tenant_id,step_id,chunk_id,query_hash);
CREATE UNIQUE INDEX final_artifact_identity ON artifacts(tenant_id,task_id,media_type);
CREATE UNIQUE INDEX evaluation_identity ON evaluations(tenant_id,task_id,evaluator);
