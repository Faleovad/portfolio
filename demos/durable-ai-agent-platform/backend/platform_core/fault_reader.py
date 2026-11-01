from uuid import UUID

from .database import event, transaction
from .faults import FaultEngine
from .proof import EffectIdentity, Observation, ObservationState
from .provider_reader import ProviderReader


class FaultReader:
    """Recovery observations may fail; inspection of provider reality is independent."""

    def __init__(self, dsn: str, reader_dsn: str, task: UUID) -> None:
        self.dsn, self.task = dsn, task
        self.reader = ProviderReader(reader_dsn)
        self.faults = FaultEngine(dsn)

    async def observe(self, identity: EffectIdentity) -> Observation:
        fault = await self.faults.consume(identity.tenant_id, self.task, "readback")
        states = {
            "stale_readback": ObservationState.STALE,
            "readback_outage": ObservationState.UNAVAILABLE,
        }
        observation = (
            Observation(states[fault.mode])
            if fault.mode in states
            else await self.reader.observe(identity)
        )
        async with transaction(self.dsn) as c:
            await event(
                c,
                identity.tenant_id,
                self.task,
                "external_observation",
                {
                    "intent_id": str(identity.intent_id),
                    "state": observation.state.value,
                    "provider_revision": observation.provider_revision,
                },
            )
        await self.faults.checkpoint(identity.tenant_id, self.task, "recovery_observed")
        return observation
