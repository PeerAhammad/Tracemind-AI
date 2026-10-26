"""Helpers for comparing trace data without being fooled by cosmetic differences."""
import json
from typing import Any

from app.schemas.trace import Event, EventType, Trace


def normalize_value(v: Any) -> Any:
    """Lowercase/strip/collapse whitespace in strings, recursively, so that
    'Refund Policy ' and 'refund policy' count as equivalent."""
    if isinstance(v, str):
        return " ".join(v.lower().split())
    if isinstance(v, dict):
        return {k: normalize_value(x) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [normalize_value(x) for x in v]
    return v


def canonical(v: Any) -> str:
    return json.dumps(normalize_value(v), sort_keys=True, default=str)


def is_empty(v: Any) -> bool:
    """True for None, blank strings, and containers whose contents are all empty."""
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, dict):
        return all(is_empty(x) for x in v.values())
    if isinstance(v, (list, tuple)):
        return all(is_empty(x) for x in v)
    return False


def has_empty_input_value(inp: dict) -> bool:
    return any(is_empty(x) for x in inp.values())


def has_error(e: Event) -> bool:
    return bool(e.error_details and e.error_details.strip())


def tool_calls(trace: Trace) -> list[Event]:
    return [e for e in trace.events if e.event_type == EventType.TOOL_CALL]


def short(v: Any, limit: int = 160) -> str:
    s = json.dumps(v, sort_keys=True, default=str)
    return s if len(s) <= limit else s[: limit - 3] + "..."
