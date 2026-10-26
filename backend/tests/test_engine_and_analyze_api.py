from fastapi.testclient import TestClient

from app.detectors.base import Detector
from app.detectors.engine import analyze_trace
from app.main import app
from app.schemas.finding import FailureCategory
from tests.helpers import FIXTURES, load_fixture

client = TestClient(app)


def _upload(name):
    r = client.post("/api/traces", files={"file": (f"{name}.json", (FIXTURES / f"{name}.json").read_bytes(), "application/json")})
    assert r.status_code == 201
    return r.json()["id"]


def test_demo_trace_findings_via_api():
    rid = _upload("repeated_search_unsupported_claim")
    body = client.post(f"/api/traces/{rid}/analyze").json()
    assert {f["category"] for f in body["findings"]} == {
        FailureCategory.REPEATED_CALL.value, FailureCategory.UNSUPPORTED_COMPLETION.value}
    assert client.get(f"/api/traces/{rid}/findings").json()["run_id"] == rid


def test_clean_trace_has_zero_findings():
    rid = _upload("successful_refund_lookup")
    assert client.post(f"/api/traces/{rid}/analyze").json()["findings"] == []


def test_legit_retry_not_flagged_as_repeated_call():
    rid = _upload("legit_retry_after_error")
    cats = {f["category"] for f in client.post(f"/api/traces/{rid}/analyze").json()["findings"]}
    assert FailureCategory.REPEATED_CALL.value not in cats


def test_analyze_unknown_trace_404_and_findings_before_analysis_404():
    assert client.post("/api/traces/nope/analyze").status_code == 404
    rid = _upload("unrecovered_tool_error")
    assert client.get(f"/api/traces/{rid}/findings").status_code == 404


def test_crashing_detector_is_isolated():
    class Boom(Detector):
        name = "boom"
        def detect(self, trace, config):
            raise RuntimeError("bad")
    from app.detectors.engine import DEFAULT_DETECTORS
    res = analyze_trace(load_fixture("repeated_search_unsupported_claim"), [Boom(), *DEFAULT_DETECTORS])
    assert len(res.findings) == 2 and res.detector_errors and "boom" in res.detector_errors[0]
