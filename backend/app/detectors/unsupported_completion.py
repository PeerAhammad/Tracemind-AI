import re

from app.detectors.base import Detector, DetectorConfig
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Event, EventType, ExecutionStatus, Trace
from app.trace_processor.normalize import has_empty_input_value, has_error, is_empty, tool_calls

_CLAIM = re.compile(r"\b(complete[d]?|done|success(ful(ly)?)?|finished|resolved)\b", re.I)
_NEGATION = re.compile(r"\b(not|unable|couldn't|cannot|can't|failed|unsuccessful)\b", re.I)


def claims_completion(trace: Trace) -> tuple[bool, Event | None]:
    finals = [e for e in trace.events if e.event_type == EventType.FINAL_ANSWER]
    final = finals[-1] if finals else None
    if trace.execution_status == ExecutionStatus.COMPLETED:
        return True, final
    if final is not None and isinstance(final.output, str):
        if _CLAIM.search(final.output) and not _NEGATION.search(final.output):
            return True, final
    return False, final


class UnsupportedCompletionDetector(Detector):
    """Flags traces that claim success while the recorded evidence does not support it.

    Rule 1: the last tool call ended in an error.
    Rule 2: a tool call received an empty input value after an earlier tool returned an empty result
            (the agent kept going on top of nothing).
    Heuristic only: it checks the data flow in the trace, not whether the final text is true.
    """

    name = "unsupported_completion_claim"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        claimed, final = claims_completion(trace)
        if not claimed:
            return []
        final_ids = [final.event_id] if final else []
        calls = tool_calls(trace)
        findings: list[Finding] = []

        if calls and has_error(calls[-1]):
            last = calls[-1]
            findings.append(Finding(
                finding_id=f"{trace.run_id}:unsupported_completion:last_call_error",
                category=FailureCategory.UNSUPPORTED_COMPLETION,
                severity=Severity.HIGH,
                evidence_event_ids=[last.event_id] + final_ids,
                observed_facts=[
                    "The run reports completion.",
                    f"The last tool call ('{last.tool_name}', step {last.step_number}) ended with an error.",
                ],
                explanation="Success was claimed although the final tool call failed.",
                likely_root_cause="Hypothesis: the agent does not check tool results before declaring the task done.",
                alternative_explanations=["The failed call may have been optional for the task."],
                recommended_action="Require a successful result from the final required step before the agent may declare completion.",
            ))

        empty_out = None
        for e in calls:
            if empty_out is not None and has_empty_input_value(e.input):
                findings.append(Finding(
                    finding_id=f"{trace.run_id}:unsupported_completion:empty_dataflow",
                    category=FailureCategory.UNSUPPORTED_COMPLETION,
                    severity=Severity.HIGH,
                    evidence_event_ids=[empty_out.event_id, e.event_id] + final_ids,
                    observed_facts=[
                        "The run reports completion.",
                        f"'{empty_out.tool_name}' returned an empty result at step {empty_out.step_number}.",
                        f"'{e.tool_name}' was then called at step {e.step_number} with an empty input value.",
                    ],
                    explanation="The task was declared complete, but a later step ran on empty data, so its output is not grounded in retrieved evidence.",
                    likely_root_cause="Hypothesis: the workflow has no prerequisite requiring a non-empty retrieval before the next step.",
                    alternative_explanations=["The empty input may be a legitimate optional argument."],
                    recommended_action="Require a successful, non-empty retrieval before the dependent step, and require evidence before declaring completion.",
                ))
                break
            if is_empty(e.output):
                empty_out = e
        return findings
