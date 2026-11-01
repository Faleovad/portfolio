from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from platform_core.budgets import Limits, Usage
from platform_core.errors import (
    BudgetExceeded,
    OwnershipLost,
    ProofMismatch,
    TenantDenied,
)
from platform_core.identity import TenantScope, fingerprint, idempotency_identity
from platform_core.ownership import transfer
from platform_core.proof import EffectIdentity, Observation, ObservationState, confirm


def test_active_lease_cannot_be_stolen() -> None:
    now = datetime.now(UTC)
    lease = transfer(None, "worker-a", now, timedelta(seconds=10))
    with pytest.raises(OwnershipLost):
        transfer(lease, "worker-b", now, timedelta(seconds=10))


def test_expiry_transfers_fence_and_rejects_stale_writer() -> None:
    now = datetime.now(UTC)
    original = transfer(None, "a", now, timedelta(seconds=1))
    current = transfer(original, "b", now + timedelta(seconds=2), timedelta(seconds=10))
    assert current.revision == original.revision + 1
    assert current.token != original.token
    with pytest.raises(OwnershipLost):
        current.assert_valid(original.token, original.revision, now + timedelta(seconds=2))


def test_heartbeat_does_not_resurrect_expired_owner() -> None:
    now = datetime.now(UTC)
    lease = transfer(None, "a", now, timedelta(seconds=1))
    with pytest.raises(OwnershipLost):
        lease.heartbeat(
            lease.token, lease.revision, now + timedelta(seconds=1), timedelta(seconds=10)
        )


def test_payload_fingerprint_canonicalizes_keys() -> None:
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})
    assert fingerprint({"a": 1}) != fingerprint({"a": "1"})


def test_fingerprint_rejects_nan() -> None:
    with pytest.raises(ValueError):
        fingerprint({"value": float("nan")})


def test_tenant_is_in_idempotency_identity() -> None:
    task = uuid4()
    assert idempotency_identity(uuid4(), task, 1) != idempotency_identity(uuid4(), task, 1)


def test_foreign_resource_denied() -> None:
    scope = TenantScope(uuid4())
    with pytest.raises(TenantDenied):
        scope.require(uuid4())
    scope.require(scope.tenant_id)


@pytest.mark.parametrize("dimension", list(vars(Usage())))
def test_retry_cannot_bypass_each_budget_dimension(dimension: str) -> None:
    limits = Limits()
    usage = Usage()
    reserved = usage.reserve(limits, dimension, getattr(limits, dimension))
    with pytest.raises(BudgetExceeded):
        reserved.reserve(limits, dimension)
    assert getattr(usage, dimension) == 0


def test_logical_deadline_is_inclusive() -> None:
    now = datetime.now(UTC)
    with pytest.raises(BudgetExceeded):
        Usage().assert_deadline(now, now)


@pytest.mark.parametrize(
    "field",
    [
        "tenant_id",
        "intent_id",
        "external_identity",
        "payload_fingerprint",
        "idempotency_key",
        "tool",
    ],
)
def test_proof_requires_exact_identity_match(field: str) -> None:
    expected = EffectIdentity(uuid4(), uuid4(), "crm:entity", "hash", "key")
    value = uuid4() if field.endswith("_id") else "different"
    actual = replace(expected, **{field: value})
    observation = Observation(ObservationState.COMMITTED, actual, 1)
    with pytest.raises(ProofMismatch):
        confirm(expected, observation, "proof")


@pytest.mark.parametrize(
    "state",
    [
        ObservationState.NOT_FOUND,
        ObservationState.UNAVAILABLE,
        ObservationState.STALE,
    ],
)
def test_observation_is_not_commit_proof(state: ObservationState) -> None:
    identity = EffectIdentity(uuid4(), uuid4(), "entity", "hash", "key")
    with pytest.raises(ProofMismatch):
        confirm(identity, Observation(state), "proof")
