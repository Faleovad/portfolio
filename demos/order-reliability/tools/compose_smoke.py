"""Exercise synthetic persisted UNKNOWN across a real Compose backend restart."""

import json
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:5173/api"


def call(path: str, method: str = "GET") -> dict:
    request = urllib.request.Request(BASE + path, method=method)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def main() -> None:
    for _ in range(60):
        try:
            data = call("/system")
            break
        except (OSError, urllib.error.HTTPError):
            time.sleep(1)
    else:
        raise RuntimeError("Compose API did not become ready")
    if "--recover" not in sys.argv:
        call("/scenarios/completion_lost/reset", "POST")
        for _ in range(5):
            call("/orders/DEMO-1001/step", "POST")
        data = call("/system")
    assert data["orders"][0]["state"] == "UNKNOWN"
    assert data["external"]["orders"][0]["status"] == "DONE"
    assert data["tasks"][0]["state"] == "PENDING"
    assert data["fences"][0]["state"] == "UNKNOWN"
    assert sum(c["operation"] == "FULFILL" for c in data["external"]["calls"]) == 1
    if "--recover" in sys.argv:
        result = call("/recovery/run", "POST")
        assert result["orders"][0]["state"] == "DONE"
        assert result["tasks"][0]["state"] == "COMPLETE"
        assert result["external"]["calls"] == data["external"]["calls"]
    print("PASS: synthetic Compose state and one-send/restart boundary")


if __name__ == "__main__":
    main()
