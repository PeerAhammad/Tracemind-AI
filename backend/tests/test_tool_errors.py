from app.detectors.base import DetectorConfig
from app.detectors.tool_errors import ToolErrorDetector
from app.schemas.finding import Severity
from tests.helpers import load_fixture, make_trace

D = ToolErrorDetector()
CFG = DetectorConfig()


def test_unrecovered_error_is_high():
    f = D.detect(load_fixture("unrecovered_tool_error"), CFG)
    assert len(f) == 1 and f[0].severity == Severity.HIGH and f[0].evidence_event_ids == ["e1"]


def test_recovered_error_is_low_and_cites_recovery():
    f = D.detect(load_fixture("legit_retry_after_error"), CFG)
    assert len(f) == 1 and f[0].severity == Severity.LOW and f[0].evidence_event_ids == ["e1", "e2"]


def test_clean_trace_has_no_findings():
    assert D.detect(load_fixture("successful_refund_lookup"), CFG) == []


def test_blank_error_ignored():
    assert D.detect(make_trace([("t", {}, {"ok": 1}, "   ")]), CFG) == []
