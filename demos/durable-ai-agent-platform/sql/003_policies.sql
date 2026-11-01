ALTER TABLE tasks ADD COLUMN token_limit bigint NOT NULL DEFAULT 16000 CHECK(token_limit>=0);
ALTER TABLE tasks ADD COLUMN token_used bigint NOT NULL DEFAULT 0 CHECK(token_used>=0);
ALTER TABLE tasks ADD COLUMN cost_limit bigint NOT NULL DEFAULT 2000000 CHECK(cost_limit>=0);
ALTER TABLE tasks ADD COLUMN cost_used bigint NOT NULL DEFAULT 0 CHECK(cost_used>=0);
ALTER TABLE tasks ADD CONSTRAINT estimated_budget_bounds CHECK(token_used<=token_limit AND cost_used<=cost_limit);
