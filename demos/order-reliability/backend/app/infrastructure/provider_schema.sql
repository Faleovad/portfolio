CREATE TABLE IF NOT EXISTS crm_orders (
    id TEXT PRIMARY KEY, external_id TEXT NOT NULL, warehouse_id TEXT NOT NULL,
    lines TEXT NOT NULL, status TEXT NOT NULL, tracking TEXT,
    stock_status TEXT NOT NULL, intent_id TEXT NOT NULL,
    previous_view TEXT, hidden_reads INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS crm_inventory (
    warehouse_id TEXT NOT NULL, sku TEXT NOT NULL, on_hand INTEGER NOT NULL,
    reserved INTEGER NOT NULL, fulfilled INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(warehouse_id, sku),
    CHECK(on_hand >= 0 AND reserved >= 0 AND reserved <= on_hand)
);
CREATE TABLE IF NOT EXISTS crm_calls (
    id INTEGER PRIMARY KEY, operation TEXT NOT NULL, external_id TEXT NOT NULL,
    intent_id TEXT NOT NULL, committed INTEGER NOT NULL DEFAULT 0
);
