from typing import Protocol


class ProviderReader(Protocol):
    """The only provider capability available to confirmation and reconciliation."""

    def read(self, external_id: str, point: str) -> dict | None: ...


class ProviderWriter(ProviderReader, Protocol):
    def create(self, order: dict, intent: str) -> dict: ...

    def fulfill(self, order: dict, intent: str) -> dict: ...
