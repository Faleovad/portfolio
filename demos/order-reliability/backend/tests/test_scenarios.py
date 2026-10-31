import pytest

from app.container import Lab
from app.scenarios.catalog import SCENARIOS, Scenario
from conftest import complete


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_every_executable_scenario_reaches_its_declared_outcome(
    lab: Lab, scenario: Scenario
) -> None:
    lab.scenarios.reset(scenario.id)
    assert complete(lab)["state"] == scenario.expected
    data = lab.snapshot()
    assert len(data["external"]["orders"]) <= 1
    for operation in ("CREATE", "FULFILL"):
        assert sum(c["operation"] == operation for c in data["external"]["calls"]) <= 1
    for owner in (data["inventory"], data["external"]["inventory"]):
        assert all(row["available"] == row["on_hand"] - row["reserved"] >= 0 for row in owner)
    if scenario.expected == "DONE":
        assert data["inventory"] == data["external"]["inventory"]
        assert {r["kind"] for r in data["receipts"]} == {"CREATE", "FULFILL"}


def test_insufficient_stock_has_no_partial_reserve_or_create(lab: Lab) -> None:
    lab.scenarios.reset("insufficient")
    complete(lab)
    snapshot = lab.snapshot()
    assert snapshot["reservations"] == []
    assert snapshot["external"]["calls"] == []
    assert all(row["reserved"] == 0 for row in snapshot["inventory"])


def test_reset_restores_known_state_but_not_event_sequence_reuse(lab: Lab) -> None:
    complete(lab)
    previous_sequence = lab.events()[-1]["sequence"]
    lab.scenarios.reset("happy")
    data = lab.snapshot()
    assert data["orders"][0]["state"] == "DISCOVERED"
    assert not data["receipts"] and not data["external"]["calls"]
    assert data["events"][0]["sequence"] > previous_sequence
