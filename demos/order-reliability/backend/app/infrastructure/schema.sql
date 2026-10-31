PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY, external_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
    lines TEXT NOT NULL, components TEXT NOT NULL DEFAULT '[]',
    warehouse_id TEXT NOT NULL, crm_id TEXT, tracking TEXT NOT NULL,
    read_attempts INTEGER NOT NULL DEFAULT 0, scenario TEXT NOT NULL,
    error TEXT, version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS inventory (
    warehouse_id TEXT NOT NULL, sku TEXT NOT NULL,
    on_hand INTEGER NOT NULL CHECK(on_hand >= 0),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK(reserved >= 0 AND reserved <= on_hand),
    fulfilled INTEGER NOT NULL DEFAULT 0 CHECK(fulfilled >= 0),
    PRIMARY KEY (warehouse_id, sku)
);
CREATE TABLE IF NOT EXISTS reservations (
    order_id TEXT NOT NULL REFERENCES orders(id), warehouse_id TEXT NOT NULL,
    sku TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity > 0),
    state TEXT NOT NULL, PRIMARY KEY(order_id, warehouse_id, sku)
);
CREATE TABLE IF NOT EXISTS create_journal (
    external_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
    intent_id TEXT NOT NULL UNIQUE, fingerprint TEXT NOT NULL, state TEXT NOT NULL,
    created_at TEXT NOT NULL, crm_id TEXT, result TEXT
);
CREATE TABLE IF NOT EXISTS mutation_fences (
    resource_id TEXT NOT NULL, mutation_type TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(id), intent_id TEXT NOT NULL UNIQUE,
    state TEXT NOT NULL, owner TEXT, lease_until REAL NOT NULL,
    created_at TEXT NOT NULL, PRIMARY KEY(resource_id, mutation_type)
);
CREATE TABLE IF NOT EXISTS recovery_tasks (
    id INTEGER PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
    kind TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    owner TEXT, lease_until REAL NOT NULL DEFAULT 0, reason TEXT NOT NULL,
    UNIQUE(order_id, kind)
);
CREATE TABLE IF NOT EXISTS terminal_receipts (
    intent_id TEXT PRIMARY KEY, order_id TEXT NOT NULL REFERENCES orders(id),
    kind TEXT NOT NULL, proof TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT,
    component TEXT NOT NULL, event TEXT NOT NULL, state TEXT,
    timestamp TEXT NOT NULL, details TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fault_plans (
    point TEXT PRIMARY KEY, mode TEXT NOT NULL, remaining INTEGER NOT NULL,
    delay_reads INTEGER NOT NULL DEFAULT 0
);
