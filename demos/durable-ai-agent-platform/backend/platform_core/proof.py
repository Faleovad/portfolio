from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from .errors import ProofMismatch


class ObservationState(StrEnum):
    COMMITTED = "COMMITTED"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"


@dataclass(frozen=True)
class EffectIdentity:
    tenant_id: UUID
    intent_id: UUID
    external_identity: str
    payload_fingerprint: str
    idempotency_key: str
    tool: str = "crm"


@dataclass(frozen=True)
class Observation:
    state: ObservationState
    identity: EffectIdentity | None = None
    provider_revision: int | None = None
    authoritative_absence: bool = False


@dataclass(frozen=True)
class Receipt:
    identity: EffectIdentity
    provider_revision: int
    observation_fingerprint: str


def confirm(expected: EffectIdentity, observation: Observation, proof_hash: str) -> Receipt:
    if observation.state != ObservationState.COMMITTED:
        raise ProofMismatch("no committed observation")
    if observation.identity != expected:
        raise ProofMismatch("tenant, intent, payload or external identity differs")
    revision = observation.provider_revision
    if revision is None or revision < 1 or not proof_hash:
        raise ProofMismatch("missing provider revision or proof fingerprint")
    return Receipt(expected, revision, proof_hash)
