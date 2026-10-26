from app import storage
from app.runner.agent import run_task
from app.runner.tasks import get_task
from app.schemas.run import RunConfig


def test_run_and_trace_persist_in_sqlite():
    run = run_task(get_task("refund_ok"), RunConfig(), "r-persist")
    storage.save_run(run)
    storage.save_trace(run.to_trace())
    assert storage.get_run("r-persist").events == run.events
    assert storage.get_trace("r-persist").run_id == "r-persist"
    assert storage.get_run("missing") is None and storage.get_trace("missing") is None


def test_latest_child_run():
    parent = run_task(get_task("refund_ok"), RunConfig(), "p")
    c1 = run_task(get_task("refund_ok"), RunConfig(max_retries=1), "c1", "p")
    c2 = run_task(get_task("refund_ok"), RunConfig(max_retries=0), "c2", "p")
    for r in (parent, c1, c2):
        storage.save_run(r)
    assert storage.latest_child_run("p").run_id == "c2"
    assert storage.latest_child_run("c2") is None
