"""The five original synthetic tools. No tool can address real external resources."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

ToolName = Literal["search", "crm", "quota", "email", "http"]


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchPayload(Payload):
    query: str = Field(min_length=1, max_length=1000)


class CRMPayload(Payload):
    name: str = Field(min_length=1, max_length=1000)
    entity_key: str | None = Field(default=None, min_length=1, max_length=100)
    operation: Literal["create", "update"] = "create"


class QuotaPayload(Payload):
    account: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    delta: str = Field(pattern=r"^-?[1-9][0-9]{0,5}$")

    @field_validator("delta")
    @classmethod
    def bounded_units(cls, value: str) -> str:
        if abs(int(value)) > 100000:
            raise ValueError("synthetic quota adjustment exceeds bound")
        return value


class EmailPayload(Payload):
    recipient_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=1000)
    message_key: str | None = Field(default=None, min_length=1, max_length=100)


class HTTPPayload(Payload):
    method: Literal["POST", "PUT"]
    path: str = Field(pattern=r"^/synthetic/[a-zA-Z0-9_-]{1,64}$")
    body: str = Field(min_length=1, max_length=1000)


@dataclass(frozen=True)
class ToolSpec:
    read_only: bool
    payload_type: type[Payload]
    identity: str


TOOLS: dict[str, ToolSpec] = {
    "search": ToolSpec(True, SearchPayload, "query fingerprint / immutable catalog record IDs"),
    "crm": ToolSpec(False, CRMPayload, "tenant + entity_key; create/update"),
    "quota": ToolSpec(False, QuotaPayload, "tenant + account; integer delta"),
    "email": ToolSpec(False, EmailPayload, "tenant + message_key; synthetic inbox delivery"),
    "http": ToolSpec(False, HTTPPayload, "tenant + synthetic path; POST/PUT resource"),
}


def validate_payload(tool: str, payload: dict[str, object]) -> Payload:
    if tool not in TOOLS:
        raise ValueError("unknown synthetic tool")
    try:
        return TOOLS[tool].payload_type.model_validate(payload)
    except ValidationError as error:
        raise ValueError("invalid " + tool + " payload") from error
