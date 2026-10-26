"""Benchmark evaluation. Unit of analysis: one (scenario, failure category) cell, labelled present/absent by hand."""
import json
import os
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, model_validator

from app.detectors.base import Detector, DetectorConfig
from app.detectors.engine import analyze_trace
from app.evaluation.sweep import SweepResult, evaluate_config
from app.schemas.finding import FailureCategory
from app.schemas.run import RunConfig
from app.schemas.trace import Trace

CATEGORIES = [c.value for c in FailureCategory]
FULL_FIX = RunConfig(max_retries=1, reformulate_on_empty=True, require_retrieval_before_summary=True)

LIMITATIONS = [
    "28 hand-written scenarios: far too few to establish general reliability of the detectors.",
    "Ground truth, detectors and scenarios were all written by the same team; the held-out set was written after the "
    "detector code was frozen, but it is not independent or blind.",
    "Traces are synthetic and short; real agent traces are noisier.",
    "Missing-step, invalid-sequence and contradiction detectors only work when the trace configuration declares "
    "required_steps, sequence_rules or constraints.",
    "Corrective-change effects are measured only on the 3 runnable tasks (runner_sweep), not on every scenario.",
    "Durations in runner_sweep are simulated by deterministic mock tools; token usage is not measured.",
]


def scenarios_dir() -> Path:
    env = os.getenv("TRACEMIND_SCENARIOS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "benchmarks" / "scenarios"


def saved_results_path() -> Path:
    return Path(__file__).resolve().parents[3] / "benchmarks" / "expected_results" / "benchmark_results.json"


class Scenario(BaseModel):
    scenario_id: str
    split: Literal["dev", "heldout"]
    description: str
    notes: str = ""
    expected_task_outcome: Literal["success", "failure"]
    ground_truth_failures: dict[str, list[str]]      # category -> minimal evidence event ids
    expected_detector_behavior: str
    expected_correction: str
    trace: Trace

    @model_validator(mode="after")
    def labels_are_consistent(self):
        ids = {e.event_id for e in self.trace.events}
        for cat, ev in self.ground_truth_failures.items():
            if cat not in CATEGORIES:
                raise ValueError(f"{self.scenario_id}: unknown category {cat}")
            if not ev or not set(ev) <= ids:
                raise ValueError(f"{self.scenario_id}: bad evidence ids for {cat}")
        return self


class Confusion(BaseModel):
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    precision: Optional[float] = None   # None when undefined (no positive predictions)
    recall: Optional[float] = None      # None when undefined (no true failures)
    false_positive_rate: Optional[float] = None


def _ratio(n: int, d: int) -> Optional[float]:
    return round(n / d, 4) if d else None


def _confusion(tp: int, fp: int, tn: int, fn: int) -> Confusion:
    return Confusion(tp=tp, fp=fp, tn=tn, fn=fn, precision=_ratio(tp, tp + fp),
                     recall=_ratio(tp, tp + fn), false_positive_rate=_ratio(fp, fp + tn))


class SplitMetrics(Confusion):
    scenarios: int = 0
    clean_scenarios: int = 0            # scenarios with no ground-truth failure
    clean_scenarios_flagged: int = 0    # ... where at least one finding was still raised
    exact_match_scenarios: int = 0      # predicted category set == true category set
    evidence_hit_rate: Optional[float] = None   # share of true positives whose evidence covers the labelled events
    per_category: dict[str, Confusion] = {}


class ScenarioResult(BaseModel):
    scenario_id: str
    split: str
    truth: dict[str, list[str]]
    predicted: dict[str, list[str]]
    true_positives: list[str]
    false_positives: list[str]
    false_negatives: list[str]
    evidence_hits: dict[str, bool]
    detector_errors: list[str] = []


class BenchmarkResult(BaseModel):
    benchmark_id: str = "tracemind-benchmark-v1"
    total_cases: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: Optional[float]
    recall: Optional[float]
    task_success_rate_of_recorded_scenarios: Optional[float]   # property of the labelled data, not of the detectors
    overall: SplitMetrics
    dev: SplitMetrics
    heldout: SplitMetrics
    scenario_results: list[ScenarioResult]
    runner_sweep: Optional[SweepResult] = None   # baseline_metrics vs corrected_metrics, from live runner runs
    limitations: list[str] = LIMITATIONS
    data_source: str = "live computation over labelled benchmark scenarios"


def load_scenarios() -> list[Scenario]:
    return [Scenario.model_validate_json(p.read_text()) for p in sorted(scenarios_dir().glob("*.json"))]


def _run_scenario(s: Scenario, detectors, config) -> ScenarioResult:
    res = analyze_trace(s.trace, detectors, config)
    predicted: dict[str, list[str]] = {}
    for f in res.findings:
        ids = predicted.setdefault(f.category.value, [])
        ids.extend(i for i in f.evidence_event_ids if i not in ids)
    truth = s.ground_truth_failures
    tp = [c for c in CATEGORIES if c in truth and c in predicted]
    return ScenarioResult(
        scenario_id=s.scenario_id, split=s.split, truth=truth, predicted=predicted,
        true_positives=tp,
        false_positives=[c for c in CATEGORIES if c in predicted and c not in truth],
        false_negatives=[c for c in CATEGORIES if c in truth and c not in predicted],
        evidence_hits={c: set(truth[c]) <= set(predicted[c]) for c in tp},
        detector_errors=res.detector_errors)


def _metrics(rows: list[ScenarioResult]) -> SplitMetrics:
    per = {}
    for cat in CATEGORIES:
        tp = sum(cat in r.true_positives for r in rows)
        fp = sum(cat in r.false_positives for r in rows)
        fn = sum(cat in r.false_negatives for r in rows)
        per[cat] = _confusion(tp, fp, len(rows) - tp - fp - fn, fn)
    tp, fp = sum(c.tp for c in per.values()), sum(c.fp for c in per.values())
    tn, fn = sum(c.tn for c in per.values()), sum(c.fn for c in per.values())
    hits = [h for r in rows for h in r.evidence_hits.values()]
    clean = [r for r in rows if not r.truth]
    return SplitMetrics(
        **_confusion(tp, fp, tn, fn).model_dump(), scenarios=len(rows), clean_scenarios=len(clean),
        clean_scenarios_flagged=sum(bool(r.predicted) for r in clean),
        exact_match_scenarios=sum(set(r.truth) == set(r.predicted) for r in rows),
        evidence_hit_rate=_ratio(sum(hits), len(hits)), per_category=per)


def evaluate_scenarios(scenarios: list[Scenario], detectors: Optional[list[Detector]] = None,
                       config: Optional[DetectorConfig] = None) -> BenchmarkResult:
    rows = [_run_scenario(s, detectors, config) for s in scenarios]
    overall = _metrics(rows)
    outcomes = [s.expected_task_outcome == "success" for s in scenarios]
    return BenchmarkResult(
        total_cases=len(rows), true_positives=overall.tp, false_positives=overall.fp,
        true_negatives=overall.tn, false_negatives=overall.fn, precision=overall.precision, recall=overall.recall,
        task_success_rate_of_recorded_scenarios=_ratio(sum(outcomes), len(outcomes)),
        overall=overall, dev=_metrics([r for r in rows if r.split == "dev"]),
        heldout=_metrics([r for r in rows if r.split == "heldout"]), scenario_results=rows)


def run_benchmark() -> BenchmarkResult:
    result = evaluate_scenarios(load_scenarios())
    return result.model_copy(update={"runner_sweep": evaluate_config(FULL_FIX)})


def load_saved_results() -> Optional[dict]:
    p = saved_results_path()
    return json.loads(p.read_text()) if p.exists() else None
