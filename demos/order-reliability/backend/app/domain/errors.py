class LabError(Exception):
    """Application error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


class ExternalUncertain(LabError):
    def __init__(self, message: str) -> None:
        super().__init__("external_outcome_unknown", message, 503)


class ReadUnavailable(LabError):
    def __init__(self) -> None:
        super().__init__("read_unavailable", "Injected provider read failure", 503)


class ProviderHTTPError(LabError):
    def __init__(self) -> None:
        super().__init__("provider_http_error", "Simulated upstream HTTP 500 response", 502)


class SimulatedInterruption(LabError):
    def __init__(self, point: str) -> None:
        super().__init__("simulated_interruption", f"Execution interrupted at {point}", 503)
