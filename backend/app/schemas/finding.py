from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    REPEATED_CALL = "repeated_call_no_progress"
    MISSING_STEP = "missing_required_step"
    INVALID_SEQUENCE = "invalid_action_sequence"
    TOOL_ERROR = "explicit_tool_error"
    UNSUPPORTED_COMPLETION = "unsupported_completion_claim"
    CONTRADICTION = "evidence_constraint_contradiction"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VerificationStatus(str, Enum):
    DETECTED = "detected"
    FIX_PROPOSED = "fix_proposed"
    FIX_VERIFIED = "fix_verified"          # only after a replay confirms it
    FIX_NOT_EFFECTIVE = "fix_not_effective"


class Finding(BaseModel):
    finding_id: str
    category: FailureCategory
    severity: Severity
    evidence_event_ids: list[str] = Field(min_length=1)
    observed_facts: list[str]              # directly in the trace
    explanation: str
    likely_root_cause: str                 # hypothesis, labelled as such in UI
    alternative_explanations: list[str] = Field(default_factory=list)
    recommended_action: str
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    explanation_source: str = "rule_based"  # or "llm"
    verification_status: VerificationStatus = VerificationStatus.DETECTED
