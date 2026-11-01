import hashlib
import json
from dataclasses import dataclass
from uuid import UUID

from .errors import TenantDenied


def fingerprint(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def idempotency_identity(tenant_id: UUID, task_id: UUID, sequence: int) -> str:
    if sequence < 0:
        raise ValueError("negative step sequence")
    return hashlib.sha256(f"{tenant_id}:{task_id}:{sequence}".encode()).hexdigest()


@dataclass(frozen=True)
class TenantScope:
    tenant_id: UUID

    def require(self, resource_tenant_id: UUID) -> None:
        if resource_tenant_id != self.tenant_id:
            # Avoid revealing whether the requested foreign object exists.
            raise TenantDenied("resource unavailable")
