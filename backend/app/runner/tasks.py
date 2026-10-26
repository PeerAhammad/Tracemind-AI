import os
from pathlib import Path

from app.schemas.run import TaskDefinition


def tasks_dir() -> Path:
    env = os.getenv("TRACEMIND_TASKS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "benchmarks" / "tasks"


def load_tasks() -> dict[str, TaskDefinition]:
    tasks = {}
    for p in sorted(tasks_dir().glob("*.json")):
        t = TaskDefinition.model_validate_json(p.read_text())
        tasks[t.task_id] = t
    return tasks


def get_task(task_id: str) -> TaskDefinition:
    return load_tasks()[task_id]  # KeyError if unknown
