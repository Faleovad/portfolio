from fastapi import APIRouter

from ..domain.models import OrderState
from .dependencies import LabDependency

router = APIRouter(prefix="/api", tags=["reliability"])


@router.get("/mutations")
def mutations(lab: LabDependency) -> dict:
    snapshot = lab.snapshot()
    return {key: snapshot[key] for key in ("journals", "fences", "receipts")}


@router.get("/recovery")
def tasks(lab: LabDependency) -> list[dict]:
    return lab.snapshot()["tasks"]


@router.post("/recovery/run")
def recover(lab: LabDependency) -> dict:
    with lab.engine.lock:
        for order in lab.snapshot()["orders"]:
            if order["state"] in {OrderState.UNKNOWN, OrderState.RECONCILING}:
                lab.engine.run(order["id"])
    return lab.snapshot()
