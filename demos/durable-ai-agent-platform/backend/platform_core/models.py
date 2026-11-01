import asyncio
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from .schemas import ModelOutput
from .tool_contracts import ToolName


@dataclass(frozen=True)
class ModelRequest:
    instructions: str
    objective: str
    untrusted_context: tuple[dict[str, object], ...]
    requested_tool: bool = False
    requested_tool_name: ToolName = "crm"


class ModelProvider(Protocol):
    async def generate(self, request: ModelRequest, mode: str = "none") -> str: ...


class DeterministicModel:
    """No network or API key. Retrieved text is data, never parsed as authority."""

    async def generate(self, request: ModelRequest, mode: str = "none") -> str:
        await asyncio.sleep(0)
        if mode == "model_timeout":
            raise TimeoutError("synthetic model timeout")
        if mode == "malformed_model_output":
            return '{"decision":'
        excerpts = [str(hit["content"])[:240] for hit in request.untrusted_context]
        output = ModelOutput(
            decision="review" if mode == "manual_review_required" else "continue",
            confidence=0.8 if excerpts else 0.3,
            answer="Evidence summary: " + " | ".join(excerpts)
            if excerpts
            else "No supporting documents found.",
            citations=[
                UUID(str(hit["hit_id"])) for hit in request.untrusted_context
            ],  # Pydantic parses UUIDs.
            tool_requests=[request.requested_tool_name] if request.requested_tool else [],
            reason_codes=["UNTRUSTED_CONTEXT_DATA_ONLY"],
        )
        return output.model_dump_json()
