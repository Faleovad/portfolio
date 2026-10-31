from ..domain.errors import LabError
from ..domain.models import JournalState as J
from ..domain.models import OrderState as S
from ..domain.models import TaskState as T
from ..infrastructure.database import Database
from ..infrastructure.orders import Orders
from ..reliability.journals import CreateJournal
from ..reliability.policy import ReadPolicy
from ..reliability.receipts import Receipts
from ..reliability.tasks import Tasks
from .readback import Readback


class Recovery:
    """Read-only provider reconciliation. This worker has no reference to a mutation transport."""

    def __init__(
        self,
        db: Database,
        orders: Orders,
        tasks: Tasks,
        readback: Readback,
        journal: CreateJournal,
        policy: ReadPolicy,
    ) -> None:
        self.db, self.orders, self.tasks = db, orders, tasks
        self.readback, self.journal, self.policy = readback, journal, policy

    def step(self, order: dict) -> None:
        if order["state"] == S.UNKNOWN:
            self.orders.move(order["id"], S.RECONCILING, "reconciliation")
            return
        task = self.tasks.claim(order["id"])
        if task is None:
            raise LabError("recovery_busy", "No due task or another worker owns its lease")
        table = "create_journal" if task["kind"] == "CREATE" else "mutation_fences"
        rows = self.db.rows(f"SELECT * FROM {table} WHERE order_id=?", (order["id"],))
        if not rows:
            raise LabError("journal_missing", "Cannot reconcile without persisted intent")
        intent = rows[0]["intent_id"]
        proof = self.readback.observe(order, task["kind"], intent)
        with self.db.transaction() as tx:
            if proof:
                Receipts.add(tx, order["id"], intent, task["kind"], proof)
                if task["kind"] == "CREATE":
                    self.journal.confirm(tx, order["external_id"], proof)
                    self.orders.move(
                        order["id"], S.CREATED, "reconciliation", tx, crm_id=proof["id"], error=None
                    )
                else:
                    tx.execute(
                        "UPDATE mutation_fences SET state=? WHERE intent_id=?",
                        (J.CONFIRMED, intent),
                    )
                    self.orders.move(order["id"], S.CONFIRMED, "reconciliation", tx, error=None)
                self.tasks.finish(tx, task, T.COMPLETE)
            elif self.policy.exhausted(task["attempts"] + 1, recovery=True):
                self.orders.move(
                    order["id"],
                    S.MANUAL_REVIEW,
                    "reconciliation",
                    tx,
                    error="No exact effect proof within the read-only recovery policy",
                )
                self.tasks.finish(tx, task, T.MANUAL_REVIEW)
            else:
                self.tasks.finish(tx, task, T.PENDING)
