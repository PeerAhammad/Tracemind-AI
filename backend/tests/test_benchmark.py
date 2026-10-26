import json

from fastapi.testclient import TestClient

from app.evaluation.benchmark import (CATEGORIES, Scenario, evaluate_scenarios, load_scenarios,
                                      run_benchmark, saved_results_path)
from app.main import app
from tests.helpers import make_trace

client = TestClient(app)


def _scenario(sid, trace, truth, split="dev"):
    return Scenario(scenario_id=sid, split=split, description="x", expected_task_outcome="failure",
                    ground_truth_failures=truth, expected_detector_behavior="", expected_correction="", trace=trace)


REPEATED = lambda: make_trace([("search", {"q": "a"}, {"results": []})] * 3, final="Task failed", status="failed")  # noqa: E731
CLEAN = lambda: make_trace([("search", {"q": "a"}, {"results": ["x"]})], final="Task complete")  # noqa: E731


# ---------- metric arithmetic on tiny synthetic scenarios ----------
def test_confusion_counts_and_ratios():
    res = evaluate_scenarios([
        _scenario("A", REPEATED(), {"repeated_call_no_progress": ["e1"]}),   # TP
        _scenario("B", CLEAN(), {}),                                          # all TN
        _scenario("C", REPEATED(), {}),                                       # FP
        _scenario("D", CLEAN(), {"repeated_call_no_progress": ["e1"]}),       # FN
    ])
    assert (res.true_positives, res.false_positives, res.false_negatives) == (1, 1, 1)
    assert res.true_negatives == 4 * len(CATEGORIES) - 3
    assert res.precision == 0.5 and res.recall == 0.5
    assert res.overall.clean_scenarios == 2 and res.overall.clean_scenarios_flagged == 1
    assert res.overall.per_category["repeated_call_no_progress"].tp == 1


def test_undefined_ratios_are_none_not_zero():
    res = evaluate_scenarios([_scenario("B", CLEAN(), {})])
    assert res.precision is None and res.recall is None and res.overall.false_positive_rate == 0.0


def test_evidence_hit_requires_labelled_events_to_be_covered():
    ok = evaluate_scenarios([_scenario("A", REPEATED(), {"repeated_call_no_progress": ["e1", "e2"]})])
    assert ok.overall.evidence_hit_rate == 1.0
    # label cites an event the finding does not cover (e4 is the final answer)
    bad = evaluate_scenarios([_scenario("A", REPEATED(), {"repeated_call_no_progress": ["e4"]})])
    assert bad.overall.evidence_hit_rate == 0.0


def test_bad_labels_rejected():
    import pytest
    with pytest.raises(ValueError):
        _scenario("X", CLEAN(), {"not_a_category": ["e1"]})
    with pytest.raises(ValueError):
        _scenario("X", CLEAN(), {"repeated_call_no_progress": ["e99"]})


# ---------- the shipped benchmark ----------
def test_benchmark_data_integrity():
    sc = load_scenarios()
    ids = [s.scenario_id for s in sc]
    assert len(ids) == len(set(ids)) and 20 <= len(sc) <= 30
    assert sum(s.split == "heldout" for s in sc) >= 8
    covered = {c for s in sc for c in s.ground_truth_failures}
    assert covered == set(CATEGORIES)                                   # every category has labelled examples
    assert any(not s.ground_truth_failures for s in sc)                 # clean runs exist
    assert any("retry" in s.scenario_id.lower() or "retry" in s.notes.lower() for s in sc)  # legitimate retry exists


def test_saved_results_match_live_recomputation():
    """If this fails, detectors or scenarios changed: re-run `python -m app.evaluation.run_benchmark --write`
    and review the diff before trusting the new numbers."""
    saved = json.loads(saved_results_path().read_text())
    live = json.loads(run_benchmark().model_dump_json())
    assert live == saved


def test_no_detector_crashed_on_benchmark():
    assert all(not r.detector_errors for r in run_benchmark().scenario_results)


def test_heldout_split_is_reported_separately_and_honestly():
    r = run_benchmark()
    assert r.heldout.scenarios == 10 and r.dev.scenarios == 18
    assert r.overall.tp == r.dev.tp + r.heldout.tp and r.overall.fn == r.dev.fn + r.heldout.fn


# ---------- API ----------
def test_benchmark_endpoints():
    live = client.get("/api/benchmark").json()
    assert live["total_cases"] == 28 and live["runner_sweep"]["tasks_regressed"] == []
    assert live["data_source"].startswith("live")
    saved = client.get("/api/benchmark/saved").json()
    assert saved["data_source"].startswith("saved") and saved["total_cases"] == 28
    assert len(client.get("/api/benchmark/scenarios").json()) == 28
    assert client.get("/api/benchmark/scenarios/D03").json()["trace"]["run_id"] == "D03-repeated_empty_claim"
    assert client.get("/api/benchmark/scenarios/nope").status_code == 404


def test_scenario_can_be_loaded_and_analyzed_through_trace_endpoints():
    rid = client.post("/api/benchmark/scenarios/D03/load").json()["id"]
    cats = {f["category"] for f in client.post(f"/api/traces/{rid}/analyze").json()["findings"]}
    assert cats == {"repeated_call_no_progress", "unsupported_completion_claim"}
