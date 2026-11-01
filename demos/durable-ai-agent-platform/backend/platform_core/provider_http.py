from dataclasses import asdict

import httpx

from .errors import ProofMismatch
from .proof import EffectIdentity, Observation, ObservationState
from .provider import ProviderResponseLost, ProviderWriter
from .tool_contracts import TOOLS


class HTTPProviderWriter(ProviderWriter):
    """No database writer DSN; transport failure remains ambiguous and is never retried."""

    def __init__(self, url: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url, self.transport = url, transport

    async def dispatch(
        self,
        identity: EffectIdentity,
        payload: dict[str, object],
        tool: str = "crm",
        response_lost: bool = False,
        timeout_before_commit: bool = False,
        visibility_delay: float = 0,
        error_before_commit: bool = False,
        error_after_commit: bool = False,
    ) -> Observation:
        if tool not in TOOLS or TOOLS[tool].read_only or tool != identity.tool:
            raise ProofMismatch("unsupported synthetic tool")
        body = {key: str(value) for key, value in asdict(identity).items()}
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=10) as client:
                response = await client.post(
                    self.url + "/dispatch",
                    headers={"X-Lab-Service": "synthetic-only-lab"},
                    json={
                        **body,
                        "payload": payload,
                        "response_lost": response_lost,
                        "timeout_before_commit": timeout_before_commit,
                        "visibility_delay": visibility_delay,
                        "error_before_commit": error_before_commit,
                        "error_after_commit": error_after_commit,
                    },
                )
        except httpx.TransportError as error:
            raise ProviderResponseLost("synthetic provider transport unconfirmed") from error
        if response.status_code == 504:
            raise ProviderResponseLost("synthetic provider result unconfirmed")
        if response.status_code != 200:
            raise ProofMismatch("synthetic provider rejected request")
        result = response.json()
        return Observation(ObservationState(result["state"]), identity, result["provider_revision"])
