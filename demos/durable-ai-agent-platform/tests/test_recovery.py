from uuid import uuid4

import pytest
from platform_core.errors import BudgetExceeded
from platform_core.proof import EffectIdentity, Observation, ObservationState, Receipt
from platform_core.recovery import RecoveryOutcome, RecoveryPolicy, RecoveryService


class MemoryRecoveryRepository:
    """Unit-test double only; does not claim persistence or concurrent SQL behavior."""

    def __init__(self) -> None:
        self.attempts = 0
        self.confirmed: Receipt | None = None
        self.reason: str | None = None
        self.exhausted = False

    async def record_attempt(self, identity: EffectIdentity) -> int:
        if self.exhausted:
            raise BudgetExceeded("recovery_attempts")
        self.attempts += 1
        return self.attempts

    async def receipt(self, identity: EffectIdentity) -> Receipt | None:
        return self.confirmed

    async def confirm(self, identity: EffectIdentity, receipt: Receipt) -> None:
        self.confirmed = receipt

    async def defer(self, identity: EffectIdentity, reason: str) -> None:
        self.reason = reason

    async def review(self, identity: EffectIdentity, reason: str) -> None:
        self.reason = reason


class Reader:
    def __init__(self, observation: Observation) -> None:
        self.observation = observation
        self.reads = 0

    async def observe(self, identity: EffectIdentity) -> Observation:
        self.reads += 1
        return self.observation


def identity() -> EffectIdentity:
    return EffectIdentity(uuid4(), uuid4(), "synthetic:crm:one", "fingerprint", "key")


async def test_confirmation_and_terminal_receipt_short_circuit() -> None:
    effect = identity()
    reader = Reader(Observation(ObservationState.COMMITTED, effect, 1))
    repository = MemoryRecoveryRepository()
    recovery = RecoveryService(reader, repository, RecoveryPolicy())
    assert await recovery.reconcile(effect) == RecoveryOutcome.CONFIRMED
    assert await recovery.reconcile(effect) == RecoveryOutcome.ALREADY_CONFIRMED
    assert reader.reads == 1
    assert repository.attempts == 1


@pytest.mark.parametrize(
    "state",
    [
        ObservationState.NOT_FOUND,
        ObservationState.UNAVAILABLE,
        ObservationState.STALE,
    ],
)
async def test_missing_outage_or_stale_read_defers_without_replay(state: ObservationState) -> None:
    effect = identity()
    reader = Reader(Observation(state))
    repository = MemoryRecoveryRepository()
    recovery = RecoveryService(reader, repository, RecoveryPolicy(2))
    assert await recovery.reconcile(effect) == RecoveryOutcome.DEFERRED
    assert await recovery.reconcile(effect) == RecoveryOutcome.MANUAL_REVIEW
    assert repository.confirmed is None
    assert not hasattr(reader, "dispatch")


async def test_foreign_provider_identity_cannot_confirm() -> None:
    effect = identity()
    repository = MemoryRecoveryRepository()
    recovery = RecoveryService(
        Reader(Observation(ObservationState.COMMITTED, identity(), 1)),
        repository,
        RecoveryPolicy(),
    )
    assert await recovery.reconcile(effect) == RecoveryOutcome.MANUAL_REVIEW
    assert repository.reason == "provider identity mismatch"
    assert repository.confirmed is None


async def test_durable_budget_rejection_never_calls_provider() -> None:
    effect = identity()
    repository = MemoryRecoveryRepository()
    repository.exhausted = True
    reader = Reader(Observation(ObservationState.COMMITTED, effect, 1))
    recovery = RecoveryService(reader, repository, RecoveryPolicy())
    assert await recovery.reconcile(effect) == RecoveryOutcome.MANUAL_REVIEW
    assert reader.reads == 0
