import hashlib
import json
import sqlite3
from uuid import uuid4

from ..domain.errors import LabError
from ..domain.models import JournalState as J
from ..infrastructure.database import Database
from ..infrastructure.events import now, record


def fingerprint(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class CreateJournal:
    """External identity authority. SENT/UNKNOWN never become dispatchable through expiry."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def prepare(self, order: dict) -> dict:
        digest = fingerprint((order["external_id"], order["warehouse_id"], order["components"]))
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM create_journal WHERE external_id=?",
                (order["external_id"],),
            ).fetchone()
            if row:
                if row["fingerprint"] != digest:
                    raise LabError(
                        "identity_conflict", "Same external identity has a different intent"
                    )
                return dict(row)
            intent = f"create-{uuid4()}"
            tx.execute(
                "INSERT INTO create_journal VALUES(?,?,?,?,?,?,?,?)",
                (
                    order["external_id"],
                    order["id"],
                    intent,
                    digest,
                    J.PREPARED,
                    now(),
                    None,
                    None,
                ),
            )
            record(tx, order["id"], "create_journal", "intent_prepared", intent_id=intent)
            return dict(
                tx.execute(
                    "SELECT * FROM create_journal WHERE external_id=?",
                    (order["external_id"],),
                ).fetchone()
            )

    def mark_sent(self, identity: str) -> None:
        with self.db.transaction() as tx:
            cursor = tx.execute(
                "UPDATE create_journal SET state=? WHERE external_id=? AND state=?",
                (J.SENT, identity, J.PREPARED),
            )
            if cursor.rowcount != 1:
                raise LabError("create_fenced", "A prior CREATE may already have been dispatched")

    def unknown(self, identity: str) -> None:
        with self.db.transaction() as tx:
            tx.execute(
                "UPDATE create_journal SET state=? WHERE external_id=? AND state=?",
                (J.UNKNOWN, identity, J.SENT),
            )

    def confirm(self, tx: sqlite3.Connection, identity: str, proof: dict) -> None:
        tx.execute(
            "UPDATE create_journal SET state=?,crm_id=?,result=? WHERE external_id=?",
            (J.CONFIRMED, proof["id"], json.dumps(proof), identity),
        )


class MutationFence:
    """One resource/mutation pair owns one intent. Ownership expiry is not provider finality."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def prepare(self, tx: sqlite3.Connection, order: dict) -> dict:
        row = tx.execute(
            "SELECT * FROM mutation_fences WHERE resource_id=? AND mutation_type=?",
            (order["crm_id"], "FULFILL"),
        ).fetchone()
        if row:
            return dict(row)
        intent = f"fulfill-{uuid4()}"
        tx.execute(
            "INSERT INTO mutation_fences VALUES(?,?,?,?,?,?,?,?)",
            (
                order["crm_id"],
                "FULFILL",
                order["id"],
                intent,
                J.PREPARED,
                None,
                0,
                now(),
            ),
        )
        return dict(
            tx.execute("SELECT * FROM mutation_fences WHERE intent_id=?", (intent,)).fetchone()
        )

    def dispatch(self, intent: str, owner: str, lease_until: float) -> None:
        with self.db.transaction() as tx:
            cursor = tx.execute(
                "UPDATE mutation_fences SET state=?,owner=?,lease_until=? "
                "WHERE intent_id=? AND state=? AND NOT EXISTS "
                "(SELECT 1 FROM terminal_receipts WHERE intent_id=?)",
                (J.SENT, owner, lease_until, intent, J.PREPARED, intent),
            )
            if cursor.rowcount != 1:
                raise LabError(
                    "mutation_fenced", "Unknown or terminal mutation cannot be dispatched"
                )

    def unknown(self, intent: str) -> None:
        with self.db.transaction() as tx:
            tx.execute(
                "UPDATE mutation_fences SET state=? WHERE intent_id=? AND state=?",
                (J.UNKNOWN, intent, J.SENT),
            )
