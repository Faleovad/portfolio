class DomainError(Exception):
    """A rejected domain operation, never an instruction to replay an effect."""


class InvalidTransition(DomainError):
    pass


class OwnershipLost(DomainError):
    pass


class TenantDenied(DomainError):
    pass


class BudgetExceeded(DomainError):
    pass


class ProofMismatch(DomainError):
    pass


class ReplayForbidden(DomainError):
    pass
