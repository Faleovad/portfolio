import sqlite3
import time
from uuid import uuid4

from ..domain.errors import LabError
from ..domain.models import TaskState as T
from ..infrastructure.database import Database
from ..infrastructure.events import record


class Tasks:
    def __init__(self, db: Database, lease_seconds: int = 30) -> None:
        self.db = db
        self.lease_seconds = lease_seconds

    def enqueue(self, tx: sqlite3.Connection, order_id: str, kind: str, reason: str) -> None:
        tx.execute(
            "INSERT OR IGNORE INTO recovery_tasks(order_id,kind,state,reason) VALUES(?,?,?,?)",
            (order_id, kind, T.PENDING, reason),
        )
        record(tx, order_id, "recovery_queue", "task_enqueued", kind=kind, reason=reason)

    def claim(self, order_id: str) -> dict | None:
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM recovery_tasks WHERE order_id=? AND "
                "(state=? OR (state=? AND lease_until<?)) ORDER BY id LIMIT 1",
                (order_id, T.PENDING, T.LEASED, time.time()),
            ).fetchone()
            if row is None:
                return None
            owner = str(uuid4())
            tx.execute(
                "UPDATE recovery_tasks SET state=?,owner=?,lease_until=? WHERE id=?",
                (T.LEASED, owner, time.time() + self.lease_seconds, row["id"]),
            )
            return {**dict(row), "owner": owner}

    def finish(self, tx: sqlite3.Connection, task: dict, state: T) -> None:
        cursor = tx.execute(
            "UPDATE recovery_tasks SET state=?,attempts=attempts+1,owner=NULL,lease_until=0 "
            "WHERE id=? AND owner=? AND state=? AND lease_until>=?",
            (state, task["id"], task["owner"], T.LEASED, time.time()),
        )
        if cursor.rowcount != 1:
            raise LabError(
                "task_ownership_lost", "A stale worker cannot finish another owner's task"
            )
        record(tx, task["order_id"], "recovery_queue", "task_finished", task_state=state)
