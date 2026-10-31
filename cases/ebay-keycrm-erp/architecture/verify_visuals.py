"""Validate public artifacts without access to private source or live services."""

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ARCH = Path(__file__).resolve().parent
CASE = ARCH.parent
REPO = CASE.parents[1]


def main() -> None:
    graph = json.loads((ARCH / "data/relationships.json").read_text(encoding='utf-8'))
    chains = json.loads((ARCH / "data/critical-chains.json").read_text(encoding='utf-8'))
    assert len(graph["nodes"]) == 805 and len(graph["edges"]) == 1208
    ids = {n["id"] for n in graph["nodes"]}
    assert len(ids) == 805
    assert all(e["source"] in ids and e["target"] in ids for e in graph["edges"])
    assert len({e["id"] for e in graph["edges"]}) == 1208
    assert len(chains) == len({c["path"] for c in chains}) == len({c["id"] for c in chains}) == 50
    assert Counter(e["path_class"] for e in graph["edges"]) == {
        "normal": 981, "failure": 157, "recovery": 65, "release/operations": 5,
    }
    sg = (ARCH / "safeguards.md").read_text(encoding='utf-8')
    assert len(set(re.findall(r"^### (SG\d{2})", sg, re.M))) == 28
    state = (ARCH / "state-authority-map.md").read_text(encoding='utf-8')
    assert len(re.findall(r"^\| SM\d{2} ", state, re.M)) == 30
    assert len(re.findall(r"^\| DO\d{2} ", state, re.M)) == 10
    assert len(re.findall(r"^\| AT\d{2} ", state, re.M)) == 24
    capture = json.loads((CASE / "assets/capture-verification.json").read_text(encoding='utf-8'))
    assert len(capture["captures"]) == 5
    for item in capture["captures"]:
        assert hashlib.sha256((CASE / "assets" / item["file"]).read_bytes()).hexdigest() == item["sha256"]
    by_name = {item["file"]: item for item in capture["captures"]}
    timeout, recovered = by_name["lab-timeout.png"], by_name["lab-recovered.png"]
    assert timeout["erp_state"] == "UNKNOWN" and timeout["provider_state"] == "DONE"
    assert timeout["fence_state"] == "UNKNOWN" and timeout["task_state"] == "PENDING"
    assert all(r["state"] == "RESERVED" for r in timeout["reservations"])
    assert recovered["erp_state"] == "DONE" and recovered["task_state"] == "COMPLETE"
    assert timeout["fulfill_calls"] == recovered["fulfill_calls"] == 1
    assert by_name["lab-duplicate.png"]["create_calls"] == 1
    assert by_name["lab-duplicate.png"]["journal_state"] == "SENT"
    svg_files = list((CASE / "assets").glob("*.svg"))
    assert len(svg_files) == 12
    for svg in svg_files:
        root = ET.parse(svg).getroot()
        assert root.tag.endswith("svg") and root.get("viewBox")
        assert not any(node.tag.endswith("script") for node in root.iter())
    links = 0
    for doc in [REPO / "README.md", CASE / "README.md", *ARCH.glob("*.md"),
                REPO / "demos/order-reliability/README.md"]:
        text = doc.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", re.sub(r"```[\s\S]*?```", "", text)):
            if re.match(r"https?://", target):
                continue
            relative, _, fragment = target.partition("#")
            dest = (doc.parent / relative).resolve() if relative else doc
            assert dest.is_file(), (doc, target)
            if fragment and dest.suffix == ".md":
                headings = re.findall(r"^#{1,6} (.+)$", dest.read_text(encoding="utf-8"), re.M)
                anchors = {re.sub(r"[^\w\- ]", "", h.lower()).replace(" ", "-") for h in headings}
                assert fragment in anchors, (doc, target)
            links += 1
    print(json.dumps({"nodes": 805, "relationships": 1208, "dangling": 0,
                      "chains": dict(Counter(c["path_class"] for c in chains)),
                      "safeguards": 28, "states": 40, "authorities": 24,
                      "svg_files": len(svg_files), "verified_captures": 5,
                      "relative_links": links}, indent=2))


if __name__ == "__main__":
    main()
