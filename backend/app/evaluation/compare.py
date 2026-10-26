from typing import Any

from pydantic import BaseModel

from app.detectors.engine import AnalysisResult
from app.schemas.finding import FailureCategory, VerificationStatus
from app.schemas.run import Run, RunConfig


class RunSummary(BaseModel):
    run_id: str
    configuration: RunConfig
    task_outcome: str
    agent_reported_status: str
    tool_call_count: int
    duration_ms: float
    finding_count: int
    finding_categories: list[str]


class FindingVerification(BaseModel):
    finding_id: str
    category: FailureCategory
    verification_status: VerificationStatus


class Comparison(BaseModel):
    task_id: str
    baseline: RunSummary
    corrected: RunSummary
    config_changes: dict[str, Any]
    outcome_change: str
    tool_call_delta: int
    duration_delta_ms: float
    findings_resolved: list[str]
    findings_remaining: list[str]
    findings_introduced: list[str]
    regression: bool
    verifications: list[FindingVerification]
    data_source: str = "live measurement from deterministic mock-tool runs; durations are simulated"


def _summary(run: Run, res: AnalysisResult) -> RunSummary:
    return RunSummary(
        run_id=run.run_id, configuration=run.configuration, task_outcome=run.task_outcome,
        agent_reported_status=run.agent_reported_status.value, tool_call_count=run.tool_call_count,
        duration_ms=run.duration_ms, finding_count=len(res.findings),
        finding_categories=sorted({f.category.value for f in res.findings}))


def compare_runs(base: Run, corr: Run, base_res: AnalysisResult, corr_res: AnalysisResult) -> Comparison:
    b_cats = {f.category for f in base_res.findings}
    c_cats = {f.category for f in corr_res.findings}
    regression = base.task_outcome == "success" and corr.task_outcome == "failure"
    verifications = [
        FindingVerification(
            finding_id=f.finding_id, category=f.category,
            # Verified only if this failure category is gone in the replay AND the task did not regress.
            verification_status=(VerificationStatus.FIX_VERIFIED
                                 if f.category not in c_cats and not regression
                                 else VerificationStatus.FIX_NOT_EFFECTIVE))
        for f in base_res.findings]
    b_cfg, c_cfg = base.configuration.model_dump(), corr.configuration.model_dump()
    return Comparison(
        task_id=base.task_id,
        baseline=_summary(base, base_res), corrected=_summary(corr, corr_res),
        config_changes={k: v for k, v in c_cfg.items() if b_cfg[k] != v},
        outcome_change=f"{base.task_outcome} -> {corr.task_outcome}",
        tool_call_delta=corr.tool_call_count - base.tool_call_count,
        duration_delta_ms=corr.duration_ms - base.duration_ms,
        findings_resolved=sorted(c.value for c in b_cats - c_cats),
        findings_remaining=sorted(c.value for c in b_cats & c_cats),
        findings_introduced=sorted(c.value for c in c_cats - b_cats),
        regression=regression, verifications=verifications)
