from app.detectors.base import DetectorConfig
from app.detectors.repeated_calls import RepeatedCallDetector
from tests.helpers import load_fixture, make_trace

D = RepeatedCallDetector()
CFG = DetectorConfig()
EMPTY = {"results": []}


def test_flags_three_identical_calls_with_same_result():
    f = D.detect(make_trace([("search", {"q": "a"}, EMPTY)] * 3), CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e1", "e2", "e3"]


def test_demo_fixture_flagged():
    f = D.detect(load_fixture("repeated_search_unsupported_claim"), CFG)
    assert [x.evidence_event_ids for x in f] == [["e1", "e2", "e3"]]


def test_two_identical_calls_not_flagged():
    assert D.detect(make_trace([("search", {"q": "a"}, EMPTY)] * 2), CFG) == []


def test_changing_result_is_legitimate_polling():
    calls = [("poll", {"id": 1}, {"s": "pending"})] * 2 + [("poll", {"id": 1}, {"s": "done"})]
    assert D.detect(make_trace(calls), CFG) == []


def test_changing_input_not_flagged():
    calls = [("search", {"q": f"q{i}"}, EMPTY) for i in range(4)]
    assert D.detect(make_trace(calls), CFG) == []


def test_cosmetic_input_differences_are_equivalent():
    calls = [("search", {"q": "Refund Policy"}, EMPTY), ("search", {"q": " refund  policy"}, EMPTY),
             ("search", {"q": "refund policy"}, EMPTY)]
    assert len(D.detect(make_trace(calls), CFG)) == 1


def test_interleaved_calls_not_flagged():
    calls = [("a", {}, EMPTY), ("b", {}, EMPTY)] * 3
    assert D.detect(make_trace(calls), CFG) == []


def test_allow_list_and_threshold_config():
    t = make_trace([("poll", {}, EMPTY)] * 3)
    assert D.detect(t, DetectorConfig(allow_repeat_tools=frozenset({"poll"}))) == []
    assert len(D.detect(make_trace([("x", {}, EMPTY)] * 2), DetectorConfig(repeat_threshold=2))) == 1
