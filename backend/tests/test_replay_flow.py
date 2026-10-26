from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _run(task_id, cfg=None):
    r = client.post("/api/tasks/run", json={"task_id": task_id, "configuration": cfg or {}})
    assert r.status_code == 201
    return r.json()


def test_full_observe_to_verify_loop():
    base = _run("refund_empty_search")
    rid = base["run_id"]
    assert base["task_outcome"] == "failure"

    # detect
    analysis = client.post(f"/api/runs/{rid}/analyze").json()
    assert {f["category"] for f in analysis["findings"]} == {"repeated_call_no_progress", "unsupported_completion_claim"}

    # propose
    corr = client.get(f"/api/runs/{rid}/corrections").json()
    assert len(corr["corrections"]) == 2
    assert corr["combined_changes"] == {"max_retries": 1, "reformulate_on_empty": True,
                                        "require_retrieval_before_summary": True}
    assert client.get(f"/api/traces/{rid}/findings").json()["findings"][0]["verification_status"] == "fix_proposed"

    # approval is mandatory and validated
    assert client.post(f"/api/runs/{rid}/replay", json={"approved_changes": corr["combined_changes"]}).status_code == 400
    assert client.post(f"/api/runs/{rid}/replay", json={"approved": True, "approved_changes": {}}).status_code == 400
    assert client.post(f"/api/runs/{rid}/replay", json={"approved": True, "approved_changes": {"nope": 1}}).status_code == 422
    assert client.get(f"/api/runs/{rid}/comparison").status_code == 404   # nothing replayed yet

    # replay + compare
    rep = client.post(f"/api/runs/{rid}/replay", json={"approved": True, "approved_changes": corr["combined_changes"]}).json()
    assert rep["parent_run_id"] == rid and rep["task_outcome"] == "success"
    cmp = client.get(f"/api/runs/{rid}/comparison").json()
    assert cmp["outcome_change"] == "failure -> success" and cmp["regression"] is False
    assert cmp["tool_call_delta"] == -1 and cmp["findings_introduced"] == [] and cmp["findings_remaining"] == []
    assert cmp["findings_resolved"] == ["repeated_call_no_progress", "unsupported_completion_claim"]
    assert {v["verification_status"] for v in cmp["verifications"]} == {"fix_verified"}
    assert client.get(f"/api/runs/{rep['run_id']}/comparison").json()["baseline"]["run_id"] == rid
    assert {f["verification_status"] for f in client.get(f"/api/traces/{rid}/findings").json()["findings"]} == {"fix_verified"}


def test_bad_fix_is_reported_as_regression():
    base = _run("flaky_search_retry")
    rid = base["run_id"]
    client.post(f"/api/runs/{rid}/replay", json={"approved": True, "approved_changes": {"max_retries": 0}})
    cmp = client.get(f"/api/runs/{rid}/comparison").json()
    assert cmp["regression"] is True and cmp["outcome_change"] == "success -> failure"
    assert "unsupported_completion_claim" in cmp["findings_introduced"]
    assert {v["verification_status"] for v in cmp["verifications"]} == {"fix_not_effective"}


def test_clean_run_has_no_corrections():
    rid = _run("refund_ok")["run_id"]
    assert client.get(f"/api/runs/{rid}/corrections").json()["corrections"] == []


def test_unknown_task_and_run_404_and_bad_config_422():
    assert client.post("/api/tasks/run", json={"task_id": "zzz"}).status_code == 404
    assert client.get("/api/runs/zzz").status_code == 404
    assert client.post("/api/tasks/run", json={"task_id": "refund_ok", "configuration": {"max_retries": 99}}).status_code == 422


def test_list_tasks_and_sweep_endpoint():
    assert len(client.get("/api/tasks").json()) == 3
    res = client.post("/api/tasks/evaluate", json={"configuration": {
        "max_retries": 1, "reformulate_on_empty": True, "require_retrieval_before_summary": True}}).json()
    assert res["completion_rate_before"] == 2 / 3 and res["completion_rate_after"] == 1.0
    assert res["tasks_fixed"] == ["refund_empty_search"] and res["tasks_regressed"] == []
    bad = client.post("/api/tasks/evaluate", json={"configuration": {"max_retries": 0}}).json()
    assert bad["tasks_regressed"] == ["flaky_search_retry"] and bad["completion_rate_after"] == 1 / 3
