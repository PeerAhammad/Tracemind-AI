from app.detectors.base import Detector, DetectorConfig
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Trace
from app.trace_processor.normalize import has_error, short, tool_calls


class ToolErrorDetector(Detector):
    """Flags every tool call that recorded error_details.
    Severity is LOW if a later call to the same tool succeeded (recovered), HIGH otherwise."""

    name = "explicit_tool_error"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        calls = tool_calls(trace)
        findings: list[Finding] = []
        for idx, e in enumerate(calls):
            if not has_error(e):
                continue
            recovery = next(
                (c for c in calls[idx + 1:] if c.tool_name == e.tool_name and not has_error(c)), None
            )
            evidence = [e.event_id] + ([recovery.event_id] if recovery else [])
            facts = [
                f"Tool '{e.tool_name}' reported an error at step {e.step_number}: {short(e.error_details)}",
            ]
            facts.append(
                f"A later call to '{e.tool_name}' succeeded at step {recovery.step_number}."
                if recovery else
                f"No later successful call to '{e.tool_name}' appears in the trace."
            )
            findings.append(Finding(
                finding_id=f"{trace.run_id}:tool_error:{e.event_id}",
                category=FailureCategory.TOOL_ERROR,
                severity=Severity.LOW if recovery else Severity.HIGH,
                evidence_event_ids=evidence,
                observed_facts=facts,
                explanation=(
                    "The tool call recorded an explicit error. "
                    + ("It was followed by a successful call, so the task may have recovered."
                       if recovery else "The error was never followed by a successful call to the same tool.")
                ),
                likely_root_cause=(
                    "Hypothesis: invalid input, a missing credential, or a transient service problem. "
                    "Read the recorded error text to tell these apart."
                ),
                alternative_explanations=["The error may be transient and unrelated to the agent's behaviour."],
                recommended_action="Validate tool inputs before execution and handle this error explicitly "
                                   "(bounded retry, fallback tool, or stop and report failure).",
            ))
        return findings
