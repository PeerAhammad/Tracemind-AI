from app.detectors.base import Detector, DetectorConfig
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Trace
from app.trace_processor.normalize import canonical, has_error, short, tool_calls


def _signature(e):
    return (e.tool_name, canonical(e.input), canonical(e.output), canonical(e.error_details))


class RepeatedCallDetector(Detector):
    """Flags runs of >= threshold back-to-back tool calls with equivalent input AND equivalent result.

    Deliberately NOT flagged (legitimate retries / progress):
      - the result changed between calls (e.g. error then success, pending then done)
      - the input changed
      - calls separated by a different tool call
      - tools listed in config.allow_repeat_tools
    """

    name = "repeated_call_no_progress"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        calls = tool_calls(trace)
        findings: list[Finding] = []
        i = 0
        while i < len(calls):
            sig = _signature(calls[i])
            j = i + 1
            while j < len(calls) and _signature(calls[j]) == sig:
                j += 1
            run = calls[i:j]
            first, last = run[0], run[-1]
            if len(run) >= config.repeat_threshold and first.tool_name not in config.allow_repeat_tools:
                errored = has_error(first)
                findings.append(Finding(
                    finding_id=f"{trace.run_id}:repeated_call:{first.event_id}",
                    category=FailureCategory.REPEATED_CALL,
                    severity=Severity.HIGH if len(run) >= 5 else Severity.MEDIUM,
                    evidence_event_ids=[e.event_id for e in run],
                    observed_facts=[
                        f"Tool '{first.tool_name}' was called {len(run)} times consecutively "
                        f"(steps {first.step_number}-{last.step_number}) with equivalent input.",
                        "Every call returned an equivalent " + ("error." if errored else "result."),
                        f"Input: {short(first.input)}",
                    ],
                    explanation=(
                        "Back-to-back calls with the same input produced the same result each time, "
                        "so the repetition made no measurable progress."
                    ),
                    likely_root_cause=(
                        "Hypothesis: the agent has no retry limit and no rule for changing its input "
                        "after an unchanged result. The trace shows the repetition, not why it happened."
                    ),
                    alternative_explanations=[
                        "The tool may be ignoring part of the input, so changing the input would not help either.",
                        "The call may be an intentional poll; if so, add the tool to the allow-list.",
                    ],
                    recommended_action=(
                        "Add a maximum retry limit for this tool and require the agent to change its input "
                        "or stop after an unchanged result."
                    ),
                ))
            i = j
        return findings
