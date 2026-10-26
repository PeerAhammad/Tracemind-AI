"""SQLite persistence (stdlib sqlite3). Schema is created on first connection (controlled init, no migrations needed yet)."""
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.detectors.engine import AnalysisResult
from app.schemas.run import Run
from app.schemas.trace import Trace

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces   (run_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (run_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs     (run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,
                                     parent_run_id TEXT, data TEXT NOT NULL);
"""


def _db_path() -> str:
    return os.getenv("TRACEMIND_DB", "tracemind.db")


@contextmanager
def _conn():
    c = sqlite3.connect(_db_path())
    try:
        c.executescript(SCHEMA)
        yield c
        c.commit()
    finally:
        c.close()


def save_trace(trace: Trace) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO traces VALUES (?, ?)", (trace.run_id, trace.model_dump_json()))
        c.execute("DELETE FROM findings WHERE run_id = ?", (trace.run_id,))  # stale analysis


def get_trace(run_id: str) -> Optional[Trace]:
    with _conn() as c:
        row = c.execute("SELECT data FROM traces WHERE run_id = ?", (run_id,)).fetchone()
    return Trace.model_validate_json(row[0]) if row else None


def save_findings(run_id: str, result: AnalysisResult) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO findings VALUES (?, ?)", (run_id, result.model_dump_json()))


def get_findings(run_id: str) -> Optional[AnalysisResult]:
    with _conn() as c:
        row = c.execute("SELECT data FROM findings WHERE run_id = ?", (run_id,)).fetchone()
    return AnalysisResult.model_validate_json(row[0]) if row else None


def save_run(run: Run) -> None:
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, ?, ?)",
                  (run.run_id, run.task_id, run.parent_run_id, run.model_dump_json()))


def get_run(run_id: str) -> Optional[Run]:
    with _conn() as c:
        row = c.execute("SELECT data FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return Run.model_validate_json(row[0]) if row else None


def latest_child_run(parent_run_id: str) -> Optional[Run]:
    with _conn() as c:
        row = c.execute("SELECT data FROM runs WHERE parent_run_id = ? ORDER BY rowid DESC LIMIT 1",
                        (parent_run_id,)).fetchone()
    return Run.model_validate_json(row[0]) if row else None
