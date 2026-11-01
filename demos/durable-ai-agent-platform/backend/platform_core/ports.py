from typing import Protocol

from .proof import EffectIdentity, Observation, Receipt


class ReadOnlyToolPort(Protocol):
    async def observe(self, identity: EffectIdentity) -> Observation: ...


class MutationToolPort(Protocol):
    async def dispatch(
        self, identity: EffectIdentity, payload: dict[str, object]
    ) -> Observation: ...


class RecoveryRepository(Protocol):
    async def record_attempt(self, identity: EffectIdentity) -> int:
        """Atomically consume a durable recovery budget and return its attempt ordinal."""
        ...

    async def receipt(self, identity: EffectIdentity) -> Receipt | None: ...

    async def confirm(self, identity: EffectIdentity, receipt: Receipt) -> None:
        """CAS the intent and insert the unique immutable receipt in one transaction."""
        ...

    async def defer(self, identity: EffectIdentity, reason: str) -> None: ...

    async def review(self, identity: EffectIdentity, reason: str) -> None: ...
