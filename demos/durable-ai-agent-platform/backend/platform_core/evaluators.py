from dataclasses import dataclass
from typing import Any

from .schemas import ModelOutput


@dataclass(frozen=True)
class EvaluationResult:
    evaluator: str
    passed: bool
    details: dict[str, object]


def evaluate(
    raw: dict[str, Any],
    hits: list[dict[str, Any]],
    allowlist: list[str],
    expected_keywords: list[str],
    unresolved: int,
) -> list[EvaluationResult]:
    output = ModelOutput.model_validate(raw)
    valid_ids = {str(hit["id"]) for hit in hits}
    cited = {str(value) for value in output.citations}
    citation_ok = cited <= valid_ids and (not hits or bool(cited))
    tools_ok = set(output.tool_requests) <= set(allowlist)
    expected_ok = all(word.casefold() in output.answer.casefold() for word in expected_keywords)
    return [
        EvaluationResult("schema", True, {"schema": "ModelOutput"}),
        EvaluationResult(
            "citation", citation_ok, {"cited": len(cited), "available": len(valid_ids)}
        ),
        EvaluationResult(
            "tool_use", tools_ok, {"requested": output.tool_requests, "allowed": allowlist}
        ),
        EvaluationResult("expected_result", expected_ok, {"keyword_count": len(expected_keywords)}),
        EvaluationResult("invariant", unresolved == 0, {"unresolved_intents": unresolved}),
    ]
