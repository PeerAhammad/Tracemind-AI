from app.detectors.base import Detector, DetectorConfig
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Trace
from app.trace_processor.normalize import has_error, tool_calls


class InvalidSequenceDetector(Detector):
    """Reads initial_configuration['sequence_rules'], a list of [before, after] tool-name pairs.
    Flags the first call to `after` that happens with no earlier successful call to `before`."""

    name = "invalid_action_sequence"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        rules = trace.initial_configuration.get("sequence_rules")
        if not isinstance(rules, list):
            return []
        calls = tool_calls(trace)
        findings: list[Finding] = []
        for rule in rules:
            if not (isinstance(rule, list) and len(rule) == 2):
                continue
            before, after = rule
            for idx, e in enumerate(calls):
                if e.tool_name != after:
                    continue
                if not any(c.tool_name == before and not has_error(c) for c in calls[:idx]):
                    findings.append(Finding(
                        finding_id=f"{trace.run_id}:invalid_sequence:{e.event_id}",
                        category=FailureCategory.INVALID_SEQUENCE,
                        severity=Severity.MEDIUM,
                        evidence_event_ids=[e.event_id],
                        observed_facts=[
                            f"Rule: '{before}' must succeed before '{after}'.",
                            f"'{after}' was called at step {e.step_number} with no earlier successful '{before}'.",
                        ],
                        explanation="A tool was called before its prerequisite action had succeeded.",
                        likely_root_cause="Hypothesis: the workflow does not enforce the order of these actions.",
                        alternative_explanations=["The rule may not apply to this particular task variant."],
                        recommended_action=f"Add an explicit prerequisite: do not allow '{after}' until '{before}' has succeeded.",
                    ))
                    break
        return findings
