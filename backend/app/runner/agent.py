"""A deterministic, policy-driven agent. It is NOT an LLM: it is a controlled workflow whose behaviour
depends only on the task and the RunConfig, so a replay with a changed config is a genuine behavioural change."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.runner.tools import MockToolbox
from app.schemas.run import Run, RunConfig, TaskDefinition
from app.schemas.trace import Event, EventType, ExecutionStatus
from app.trace_processor.normalize import is_empty

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def run_task(task: TaskDefinition, config: RunConfig, run_id: str, parent_run_id: Optional[str] = None) -> Run:
    tools = MockToolbox(task)
    events: list[Event] = []
    elapsed = 0.0

    def add(kind, tool=None, inp=None, out=None, err=None, dur=0.0):
        nonlocal elapsed
        n = len(events) + 1
        events.append(Event(
            event_id=f"e{n}", step_number=n, event_type=kind, tool_name=tool, input=inp or {},
            output=out, error_details=err, duration_ms=dur,
            timestamp=BASE + timedelta(milliseconds=elapsed),
        ))
        elapsed += dur

    # 1. retrieval loop
    query, fallbacks, retries, docs = task.query, list(task.fallback_queries), 0, None
    while True:
        out, err, dur = tools.search_docs(query)
        add(EventType.TOOL_CALL, "search_docs", {"query": query}, out, err, dur)
        if err is None and not is_empty(out):
            docs = out["results"]
            break
        if retries >= config.max_retries:
            break
        retries += 1
        if err is None and config.reformulate_on_empty and fallbacks:
            query = fallbacks.pop(0)

    # 2. summarize / finish
    if docs:
        text = " ".join(d["text"] for d in docs)
        out, err, dur = tools.summarize(text)
        add(EventType.TOOL_CALL, "summarize", {"text": text}, out, err, dur)
        final, reported = f"Task complete: {out['summary']}", ExecutionStatus.COMPLETED
    elif config.require_retrieval_before_summary:
        final, reported = "Task failed: no documents could be retrieved, so no summary was produced.", ExecutionStatus.FAILED
    else:
        out, err, dur = tools.summarize("")
        add(EventType.TOOL_CALL, "summarize", {"text": ""}, out, err, dur)
        final, reported = f"Task complete: {out['summary']}", ExecutionStatus.COMPLETED
    add(EventType.FINAL_ANSWER, out=final)

    # 3. ground-truth outcome: reported complete AND the summary was built from text containing the expected fact
    summarize_inputs = [e.input.get("text", "") for e in events if e.tool_name == "summarize"]
    grounded = any(task.expected_fact.lower() in t.lower() for t in summarize_inputs)
    outcome = "success" if reported == ExecutionStatus.COMPLETED and grounded else "failure"

    return Run(
        run_id=run_id, task_id=task.task_id, task_description=task.description, configuration=config,
        parent_run_id=parent_run_id, events=events, agent_reported_status=reported, task_outcome=outcome,
        duration_ms=elapsed, tool_call_count=sum(e.event_type == EventType.TOOL_CALL for e in events),
    )
