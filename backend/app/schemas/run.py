from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.trace import Event, ExecutionStatus, Trace


class RunConfig(BaseModel):
    """The agent's tunable policy. Unknown keys are rejected so a replay can only change real settings."""
    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=2, ge=0, le=10)           # retries after an empty result or error
    reformulate_on_empty: bool = False                          # try a fallback query after an empty result
    require_retrieval_before_summary: bool = False              # refuse to summarize without retrieved docs


class TaskDefinition(BaseModel):
    task_id: str
    description: str
    query: str
    fallback_queries: list[str] = Field(default_factory=list)
    corpus: dict[str, list[dict[str, str]]]
    fail_first_calls: int = Field(default=0, ge=0)   # injected failure: search errors on its first N calls
    expected_fact: str                               # ground truth the summary must be grounded in
    ungrounded_summary: str                          # what the mock summarizer invents from empty input


class Run(BaseModel):
    run_id: str
    task_id: str
    task_description: str
    configuration: RunConfig
    parent_run_id: Optional[str] = None
    events: list[Event]
    agent_reported_status: ExecutionStatus
    task_outcome: Literal["success", "failure"]      # ground truth: grounded and reported complete
    duration_ms: float                               # simulated, deterministic
    tool_call_count: int
    token_usage: Optional[int] = None                # not available for deterministic mock tools
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_trace(self) -> Trace:
        return Trace(
            run_id=self.run_id,
            task_description=self.task_description,
            initial_configuration=self.configuration.model_dump(),
            events=self.events,
            execution_status=self.agent_reported_status,
        )
