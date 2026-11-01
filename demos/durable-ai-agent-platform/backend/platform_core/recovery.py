from dataclasses import dataclass
from enum import StrEnum

from .errors import BudgetExceeded, ProofMismatch
from .identity import fingerprint
from .ports import ReadOnlyToolPort, RecoveryRepository
from .proof import EffectIdentity, ObservationState, confirm


class RecoveryOutcome(StrEnum):
    CONFIRMED = "CONFIRMED"
    DEFERRED = "DEFERRED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    ALREADY_CONFIRMED = "ALREADY_CONFIRMED"


@dataclass(frozen=True)
class RecoveryPolicy:
    max_attempts: int = 6

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("recovery needs a positive attempt bound")


class RecoveryService:
    """Read-only provider capability. No mutating tool port is accepted or imported."""

    def __init__(
        self,
        reader: ReadOnlyToolPort,
        repository: RecoveryRepository,
        policy: RecoveryPolicy,
    ) -> None:
        self.reader = reader
        self.repository = repository
        self.policy = policy

    async def reconcile(self, identity: EffectIdentity) -> RecoveryOutcome:
        existing = await self.repository.receipt(identity)
        if existing is not None:
            if existing.identity != identity:
                raise ProofMismatch("terminal receipt identity changed")
            return RecoveryOutcome.ALREADY_CONFIRMED
        try:
            attempt = await self.repository.record_attempt(identity)
        except BudgetExceeded:
            await self.repository.review(identity, "recovery budget exhausted")
            return RecoveryOutcome.MANUAL_REVIEW
        if attempt > self.policy.max_attempts:
            await self.repository.review(identity, "readback policy exhausted")
            return RecoveryOutcome.MANUAL_REVIEW
        observation = await self.reader.observe(identity)
        if observation.state == ObservationState.COMMITTED:
            digest = fingerprint(
                {
                    "provider_revision": observation.provider_revision,
                    "identity": str(observation.identity),
                    "state": observation.state.value,
                }
            )
            try:
                receipt = confirm(identity, observation, digest)
            except ProofMismatch:
                await self.repository.review(identity, "provider identity mismatch")
                return RecoveryOutcome.MANUAL_REVIEW
            await self.repository.confirm(identity, receipt)
            return RecoveryOutcome.CONFIRMED
        # Neither lease expiry nor a missing/stale read permits a second dispatch.
        if attempt == self.policy.max_attempts:
            await self.repository.review(identity, "effect remains unprovable")
            return RecoveryOutcome.MANUAL_REVIEW
        await self.repository.defer(identity, observation.state.value)
        return RecoveryOutcome.DEFERRED
