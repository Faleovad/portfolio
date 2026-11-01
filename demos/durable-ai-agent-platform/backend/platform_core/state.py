from enum import StrEnum

from .errors import InvalidTransition


class TaskState(StrEnum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_MODEL = "WAITING_MODEL"
    WAITING_TOOL = "WAITING_TOOL"
    WAITING_READBACK = "WAITING_READBACK"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class IntentState(StrEnum):
    PREPARED = "PREPARED"
    SENT = "SENT"
    UNKNOWN = "UNKNOWN"
    CONFIRMED = "CONFIRMED"
    PROVEN_NOT_APPLIED = "PROVEN_NOT_APPLIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class StepState(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"
    CANCELLED = "CANCELLED"


class RecoveryState(StrEnum):
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    WAITING = "WAITING"
    CONFIRMED = "CONFIRMED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


TASK_EDGES: dict[TaskState, frozenset[TaskState]] = {
    TaskState.CREATED: frozenset({TaskState.QUEUED, TaskState.CANCELLED}),
    TaskState.QUEUED: frozenset({TaskState.RUNNING, TaskState.CANCELLED}),
    TaskState.RUNNING: frozenset(
        {
            TaskState.WAITING_MODEL,
            TaskState.WAITING_TOOL,
            TaskState.COMPLETED,
            TaskState.FAILED_RETRYABLE,
            TaskState.FAILED_TERMINAL,
            TaskState.MANUAL_REVIEW,
            TaskState.CANCEL_REQUESTED,
            TaskState.BUDGET_EXHAUSTED,
        }
    ),
    TaskState.WAITING_MODEL: frozenset(
        {
            TaskState.RUNNING,
            TaskState.FAILED_RETRYABLE,
            TaskState.MANUAL_REVIEW,
            TaskState.CANCEL_REQUESTED,
            TaskState.BUDGET_EXHAUSTED,
        }
    ),
    TaskState.WAITING_TOOL: frozenset(
        {
            TaskState.WAITING_READBACK,
            TaskState.UNKNOWN,
            TaskState.CANCEL_REQUESTED,
        }
    ),
    TaskState.WAITING_READBACK: frozenset(
        {
            TaskState.RUNNING,
            TaskState.UNKNOWN,
            TaskState.RECOVERING,
            TaskState.CANCEL_REQUESTED,
        }
    ),
    TaskState.UNKNOWN: frozenset(
        {
            TaskState.RECOVERING,
            TaskState.MANUAL_REVIEW,
            TaskState.CANCEL_REQUESTED,
        }
    ),
    TaskState.RECOVERING: frozenset(
        {
            TaskState.BUDGET_EXHAUSTED,
            TaskState.RUNNING,
            TaskState.UNKNOWN,
            TaskState.MANUAL_REVIEW,
            TaskState.CANCEL_REQUESTED,
        }
    ),
    TaskState.FAILED_RETRYABLE: frozenset(
        {
            TaskState.QUEUED,
            TaskState.CANCELLED,
            TaskState.BUDGET_EXHAUSTED,
        }
    ),
    TaskState.CANCEL_REQUESTED: frozenset(
        {
            TaskState.RECOVERING,
            TaskState.CANCELLED,
            TaskState.MANUAL_REVIEW,
        }
    ),
    TaskState.MANUAL_REVIEW: frozenset({TaskState.RECOVERING, TaskState.CANCEL_REQUESTED}),
}
INTENT_EDGES: dict[IntentState, frozenset[IntentState]] = {
    IntentState.PREPARED: frozenset({IntentState.SENT}),
    IntentState.SENT: frozenset({IntentState.UNKNOWN, IntentState.CONFIRMED}),
    IntentState.UNKNOWN: frozenset(
        {
            IntentState.CONFIRMED,
            IntentState.PROVEN_NOT_APPLIED,
            IntentState.MANUAL_REVIEW,
        }
    ),
    IntentState.MANUAL_REVIEW: frozenset(
        {
            IntentState.CONFIRMED,
            IntentState.PROVEN_NOT_APPLIED,
        }
    ),
}
STEP_EDGES: dict[StepState, frozenset[StepState]] = {
    StepState.PENDING: frozenset({StepState.CLAIMED, StepState.CANCELLED}),
    StepState.CLAIMED: frozenset({StepState.RUNNING, StepState.FAILED_RETRYABLE}),
    StepState.RUNNING: frozenset(
        {
            StepState.WAITING,
            StepState.COMPLETED,
            StepState.FAILED_RETRYABLE,
            StepState.FAILED_TERMINAL,
            StepState.CANCELLED,
        }
    ),
    StepState.WAITING: frozenset(
        {
            StepState.COMPLETED,
            StepState.FAILED_TERMINAL,
            StepState.CANCELLED,
        }
    ),
    StepState.FAILED_RETRYABLE: frozenset({StepState.CLAIMED, StepState.CANCELLED}),
}
RECOVERY_EDGES: dict[RecoveryState, frozenset[RecoveryState]] = {
    RecoveryState.PENDING: frozenset({RecoveryState.CLAIMED}),
    RecoveryState.CLAIMED: frozenset(
        {
            RecoveryState.WAITING,
            RecoveryState.CONFIRMED,
            RecoveryState.MANUAL_REVIEW,
        }
    ),
    RecoveryState.WAITING: frozenset({RecoveryState.CLAIMED}),
    RecoveryState.MANUAL_REVIEW: frozenset({RecoveryState.PENDING}),
}


def task_transition(source: TaskState, target: TaskState) -> None:
    if target not in TASK_EDGES.get(source, frozenset()):
        raise InvalidTransition(f"task: {source} -> {target}")


def intent_transition(source: IntentState, target: IntentState) -> None:
    if target not in INTENT_EDGES.get(source, frozenset()):
        raise InvalidTransition(f"intent: {source} -> {target}")


def step_transition(source: StepState, target: StepState) -> None:
    if target not in STEP_EDGES.get(source, frozenset()):
        raise InvalidTransition(f"step: {source} -> {target}")


def recovery_transition(source: RecoveryState, target: RecoveryState) -> None:
    if target not in RECOVERY_EDGES.get(source, frozenset()):
        raise InvalidTransition(f"recovery: {source} -> {target}")


def cancellation_target(has_unresolved_intent: bool) -> TaskState:
    return TaskState.CANCEL_REQUESTED if has_unresolved_intent else TaskState.CANCELLED
