from app.detectors.base import DetectorConfig
from app.detectors.contradiction import ContradictionDetector
from app.detectors.invalid_sequence import InvalidSequenceDetector
from app.detectors.missing_steps import MissingStepDetector
from tests.helpers import make_trace

CFG = DetectorConfig()


def _with(trace, **cfg):
    return trace.model_copy(update={"initial_configuration": cfg})


def test_missing_step_flagged_only_when_completion_claimed():
    t = make_trace([("execute", {}, {"ok": 1})], final="Task complete")
    t = _with(t, required_steps=["validate", "execute"])
    f = MissingStepDetector().detect(t, CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e2"]
    honest = _with(make_trace([("execute", {}, {"ok": 1})], final="Task failed", status="failed"),
                   required_steps=["validate", "execute"])
    assert MissingStepDetector().detect(honest, CFG) == []


def test_missing_step_satisfied_or_unconfigured_is_silent():
    t = make_trace([("validate", {}, {"ok": 1}), ("execute", {}, {"ok": 1})], final="Task complete")
    assert MissingStepDetector().detect(_with(t, required_steps=["validate", "execute"]), CFG) == []
    assert MissingStepDetector().detect(t, CFG) == []


def test_errored_required_step_does_not_count():
    t = _with(make_trace([("validate", {}, None, "boom")], final="done"), required_steps=["validate"])
    assert len(MissingStepDetector().detect(t, CFG)) == 1


def test_invalid_sequence_flags_call_made_too_early():
    t = _with(make_trace([("b", {}, {"x": 1}), ("a", {}, {"x": 1})]), sequence_rules=[["a", "b"]])
    f = InvalidSequenceDetector().detect(t, CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e1"]


def test_valid_sequence_and_bad_rule_shapes_are_silent():
    ok = _with(make_trace([("a", {}, {"x": 1}), ("b", {}, {"x": 1})]), sequence_rules=[["a", "b"]])
    assert InvalidSequenceDetector().detect(ok, CFG) == []
    weird = _with(make_trace([("b", {}, {"x": 1})]), sequence_rules=["oops", ["only-one"]])
    assert InvalidSequenceDetector().detect(weird, CFG) == []


def test_contradiction_uses_last_call_and_requires_claim():
    rule = [{"tool": "quote", "field": "price", "max": 500}]
    bad = _with(make_trace([("quote", {}, {"price": 720})], final="Booked, done"), constraints=rule)
    f = ContradictionDetector().detect(bad, CFG)
    assert len(f) == 1 and f[0].evidence_event_ids == ["e1", "e2"]
    fixed = _with(make_trace([("quote", {}, {"price": 720}), ("quote", {}, {"price": 450})], final="Booked, done"),
                  constraints=rule)
    assert ContradictionDetector().detect(fixed, CFG) == []
    no_claim = _with(make_trace([("quote", {}, {"price": 720})], final="Task failed", status="failed"), constraints=rule)
    assert ContradictionDetector().detect(no_claim, CFG) == []


def test_contradiction_ignores_non_numeric_and_bool():
    t = _with(make_trace([("quote", {}, {"price": True})], final="done"),
              constraints=[{"tool": "quote", "field": "price", "max": 0}])
    assert ContradictionDetector().detect(t, CFG) == []
