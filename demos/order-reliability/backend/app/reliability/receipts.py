import json
import sqlite3

from ..domain.errors import LabError
from ..infrastructure.events import now, record


class Receipts:
    """Immutable positive proof; never replace evidence under the same intent identity."""

    @staticmethod
    def add(tx: sqlite3.Connection, order_id: str, intent: str, kind: str, proof: dict) -> None:
        existing = tx.execute(
            "SELECT proof FROM terminal_receipts WHERE intent_id=?", (intent,)
        ).fetchone()
        if existing and json.loads(existing["proof"]) != proof:
            raise LabError("receipt_conflict", "A terminal receipt cannot change its proof")
        tx.execute(
            "INSERT OR IGNORE INTO terminal_receipts VALUES(?,?,?,?,?)",
            (intent, order_id, kind, json.dumps(proof, sort_keys=True), now()),
        )
        record(tx, order_id, "terminal_receipts", "receipt_retained", intent_id=intent, kind=kind)
