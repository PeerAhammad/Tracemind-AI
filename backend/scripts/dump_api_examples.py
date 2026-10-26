"""Writes real API responses to docs/api_examples/ so the frontend can be built and mocked against true shapes.
Run from backend/: python scripts/dump_api_examples.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["TRACEMIND_DB"] = str(Path(tempfile.mkdtemp()) / "examples.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "api_examples"
OUT.mkdir(parents=True, exist_ok=True)
c = TestClient(app)


def save(name, resp, expect=None):
    if expect:
        assert resp.status_code == expect, (name, resp.status_code, resp.text)
    (OUT / f"{name}.json").write_text(json.dumps(resp.json(), indent=2))
    return resp.json()


save("tasks", c.get("/api/tasks"), 200)
run = save("run_baseline", c.post("/api/tasks/run", json={"task_id": "refund_empty_search"}), 201)
rid = run["run_id"]
save("trace", c.get(f"/api/traces/{rid}"), 200)
save("analysis", c.post(f"/api/runs/{rid}/analyze"), 200)
corr = save("corrections", c.get(f"/api/runs/{rid}/corrections"), 200)
save("run_replayed", c.post(f"/api/runs/{rid}/replay",
                            json={"approved": True, "approved_changes": corr["combined_changes"]}), 201)
save("comparison", c.get(f"/api/runs/{rid}/comparison"), 200)
save("sweep_full_fix", c.post("/api/tasks/evaluate", json={"configuration": corr["combined_changes"]}), 200)
save("sweep_bad_fix_regression", c.post("/api/tasks/evaluate", json={"configuration": {"max_retries": 0}}), 200)
save("benchmark", c.get("/api/benchmark"), 200)
save("benchmark_scenarios", c.get("/api/benchmark/scenarios"), 200)
errors = {
    "malformed_json_upload_400": c.post("/api/traces", files={"file": ("t.json", b"{nope", "application/json")}).json(),
    "invalid_schema_upload_422": c.post("/api/traces", files={"file": ("t.json", b'{"run_id": "x"}', "application/json")}).json(),
    "replay_not_approved_400": c.post(f"/api/runs/{rid}/replay", json={"approved_changes": {"max_retries": 1}}).json(),
    "unknown_run_404": c.get("/api/runs/nope").json(),
}
(OUT / "errors.json").write_text(json.dumps(errors, indent=2))
print("wrote", len(list(OUT.glob("*.json"))), "example files to", OUT)
