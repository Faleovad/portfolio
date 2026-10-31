import json
from pathlib import Path

from .infrastructure.database import Database
from .infrastructure.mock_crm import MockCRM
from .infrastructure.orders import Orders
from .reliability.faults import Faults
from .reliability.journals import CreateJournal, MutationFence
from .reliability.policy import ReadPolicy
from .reliability.tasks import Tasks
from .services.engine import Engine
from .services.importer import Importer
from .services.mutations import Mutations
from .services.readback import Readback
from .services.recovery import Recovery
from .services.reservations import Reservations
from .services.scenarios import ScenarioService


class Lab:
    def __init__(self, directory: Path) -> None:
        self.db = Database(directory / "erp.sqlite3")
        self.provider_db = Database(directory / "provider.sqlite3", "provider_schema.sql")
        self.orders = Orders(self.db)
        self.faults = Faults(self.db)
        self.crm = MockCRM(self.provider_db, self.faults)
        self.journal = CreateJournal(self.db)
        self.fence = MutationFence(self.db)
        self.policy = ReadPolicy()
        self.tasks = Tasks(self.db, self.policy.lease_seconds)
        self.readback = Readback(self.db, self.crm)
        self.reservations = Reservations(self.db)
        self.importer = Importer(
            self.db, self.orders, self.crm, self.journal, self.readback, self.tasks, self.faults
        )
        self.mutations = Mutations(
            self.db,
            self.orders,
            self.crm,
            self.fence,
            self.readback,
            self.tasks,
            self.faults,
            self.policy,
        )
        self.recovery = Recovery(
            self.db, self.orders, self.tasks, self.readback, self.journal, self.policy
        )
        self.engine = Engine(
            self.db,
            self.orders,
            self.importer,
            self.mutations,
            self.recovery,
            self.reservations,
            self.faults,
        )
        self.scenarios = ScenarioService(self.db, self.provider_db, self.faults)
        if not self.db.rows("SELECT id FROM orders"):
            self.scenarios.reset("happy")

    def events(self, after: int = 0) -> list[dict]:
        return [
            {**row, "details": json.loads(row["details"])}
            for row in self.db.rows(
                "SELECT * FROM events WHERE sequence>? ORDER BY sequence",
                (after,),
            )
        ]

    def snapshot(self) -> dict:
        with self.engine.lock:
            return self._snapshot()

    def _snapshot(self) -> dict:
        return {
            "orders": [self.orders.get(row["id"]) for row in self.db.rows("SELECT id FROM orders")],
            "inventory": self.db.rows("SELECT *,on_hand-reserved AS available FROM inventory"),
            "reservations": self.db.rows("SELECT * FROM reservations"),
            "journals": self.db.rows("SELECT * FROM create_journal"),
            "fences": self.db.rows("SELECT * FROM mutation_fences"),
            "tasks": self.db.rows("SELECT * FROM recovery_tasks"),
            "receipts": self.db.rows("SELECT * FROM terminal_receipts"),
            "faults": self.db.rows("SELECT * FROM fault_plans"),
            "external": self.crm.inspect(),
            "events": self.events(),
        }
