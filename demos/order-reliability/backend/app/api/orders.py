from fastapi import APIRouter

from .dependencies import LabDependency

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("")
def list_orders(lab: LabDependency) -> list[dict]:
    return lab.snapshot()["orders"]


@router.get("/{order_id}")
def get_order(order_id: str, lab: LabDependency) -> dict:
    return lab.orders.get(order_id)


@router.post("/{order_id}/step")
def step(order_id: str, lab: LabDependency) -> dict:
    return lab.engine.step(order_id)


@router.post("/{order_id}/run")
def run(order_id: str, lab: LabDependency) -> dict:
    return lab.engine.run(order_id)
