from typing import Optional

from pydantic import BaseModel

from app.detectors.base import Detector, DetectorConfig
from app.detectors.contradiction import ContradictionDetector
from app.detectors.invalid_sequence import InvalidSequenceDetector
from app.detectors.missing_steps import MissingStepDetector
from app.detectors.repeated_calls import RepeatedCallDetector
from app.detectors.tool_errors import ToolErrorDetector
from app.detectors.unsupported_completion import UnsupportedCompletionDetector
from app.schemas.finding import Finding
from app.schemas.trace import Trace

DEFAULT_DETECTORS: list[Detector] = [
    RepeatedCallDetector(),
    ToolErrorDetector(),
    UnsupportedCompletionDetector(),
    MissingStepDetector(),
    InvalidSequenceDetector(),
    ContradictionDetector(),
]


class AnalysisResult(BaseModel):
    run_id: str
    findings: list[Finding]
    detector_errors: list[str] = []


def analyze_trace(
    trace: Trace,
    detectors: Optional[list[Detector]] = None,
    config: Optional[DetectorConfig] = None,
) -> AnalysisResult:
    """Run every detector independently; one crashing detector never hides the others' findings."""
    config = config or DetectorConfig()
    step_of = {e.event_id: e.step_number for e in trace.events}
    findings: list[Finding] = []
    errors: list[str] = []
    for d in detectors if detectors is not None else DEFAULT_DETECTORS:
        try:
            findings.extend(d.detect(trace, config))
        except Exception as exc:  # noqa: BLE001 - isolate detector failures
            errors.append(f"{d.name}: {type(exc).__name__}: {exc}")
    findings.sort(key=lambda f: (min(step_of.get(i, 10**9) for i in f.evidence_event_ids), f.finding_id))
    return AnalysisResult(run_id=trace.run_id, findings=findings, detector_errors=errors)
