import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ValidationError

from app import storage
from app.detectors.engine import AnalysisResult, analyze_trace
from app.diagnosis.corrections import propose_corrections
from app.evaluation.compare import compare_runs
from app.evaluation.sweep import evaluate_config
from app.runner.agent import run_task
from app.runner.tasks import get_task, load_tasks
from app.schemas.finding import VerificationStatus
from app.schemas.run import Run, RunConfig

tasks_router = APIRouter(prefix="/api/tasks", tags=["tasks"])
runs_router = APIRouter(prefix="/api/runs", tags=["runs"])


def _merge_config(base: RunConfig, changes: dict[str, Any]) -> RunConfig:
    try:
        return RunConfig.model_validate({**base.model_dump(), **changes})
    except ValidationError as e:
        raise HTTPException(422, detail=json.loads(e.json(include_url=False)))


def _execute(task_id: str, config: RunConfig, parent: str | None = None) -> Run:
    try:
        task = get_task(task_id)
    except KeyError:
        raise HTTPException(404, f"Unknown task_id '{task_id}'")
    run = run_task(task, config, f"run-{uuid.uuid4().hex[:8]}", parent)
    storage.save_run(run)
    storage.save_trace(run.to_trace())   # so /api/traces/{run_id} and /analyze work for runs too
    return run


def _get_run(run_id: str) -> Run:
    run = storage.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


class RunRequest(BaseModel):
    task_id: str
    configuration: dict[str, Any] = {}


class ReplayRequest(BaseModel):
    approved: bool = False
    approved_changes: dict[str, Any] = {}


class EvaluateRequest(BaseModel):
    configuration: dict[str, Any]


# ---- tasks ----
@tasks_router.get("")
def list_tasks():
    return [{"task_id": t.task_id, "description": t.description} for t in load_tasks().values()]


@tasks_router.post("/run", status_code=201)
def run_controlled_task(req: RunRequest):
    return _execute(req.task_id, _merge_config(RunConfig(), req.configuration))


@tasks_router.post("/evaluate")
def evaluate(req: EvaluateRequest):
    """Run all tasks under the default baseline and a candidate config; reports fixes and regressions."""
    return evaluate_config(_merge_config(RunConfig(), req.configuration))


# ---- runs ----
@runs_router.get("/{run_id}")
def read_run(run_id: str):
    return _get_run(run_id)


@runs_router.post("/{run_id}/analyze")
def analyze_run(run_id: str) -> AnalysisResult:
    result = analyze_trace(_get_run(run_id).to_trace())
    storage.save_findings(run_id, result)
    return result


@runs_router.get("/{run_id}/corrections")
def read_corrections(run_id: str):
    run = _get_run(run_id)
    result = analyze_trace(run.to_trace())
    proposals = propose_corrections(run, result.findings)
    covered = {fid for p in proposals for fid in p.finding_ids}
    result = result.model_copy(update={"findings": [
        f.model_copy(update={"verification_status": VerificationStatus.FIX_PROPOSED}) if f.finding_id in covered else f
        for f in result.findings]})
    storage.save_findings(run_id, result)
    combined: dict[str, Any] = {}
    for p in proposals:
        combined.update(p.config_changes)
    return {"run_id": run_id, "corrections": proposals, "combined_changes": combined}


@runs_router.post("/{run_id}/replay", status_code=201)
def replay(run_id: str, req: ReplayRequest):
    run = _get_run(run_id)
    if not req.approved:
        raise HTTPException(400, "Corrections must be explicitly approved (approved: true) before replay.")
    if not req.approved_changes:
        raise HTTPException(400, "approved_changes is empty; nothing to apply.")
    config = _merge_config(run.configuration, req.approved_changes)
    return _execute(run.task_id, config, parent=run.run_id)


@runs_router.get("/{run_id}/comparison")
def comparison(run_id: str):
    """Accepts either the baseline run id (compares with its latest replay) or a replayed run id."""
    run = _get_run(run_id)
    if run.parent_run_id:
        base, corr = _get_run(run.parent_run_id), run
    else:
        child = storage.latest_child_run(run_id)
        if child is None:
            raise HTTPException(404, "No replay exists for this run yet; call POST /api/runs/{id}/replay")
        base, corr = run, child
    base_res, corr_res = analyze_trace(base.to_trace()), analyze_trace(corr.to_trace())
    cmp = compare_runs(base, corr, base_res, corr_res)
    status = {v.finding_id: v.verification_status for v in cmp.verifications}
    storage.save_findings(base.run_id, base_res.model_copy(update={"findings": [
        f.model_copy(update={"verification_status": status[f.finding_id]}) for f in base_res.findings]}))
    return cmp
