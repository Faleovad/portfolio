import sqlite3

import pytest

from app.container import Lab
from app.domain.errors import LabError
from app.domain.models import OrderState
from app.reliability.receipts import Receipts
from conftest import complete, until


def test_local_reservation_rolls_back_if_later_component_is_insufficient(lab: Lab) -> None:
    order = until(lab, OrderState.CREATED)
    with lab.db.transaction() as tx:
        tx.execute("UPDATE inventory SET on_hand=0 WHERE sku='SENSOR'")
    with pytest.raises(LabError):
        with lab.db.transaction() as tx:
            lab.reservations.reserve(order, tx)
    assert lab.snapshot()["reservations"] == []
    assert all(row["reserved"] == 0 for row in lab.snapshot()["inventory"])


def test_provider_create_rolls_back_all_component_reserves(lab: Lab) -> None:
    order = until(lab, OrderState.VALIDATED)
    with lab.provider_db.transaction() as tx:
        tx.execute("UPDATE crm_inventory SET on_hand=0 WHERE sku='SENSOR'")
    with pytest.raises(LabError):
        lab.crm.create(order, "synthetic-intent")
    assert lab.crm.inspect()["orders"] == []
    assert all(row["reserved"] == 0 for row in lab.crm.inspect()["inventory"])


def test_sql_constraints_reject_negative_inventory(lab: Lab) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        with lab.db.transaction() as tx:
            tx.execute("UPDATE inventory SET reserved=on_hand+1")


def test_preflight_changed_lines_never_send_fulfillment(lab: Lab) -> None:
    until(lab, OrderState.MUTATION_PENDING)
    with lab.provider_db.transaction() as tx:
        tx.execute("UPDATE crm_orders SET lines='[]'")
    complete(lab)
    assert all(c["operation"] != "FULFILL" for c in lab.crm.inspect()["calls"])
    assert lab.orders.get("DEMO-1001")["state"] == "MANUAL_REVIEW"


def test_terminal_proof_is_immutable(lab: Lab) -> None:
    complete(lab)
    receipt = lab.snapshot()["receipts"][0]
    with pytest.raises(LabError, match="cannot change"):
        with lab.db.transaction() as tx:
            Receipts.add(tx, "DEMO-1001", receipt["intent_id"], "CREATE", {"id": "WRONG"})
