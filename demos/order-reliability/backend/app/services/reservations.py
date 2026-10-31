import sqlite3

from ..domain.errors import LabError
from ..infrastructure.database import Database
from ..infrastructure.events import record


class Reservations:
    def __init__(self, db: Database) -> None:
        self.db = db

    def reserve(self, order: dict, tx: sqlite3.Connection) -> None:
        existing = tx.execute("SELECT state FROM reservations WHERE order_id=?", (order["id"],))
        if existing.fetchone():
            return
        for line in order["components"]:
            row = tx.execute(
                "SELECT * FROM inventory WHERE warehouse_id=? AND sku=?",
                (order["warehouse_id"], line["sku"]),
            ).fetchone()
            if not row or row["on_hand"] - row["reserved"] < line["quantity"]:
                raise LabError("insufficient_stock", "All bundle components must be reservable")
        for line in order["components"]:
            tx.execute(
                "UPDATE inventory SET reserved=reserved+? WHERE warehouse_id=? AND sku=?",
                (line["quantity"], order["warehouse_id"], line["sku"]),
            )
            tx.execute(
                "INSERT INTO reservations VALUES(?,?,?,?,?)",
                (
                    order["id"],
                    order["warehouse_id"],
                    line["sku"],
                    line["quantity"],
                    "RESERVED",
                ),
            )
        record(tx, order["id"], "reservations", "components_reserved")

    def fulfill(self, tx: sqlite3.Connection, order_id: str) -> None:
        rows = tx.execute(
            "SELECT * FROM reservations WHERE order_id=? AND state='RESERVED'", (order_id,)
        ).fetchall()
        for row in rows:
            qty = row["quantity"]
            tx.execute(
                "UPDATE inventory SET on_hand=on_hand-?,reserved=reserved-?,"
                "fulfilled=fulfilled+? WHERE warehouse_id=? AND sku=?",
                (qty, qty, qty, row["warehouse_id"], row["sku"]),
            )
        tx.execute("UPDATE reservations SET state='FULFILLED' WHERE order_id=?", (order_id,))
        record(tx, order_id, "reservations", "local_stock_settled", affected_lines=len(rows))
