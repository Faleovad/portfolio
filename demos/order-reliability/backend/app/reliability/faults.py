from ..domain.errors import SimulatedInterruption
from ..domain.models import FaultMode, FaultSpec
from ..infrastructure.database import Database
from ..infrastructure.events import record


class Faults:
    """Persisted, deterministic, consume-once fault slots; no scenario branching in services."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def install(self, specs: tuple[FaultSpec, ...]) -> None:
        with self.db.transaction() as tx:
            for spec in specs:
                tx.execute(
                    "INSERT INTO fault_plans VALUES(?,?,?,?)",
                    (
                        spec.point,
                        spec.mode,
                        spec.times,
                        spec.delay_reads,
                    ),
                )

    def take(self, point: str) -> dict | None:
        with self.db.transaction() as tx:
            row = tx.execute(
                "SELECT * FROM fault_plans WHERE point=? AND remaining>0",
                (point,),
            ).fetchone()
            if row is None:
                return None
            tx.execute("UPDATE fault_plans SET remaining=remaining-1 WHERE point=?", (point,))
            record(
                tx, "DEMO-1001", "fault_injection", "fault_consumed", point=point, mode=row["mode"]
            )
            return dict(row)

    def checkpoint(self, point: str) -> None:
        fault = self.take(point)
        if fault and fault["mode"] in {FaultMode.INTERRUPT, FaultMode.LOSE_ACK}:
            raise SimulatedInterruption(point)
