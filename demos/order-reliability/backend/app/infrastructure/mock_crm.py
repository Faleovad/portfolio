import json
from uuid import uuid4

from ..domain.errors import ExternalUncertain, LabError, ProviderHTTPError, ReadUnavailable
from ..domain.models import FaultMode, Operation
from ..reliability.faults import Faults
from .database import Database


class MockCRM:
    """Independent provider state. Deliberately no CREATE idempotency supplied by the provider."""

    def __init__(self, db: Database, faults: Faults) -> None:
        self.db = db
        self.faults = faults

    def _attempt(
        self, operation: Operation, external_id: str, intent: str
    ) -> tuple[int, dict | None]:
        with self.db.transaction() as tx:
            row = tx.execute(
                "INSERT INTO crm_calls(operation,external_id,intent_id) VALUES(?,?,?) RETURNING id",
                (operation, external_id, intent),
            ).fetchone()
            call_id = row["id"]
        fault = self.faults.take(operation.lower())
        if fault and fault["mode"] == FaultMode.HTTP_ERROR:
            raise ProviderHTTPError()
        if fault and fault["mode"] == FaultMode.BEFORE_COMMIT:
            raise ExternalUncertain(
                "Provider did not commit; caller cannot infer that from a timeout"
            )
        return call_id, fault

    @staticmethod
    def _after(fault: dict | None) -> None:
        if fault and fault["mode"] in {FaultMode.COMMIT_THEN_TIMEOUT, FaultMode.LOSE_ACK}:
            raise ExternalUncertain("Provider committed, but its response was lost")

    def create(self, order: dict, intent: str) -> dict:
        call_id, fault = self._attempt(Operation.CREATE, order["external_id"], intent)
        crm_id = f"CRM-{uuid4().hex[:8]}"
        with self.db.transaction() as tx:
            for line in order["components"]:
                cursor = tx.execute(
                    "UPDATE crm_inventory SET reserved=reserved+? "
                    "WHERE warehouse_id=? AND sku=? AND on_hand-reserved>=?",
                    (line["quantity"], order["warehouse_id"], line["sku"], line["quantity"]),
                )
                if cursor.rowcount != 1:
                    raise LabError(
                        "provider_stock_conflict", "Provider cannot reserve every component"
                    )
            tx.execute(
                "INSERT INTO crm_orders VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    crm_id,
                    order["external_id"],
                    order["warehouse_id"],
                    json.dumps(order["components"]),
                    "NEW",
                    None,
                    "RESERVED",
                    intent,
                    None,
                    fault["delay_reads"] if fault else 0,
                ),
            )
            tx.execute("UPDATE crm_calls SET committed=1 WHERE id=?", (call_id,))
        self._after(fault)
        return {"accepted": True, "id": crm_id}

    def fulfill(self, order: dict, intent: str) -> dict:
        call_id, fault = self._attempt(Operation.FULFILL, order["external_id"], intent)
        with self.db.transaction() as tx:
            row = tx.execute("SELECT * FROM crm_orders WHERE id=?", (order["crm_id"],)).fetchone()
            if not row or row["status"] != "NEW" or row["stock_status"] != "RESERVED":
                raise LabError("provider_state_conflict", "Provider requires a reserved NEW order")
            for line in json.loads(row["lines"]):
                qty = line["quantity"]
                cursor = tx.execute(
                    "UPDATE crm_inventory SET on_hand=on_hand-?,reserved=reserved-?,"
                    "fulfilled=fulfilled+? WHERE warehouse_id=? AND sku=? AND reserved>=?",
                    (qty, qty, qty, row["warehouse_id"], line["sku"], qty),
                )
                if cursor.rowcount != 1:
                    raise LabError("provider_stock_conflict", "Provider reservation missing")
            tx.execute(
                "UPDATE crm_orders SET status='DONE',stock_status='FULFILLED',tracking=?,"
                "intent_id=?,previous_view=?,hidden_reads=? WHERE id=?",
                (
                    order["tracking"],
                    intent,
                    json.dumps(dict(row)),
                    fault["delay_reads"] if fault else 0,
                    order["crm_id"],
                ),
            )
            tx.execute("UPDATE crm_calls SET committed=1 WHERE id=?", (call_id,))
        self._after(fault)
        return {"accepted": True, "http_status": 202}

    def read(self, external_id: str, point: str) -> dict | None:
        fault = self.faults.take(point)
        if fault and fault["mode"] == FaultMode.FAIL_READBACK:
            raise ReadUnavailable()
        with self.db.transaction() as tx:
            rows = tx.execute(
                "SELECT * FROM crm_orders WHERE external_id=?", (external_id,)
            ).fetchall()
            if len(rows) > 1:
                raise LabError("provider_duplicate", "Exact identity is ambiguous")
            if not rows:
                return None
            view = dict(rows[0])
            stale = view["hidden_reads"] > 0 or (
                fault and fault["mode"] == FaultMode.STALE_RESPONSE
            )
            if view["hidden_reads"] > 0:
                tx.execute(
                    "UPDATE crm_orders SET hidden_reads=hidden_reads-1 WHERE id=?", (view["id"],)
                )
            if stale:
                if not view["previous_view"]:
                    return None
                view = json.loads(view["previous_view"])
            view["lines"] = json.loads(view["lines"])
            view.pop("previous_view", None)
            return view

    def inspect(self) -> dict:
        """Lab-only omniscient observer. The application cannot use this as readback proof."""
        return {
            "orders": self.db.rows("SELECT * FROM crm_orders"),
            "inventory": self.db.rows("SELECT *,on_hand-reserved AS available FROM crm_inventory"),
            "calls": self.db.rows("SELECT * FROM crm_calls ORDER BY id"),
        }
