from fastapi import APIRouter, Query

from .dependencies import LabDependency

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"ok": True, "mode": "synthetic-local-lab"}


@router.get("/system")
def system(lab: LabDependency) -> dict:
    return lab.snapshot()


@router.get("/events")
def events(lab: LabDependency, after: int = Query(0, ge=0)) -> list[dict]:
    return lab.events(after)
