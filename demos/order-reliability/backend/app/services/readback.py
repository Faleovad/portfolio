from ..domain.errors import LabError, ReadUnavailable
from ..domain.ports import ProviderReader
from ..infrastructure.database import Database
from ..infrastructure.events import record


class Readback:
    def __init__(self, db: Database, crm: ProviderReader) -> None:
        self.db = db
        self.crm = crm

    def observe(self, order: dict, kind: str, intent: str) -> dict | None:
        try:
            proof = self.crm.read(order["external_id"], f"{kind.lower()}_read")
        except (ReadUnavailable, LabError) as error:
            with self.db.transaction() as tx:
                record(tx, order["id"], "readback", "read_unavailable", reason=error.code)
            return None
        identity = bool(
            proof
            and proof["external_id"] == order["external_id"]
            and proof["warehouse_id"] == order["warehouse_id"]
            and proof["lines"] == order["components"]
        )
        if kind == "FULFILL":
            matched = bool(
                identity
                and proof["id"] == order["crm_id"]
                and proof["status"] == "DONE"
                and proof["stock_status"] == "FULFILLED"
                and proof["tracking"] == order["tracking"]
                and proof["intent_id"] == intent
            )
        else:
            matched = bool(identity and proof["intent_id"] == intent)
        with self.db.transaction() as tx:
            record(
                tx,
                order["id"],
                "readback",
                "effect_confirmed" if matched else "not_confirmed",
                observed_status=proof["status"] if proof else None,
                kind=kind,
            )
        return proof if matched else None
