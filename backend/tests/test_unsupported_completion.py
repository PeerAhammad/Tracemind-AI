from app.detectors.base import DetectorConfig
from app.detectors.unsupported_completion import UnsupportedCompletionDetector
from tests.helpers import load_fixture, make_trace

D = UnsupportedCompletionDetector()
CFG = DetectorConfig()


def test_demo_fixture_empty_dataflow_flagged():
    f = D.detect(load_fixture("repeated_search_unsupported_claim"), CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e3", "e4", "e5"]


def test_successful_run_not_flagged():
    assert D.detect(load_fixture("successful_refund_lookup"), CFG) == []


def test_last_call_error_with_completion_claim():
    f = D.detect(load_fixture("unrecovered_tool_error"), CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e1", "e2"]


def test_honest_failure_not_flagged():
    t = make_trace([("t", {}, None, "boom")], final="I could not complete the task.", status="failed")
    assert D.detect(t, CFG) == []


def test_text_claim_without_completed_status():
    t = make_trace([("t", {}, None, "boom")], final="Done!", status="incomplete")
    assert len(D.detect(t, CFG)) == 1


def test_negated_text_not_a_claim():
    t = make_trace([("t", {}, None, "boom")], final="Task not complete", status="incomplete")
    assert D.detect(t, CFG) == []
