from itertools import product

import pytest
from platform_core.errors import InvalidTransition
from platform_core.state import (
    INTENT_EDGES,
    RECOVERY_EDGES,
    STEP_EDGES,
    TASK_EDGES,
    IntentState,
    RecoveryState,
    StepState,
    TaskState,
    cancellation_target,
    intent_transition,
    recovery_transition,
    step_transition,
    task_transition,
)


@pytest.mark.parametrize("source,target", list(product(TaskState, repeat=2)))
def test_task_transition_matrix(source: TaskState, target: TaskState) -> None:
    if target in TASK_EDGES.get(source, frozenset()):
        task_transition(source, target)
    else:
        with pytest.raises(InvalidTransition):
            task_transition(source, target)


@pytest.mark.parametrize("source,target", list(product(IntentState, repeat=2)))
def test_intent_transition_matrix(source: IntentState, target: IntentState) -> None:
    if target in INTENT_EDGES.get(source, frozenset()):
        intent_transition(source, target)
    else:
        with pytest.raises(InvalidTransition):
            intent_transition(source, target)


@pytest.mark.parametrize("source,target", list(product(StepState, repeat=2)))
def test_step_transition_matrix(source: StepState, target: StepState) -> None:
    if target in STEP_EDGES.get(source, frozenset()):
        step_transition(source, target)
    else:
        with pytest.raises(InvalidTransition):
            step_transition(source, target)


@pytest.mark.parametrize("source,target", list(product(RecoveryState, repeat=2)))
def test_recovery_transition_matrix(source: RecoveryState, target: RecoveryState) -> None:
    if target in RECOVERY_EDGES.get(source, frozenset()):
        recovery_transition(source, target)
    else:
        with pytest.raises(InvalidTransition):
            recovery_transition(source, target)


def test_unknown_never_reopens_prepared() -> None:
    with pytest.raises(InvalidTransition):
        intent_transition(IntentState.UNKNOWN, IntentState.PREPARED)


def test_confirmed_receipt_has_no_dispatch_transition() -> None:
    assert IntentState.CONFIRMED not in INTENT_EDGES


def test_cancellation_preserves_uncertainty() -> None:
    assert cancellation_target(True) == TaskState.CANCEL_REQUESTED
    assert cancellation_target(False) == TaskState.CANCELLED
