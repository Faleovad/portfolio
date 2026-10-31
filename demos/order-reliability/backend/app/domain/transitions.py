from .errors import LabError
from .models import OrderState as S

TRANSITIONS: dict[S, frozenset[S]] = {
    S.DISCOVERED: frozenset({S.VALIDATED, S.MANUAL_REVIEW}),
    S.VALIDATED: frozenset({S.CREATED, S.UNKNOWN, S.MANUAL_REVIEW}),
    S.CREATED: frozenset({S.RESERVED, S.MANUAL_REVIEW}),
    S.RESERVED: frozenset({S.MUTATION_PENDING}),
    S.MUTATION_PENDING: frozenset({S.CONFIRMING, S.UNKNOWN}),
    S.CONFIRMING: frozenset({S.CONFIRMED, S.UNKNOWN}),
    S.UNKNOWN: frozenset({S.RECONCILING}),
    S.RECONCILING: frozenset({S.CREATED, S.CONFIRMED, S.MANUAL_REVIEW}),
    S.CONFIRMED: frozenset({S.DONE}),
    S.DONE: frozenset(),
    S.MANUAL_REVIEW: frozenset(),
}


def require_transition(current: S, target: S) -> None:
    if target not in TRANSITIONS[current]:
        raise LabError("invalid_transition", f"Rejected {current} -> {target}")
