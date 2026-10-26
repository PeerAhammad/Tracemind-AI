import pytest
from pydantic import ValidationError

from app.runner.agent import run_task
from app.runner.tasks import get_task, load_tasks
from app.schemas.run import RunConfig

FIX = RunConfig(max_retries=1, reformulate_on_empty=True, require_retrieval_before_summary=True)


def _run(task_id, cfg=None):
    return run_task(get_task(task_id), cfg or RunConfig(), "r1")


def test_tasks_load():
    assert set(load_tasks()) == {"refund_empty_search", "refund_ok", "flaky_search_retry"}


def test_baseline_repeats_then_claims_unsupported_success():
    r = _run("refund_empty_search")
    searches = [e for e in r.events if e.tool_name == "search_docs"]
    assert len(searches) == 3 and len({e.input["query"] for e in searches}) == 1
    assert r.agent_reported_status.value == "completed" and r.task_outcome == "failure"
    assert r.tool_call_count == 4 and r.duration_ms == 3 * 120 + 300


def test_correction_genuinely_changes_behaviour_and_outcome():
    r = _run("refund_empty_search", FIX)
    assert [e.input["query"] for e in r.events if e.tool_name == "search_docs"] == ["refund policy", "refunds"]
    assert r.task_outcome == "success" and r.tool_call_count == 3


def test_require_retrieval_alone_fails_honestly():
    r = _run("refund_empty_search", RunConfig(require_retrieval_before_summary=True))
    assert r.agent_reported_status.value == "failed" and r.task_outcome == "failure"
    assert not any(e.tool_name == "summarize" for e in r.events)


def test_runs_are_deterministic():
    a, b = _run("refund_empty_search"), _run("refund_empty_search")
    assert [e.model_dump() for e in a.events] == [e.model_dump() for e in b.events]


def test_flaky_task_legit_retry_succeeds_but_zero_retries_fails():
    assert _run("flaky_search_retry").task_outcome == "success"
    assert _run("flaky_search_retry", RunConfig(max_retries=0)).task_outcome == "failure"


def test_ok_task_succeeds_under_fix_too():
    assert _run("refund_ok").task_outcome == "success" and _run("refund_ok", FIX).task_outcome == "success"


def test_unknown_config_key_rejected():
    with pytest.raises(ValidationError):
        RunConfig.model_validate({"max_retriez": 1})
