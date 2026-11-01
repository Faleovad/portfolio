from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .tool_contracts import ToolName, validate_payload


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def reject_null_characters(cls, value: Any) -> Any:
        values = [value]
        if isinstance(value, dict):
            values.extend(value.keys())
            values.extend(value.values())
        if any(isinstance(item, str) and "\x00" in item for item in values):
            raise ValueError("NUL characters are not supported")
        return value


class TenantCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class AgentCreate(StrictModel):
    name: str = Field(min_length=1, max_length=100)


class AgentConfig(StrictModel):
    tools: list[ToolName] = Field(default_factory=list, max_length=5)
    instructions: str = Field(default="Answer using cited evidence.", max_length=2000)
    expected_keywords: list[str] = Field(default_factory=list, max_length=20)
    model: Literal["deterministic"] = "deterministic"
    repair_limit: int = Field(default=2, ge=0, le=3)


class TaskCreate(StrictModel):
    agent_version_id: UUID
    enqueue_key: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=4000)
    tool_payload: dict[str, str] | None = None
    tool_name: ToolName = "crm"
    model_limit: int = Field(default=8, ge=0, le=20)
    tool_limit: int = Field(default=8, ge=0, le=20)
    recovery_limit: int = Field(default=12, ge=0, le=30)
    step_limit: int = Field(default=24, ge=0, le=100)
    token_limit: int = Field(default=16000, ge=0, le=1000000)
    cost_limit: int = Field(default=2000000, ge=0, le=100000000)
    duration_seconds: int = Field(default=3600, ge=1, le=86400)
    lab_controlled: bool = False

    @model_validator(mode="after")
    def tool_contract(self) -> "TaskCreate":
        if self.tool_payload is not None:
            validate_payload(self.tool_name, dict(self.tool_payload))
        return self

    @field_validator("tool_payload")
    @classmethod
    def bounded_payload(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is not None and (
            len(value) > 20 or any(len(k) > 100 or len(v) > 1000 for k, v in value.items())
        ):
            raise ValueError("tool payload too large")
        return value


class DocumentUpload(StrictModel):
    name: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=64000)

    @field_validator("name")
    @classmethod
    def safe_name(cls, value: str) -> str:
        if any(c in value for c in ["/", "\\", "\x00"]) or value in {".", ".."}:
            raise ValueError("filename must be a basename")
        return value

    @field_validator("text")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if "\x00" in value or len(value.encode("utf-8")) > 64000:
            raise ValueError("invalid or oversized document")
        return value


class SearchQuery(StrictModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)


class ModelOutput(StrictModel):
    decision: Literal["continue", "review"]
    confidence: float = Field(ge=0, le=1)
    answer: str = Field(min_length=1, max_length=10000)
    citations: list[UUID] = Field(max_length=20)
    tool_requests: list[ToolName] = Field(default_factory=list, max_length=1)
    reason_codes: list[str] = Field(max_length=10)


class FaultRequest(StrictModel):
    mode: str = Field(min_length=1, max_length=80)
    remaining: int = Field(default=1, ge=1, le=10)


class ReviewAction(StrictModel):
    action: Literal["reconcile", "acknowledge"]
    note: str = Field(min_length=1, max_length=1000)
