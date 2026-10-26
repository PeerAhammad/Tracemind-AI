from fastapi import APIRouter, HTTPException

from app import storage
from app.evaluation.benchmark import BenchmarkResult, load_saved_results, load_scenarios, run_benchmark

router = APIRouter(prefix="/api/benchmark", tags=["benchmark"])


@router.get("")
def live_results() -> BenchmarkResult:
    """Recomputed on every call from the labelled scenarios and the current detectors."""
    return run_benchmark()


@router.get("/saved")
def saved_results():
    """The last result stored with the repo (benchmarks/expected_results). Static, may be older than the code."""
    saved = load_saved_results()
    if saved is None:
        raise HTTPException(404, "No saved results; run: python -m app.evaluation.run_benchmark --write")
    return {**saved, "data_source": "saved results file, not recomputed"}


@router.get("/scenarios")
def list_scenarios():
    return [{"scenario_id": s.scenario_id, "split": s.split, "description": s.description,
             "expected_task_outcome": s.expected_task_outcome,
             "ground_truth_categories": sorted(s.ground_truth_failures), "notes": s.notes}
            for s in load_scenarios()]


@router.get("/scenarios/{scenario_id}")
def read_scenario(scenario_id: str):
    for s in load_scenarios():
        if s.scenario_id == scenario_id:
            return s
    raise HTTPException(404, "Scenario not found")


@router.post("/scenarios/{scenario_id}/load", status_code=201)
def load_scenario_as_trace(scenario_id: str):
    """Stores the scenario's trace so the normal /api/traces/{id} and /analyze endpoints work on it."""
    for s in load_scenarios():
        if s.scenario_id == scenario_id:
            storage.save_trace(s.trace)
            return {"id": s.trace.run_id, "event_count": len(s.trace.events)}
    raise HTTPException(404, "Scenario not found")
