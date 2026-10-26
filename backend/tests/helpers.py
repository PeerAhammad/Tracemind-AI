from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas.trace import Trace

FIXTURES = Path(__file__).resolve().parents[2] / "benchmarks" / "fixtures"


def load_fixture(name: str) -> Trace:
    return Trace.model_validate_json((FIXTURES / f"{name}.json").read_text())


def make_trace(calls, final=None, status="completed", run_id="t"):
    """calls: list of (tool, input, output[, error]) tuples."""
    t0 = datetime(2026, 10, 12, tzinfo=timezone.utc)
    events = []
    for i, c in enumerate(calls, start=1):
        events.append({
            "event_id": f"e{i}", "step_number": i, "event_type": "tool_call", "tool_name": c[0],
            "input": c[1], "output": c[2], "error_details": c[3] if len(c) > 3 else None,
            "timestamp": (t0 + timedelta(seconds=i)).isoformat(), "duration_ms": 10,
        })
    if final is not None:
        n = len(calls) + 1
        events.append({"event_id": f"e{n}", "step_number": n, "event_type": "final_answer",
                       "output": final, "timestamp": (t0 + timedelta(seconds=n)).isoformat()})
    return Trace.model_validate({
        "run_id": run_id, "task_description": "test task", "execution_status": status, "events": events,
    })
