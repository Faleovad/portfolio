import json
import sqlite3

from ..domain.errors import LabError
from ..domain.models import OrderState
from ..domain.transitions import require_transition
from .database import Database
from .events import record


def decode_order(row: sqlite3.Row | dict) -> dict:
    result = dict(row)
    for key in ("lines", "components"):
        result[key] = json.loads(result[key])
    return result


class Orders:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get(self, order_id: str, tx: sqlite3.Connection | None = None) -> dict:
        if tx is None:
            with self.db.transaction() as connection:
                return self.get(order_id, connection)
        row = tx.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise LabError("order_not_found", "Synthetic order not found", 404)
        return decode_order(row)

    def move(
        self,
        order_id: str,
        target: OrderState,
        component: str,
        tx: sqlite3.Connection | None = None,
        **changes: object,
    ) -> None:
        if tx is None:
            with self.db.transaction() as connection:
                self.move(order_id, target, component, connection, **changes)
                return
        current = self.get(order_id, tx)
        require_transition(OrderState(current["state"]), target)
        allowed = {"crm_id", "components", "error", "read_attempts"}
        if not changes.keys() <= allowed:
            raise ValueError("Unsupported order field")
        fields = ["state=?", "version=version+1"] + [f"{key}=?" for key in changes]
        values = [target] + [json.dumps(v) if k == "components" else v for k, v in changes.items()]
        tx.execute(f"UPDATE orders SET {','.join(fields)} WHERE id=?", (*values, order_id))
        record(tx, order_id, component, "state_transition", target, previous=current["state"])
