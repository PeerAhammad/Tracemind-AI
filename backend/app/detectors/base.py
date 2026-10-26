from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.finding import Finding
from app.schemas.trace import Trace


@dataclass(frozen=True)
class DetectorConfig:
    # Minimum number of consecutive equivalent calls (same tool, input AND result) to flag.
    repeat_threshold: int = 3
    # Tools where identical repeated calls are expected (e.g. polling).
    allow_repeat_tools: frozenset = frozenset()


class Detector(ABC):
    """A detector is a pure function of the trace: no I/O, no randomness, no LLM."""

    name: str

    @abstractmethod
    def detect(self, trace: Trace, config: DetectorConfig) -> list[Finding]:
        ...
