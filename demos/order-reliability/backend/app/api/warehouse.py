from fastapi import APIRouter

from .dependencies import LabDependency

router = APIRouter(prefix="/api/warehouse", tags=["warehouse"])


@router.get("")
def warehouse(lab: LabDependency) -> dict:
    snapshot = lab.snapshot()
    return {key: snapshot[key] for key in ("inventory", "reservations")}
