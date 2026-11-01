from platform_core.faults import FaultEngine
from platform_core.scenario_catalog import CATALOG


def test_every_durable_mode_has_an_executable_scenario():
    configured = {mode for spec in CATALOG for mode, _ in spec.fault_plan}
    assert set(FaultEngine.MODES) == configured
    assert len(configured) >= 20


def test_catalog_has_distinct_identifiers_and_complete_contracts():
    assert len({spec.id for spec in CATALOG}) == len(CATALOG) >= 25
    for spec in CATALOG:
        contract = spec.public()
        for field in [
            "setup",
            "execution_steps",
            "expected_state_transitions",
            "expected_provider_state",
            "expected_receipt_recovery_state",
            "final_assertions",
        ]:
            assert contract[field], (spec.id, field)
