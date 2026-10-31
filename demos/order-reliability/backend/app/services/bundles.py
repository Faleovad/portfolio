from collections import Counter

from ..domain.errors import LabError
from ..domain.models import Line

DEFAULT_RULES: dict[str, tuple[Line, ...]] = {
    "KIT-DESK": (Line("KIT-CORE", 1), Line("CABLE", 2)),
    "KIT-CORE": (Line("SENSOR", 2), Line("CABLE", 1)),
}
CATALOG = frozenset({"SENSOR", "CABLE"})
MAX_QUANTITY = 1_000_000


class Bundles:
    def __init__(self, rules: dict[str, tuple[Line, ...]] | None = None) -> None:
        self.rules = DEFAULT_RULES if rules is None else rules

    def expand(self, lines: list[dict]) -> list[dict]:
        """Expand recursively with path-local cycle detection and deterministic aggregation."""
        result: Counter[str] = Counter()

        def visit(line: Line, path: tuple[str, ...]) -> None:
            if len(path) >= 12 or line.sku in path:
                raise LabError("invalid_bundle", "Bundle recursion or maximum nesting exceeded")
            if line.quantity > MAX_QUANTITY:
                raise LabError("invalid_quantity", "Bundle quantity exceeds the bounded domain")
            if line.sku in self.rules:
                components = self.rules[line.sku]
                if not components:
                    raise LabError("invalid_bundle", "Bundle has no components")
                for component in components:
                    visit(
                        Line(component.sku, component.quantity * line.quantity), (*path, line.sku)
                    )
            elif line.sku in CATALOG:
                result[line.sku] += line.quantity
                if result[line.sku] > MAX_QUANTITY:
                    raise LabError("invalid_quantity", "Aggregated quantity exceeds domain")
            else:
                raise LabError("unknown_sku", "Cannot resolve every component")

        if not lines:
            raise LabError("empty_order", "An order needs at least one line")
        for raw in lines:
            visit(Line(**raw), ())
        return [{"sku": sku, "quantity": qty} for sku, qty in sorted(result.items())]
