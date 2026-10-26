from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class EventType(str, Enum):
    TOOL_CALL = "tool_call"
    MODEL_MESSAGE = "model_message"
    FINAL_ANSWER = "final_answer"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"    # agent reported success
    FAILED = "failed"          # agent reported failure
    INCOMPLETE = "incomplete"  # ended without a report


class Event(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    step_number: int = Field(ge=1)
    event_type: EventType
    tool_name: Optional[str] = None
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    timestamp: datetime
    duration_ms: float = Field(default=0, ge=0)
    error_details: Optional[str] = None

    @model_validator(mode="after")
    def tool_call_needs_name(self):
        if self.event_type == EventType.TOOL_CALL and not self.tool_name:
            raise ValueError(f"{self.event_id}: tool_call events require tool_name")
        return self


class Trace(BaseModel):
    run_id: str = Field(min_length=1, max_length=64)
    task_description: str = Field(min_length=1, max_length=2000)
    initial_configuration: dict[str, Any] = Field(default_factory=dict)
    events: list[Event] = Field(min_length=1, max_length=2000)
    execution_status: ExecutionStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @model_validator(mode="after")
    def events_are_ordered_and_unique(self):
        ids = [e.event_id for e in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("event_id values must be unique")
        steps = [e.step_number for e in self.events]
        if steps != sorted(set(steps)):
            raise ValueError("step_number must be strictly increasing")
        return self
