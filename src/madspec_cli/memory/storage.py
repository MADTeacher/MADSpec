from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..git_ops import get_current_branch
from .records import PROCEDURE_FILES


@dataclass(frozen=True)
class MemoryPaths:
    branch_dir: Path
    memory_dir: Path
    progress: Path
    working_dir: Path
    active_session: Path
    decision_log: Path
    episodes_dir: Path
    events: Path
    semantic_dir: Path
    facts: Path
    decisions: Path
    contracts: Path

    def __getitem__(self, key: str) -> Path:
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def as_dict(self) -> dict[str, Path]:
        return {
            "branch_dir": self.branch_dir,
            "memory_dir": self.memory_dir,
            "progress": self.progress,
            "working_dir": self.working_dir,
            "active_session": self.active_session,
            "decision_log": self.decision_log,
            "episodes_dir": self.episodes_dir,
            "events": self.events,
            "semantic_dir": self.semantic_dir,
            "facts": self.facts,
            "decisions": self.decisions,
            "contracts": self.contracts,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_branch(project_path: Path) -> str:
    return get_current_branch(project_path)


def _default_progress_state() -> dict[str, Any]:
    return {
        "currentImplementStep": None,
        "completedSteps": [],
        "plannedSteps": [],
        "stepStatus": {},
        "coversFunctions": {},
        "planningMetadata": {
            "lastPlannedStep": None,
            "planningPhase": "initial",
            "totalStepsEstimated": None,
            "stepDependencies": {},
            "progressMetrics": {
                "p1Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p2Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "p3Coverage": {"covered": 0, "total": 0, "percentage": 0},
                "overallProgress": 0,
            },
        },
    }


def _default_active_session(branch_name: str) -> dict[str, Any]:
    ts = now_iso()
    return {
        "branch": branch_name,
        "active_goal": "",
        "stage": "idle",
        "current_step": None,
        "pending_actions": [],
        "open_questions": [],
        "current_hypotheses": [],
        "last_checkpoint_at": None,
        "updated_at": ts,
    }


def _memory_root(project_path: Path, branch_name: str) -> Path:
    return project_path / ".madspec" / branch_name / "memory"


def get_memory_paths(project_path: Path, branch_name: str) -> MemoryPaths:
    branch_dir = project_path / ".madspec" / branch_name
    memory_dir = _memory_root(project_path, branch_name)
    return MemoryPaths(
        branch_dir=branch_dir,
        memory_dir=memory_dir,
        progress=memory_dir / "progress.json",
        working_dir=memory_dir / "working",
        active_session=memory_dir / "working" / "active-session.json",
        decision_log=memory_dir / "working" / "decision-log.jsonl",
        episodes_dir=memory_dir / "episodes",
        events=memory_dir / "episodes" / "events.jsonl",
        semantic_dir=memory_dir / "semantic",
        facts=memory_dir / "semantic" / "facts.jsonl",
        decisions=memory_dir / "semantic" / "decisions.jsonl",
        contracts=memory_dir / "semantic" / "contracts.jsonl",
    )


def read_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_procedures_layout(project_path: Path) -> list[Path]:
    procedures_dir = project_path / ".madspec" / "procedures"
    procedures_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for relative_name, content in PROCEDURE_FILES.items():
        path = procedures_dir / relative_name
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            created.append(path)
    return created


def ensure_memory_layout(project_path: Path, branch_name: str) -> list[Path]:
    from .planning import _compute_progress_metrics, extract_function_catalog

    paths = get_memory_paths(project_path, branch_name)
    created: list[Path] = []

    paths.branch_dir.mkdir(parents=True, exist_ok=True)
    paths.working_dir.mkdir(parents=True, exist_ok=True)
    paths.episodes_dir.mkdir(parents=True, exist_ok=True)
    paths.semantic_dir.mkdir(parents=True, exist_ok=True)

    if not paths.progress.exists():
        write_json(paths.progress, _default_progress_state())
        created.append(paths.progress)

    if not paths.active_session.exists():
        write_json(paths.active_session, _default_active_session(branch_name))
        created.append(paths.active_session)

    for path in (
        paths.decision_log,
        paths.events,
        paths.facts,
        paths.decisions,
        paths.contracts,
    ):
        if not path.exists():
            path.write_text("", encoding="utf-8")
            created.append(path)

    progress = read_json(paths.progress, _default_progress_state())
    if isinstance(progress, dict):
        catalog: dict[str, list[str]] = {}
        for stage_name in ("mvp.plan", "feature.plan"):
            stage_catalog = extract_function_catalog(project_path, branch_name, stage_name)
            if any(stage_catalog.values()):
                catalog = stage_catalog
                break
        if catalog:
            planning_metadata = progress.setdefault("planningMetadata", {})
            covers_functions = progress.setdefault("coversFunctions", {})
            expected_metrics = _compute_progress_metrics(catalog, covers_functions)
            if planning_metadata.get("progressMetrics") != expected_metrics:
                planning_metadata["progressMetrics"] = expected_metrics
                write_json(paths.progress, progress)

    created.extend(ensure_procedures_layout(project_path))
    return created
