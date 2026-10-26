from app.detectors.base import Detector, DetectorConfig
from app.detectors.unsupported_completion import claims_completion
from app.schemas.finding import FailureCategory, Finding, Severity
from app.schemas.trace import Trace
from app.trace_processor.normalize import has_error, tool_calls


def _violates(value, rule) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if "max" in rule and value > rule["max"]:
        return True
    if "min" in rule and value < rule["min"]:
        return True
    return "equals" in rule and value != rule["equals"]


class ContradictionDetector(Detector):
    """Reads initial_configuration['constraints'], a list of {tool, field, max|min|equals}.
    Flags a completion claim when the LAST successful call to that tool recorded a value violating the constraint."""

    name = "evidence_constraint_contradiction"

    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        rules = trace.initial_configuration.get("constraints")
        if not isinstance(rules, list):
            return []
        claimed, final = claims_completion(trace)
        if not claimed:
            return []
        calls = tool_calls(trace)
        findings: list[Finding] = []
        for rule in rules:
            if not (isinstance(rule, dict) and "tool" in rule and "field" in rule):
                continue
            matching = [c for c in calls if c.tool_name == rule["tool"] and not has_error(c)
                        and isinstance(c.output, dict) and rule["field"] in c.output]
            if not matching:
                continue
            last = matching[-1]
            value = last.output[rule["field"]]
            if _violates(value, rule):
                bound = {k: rule[k] for k in ("max", "min", "equals") if k in rule}
                findings.append(Finding(
                    finding_id=f"{trace.run_id}:contradiction:{last.event_id}:{rule['field']}",
                    category=FailureCategory.CONTRADICTION,
                    severity=Severity.HIGH,
                    evidence_event_ids=[last.event_id] + ([final.event_id] if final else []),
                    observed_facts=[
                        f"'{last.tool_name}' recorded {rule['field']}={value} at step {last.step_number}.",
                        f"Task constraint on {rule['field']}: {bound}.",
                        "The run reports completion despite the violated constraint.",
                    ],
                    explanation="The recorded evidence contradicts a task constraint, but the run claims success.",
                    likely_root_cause="Hypothesis: the agent does not check tool outputs against the task's constraints.",
                    alternative_explanations=["The constraint may have been relaxed by the user outside this trace."],
                    recommended_action="Validate tool outputs against task constraints and require evidence that they hold before declaring completion.",
                ))
        return findings
