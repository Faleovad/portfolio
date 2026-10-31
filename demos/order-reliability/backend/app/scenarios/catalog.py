from ..domain.models import FaultMode as F
from ..domain.models import FaultSpec as Fault
from ..domain.models import Line, Scenario
from ..domain.models import OrderState as S

SCENARIOS = (
    Scenario(
        "happy",
        "Normal fulfillment",
        "Nested bundle, component reserve, one confirmed completion.",
        S.DONE,
    ),
    Scenario(
        "simple",
        "Single SKU",
        "The same pipeline without a bundle parent.",
        S.DONE,
        lines=(Line("SENSOR", 1),),
    ),
    Scenario(
        "insufficient",
        "Insufficient components",
        "One component cannot be reserved. No partial reserve.",
        S.MANUAL_REVIEW,
        stock=1,
    ),
    Scenario(
        "create_lost",
        "CREATE committed, response lost",
        "Recovery finds the exact provider order; no second CREATE.",
        S.DONE,
        faults=(Fault("create", F.COMMIT_THEN_TIMEOUT),),
    ),
    Scenario(
        "completion_lost",
        "Completion committed, response lost",
        "Provider stock changes while ERP still knows UNKNOWN.",
        S.DONE,
        faults=(Fault("fulfill", F.COMMIT_THEN_TIMEOUT),),
    ),
    Scenario(
        "before_commit",
        "Timeout before external commit",
        "Looks uncertain to the ERP, but the provider made no change.",
        S.MANUAL_REVIEW,
        faults=(Fault("fulfill", F.BEFORE_COMMIT),),
    ),
    Scenario(
        "http_error",
        "Provider HTTP error",
        "A failed response does not authorize a new mutation intent.",
        S.MANUAL_REVIEW,
        faults=(Fault("fulfill", F.HTTP_ERROR),),
    ),
    Scenario(
        "delayed",
        "Delayed visibility",
        "Two stale provider reads, then exact confirmation within policy.",
        S.DONE,
        faults=(Fault("fulfill", F.DELAY_VISIBILITY, delay_reads=2),),
    ),
    Scenario(
        "read_outage",
        "Readback unavailable twice",
        "Reads fail twice; the original mutation is not repeated.",
        S.DONE,
        faults=(Fault("fulfill_read", F.FAIL_READBACK, times=2),),
    ),
    Scenario(
        "stale",
        "Stale response exceeds confirmation budget",
        "Recovery continues observing after the initial read budget.",
        S.DONE,
        faults=(Fault("fulfill_read", F.STALE_RESPONSE, times=4),),
    ),
    Scenario(
        "interrupt_create",
        "Interrupt after external CREATE",
        "Local journal is SENT; restart must observe, never resend.",
        S.DONE,
        faults=(Fault("after_create", F.INTERRUPT),),
    ),
    Scenario(
        "interrupt_fence",
        "Interrupt after fence preparation",
        "A prepared but unsent intent remains dispatchable once.",
        S.DONE,
        faults=(Fault("after_fence", F.INTERRUPT),),
    ),
    Scenario(
        "lost_ack",
        "Lose final acknowledgement",
        "Receipt and local settlement commit before the caller loses its reply.",
        S.DONE,
        faults=(Fault("after_finish", F.LOSE_ACK),),
    ),
    Scenario(
        "unprovable",
        "Committed but not provable",
        "Provider commits, but visibility remains stale beyond all bounded reads.",
        S.MANUAL_REVIEW,
        faults=(Fault("fulfill", F.COMMIT_THEN_TIMEOUT, delay_reads=100),),
    ),
    Scenario(
        "invalid_bundle",
        "Cyclic bundle rule",
        "Validation rejects the whole plan before external creation.",
        S.MANUAL_REVIEW,
        invalid_rules=True,
    ),
)
BY_ID = {scenario.id: scenario for scenario in SCENARIOS}
