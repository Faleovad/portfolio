from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from .errors import OwnershipLost


@dataclass(frozen=True)
class Ownership:
    worker: str
    token: UUID
    revision: int
    expires_at: datetime

    def assert_valid(self, token: UUID, revision: int, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("ownership clock must be timezone-aware")
        if token != self.token or revision != self.revision or now >= self.expires_at:
            raise OwnershipLost("lease expired or fencing token/revision mismatch")

    def heartbeat(self, token: UUID, revision: int, now: datetime, ttl: timedelta) -> "Ownership":
        self.assert_valid(token, revision, now)
        if ttl.total_seconds() <= 0:
            raise ValueError("positive lease duration required")
        return replace(self, expires_at=now + ttl)


def transfer(previous: Ownership | None, worker: str, now: datetime, ttl: timedelta) -> Ownership:
    if now.tzinfo is None or ttl.total_seconds() <= 0 or not worker.strip():
        raise ValueError("invalid claim arguments")
    if previous is not None and now < previous.expires_at:
        raise OwnershipLost("another valid owner holds the lease")
    return Ownership(
        worker=worker,
        token=uuid4(),
        revision=1 if previous is None else previous.revision + 1,
        expires_at=now + ttl,
    )
