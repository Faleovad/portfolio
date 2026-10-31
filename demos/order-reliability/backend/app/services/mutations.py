import time
from uuid import uuid4

from ..domain.errors import LabError
from ..domain.models import JournalState as J
from ..domain.models import OrderState as S
from ..domain.ports import ProviderWriter
from ..infrastructure.database import Database
from ..infrastructure.events import record
from ..infrastructure.orders import Orders
from ..reliability.faults import Faults
from ..reliability.journals import MutationFence
from ..reliability.policy import ReadPolicy
from ..reliability.receipts import Receipts
from ..reliability.tasks import Tasks
from .readback import Readback


class Mutations:
    def __init__(
        self,
        db: Database,
        orders: Orders,
        crm: ProviderWriter,
        fence: MutationFence,
        readback: Readback,
        tasks: Tasks,
        faults: Faults,
        policy: ReadPolicy,
    ) -> None:
        self.db, self.orders, self.crm, self.fence = db, orders, crm, fence
        self.readback, self.tasks, self.faults, self.policy = readback, tasks, faults, policy

    def prepare(self, order: dict) -> None:
        with self.db.transaction() as tx:
            row = self.fence.prepare(tx, order)
            if row["state"] != J.PREPARED:
                raise LabError("mutation_fenced", "Existing mutation cannot be prepared again")
            self.orders.move(order["id"], S.MUTATION_PENDING, "mutation_service", tx)
            record(tx, order["id"], "mutation_fence", "intent_prepared", intent_id=row["intent_id"])
        self.faults.checkpoint("after_fence")

    def dispatch(self, order: dict) -> None:
        row = self.db.rows("SELECT * FROM mutation_fences WHERE order_id=?", (order["id"],))[0]
        if row["state"] != J.PREPARED:
            self.unknown(order, "FULFILL may already have been dispatched")
            return
        before = self.crm.read(order["external_id"], "preflight_read")
        if (
            not before
            or before["id"] != order["crm_id"]
            or before["status"] != "NEW"
            or before["warehouse_id"] != order["warehouse_id"]
            or before["stock_status"] != "RESERVED"
            or before["lines"] != order["components"]
        ):
            self.unknown(order, "Fresh provider precondition unavailable or changed")
            return
        self.fence.dispatch(row["intent_id"], str(uuid4()), time.time() + self.policy.lease_seconds)
        with self.db.transaction() as tx:
            record(
                tx,
                order["id"],
                "mutation_service",
                "external_mutation_dispatched",
                S.MUTATION_PENDING,
                intent_id=row["intent_id"],
            )
        try:
            self.crm.fulfill(order, row["intent_id"])
        except LabError:
            self.fence.unknown(row["intent_id"])
            self.unknown(order, "FULFILL response uncertain")
            return
        self.faults.checkpoint("after_external")
        self.orders.move(order["id"], S.CONFIRMING, "mutation_service")

    def confirm(self, order: dict) -> None:
        fence = self.db.rows("SELECT * FROM mutation_fences WHERE order_id=?", (order["id"],))[0]
        proof = self.readback.observe(order, "FULFILL", fence["intent_id"])
        if proof:
            with self.db.transaction() as tx:
                Receipts.add(tx, order["id"], fence["intent_id"], "FULFILL", proof)
                tx.execute(
                    "UPDATE mutation_fences SET state=? WHERE intent_id=?",
                    (J.CONFIRMED, fence["intent_id"]),
                )
                self.orders.move(order["id"], S.CONFIRMED, "readback", tx)
            return
        attempts = order["read_attempts"] + 1
        with self.db.transaction() as tx:
            tx.execute("UPDATE orders SET read_attempts=? WHERE id=?", (attempts, order["id"]))
        if self.policy.exhausted(attempts):
            self.fence.unknown(fence["intent_id"])
            self.unknown(order, "Bounded confirmation reads exhausted")

    def unknown(self, order: dict, reason: str) -> None:
        with self.db.transaction() as tx:
            self.orders.move(order["id"], S.UNKNOWN, "mutation_service", tx, error=reason)
            self.tasks.enqueue(tx, order["id"], "FULFILL", reason)
