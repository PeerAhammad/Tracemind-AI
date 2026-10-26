from app.detectors.base import Detector, DetectorConfig
from app.detectors.unsupported_completion import claims_completion
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Trace
from app.trace_processor.normalize import has_error, tool_calls


class MissingStepDetector(Detector):
    """Task-specific workflow check. Reads initial_configuration['required_steps'] (list of tool names).
    Flags a run that claims completion although a required tool never completed successfully.
    Without required_steps in the trace configuration this detector reports nothing."""

    name = "missing_required_step"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        required = trace.initial_configuration.get("required_steps")
        if not isinstance(required, list) or not required:
            return []
        claimed, final = claims_completion(trace)
        if not claimed:
            return []
        done = {e.tool_name for e in tool_calls(trace) if not has_error(e)}
        missing = [s for s in required if s not in done]
        if not missing:
            return []
        anchor = final or trace.events[-1]
        return [Finding(
            finding_id=f"{trace.run_id}:missing_step:{anchor.event_id}",
            category=FailureCategory.MISSING_STEP,
            severity=Severity.HIGH,
            evidence_event_ids=[anchor.event_id],
            observed_facts=[
                f"Required steps for this task: {', '.join(required)}.",
                f"No successful call to: {', '.join(missing)}.",
                "The run nevertheless reports completion.",
            ],
            explanation="The workflow requires steps that never completed successfully, yet the run claims it is done.",
            likely_root_cause="Hypothesis: the agent's workflow does not enforce prerequisites before finishing.",
            alternative_explanations=["The required_steps list may be stricter than the task really needs."],
            recommended_action=f"Add explicit workflow prerequisites: block completion until {', '.join(missing)} succeed.",
        )]
