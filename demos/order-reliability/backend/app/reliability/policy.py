from dataclasses import dataclass


@dataclass(frozen=True)
class ReadPolicy:
    confirmation_attempts: int = 3
    recovery_attempts: int = 3
    lease_seconds: int = 30

    def exhausted(self, attempts: int, *, recovery: bool = False) -> bool:
        return attempts >= (self.recovery_attempts if recovery else self.confirmation_attempts)
