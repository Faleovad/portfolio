from dataclasses import dataclass, replace
from datetime import datetime

from .errors import BudgetExceeded


@dataclass(frozen=True)
class Limits:
    model_calls: int = 8
    tool_calls: int = 8
    steps: int = 24
    estimated_tokens: int = 16000
    estimated_cost_micros: int = 2000000
    recovery_attempts: int = 12

    def __post_init__(self) -> None:
        if any(value < 0 for value in vars(self).values()):
            raise ValueError("negative budget")


@dataclass(frozen=True)
class Usage:
    model_calls: int = 0
    tool_calls: int = 0
    steps: int = 0
    estimated_tokens: int = 0
    estimated_cost_micros: int = 0
    recovery_attempts: int = 0

    def reserve(self, limits: Limits, dimension: str, amount: int = 1) -> "Usage":
        if dimension not in vars(self) or amount < 0:
            raise ValueError("invalid reservation")
        updated = getattr(self, dimension) + amount
        if updated > getattr(limits, dimension):
            raise BudgetExceeded(dimension)
        return replace(self, **{dimension: updated})

    def assert_deadline(self, now: datetime, deadline: datetime) -> None:
        if now.tzinfo is None or deadline.tzinfo is None:
            raise ValueError("timezone-aware logical clock required")
        if now >= deadline:
            raise BudgetExceeded("logical execution deadline")
