import json
import threading

from ..domain.errors import LabError
from ..domain.models import Line
from ..domain.models import OrderState as S
from ..infrastructure.database import Database
from ..infrastructure.orders import Orders
from ..reliability.faults import Faults
from ..scenarios.catalog import BY_ID
from .bundles import Bundles
from .importer import Importer
from .mutations import Mutations
from .recovery import Recovery
from .reservations import Reservations


class Engine:
    """Single-process command executor; durable fences own provider dispatch permission."""

    def __init__(
        self,
        db: Database,
        orders: Orders,
        importer: Importer,
        mutations: Mutations,
        recovery: Recovery,
        reservations: Reservations,
        faults: Faults,
    ) -> None:
        self.db, self.orders, self.importer, self.mutations = db, orders, importer, mutations
        self.recovery, self.reservations, self.faults = recovery, reservations, faults
        self.lock = threading.RLock()

    def step(self, order_id: str) -> dict:
        with self.lock:
            order = self.orders.get(order_id)
            state = S(order["state"])
            if state in {S.DONE, S.MANUAL_REVIEW}:
                return order
            if state == S.DISCOVERED:
                rules = (
                    {"KIT-DESK": (Line("KIT-DESK", 1),)}
                    if BY_ID[order["scenario"]].invalid_rules
                    else None
                )
                try:
                    components = Bundles(rules).expand(order["lines"])
                    with self.db.transaction() as tx:
                        for line in components:
                            stock = tx.execute(
                                "SELECT * FROM inventory WHERE warehouse_id=? AND sku=?",
                                (order["warehouse_id"], line["sku"]),
                            ).fetchone()
                            if (
                                stock is None
                                or stock["on_hand"] - stock["reserved"] < line["quantity"]
                            ):
                                raise LabError(
                                    "insufficient_stock", "Cannot reserve all components"
                                )
                        self.orders.move(
                            order_id, S.VALIDATED, "bundle_service", tx, components=components
                        )
                except LabError as error:
                    self.orders.move(order_id, S.MANUAL_REVIEW, "validation", error=error.code)
            elif state == S.VALIDATED:
                self.importer.execute(order)
            elif state == S.CREATED:
                try:
                    with self.db.transaction() as tx:
                        self.reservations.reserve(order, tx)
                        self.orders.move(order_id, S.RESERVED, "reservation_service", tx)
                except LabError as error:
                    self.orders.move(
                        order_id, S.MANUAL_REVIEW, "reservation_service", error=error.code
                    )
            elif state == S.RESERVED:
                self.mutations.prepare(order)
            elif state == S.MUTATION_PENDING:
                self.mutations.dispatch(order)
            elif state == S.CONFIRMING:
                self.mutations.confirm(order)
            elif state in {S.UNKNOWN, S.RECONCILING}:
                self.recovery.step(order)
            elif state == S.CONFIRMED:
                with self.db.transaction() as tx:
                    receipt = tx.execute(
                        "SELECT proof FROM terminal_receipts WHERE order_id=? AND kind='FULFILL'",
                        (order_id,),
                    ).fetchone()
                    if not receipt or json.loads(receipt["proof"])["status"] != "DONE":
                        raise LabError(
                            "receipt_required", "Local settlement requires terminal effect proof"
                        )
                    self.reservations.fulfill(tx, order_id)
                    self.orders.move(order_id, S.DONE, "settlement", tx, error=None)
                self.faults.checkpoint("after_finish")
            return self.orders.get(order_id)

    def run(self, order_id: str, max_steps: int = 32) -> dict:
        with self.lock:
            for _ in range(max_steps):
                order = self.step(order_id)
                if order["state"] in {S.DONE, S.MANUAL_REVIEW}:
                    return order
            raise LabError("step_limit", "Execution paused after the bounded step policy")
