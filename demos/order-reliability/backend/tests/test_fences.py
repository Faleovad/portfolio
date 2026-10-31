import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.container import Lab
from app.domain.errors import LabError
from app.domain.models import JournalState, OrderState
from conftest import complete, until


def test_concurrent_create_journal_claim_has_one_dispatch_winner(lab: Lab) -> None:
    order = until(lab, OrderState.VALIDATED)

    def claim() -> bool:
        lab.journal.prepare(order)
        try:
            lab.journal.mark_sent(order["external_id"])
            return True
        except LabError:
            return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        assert sum(pool.map(lambda _: claim(), range(6))) == 1
    assert len(lab.snapshot()["journals"]) == 1


def test_create_identity_conflict_is_not_a_second_intent(lab: Lab) -> None:
    order = until(lab, OrderState.VALIDATED)
    lab.journal.prepare(order)
    order["components"][0]["quantity"] += 1
    with pytest.raises(LabError, match="different intent"):
        lab.journal.prepare(order)


def test_expired_unknown_mutation_fence_does_not_reopen(lab: Lab) -> None:
    lab.scenarios.reset("completion_lost")
    until(lab, OrderState.UNKNOWN)
    fence = lab.snapshot()["fences"][0]
    with lab.db.transaction() as tx:
        tx.execute("UPDATE mutation_fences SET lease_until=0")
    with pytest.raises(LabError, match="cannot be dispatched"):
        lab.fence.dispatch(fence["intent_id"], "stale-replayer", time.time() + 30)
    assert fence["state"] == JournalState.UNKNOWN


def test_terminal_receipt_blocks_stale_dispatch(lab: Lab) -> None:
    complete(lab)
    fence = lab.snapshot()["fences"][0]
    with pytest.raises(LabError, match="cannot be dispatched"):
        lab.fence.dispatch(fence["intent_id"], "new-owner", time.time() + 30)
    assert len(lab.snapshot()["external"]["calls"]) == 2


def test_repeat_terminal_endpoint_has_no_stock_effect(lab: Lab) -> None:
    complete(lab)
    before = lab.crm.inspect()
    for _ in range(5):
        assert lab.engine.run("DEMO-1001")["state"] == "DONE"
    assert lab.crm.inspect() == before


def test_event_order_records_intent_before_provider_dispatch(lab: Lab) -> None:
    complete(lab)
    events = lab.events()
    prepared = next(e["sequence"] for e in events if e["event"] == "intent_prepared")
    sent = next(e["sequence"] for e in events if e["event"] == "external_create_dispatched")
    confirmed = next(e["sequence"] for e in events if e["event"] == "effect_confirmed")
    assert prepared < sent < confirmed
