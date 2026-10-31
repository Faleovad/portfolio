from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class OrderState(StrEnum):
    DISCOVERED = "DISCOVERED"
    VALIDATED = "VALIDATED"
    CREATED = "CREATED"
    RESERVED = "RESERVED"
    MUTATION_PENDING = "MUTATION_PENDING"
    CONFIRMING = "CONFIRMING"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"
    CONFIRMED = "CONFIRMED"
    DONE = "DONE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class JournalState(StrEnum):
    PREPARED = "PREPARED"
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"


class TaskState(StrEnum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    COMPLETE = "COMPLETE"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Operation(StrEnum):
    CREATE = "CREATE"
    FULFILL = "FULFILL"


class FaultMode(StrEnum):
    BEFORE_COMMIT = "BEFORE_COMMIT"
    COMMIT_THEN_TIMEOUT = "COMMIT_THEN_TIMEOUT"
    HTTP_ERROR = "HTTP_ERROR"
    DELAY_VISIBILITY = "DELAY_VISIBILITY"
    FAIL_READBACK = "FAIL_READBACK"
    INTERRUPT = "INTERRUPT"
    LOSE_ACK = "LOSE_ACK"
    STALE_RESPONSE = "STALE_RESPONSE"


@dataclass(frozen=True)
class Line:
    sku: str
    quantity: int

    def __post_init__(self) -> None:
        if not self.sku.strip() or type(self.quantity) is not int or self.quantity <= 0:
            raise ValueError("Lines require a nonempty SKU and positive integer quantity")


@dataclass(frozen=True)
class FaultSpec:
    point: str
    mode: FaultMode
    times: int = 1
    delay_reads: int = 0


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    expected: OrderState
    lines: tuple[Line, ...] = (Line("KIT-DESK", 1),)
    faults: tuple[FaultSpec, ...] = ()
    stock: int = 12
    invalid_rules: bool = False

    def public(self) -> dict[str, Any]:
        return asdict(self)
