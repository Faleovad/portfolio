from fastapi.testclient import TestClient


def test_api_exposes_seeded_system_and_scenario_catalog(client: TestClient) -> None:
    assert client.get("/api/health").json()["mode"] == "synthetic-local-lab"
    assert len(client.get("/api/scenarios").json()) >= 10
    assert client.get("/api/system").json()["orders"][0]["state"] == "DISCOVERED"


def test_repeated_run_endpoint_cannot_repeat_side_effect(client: TestClient) -> None:
    for _ in range(3):
        assert client.post("/api/orders/DEMO-1001/run").json()["state"] == "DONE"
    calls = client.get("/api/system").json()["external"]["calls"]
    assert len(calls) == 2


def test_structured_unknown_resource_errors(client: TestClient) -> None:
    response = client.get("/api/orders/not-a-real-order")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "order_not_found"
    assert client.post("/api/scenarios/missing/reset").status_code == 404


def test_interruption_returns_error_but_keeps_committed_state(client: TestClient) -> None:
    client.post("/api/scenarios/lost_ack/reset")
    assert client.post("/api/orders/DEMO-1001/run").status_code == 503
    assert client.get("/api/orders/DEMO-1001").json()["state"] == "DONE"


def test_events_cursor_returns_only_new_committed_events(client: TestClient) -> None:
    first = client.get("/api/events").json()
    client.post("/api/orders/DEMO-1001/step")
    later = client.get(f"/api/events?after={first[-1]['sequence']}").json()
    assert later and all(e["sequence"] > first[-1]["sequence"] for e in later)
    assert client.get("/api/events?after=-1").status_code == 422


def test_recovery_endpoint_performs_read_only_resolution(client: TestClient) -> None:
    client.post("/api/scenarios/completion_lost/reset")
    for _ in range(5):
        client.post("/api/orders/DEMO-1001/step")
    before = client.get("/api/system").json()
    assert before["orders"][0]["state"] == "UNKNOWN"
    after = client.post("/api/recovery/run").json()
    assert after["orders"][0]["state"] == "DONE"
    assert after["external"]["calls"] == before["external"]["calls"]
