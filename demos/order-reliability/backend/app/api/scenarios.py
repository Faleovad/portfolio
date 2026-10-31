from fastapi import APIRouter

from ..scenarios.catalog import SCENARIOS
from .dependencies import LabDependency

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("")
def list_scenarios() -> list[dict]:
    return [scenario.public() for scenario in SCENARIOS]


@router.post("/{scenario_id}/reset")
def reset(scenario_id: str, lab: LabDependency) -> dict:
    with lab.engine.lock:
        lab.scenarios.reset(scenario_id)
    return lab.snapshot()
