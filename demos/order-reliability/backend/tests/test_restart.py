import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.container import Lab
from app.domain.errors import LabError, SimulatedInterruption
from app.domain.models import FaultMode, FaultSpec, OrderState, TaskState
from conftest import complete, until


def test_real_new_process_recovers_persisted_unknown(lab: Lab, tmp_path: Path) -> None:
    lab.scenarios.reset("completion_lost")
    until(lab, OrderState.UNKNOWN)
    code = (
        "import json,sys;from pathlib import Path;from app.container import Lab;"
        "lab=Lab(Path(sys.argv[1]));lab.engine.run('DEMO-1001');"
        "print(json.dumps(lab.snapshot()))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(Path.cwd())},
    )
    snapshot = json.loads(result.stdout)
    assert snapshot["orders"][0]["state"] == "DONE"
    assert sum(c["operation"] == "FULFILL" for c in snapshot["external"]["calls"]) == 1


def test_interrupt_after_create_requires_journal_reconciliation(lab: Lab, tmp_path: Path) -> None:
    lab.scenarios.reset("interrupt_create")
    with pytest.raises(SimulatedInterruption):
        lab.engine.run("DEMO-1001")
    assert lab.snapshot()["journals"][0]["state"] == "SENT"
    restarted = Lab(tmp_path)
    assert complete(restarted)["state"] == "DONE"
    assert len(restarted.crm.inspect()["orders"]) == 1


def test_interrupt_after_external_update_does_not_redispatch(lab: Lab, tmp_path: Path) -> None:
    lab.faults.install((FaultSpec("after_external", FaultMode.INTERRUPT),))
    with pytest.raises(SimulatedInterruption):
        lab.engine.run("DEMO-1001")
    restarted = Lab(tmp_path)
    complete(restarted)
    assert len(restarted.crm.inspect()["calls"]) == 2


def test_lost_finish_ack_preserves_terminal_state(lab: Lab, tmp_path: Path) -> None:
    lab.scenarios.reset("lost_ack")
    with pytest.raises(SimulatedInterruption):
        lab.engine.run("DEMO-1001")
    data = lab.snapshot()
    assert data["orders"][0]["state"] == "DONE"
    complete(Lab(tmp_path))
    assert lab.snapshot()["inventory"] == data["inventory"]


def test_task_claim_excludes_second_worker_and_stale_finish(lab: Lab) -> None:
    lab.scenarios.reset("completion_lost")
    until(lab, OrderState.UNKNOWN)
    first = lab.tasks.claim("DEMO-1001")
    assert first and lab.tasks.claim("DEMO-1001") is None
    with lab.db.transaction() as tx:
        tx.execute("UPDATE recovery_tasks SET lease_until=?", (time.time() - 1,))
    second = lab.tasks.claim("DEMO-1001")
    assert second and first["owner"] != second["owner"]
    with pytest.raises(LabError, match="stale worker"):
        with lab.db.transaction() as tx:
            lab.tasks.finish(tx, first, TaskState.COMPLETE)


def test_consumed_fault_remains_consumed_after_restart(lab: Lab, tmp_path: Path) -> None:
    lab.faults.install((FaultSpec("custom_point", FaultMode.FAIL_READBACK),))
    assert lab.faults.take("custom_point") is not None
    assert Lab(tmp_path).faults.take("custom_point") is None
