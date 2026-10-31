import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


def now() -> str:
    return datetime.now(UTC).isoformat()


def record(
    tx: sqlite3.Connection,
    order_id: str | None,
    component: str,
    event: str,
    state: str | None = None,
    **details: Any,
) -> None:
    tx.execute(
        "INSERT INTO events(order_id,component,event,state,timestamp,details) VALUES(?,?,?,?,?,?)",
        (order_id, component, event, state, now(), json.dumps(details, sort_keys=True)),
    )
