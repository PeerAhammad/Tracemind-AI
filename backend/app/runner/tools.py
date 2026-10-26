"""Deterministic mock tools. No network, no randomness, no code execution."""
from typing import Any, Optional

from app.schemas.run import TaskDefinition

SEARCH_MS = 120.0
SUMMARIZE_MS = 300.0


def _norm(q: str) -> str:
    return " ".join(q.lower().split())


class MockToolbox:
    def __init__(self, task: TaskDefinition):
        self.task = task
        self.search_calls = 0
        self._corpus = {_norm(k): v for k, v in task.corpus.items()}

    def search_docs(self, query: str) -> tuple[Any, Optional[str], float]:
        self.search_calls += 1
        if self.search_calls <= self.task.fail_first_calls:
            return None, "503 service unavailable (timeout)", SEARCH_MS
        return {"results": self._corpus.get(_norm(query), [])}, None, SEARCH_MS

    def summarize(self, text: str) -> tuple[Any, Optional[str], float]:
        if not text.strip():
            # Modelled failure: the summarizer invents content when given nothing.
            return {"summary": self.task.ungrounded_summary}, None, SUMMARIZE_MS
        first = text.split(".")[0].strip()
        return {"summary": first + "."}, None, SUMMARIZE_MS
