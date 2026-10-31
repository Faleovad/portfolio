from ..domain.errors import LabError
from ..domain.models import JournalState as J
from ..domain.models import OrderState as S
from ..domain.ports import ProviderWriter
from ..infrastructure.database import Database
from ..infrastructure.events import record
from ..infrastructure.orders import Orders
from ..reliability.faults import Faults
from ..reliability.journals import CreateJournal
from ..reliability.receipts import Receipts
from ..reliability.tasks import Tasks
from .readback import Readback


class Importer:
    def __init__(
        self,
        db: Database,
        orders: Orders,
        crm: ProviderWriter,
        journal: CreateJournal,
        readback: Readback,
        tasks: Tasks,
        faults: Faults,
    ) -> None:
        self.db, self.orders, self.crm = db, orders, crm
        self.journal, self.readback, self.tasks, self.faults = journal, readback, tasks, faults

    def execute(self, order: dict) -> None:
        row = self.journal.prepare(order)
        if row["state"] == J.CONFIRMED:
            self.orders.move(order["id"], S.CREATED, "importer", crm_id=row["crm_id"])
            return
        if row["state"] != J.PREPARED:
            self.unknown(order, "CREATE was previously dispatched")
            return
        self.journal.mark_sent(order["external_id"])
        with self.db.transaction() as tx:
            record(
                tx,
                order["id"],
                "importer",
                "external_create_dispatched",
                intent_id=row["intent_id"],
            )
        try:
            self.crm.create(order, row["intent_id"])
        except LabError:
            self.journal.unknown(order["external_id"])
            self.unknown(order, "CREATE response uncertain")
            return
        self.faults.checkpoint("after_create")
        proof = self.readback.observe(order, "CREATE", row["intent_id"])
        if proof:
            with self.db.transaction() as tx:
                self.journal.confirm(tx, order["external_id"], proof)
                Receipts.add(tx, order["id"], row["intent_id"], "CREATE", proof)
                self.orders.move(order["id"], S.CREATED, "importer", tx, crm_id=proof["id"])
        else:
            self.journal.unknown(order["external_id"])
            self.unknown(order, "CREATE readback unavailable or not exact")

    def unknown(self, order: dict, reason: str) -> None:
        with self.db.transaction() as tx:
            self.orders.move(order["id"], S.UNKNOWN, "importer", tx, error=reason)
            self.tasks.enqueue(tx, order["id"], "CREATE", reason)
