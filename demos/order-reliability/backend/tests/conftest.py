from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.container import Lab
from app.domain.errors import SimulatedInterruption
from app.domain.models import OrderState
from app.main import create_app


@pytest.fixture
def lab(tmp_path: Path) -> Lab:
    return Lab(tmp_path)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path))


def complete(lab: Lab) -> dict:
    for _ in range(3):
        try:
            return lab.engine.run("DEMO-1001")
        except SimulatedInterruption:
            pass
    raise AssertionError("Scenario never resumed")


def until(lab: Lab, target: OrderState) -> dict:
    for _ in range(32):
        order = lab.orders.get("DEMO-1001")
        if order["state"] == target:
            return order
        lab.engine.step(order["id"])
    raise AssertionError(f"Never reached {target}")
