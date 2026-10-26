from typing import Any

from pydantic import BaseModel

from app.schemas.finding import FailureCategory, Finding
from app.schemas.run import Run


class Correction(BaseModel):
    correction_id: str
    title: str
    description: str
    finding_ids: list[str]
    config_changes: dict[str, Any]
    requires_approval: bool = True   # nothing is applied until the user approves a replay


def propose_corrections(run: Run, findings: list[Finding]) -> list[Correction]:
    """Rule-based proposals. A proposal is a hypothesis about a fix, not a repair, until a replay verifies it."""
    current = run.configuration.model_dump()
    proposals: list[Correction] = []

    def add(key, title, desc, cats, changes):
        ids = [f.finding_id for f in findings if f.category in cats]
        changes = {k: v for k, v in changes.items() if current.get(k) != v}
        if ids and changes:
            proposals.append(Correction(
                correction_id=f"{run.run_id}:{key}", title=title, description=desc,
                finding_ids=ids, config_changes=changes))

    add("limit_retries", "Limit retries and change the query after an empty result",
        "Cap retries at 1 and try a fallback query instead of repeating the same one.",
        {FailureCategory.REPEATED_CALL}, {"max_retries": 1, "reformulate_on_empty": True})
    add("require_retrieval", "Require a successful retrieval before summarizing",
        "Refuse to summarize without retrieved documents and report failure honestly instead of claiming success.",
        {FailureCategory.UNSUPPORTED_COMPLETION}, {"require_retrieval_before_summary": True})
    return proposals
