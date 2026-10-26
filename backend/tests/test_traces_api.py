import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
FIXTURE = Path(__file__).resolve().parents[2] / "benchmarks/fixtures/repeated_search_unsupported_claim.json"


def _upload(content: bytes):
    return client.post("/api/traces", files={"file": ("t.json", content, "application/json")})


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_valid_trace_roundtrip():
    r = _upload(FIXTURE.read_bytes())
    assert r.status_code == 201 and r.json()["event_count"] == 5
    got = client.get("/api/traces/demo-001").json()
    assert got["events"][0]["tool_name"] == "search_docs"


def test_malformed_json_rejected():
    assert _upload(b"{not json").status_code == 400


def test_duplicate_step_numbers_rejected():
    data = json.loads(FIXTURE.read_text())
    data["events"][1]["step_number"] = 1
    assert _upload(json.dumps(data).encode()).status_code == 422


def test_missing_trace_404():
    assert client.get("/api/traces/nope").status_code == 404
