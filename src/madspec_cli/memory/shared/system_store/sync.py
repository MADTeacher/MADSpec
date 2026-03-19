from __future__ import annotations

from pathlib import Path
from typing import Any

from .constants import SEARCHABLE_ARTIFACT_SUFFIXES
from .layout import ensure_system_memory_layout
from .retrieval import RetrievalOrchestrator
from .store import MemoryStore
from .text import _artifact_stage, _iso_from_mtime


def sync_branch_memory_to_store(project_path: Path, branch_name: str) -> None:
    from ..storage import get_memory_paths, read_json, read_jsonl

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    paths = get_memory_paths(project_path, branch_name)

    progress = read_json(paths.progress, {})
    if isinstance(progress, dict):
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="progress",
            payload=progress,
            source_path=str(paths.progress.relative_to(project_path)),
        )

    active_session = read_json(paths.active_session, {})
    if isinstance(active_session, dict):
        store.upsert_session(branch=branch_name, payload=active_session)

    snapshot_specs = (
        ("mvp.concept", paths.concept_state),
        ("mvp.design", paths.design_state),
        ("mvp.tech", paths.tech_state),
        ("mvp.architecture", paths.architecture_state),
        ("mvp.plan", paths.plan_state),
        ("feature.init", paths.feature_init_state),
        ("feature.plan", paths.feature_plan_state),
    )
    for snapshot_key, path in snapshot_specs:
        if not path.exists():
            continue
        payload = read_json(path, {})
        if isinstance(payload, dict):
            store.upsert_stage_snapshot(
                branch=branch_name,
                snapshot_key=snapshot_key,
                payload=payload,
                source_path=str(path.relative_to(project_path)),
            )

    for path in (paths.decision_log, paths.events, paths.facts, paths.decisions, paths.contracts):
        for record in read_jsonl(path):
            if isinstance(record, dict):
                store.upsert_record(record)


def sync_generated_artifacts(project_path: Path, branch_name: str) -> None:
    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    branch_dir = project_path / ".madspec" / branch_name
    if not branch_dir.exists():
        return
    for path in branch_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SEARCHABLE_ARTIFACT_SUFFIXES:
            continue
        if "memory" in path.parts and path.parent.name in {"semantic", "working", "episodes", "stages"}:
            continue
        content = path.read_text(encoding="utf-8")
        artifact_id = str(path.relative_to(project_path))
        stage = _artifact_stage(branch_name, path)
        store.upsert_artifact(
            artifact_id=artifact_id,
            branch=branch_name,
            stage=stage,
            path=str(path.relative_to(project_path)),
            content=content,
            updated_at=_iso_from_mtime(path),
        )


def sync_json_path_to_store(path: Path, data: Any) -> None:
    context = _path_context(path)
    if context is None or not isinstance(data, dict):
        return
    project_path, branch_name, relative = context
    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    rel = "/".join(relative)
    if rel == "memory/progress.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="progress",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/working/active-session.json":
        store.upsert_session(branch=branch_name, payload=data)
    elif rel == "memory/stages/mvp.concept.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="mvp.concept",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/mvp.design.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="mvp.design",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/mvp.tech.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="mvp.tech",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/mvp.architecture.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="mvp.architecture",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/mvp.plan.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="mvp.plan",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/feature.init.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="feature.init",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )
    elif rel == "memory/stages/feature.plan.json":
        store.upsert_stage_snapshot(
            branch=branch_name,
            snapshot_key="feature.plan",
            payload=data,
            source_path=str(path.relative_to(project_path)),
        )


def sync_jsonl_path_to_store(path: Path, records: list[dict[str, Any]]) -> None:
    context = _path_context(path)
    if context is None:
        return
    project_path, _, _ = context
    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    for record in records:
        if isinstance(record, dict):
            store.upsert_record(record)


def build_db_status(project_path: Path, branch_name: str | None = None) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    return MemoryStore(project_path).describe_status(branch_name)


def run_reindex(project_path: Path, branch_name: str | None = None, *, limit: int = 200) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    if branch_name:
        sync_branch_memory_to_store(project_path, branch_name)
        sync_generated_artifacts(project_path, branch_name)
    else:
        madspec_dir = project_path / ".madspec"
        if madspec_dir.exists():
            for path in madspec_dir.iterdir():
                if not path.is_dir() or path.name == "system":
                    continue
                sync_branch_memory_to_store(project_path, path.name)
                sync_generated_artifacts(project_path, path.name)
    return MemoryStore(project_path).process_pending_jobs(branch=branch_name, limit=limit)


def search_memory_store(
    project_path: Path,
    *,
    branch_name: str,
    stage: str,
    step_id: str | None,
    query: str | None,
    scope: str = "branch",
    recall_limit: int = 5,
    disable_semantic: bool = False,
    include_obsolete: bool = False,
    include_conflicted: bool = False,
    active_session: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_system_memory_layout(project_path)
    sync_branch_memory_to_store(project_path, branch_name)
    sync_generated_artifacts(project_path, branch_name)
    orchestrator = RetrievalOrchestrator(project_path)
    return orchestrator.search(
        branch=branch_name,
        stage=stage,
        step_id=step_id,
        query=query,
        scope=scope,
        recall_limit=recall_limit,
        disable_semantic=disable_semantic,
        include_obsolete=include_obsolete,
        include_conflicted=include_conflicted,
        active_session=active_session,
    )


def _path_context(path: Path) -> tuple[Path, str, tuple[str, ...]] | None:
    parts = path.resolve().parts
    if ".madspec" not in parts:
        return None
    index = parts.index(".madspec")
    if len(parts) <= index + 2:
        return None
    branch_name = parts[index + 1]
    if branch_name == "system":
        return None
    project_path = Path(*parts[:index])
    relative = parts[index + 2 :]
    return project_path, branch_name, relative
