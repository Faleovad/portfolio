"""Executable specifications, independent of pytest parameter matrices."""

from dataclasses import asdict, dataclass

from .tool_contracts import ToolName


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    setup: str = "research"
    fault_plan: tuple[tuple[str, int], ...] = ()
    execution_steps: tuple[str, ...] = ("finish",)
    final_state: str = "COMPLETED"
    provider_mutations: int = 0
    receipts: int = 0
    limits: tuple[tuple[str, int], ...] = ()
    tool_name: ToolName = "crm"
    tool_payload: tuple[tuple[str, str], ...] = ()
    provider_fixture: tuple[tuple[str, str], ...] = ()

    def public(self) -> dict[str, object]:
        result = asdict(self)
        path = ["QUEUED"]
        if self.execution_steps[0] != "cancel":
            path.append("RUNNING")
            if self.setup == "tool" and dict(self.limits).get("tool_limit", 1) > 0:
                path.append("WAITING_TOOL")
                if any(
                    mode
                    in {
                        "tool_commit_then_timeout",
                        "tool_timeout_before_commit",
                        "lost_acknowledgement",
                    }
                    for mode, _ in self.fault_plan
                ):
                    path.append("UNKNOWN")
                if any(mode == "cancellation_during_unknown" for mode, _ in self.fault_plan):
                    path.append("CANCEL_REQUESTED")
                path.append("RECOVERING")
        path.append(self.final_state)
        result["expected_state_transitions"] = path
        result["expected_provider_state"] = "COMMITTED" if self.provider_mutations else "NO_EFFECT"
        result["expected_receipt_recovery_state"] = (
            "CONFIRMED" if self.receipts else "NO_RECEIPT; unresolved effects remain fenced"
        )
        result["final_assertions"] = [
            "final state",
            "exact mutation and receipt counts",
            "at most one dispatch",
            "tenant-scoped evidence",
            "budgets never exceeded",
            "all configured faults consumed",
        ]
        return result


CATALOG = [
    Scenario("S01", "Normal research task"),
    Scenario("S02", "RAG and citations", execution_steps=("finish", "provenance")),
    Scenario("S03", "Tool mutation normal", "tool", provider_mutations=1, receipts=1),
    Scenario(
        "S04",
        "Tool commit then timeout",
        "tool",
        (("tool_commit_then_timeout", 1),),
        ("dispatch", "assert_unknown", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S05",
        "Timeout before commit",
        "tool",
        (("tool_timeout_before_commit", 1),),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S06",
        "Recovery after worker termination",
        "tool",
        (("tool_commit_then_timeout", 1), ("worker_pause_after_unknown", 1)),
        ("kill_unknown", "restart_dispatcher", "recover_process", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S07",
        "Duplicate enqueue",
        "tool",
        (("duplicate_enqueue", 1),),
        ("duplicate", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S08",
        "Worker race",
        "tool",
        (("competing_workers", 1),),
        ("race", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S09",
        "Stale worker rejected",
        "tool",
        (("stale_worker_write", 1),),
        ("stale", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S10",
        "Lost tool acknowledgement",
        "tool",
        (("lost_acknowledgement", 1),),
        ("dispatch", "assert_unknown", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S11",
        "Malformed model output",
        fault_plan=(("malformed_model_output", 3),),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S12", "Model outage", fault_plan=(("model_timeout", 3),), final_state="MANUAL_REVIEW"
    ),
    Scenario(
        "S13",
        "Retrieval outage",
        fault_plan=(("retrieval_outage", 1),),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S14", "Prompt injection documents", "malicious", execution_steps=("finish", "authority")
    ),
    Scenario("S15", "Tenant isolation attempt", execution_steps=("deny_tenant", "finish")),
    Scenario("S16", "Tool permission violation", execution_steps=("deny_tool", "finish")),
    Scenario(
        "S17",
        "Budget exhaustion",
        fault_plan=(("budget_exhaustion", 1),),
        final_state="BUDGET_EXHAUSTED",
    ),
    Scenario(
        "S18",
        "Cancellation before mutation",
        "tool",
        execution_steps=("cancel", "finish"),
        final_state="CANCELLED",
    ),
    Scenario(
        "S19",
        "Cancellation while UNKNOWN",
        "tool",
        (("tool_commit_then_timeout", 1), ("cancellation_during_unknown", 1)),
        ("dispatch", "assert_cancel_pending", "finish"),
        "CANCELLED",
        1,
        1,
    ),
    Scenario(
        "S20",
        "Agent version changed mid-run",
        execution_steps=("execute", "publish_v2", "finish", "pinned"),
    ),
    Scenario(
        "S21",
        "Unprovable effect enters manual review",
        "tool",
        (("tool_timeout_before_commit", 1),),
        ("finish", "review_safe"),
        "MANUAL_REVIEW",
    ),
    Scenario(
        "S22",
        "External delayed visibility",
        "tool",
        (("delayed_external_visibility", 1),),
        ("dispatch", "recover", "assert_deferred", "wait_visibility", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S23",
        "Stale visibility beyond policy",
        "tool",
        (("stale_readback", 6),),
        final_state="MANUAL_REVIEW",
        provider_mutations=1,
    ),
    Scenario(
        "S24",
        "Restart during recovery",
        "tool",
        (("recovery_crash_after_observation", 1),),
        ("dispatch", "crash_recovery", "recover_process", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S25",
        "Terminal receipt replay",
        "tool",
        execution_steps=("finish", "receipt_replay"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S26",
        "Crash before step commit",
        fault_plan=(("worker_crash_before_step_commit", 1),),
        execution_steps=("crash_executor_before", "finish", "provenance"),
    ),
    Scenario(
        "S27",
        "Crash after step commit",
        fault_plan=(("worker_crash_after_step_commit", 1),),
        execution_steps=("crash_executor_after", "finish", "steps_once"),
    ),
    Scenario(
        "S28",
        "Database transaction rollback",
        fault_plan=(("database_transaction_rollback", 1),),
        execution_steps=("execute", "assert_rollback", "finish"),
    ),
    Scenario(
        "S29",
        "Worker lease expiry before dispatch",
        "tool",
        (("worker_lease_expiry", 1),),
        ("dispatch", "assert_no_effect", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S30",
        "Malformed retrieved document",
        fault_plan=(("malformed_retrieved_document", 1),),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S31",
        "Model requires manual review",
        fault_plan=(("manual_review_required", 1),),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S32",
        "Readback outage then recovery",
        "tool",
        (("readback_outage", 1),),
        ("dispatch", "recover", "assert_deferred", "finish"),
        provider_mutations=1,
        receipts=1,
    ),
    Scenario(
        "S33",
        "Logical duration exhaustion",
        fault_plan=(("logical_duration_expiry", 1),),
        final_state="BUDGET_EXHAUSTED",
    ),
    Scenario(
        "S34",
        "Estimated token admission",
        final_state="BUDGET_EXHAUSTED",
        limits=(("token_limit", 0),),
    ),
    Scenario(
        "S35",
        "Estimated cost admission",
        final_state="BUDGET_EXHAUSTED",
        limits=(("cost_limit", 0),),
    ),
    Scenario(
        "S36",
        "Exact successful budget boundary",
        execution_steps=("finish", "exact_budget"),
        limits=(("model_limit", 1), ("step_limit", 3)),
    ),
    Scenario(
        "S37",
        "Model repair near budget boundary",
        fault_plan=(("model_timeout", 1),),
        final_state="BUDGET_EXHAUSTED",
        limits=(("model_limit", 1),),
    ),
    Scenario(
        "S38",
        "Recovery attempt budget exhaustion",
        "tool",
        (("readback_outage", 1),),
        final_state="BUDGET_EXHAUSTED",
        provider_mutations=1,
        limits=(("recovery_limit", 1),),
    ),
    Scenario(
        "S39",
        "Tool retry denied at budget boundary",
        "tool",
        execution_steps=("finish", "continue", "dispatch", "assert_no_effect"),
        final_state="BUDGET_EXHAUSTED",
        limits=(("tool_limit", 0),),
    ),
    Scenario(
        "S40",
        "Unprovable cancellation retains fence",
        "tool",
        (("tool_timeout_before_commit", 1), ("cancellation_during_unknown", 1)),
        final_state="MANUAL_REVIEW",
    ),
    Scenario(
        "S41", "Step budget exhaustion", final_state="BUDGET_EXHAUSTED", limits=(("step_limit", 1),)
    ),
]
CATALOG.extend(
    [
        Scenario(
            "S42",
            "External Search is read-only and durable",
            "external_search",
            execution_steps=("finish", "search_proof"),
            tool_name="search",
        ),
        Scenario(
            "S43",
            "CRM entity update",
            "tool",
            provider_mutations=1,
            receipts=1,
            tool_payload=(
                ("entity_key", "known-entity"),
                ("operation", "update"),
                ("name", "Updated entity"),
            ),
            provider_fixture=(("entity_key", "known-entity"), ("name", "Initial entity")),
        ),
        Scenario(
            "S44",
            "Quota credit",
            "tool",
            provider_mutations=1,
            receipts=1,
            tool_name="quota",
            tool_payload=(("account", "lab-account"), ("delta", "100")),
        ),
        Scenario(
            "S45",
            "Quota credit lost ACK",
            "tool",
            (("tool_commit_then_timeout", 1),),
            ("dispatch", "assert_unknown", "finish"),
            provider_mutations=1,
            receipts=1,
            tool_name="quota",
            tool_payload=(("account", "lab-account"), ("delta", "100")),
        ),
        Scenario(
            "S46",
            "Quota debit reconciles without charging twice",
            "tool",
            (("lost_acknowledgement", 1),),
            provider_mutations=1,
            receipts=1,
            tool_name="quota",
            tool_payload=(("account", "lab-account"), ("delta", "-25")),
            provider_fixture=(("account", "lab-account"), ("delta", "100")),
        ),
        Scenario(
            "S47",
            "Synthetic Email delivery",
            "tool",
            provider_mutations=1,
            receipts=1,
            tool_name="email",
            tool_payload=(
                ("recipient_id", "demo-inbox"),
                ("subject", "Synthetic notice"),
                ("body", "Synthetic message"),
            ),
        ),
        Scenario(
            "S48",
            "Email commit then timeout does not resend",
            "tool",
            (("tool_commit_then_timeout", 1),),
            provider_mutations=1,
            receipts=1,
            tool_name="email",
            tool_payload=(
                ("recipient_id", "demo-inbox"),
                ("subject", "Synthetic notice"),
                ("body", "Synthetic message"),
            ),
        ),
        Scenario(
            "S49",
            "Generic synthetic HTTP POST",
            "tool",
            provider_mutations=1,
            receipts=1,
            tool_name="http",
            tool_payload=(("method", "POST"), ("path", "/synthetic/resource"), ("body", "created")),
        ),
        Scenario(
            "S50",
            "Generic synthetic HTTP PUT lost ACK",
            "tool",
            (("lost_acknowledgement", 1),),
            provider_mutations=1,
            receipts=1,
            tool_name="http",
            tool_payload=(("method", "PUT"), ("path", "/synthetic/resource"), ("body", "updated")),
            provider_fixture=(
                ("method", "POST"),
                ("path", "/synthetic/resource"),
                ("body", "initial"),
            ),
        ),
        Scenario(
            "S51",
            "Provider error before quota commit",
            "tool",
            (("tool_error_before_commit", 1),),
            final_state="MANUAL_REVIEW",
            tool_name="quota",
            tool_payload=(("account", "lab-account"), ("delta", "100")),
        ),
        Scenario(
            "S52",
            "Provider ambiguous error after Email commit",
            "tool",
            (("tool_error_after_commit", 1),),
            provider_mutations=1,
            receipts=1,
            tool_name="email",
            tool_payload=(
                ("recipient_id", "demo-inbox"),
                ("subject", "Synthetic notice"),
                ("body", "Synthetic message"),
            ),
        ),
        Scenario(
            "S53",
            "External Search outage",
            "external_search",
            (("search_outage", 1),),
            final_state="MANUAL_REVIEW",
            tool_name="search",
        ),
    ]
)
SCENARIOS = {scenario.id: scenario for scenario in CATALOG}
