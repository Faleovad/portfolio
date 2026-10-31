from app.container import Lab
from app.domain.models import OrderState
from conftest import complete, until


def test_before_and_after_commit_are_observably_different(lab: Lab) -> None:
    lab.scenarios.reset("before_commit")
    until(lab, OrderState.UNKNOWN)
    before = lab.crm.inspect()
    assert before["orders"][0]["status"] == "NEW"
    assert before["calls"][-1]["committed"] == 0
    lab.scenarios.reset("completion_lost")
    until(lab, OrderState.UNKNOWN)
    after = lab.crm.inspect()
    assert after["orders"][0]["status"] == "DONE"
    assert after["calls"][-1]["committed"] == 1
    assert lab.orders.get("DEMO-1001")["state"] == "UNKNOWN"


def test_lost_success_response_never_repeats_mutation(lab: Lab) -> None:
    lab.scenarios.reset("completion_lost")
    complete(lab)
    assert sum(c["operation"] == "FULFILL" for c in lab.crm.inspect()["calls"]) == 1
    assert lab.snapshot()["tasks"][0]["state"] == "COMPLETE"


def test_unknown_never_means_failed_or_no_effect(lab: Lab) -> None:
    lab.scenarios.reset("unprovable")
    complete(lab)
    data = lab.snapshot()
    assert data["orders"][0]["state"] == "MANUAL_REVIEW"
    assert data["fences"][0]["state"] == "UNKNOWN"
    assert data["external"]["orders"][0]["status"] == "DONE"
    assert not any(r["kind"] == "FULFILL" for r in data["receipts"])


def test_stale_read_is_not_confirmation(lab: Lab) -> None:
    lab.scenarios.reset("delayed")
    until(lab, OrderState.CONFIRMING)
    lab.engine.step("DEMO-1001")
    assert lab.orders.get("DEMO-1001")["state"] == "CONFIRMING"
    assert not any(r["kind"] == "FULFILL" for r in lab.snapshot()["receipts"])


def test_delayed_visibility_can_confirm_within_policy(lab: Lab) -> None:
    lab.scenarios.reset("delayed")
    complete(lab)
    assert lab.orders.get("DEMO-1001")["read_attempts"] == 2
    assert not lab.snapshot()["tasks"]


def test_exact_tracking_is_required(lab: Lab) -> None:
    until(lab, OrderState.CONFIRMING)
    with lab.provider_db.transaction() as tx:
        tx.execute("UPDATE crm_orders SET tracking='OTHER-SYNTHETIC-TRACKING'")
    complete(lab)
    assert lab.orders.get("DEMO-1001")["state"] == "MANUAL_REVIEW"


def test_wrong_warehouse_cannot_confirm(lab: Lab) -> None:
    until(lab, OrderState.CONFIRMING)
    with lab.provider_db.transaction() as tx:
        tx.execute("UPDATE crm_orders SET warehouse_id='WRONG-WH'")
    complete(lab)
    assert lab.orders.get("DEMO-1001")["state"] == "MANUAL_REVIEW"


def test_provider_commit_precedes_local_inventory_settlement(lab: Lab) -> None:
    lab.scenarios.reset("completion_lost")
    until(lab, OrderState.UNKNOWN)
    data = lab.snapshot()
    assert all(r["fulfilled"] == 0 for r in data["inventory"])
    assert all(r["fulfilled"] > 0 for r in data["external"]["inventory"])
    complete(lab)
    assert lab.snapshot()["inventory"] == lab.crm.inspect()["inventory"]
