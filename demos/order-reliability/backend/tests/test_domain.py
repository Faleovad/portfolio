import pytest

from app.domain.errors import LabError
from app.domain.models import Line
from app.domain.models import OrderState as S
from app.domain.transitions import require_transition
from app.services.bundles import Bundles


def test_nested_bundle_aggregates_shared_components() -> None:
    assert Bundles().expand([{"sku": "KIT-DESK", "quantity": 2}]) == [
        {"sku": "CABLE", "quantity": 6},
        {"sku": "SENSOR", "quantity": 4},
    ]


def test_component_output_is_deterministic() -> None:
    first = [{"sku": "SENSOR", "quantity": 2}, {"sku": "CABLE", "quantity": 1}]
    assert Bundles().expand(first) == Bundles().expand(list(reversed(first)))


def test_cycle_rejects_whole_rule() -> None:
    with pytest.raises(LabError, match="recursion"):
        Bundles({"A": (Line("B", 1),), "B": (Line("A", 1),)}).expand([{"sku": "A", "quantity": 1}])


def test_unknown_component_rejects_complete_plan() -> None:
    with pytest.raises(LabError, match="resolve"):
        Bundles({"KIT": (Line("CABLE", 1), Line("MISSING", 1))}).expand(
            [{"sku": "KIT", "quantity": 1}]
        )


def test_quantity_multiplication_is_bounded() -> None:
    with pytest.raises(LabError, match="quantity"):
        Bundles().expand([{"sku": "KIT-DESK", "quantity": 999999}])


@pytest.mark.parametrize("qty", [0, -1, True, 1.5])
def test_invalid_line_quantities(qty: object) -> None:
    with pytest.raises(ValueError):
        Line("CABLE", qty)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "current,target", [(S.UNKNOWN, S.DONE), (S.DONE, S.RESERVED), (S.DISCOVERED, S.CREATED)]
)
def test_invalid_transitions_are_rejected(current: S, target: S) -> None:
    with pytest.raises(LabError, match="Rejected"):
        require_transition(current, target)


def test_unknown_can_enter_reconciliation() -> None:
    require_transition(S.UNKNOWN, S.RECONCILING)
