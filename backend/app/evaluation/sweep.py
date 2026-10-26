"""Run every task under a baseline and a candidate config; report fixes and regressions from real runs."""
from typing import Optional

from pydantic import BaseModel

from app.detectors.engine import analyze_trace
from app.runner.agent import run_task
from app.runner.tasks import load_tasks
from app.schemas.run import RunConfig


class SweepRow(BaseModel):
    task_id: str
    outcome_before: str
    outcome_after: str
    tool_calls_before: int
    tool_calls_after: int
    duration_ms_before: float
    duration_ms_after: float
    findings_before: int
    findings_after: int


class SweepResult(BaseModel):
    baseline_config: RunConfig
    candidate_config: RunConfig
    rows: list[SweepRow]
    tasks: int
    completion_rate_before: float
    completion_rate_after: float
    tool_calls_before: int
    tool_calls_after: int
    duration_ms_before: float
    duration_ms_after: float
    tasks_fixed: list[str]
    tasks_regressed: list[str]
    data_source: str = "live measurement from deterministic mock-tool runs; durations are simulated"


def evaluate_config(candidate: RunConfig, baseline: Optional[RunConfig] = None) -> SweepResult:
    baseline = baseline or RunConfig()
    rows = []
    for task in load_tasks().values():
        b = run_task(task, baseline, f"sweep-base-{task.task_id}")
        c = run_task(task, candidate, f"sweep-cand-{task.task_id}")
        rows.append(SweepRow(
            task_id=task.task_id, outcome_before=b.task_outcome, outcome_after=c.task_outcome,
            tool_calls_before=b.tool_call_count, tool_calls_after=c.tool_call_count,
            duration_ms_before=b.duration_ms, duration_ms_after=c.duration_ms,
            findings_before=len(analyze_trace(b.to_trace()).findings),
            findings_after=len(analyze_trace(c.to_trace()).findings)))
    n = len(rows)
    return SweepResult(
        baseline_config=baseline, candidate_config=candidate, rows=rows, tasks=n,
        completion_rate_before=sum(r.outcome_before == "success" for r in rows) / n if n else 0.0,
        completion_rate_after=sum(r.outcome_after == "success" for r in rows) / n if n else 0.0,
        tool_calls_before=sum(r.tool_calls_before for r in rows), tool_calls_after=sum(r.tool_calls_after for r in rows),
        duration_ms_before=sum(r.duration_ms_before for r in rows), duration_ms_after=sum(r.duration_ms_after for r in rows),
        tasks_fixed=[r.task_id for r in rows if r.outcome_before == "failure" and r.outcome_after == "success"],
        tasks_regressed=[r.task_id for r in rows if r.outcome_before == "success" and r.outcome_after == "failure"])
