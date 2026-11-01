"""Trace every original numbered section and its checklist items to executed evidence."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Test names are validated against collected successful cases, not merely source text.
RULES = {
    1: ([], [], [], ["tools/metrics.py"]),
    2: (
        ["python", "scenarios"],
        ["test_completed_steps_and_plan_are_not_rebuilt"],
        ["S01", "S06"],
        ["backend/platform_core/executor.py"],
    ),
    3: (
        ["static", "compose", "compose_browser"],
        [],
        [],
        ["pyproject.toml", "compose.yaml", "frontend/package.json"],
    ),
    4: (["python", "scenarios", "browser"], [], [], ["tools/metrics.py"]),
    5: (
        ["python"],
        ["test_research_materializes_all_six_entities_and_provenance"],
        [],
        ["sql/001_orchestrator.sql"],
    ),
    6: (
        ["python", "browser"],
        [
            "test_tenant_api_denies_all_foreign_resources_and_actions",
            "test_cross_tenant_foreign_keys_reject_version_reference",
        ],
        ["S15"],
        ["backend/platform_core/application_repository.py"],
    ),
    7: (
        ["python", "scenarios"],
        ["test_catalog_has_distinct_identifiers_and_complete_contracts"],
        ["S01", "S06", "S19"],
        ["backend/platform_core/state.py", "backend/platform_core/repository.py"],
    ),
    8: (
        ["python"],
        ["test_competing_claims_have_one_owner", "test_expired_owner_cannot_prepare_or_heartbeat"],
        ["S08", "S09"],
        ["backend/platform_core/ownership.py", "backend/platform_core/repository.py"],
    ),
    9: (
        ["python", "scenarios"],
        [
            "test_external_search_observation_and_final_artifact",
            "test_each_tool_HTTP_fault_and_readonly_recovery",
        ],
        ["S42", "S43", "S44", "S45", "S46", "S47", "S48", "S49", "S50", "S51", "S52", "S53"],
        ["docs/TOOL_REQUIREMENTS.json"],
    ),
    10: (
        ["python", "scenarios"],
        ["test_each_tool_HTTP_fault_and_readonly_recovery"],
        ["S03", "S04", "S05", "S10", "S22", "S23", "S25", "S32", "S51", "S52"],
        ["backend/platform_core/provider.py", "backend/platform_core/fault_reader.py"],
    ),
    11: (
        ["python"],
        ["test_intent_payload_is_immutable", "test_intent_tool_identity_is_immutable"],
        ["S04", "S25"],
        ["backend/platform_core/repository.py", "sql/005_tools.sql"],
    ),
    12: (
        ["python"],
        [
            "test_provider_reader_database_role_cannot_insert",
            "test_recovery_worker_has_no_mutating_provider_import",
            "test_provider_reader_role_has_no_domain_mutation_permission",
        ],
        ["S06", "S24"],
        ["backend/platform_core/ports.py", "backend/platform_core/recovery.py"],
    ),
    13: (
        ["python"],
        ["test_fake_timeout_is_explicit_not_empty_success"],
        ["S01"],
        ["backend/platform_core/models.py"],
    ),
    14: (
        ["python"],
        ["test_malformed_model_output_is_bounded_then_reviewed"],
        ["S11", "S12"],
        ["backend/platform_core/schemas.py", "backend/platform_core/executor.py"],
    ),
    15: (
        ["python"],
        ["test_completed_steps_and_plan_are_not_rebuilt"],
        ["S26", "S27"],
        ["backend/platform_core/application_repository.py", "backend/platform_core/executor.py"],
    ),
    16: (
        ["python", "browser"],
        [
            "test_version_pin_survives_publish_and_continuation",
            "test_published_version_database_immutable",
        ],
        ["S20"],
        ["backend/platform_core/application_repository.py"],
    ),
    17: (
        ["python"],
        [
            "test_research_materializes_all_six_entities_and_provenance",
            "test_upload_enforces_utf8_byte_limit",
        ],
        ["S02"],
        ["backend/platform_core/rag.py"],
    ),
    18: (
        ["python", "browser"],
        ["test_synthetic_evaluation_dataset"],
        ["S02"],
        ["backend/platform_core/executor.py"],
    ),
    19: (
        ["python"],
        [
            "test_malicious_document_cannot_add_tool_authority",
            "test_model_cannot_switch_to_another_allowed_but_unplanned_tool",
        ],
        ["S14"],
        ["backend/platform_core/models.py"],
    ),
    20: (
        ["python"],
        ["test_tool_permission_denied_before_any_intent"],
        ["S16"],
        ["backend/platform_core/repository.py"],
    ),
    21: (
        ["python"],
        [
            "test_retry_cannot_bypass_each_budget_dimension",
            "test_operator_reconcile_cannot_reopen_budget_terminal",
        ],
        ["S17", "S33", "S34", "S35", "S36", "S37", "S38", "S39", "S41"],
        ["backend/platform_core/policy.py"],
    ),
    22: (
        ["python", "browser"],
        [
            "test_cancel_unknown_reconciles_before_final_cancellation",
            "test_cancel_race_after_sent_preserves_cancel_request",
        ],
        ["S18", "S19", "S40"],
        ["backend/platform_core/application_repository.py", "backend/platform_core/repository.py"],
    ),
    23: (
        ["python", "browser"],
        ["test_manual_review_acknowledgement_does_not_release_intent_fence"],
        ["S21"],
        ["backend/platform_core/application.py", "frontend/src/main.tsx"],
    ),
    24: (
        ["python"],
        ["test_events_are_append_only"],
        [],
        ["backend/platform_core/database.py", "frontend/src/main.tsx"],
    ),
    25: (
        ["python"],
        [
            "test_structured_logs_correlate_real_claim_ids_without_payload",
            "test_rolled_back_event_is_not_emitted_as_committed_log",
            "test_metrics_exposes_zero_states_and_failed_aggregate",
        ],
        [],
        ["backend/platform_core/telemetry.py"],
    ),
    26: (
        ["python", "scenarios"],
        [
            "test_every_durable_mode_has_an_executable_scenario",
            "test_durable_fault_consumed_once_by_competing_consumers",
        ],
        [],
        ["backend/platform_core/faults.py"],
    ),
    27: (
        ["scenarios"],
        [],
        [],
        ["backend/platform_core/scenario_catalog.py", "backend/platform_core/scenarios.py"],
    ),
    28: (["python", "scenarios"], [], [], ["docs/INVARIANTS.json"]),
    29: (
        ["python", "compose"],
        ["test_cross_tenant_foreign_keys_reject_version_reference"],
        [],
        ["sql/001_orchestrator.sql", "sql/002_provider_tools.sql"],
    ),
    30: (
        ["python", "scenarios"],
        ["test_normal_ack_still_requires_readback"],
        ["S04", "S28"],
        ["docs/ARCHITECTURE.md", "backend/platform_core/provider.py"],
    ),
    31: (
        ["python"],
        [
            "test_health_metrics_and_auth_boundary",
            "test_tenant_api_denies_all_foreign_resources_and_actions",
        ],
        [],
        ["backend/platform_core/api.py"],
    ),
    32: (
        ["browser", "compose_browser"],
        [],
        [],
        ["frontend/src/main.tsx", "frontend/src/client.ts"],
    ),
    33: (
        ["browser", "compose_browser"],
        [],
        ["S04"],
        ["backend/platform_core/inspection.py", "frontend/src/main.tsx"],
    ),
    34: (
        ["browser", "compose_browser"],
        [],
        ["S06"],
        ["backend/platform_core/control_api.py", "frontend/src/main.tsx"],
    ),
    35: (["static", "browser"], [], [], ["frontend/src/style.css", "frontend/src/main.tsx"]),
    36: (
        ["python", "scenarios", "browser"],
        [],
        [],
        ["tests/test_tools.py", "frontend/tests/operations.spec.ts"],
    ),
    37: (
        ["python", "compose_restart"],
        ["test_real_process_death_unknown_readonly_recovery_one_effect"],
        ["S06", "S24"],
        ["docs/SCENARIOS.md"],
    ),
    38: (
        ["compose", "compose_restart", "compose_browser"],
        [],
        [],
        ["compose.yaml", "tools/verify_compose.py"],
    ),
    39: (["ci"], [], [], ["../../.github/workflows/durable-agent-platform.yml"]),
    40: (
        ["python", "static"],
        [
            "test_upload_validation_and_actual_body_limit",
            "test_HTTP_tool_rejects_real_URL_or_arbitrary_route_before_dispatch",
            "test_structured_logs_correlate_real_claim_ids_without_payload",
        ],
        [],
        ["docs/SECURITY_MODEL.md"],
    ),
    41: (
        ["python"],
        [
            "test_evaluation_is_five_independent_persistable_results",
            "test_synthetic_evaluation_dataset",
        ],
        [],
        ["backend/platform_core/evaluators.py"],
    ),
    42: (
        ["python"],
        ["test_synthetic_evaluation_dataset"],
        [],
        ["tests/data/evaluation_tasks.json"],
    ),
    43: (
        ["python"],
        ["test_explicit_multilingual_aliases_share_features", "test_synthetic_evaluation_dataset"],
        [],
        ["backend/platform_core/rag.py"],
    ),
    44: (["static"], [], [], ["docs/SECURITY_MODEL.md", "tests/data/evaluation_tasks.json"]),
    45: (
        ["static"],
        [],
        [],
        [
            "README.md",
            "docs/ARCHITECTURE.md",
            "docs/STATE_MACHINES.md",
            "docs/FAILURE_MODEL.md",
            "docs/SECURITY_MODEL.md",
            "docs/EVALUATIONS.md",
            "docs/CONSOLE.md",
        ],
    ),
    46: (
        ["static"],
        [],
        [],
        ["tools/build_architecture.py", *[f"docs/diagrams/A{i}.svg" for i in range(1, 9)]],
    ),
    47: (["browser", "compose_browser"], [], [], ["frontend/tests/operations.spec.ts"]),
    48: (
        ["static"],
        [],
        [],
        ["tools/metrics.py", "tools/verify_release.py", "tools/requirement_audit.py"],
    ),
    49: (["static"], [], [], ["tools/metrics.py"]),
    50: (
        ["ci", "compose_restart"],
        [],
        [],
        ["tools/verify_release.py", "tools/source_manifest.py"],
    ),
    51: ([], [], [], ["README.md"]),
    52: (["static"], [], [], ["pyproject.toml", "compose.yaml"]),
    53: (
        ["python", "scenarios", "compose_restart", "compose_browser"],
        [],
        ["S06", "S15", "S20"],
        ["docs/SCENARIOS.md"],
    ),
    54: (
        [
            "static",
            "python",
            "scenarios",
            "browser",
            "compose",
            "compose_restart",
            "compose_browser",
            "ci",
        ],
        [],
        [],
        ["tools/verify_release.py"],
    ),
}


def _status(checks: list[bool], gates: list[str], phases: dict[str, str]) -> str:
    if not all(checks) or any(phases.get(gate) == "FAIL" for gate in gates):
        return "FAIL"
    return "PASS" if all(phases.get(gate) == "PASS" for gate in gates) else "PARTIAL"


def build(
    facts: dict[str, Any],
    phases: dict[str, str],
    passed_tests: set[str],
    passed_scenarios: set[str],
) -> dict[str, Any]:
    original = (ROOT / "docs/ORIGINAL_REQUIREMENTS.md").read_text(encoding="utf-8")
    headings = list(re.finditer(r"^# (\d+)\. (.+)$", original, re.MULTILINE))
    assert len(headings) == 54 and set(RULES) == set(range(1, 55))
    sections = []
    units = []
    for index, match in enumerate(headings):
        number = int(match.group(1))
        end = headings[index + 1].start() if index + 1 < len(headings) else len(original)
        text = original[match.end() : end]
        gates, tests, scenarios, files = RULES[number]
        checks = (
            [(ROOT / name).is_file() for name in files]
            + [name in passed_tests for name in tests]
            + [name in passed_scenarios for name in scenarios]
        )
        if number == 1:
            checks.append(facts["loc"]["size_gate"])
        if number == 4:
            checks.extend(
                [
                    facts["tests"]["functions_total"] >= 100,
                    facts["api_operations"] >= 15,
                    facts["executable_scenario_catalog"] >= 25,
                ]
            )
        if number == 26:
            checks.append(facts["fault_mode_count"] >= 20)
        if number == 27:
            checks.append(
                facts["scenario_results_current_runtime"] == facts["executable_scenario_catalog"]
            )
        if number == 36:
            checks.append(facts["tests"]["functions_total"] >= 100)
        if number == 42:
            checks.append(facts["evaluation_dataset"]["executable_tasks"] >= 20)
        if number == 46:
            checks.append(facts["diagrams"] == 8)
        if number == 47:
            checks.append(facts["screenshots"] == 7)
        if number in {40, 44, 54}:
            checks.append(facts["credential_PII_pattern_scan"] == "PASS")
        if number in {45, 54}:
            checks.append(not facts["broken_documentation_links"])
        status = _status(checks, gates, phases)
        mandatory = number != 51
        note = "Evidence is bound to the current source fingerprint."
        if number == 4:
            note = "40–80 backend modules is an orientation, not a hard file quota; actual code-bearing and package-module counts are reported without padding."
        if number == 13:
            note = "Deterministic provider is required and tested; the optional paid/OpenAI adapter is not applicable."
        if number == 51:
            status = "NOT APPLICABLE"
            note = "Owner explicitly prohibits public repository changes before Stage 1 READY; integration is a post-release action."
        section = {
            "id": f"R{number:02d}",
            "title": match.group(2),
            "mandatory": mandatory,
            "status": status,
            "implementation": files,
            "tests": tests,
            "scenarios": scenarios,
            "executed_gates": {g: phases.get(g, "NOT_RUN") for g in gates},
            "note": note,
            "source_line": original[: match.start()].count("\n") + 1,
            "source_excerpt": text.strip(),
        }
        sections.append(section)
        # Preserve each original checklist item/subheading as an independently addressable row.
        for ordinal, item in enumerate(re.finditer(r"^(?:- |### )(.+)$", text, re.MULTILINE), 1):
            raw = item.group(1)
            optional = (
                (number == 4 and "modules" in raw)
                or "optional" in raw.casefold()
                or "примерно" in raw
            )
            units.append(
                {
                    "id": f"R{number:02d}.{ordinal:02d}",
                    "requirement": raw,
                    "status": "NOT APPLICABLE" if optional else status,
                    "mandatory": mandatory and not optional,
                    "evidence_section": section["id"],
                    "implementation": files,
                    "tests": tests,
                    "scenarios": scenarios,
                    "note": "Optional/advisory clause; no artificial implementation or file padding."
                    if optional
                    else note,
                }
            )
    tool_rows = []
    for tool in json.loads((ROOT / "docs/TOOL_REQUIREMENTS.json").read_text()):
        status = _status(
            [x in passed_tests for x in tool["tests"]]
            + [x in passed_scenarios for x in tool["scenarios"]],
            ["python", "scenarios"],
            phases,
        )
        tool_rows.append({**tool, "status": status})
    invariants = []
    for row in json.loads((ROOT / "docs/INVARIANTS.json").read_text()):
        invariants.append(
            {
                **row,
                "status": _status(
                    [x in passed_tests for x in row["tests"]]
                    + [x in passed_scenarios for x in row["scenarios"]],
                    ["python", "scenarios"],
                    phases,
                ),
            }
        )
    mandatory_open = [
        row["id"]
        for row in sections + units
        if row["mandatory"] and row["status"] in {"FAIL", "PARTIAL"}
    ]
    if any(row["status"] != "PASS" for row in tool_rows):
        mandatory_open.append("TOOLS")
    if any(row["status"] != "PASS" for row in invariants):
        mandatory_open.append("INVARIANTS")
    return {
        "status": "PASS" if not mandatory_open else "FAIL",
        "source_sha256": facts["source_sha256"],
        "original_requirement_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "sections_covered": len(sections),
        "checklist_items_covered": len(units),
        "mandatory_open": mandatory_open,
        "sections": sections,
        "checklist": units,
        "tools": tool_rows,
        "invariants": invariants,
    }


def write(report: dict[str, Any]) -> None:
    (ROOT / "docs/REQUIREMENT_AUDIT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Original Stage 1 requirement audit",
        "",
        f"Status: **{report['status']}**. Source: `{report['source_sha256']}`.",
        "",
        f"All {report['sections_covered']} numbered sections and {report['checklist_items_covered']} original checklist/subheading items are preserved in the JSON report. No original section is omitted.",
        "",
        "| Requirement | Status | Implementation / executed evidence |",
        "| --- | --- | --- |",
    ]
    for row in report["sections"]:
        evidence = (
            ", ".join(row["implementation"])
            + "; tests: "
            + ", ".join(row["tests"])
            + "; scenarios: "
            + ", ".join(row["scenarios"])
        )
        lines.append(
            "| "
            + row["id"]
            + " "
            + row["title"]
            + " | "
            + row["status"]
            + " | "
            + evidence.replace("|", "/")
            + " |"
        )
    lines.extend(
        [
            "",
            "## Mandatory open requirements",
            "",
            ", ".join(report["mandatory_open"]) or "None.",
            "",
            "The optional OpenAI-compatible adapter and the advisory module range are not fabricated as implemented capabilities. Public portfolio integration remains a conditional, post-readiness action prohibited during private verification.",
        ]
    )
    (ROOT / "docs/REQUIREMENT_AUDIT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key, name in [
        ("tools", "TOOL_REQUIREMENT_AUDIT.json"),
        ("invariants", "INVARIANT_AUDIT.json"),
    ]:
        (ROOT / "docs" / name).write_text(
            json.dumps({"source_sha256": report["source_sha256"], "rows": report[key]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
