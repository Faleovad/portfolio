import json
from dataclasses import asdict

from ..domain.errors import LabError
from ..domain.models import OrderState as S
from ..infrastructure.database import ENTITY_TABLES, PROVIDER_TABLES, Database
from ..infrastructure.events import record
from ..reliability.faults import Faults
from ..scenarios.catalog import BY_ID


class ScenarioService:
    def __init__(self, db: Database, provider_db: Database, faults: Faults) -> None:
        self.db, self.provider_db, self.faults = db, provider_db, faults

    def reset(self, scenario_id: str) -> None:
        if scenario_id not in BY_ID:
            raise LabError("scenario_not_found", "Unknown synthetic scenario", 404)
        scenario = BY_ID[scenario_id]
        self.db.clear(ENTITY_TABLES)
        self.provider_db.clear(PROVIDER_TABLES)
        self.faults.install(scenario.faults)
        with self.db.transaction() as tx:
            tx.execute(
                "INSERT INTO orders(id,external_id,state,lines,warehouse_id,tracking,scenario) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    "DEMO-1001",
                    "SYNTHETIC-ORDER-001",
                    S.DISCOVERED,
                    json.dumps([asdict(line) for line in scenario.lines]),
                    "WH-DEMO",
                    "SYNTHETIC-TRACKING",
                    scenario.id,
                ),
            )
            for sku in ("SENSOR", "CABLE"):
                tx.execute(
                    "INSERT INTO inventory VALUES(?,?,?,?,?)",
                    ("WH-DEMO", sku, scenario.stock, 0, 0),
                )
            record(
                tx,
                "DEMO-1001",
                "scenario_service",
                "scenario_seeded",
                S.DISCOVERED,
                scenario=scenario.id,
            )
        with self.provider_db.transaction() as tx:
            for sku in ("SENSOR", "CABLE"):
                tx.execute(
                    "INSERT INTO crm_inventory VALUES(?,?,?,?,?)",
                    ("WH-DEMO", sku, scenario.stock, 0, 0),
                )
