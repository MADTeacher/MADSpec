from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ... import stages as _stages  # noqa: F401
from ..stage_registry import get_all_stage_defaults
from ..storage import _default_progress_state, get_memory_paths
from .constants import SYSTEM_SESSION_KEY
from .layout import ensure_system_memory_layout
from .sessions import default_session_payload
from .store import MemoryStore


@dataclass(frozen=True)
class CanonicalBranchState:
    runtime_revision: int
    progress: dict[str, Any]
    active_session: dict[str, Any]
    snapshots: dict[str, dict[str, Any]]
    present_snapshots: frozenset[str]
    record_streams: dict[str, list[dict[str, Any]]]


_SNAPSHOT_SPECS: tuple[tuple[str, str], ...] = (
    ("progress", "progress"),
    ("mvp.concept", "concept_state"),
    ("mvp.design", "design_state"),
    ("mvp.tech", "tech_state"),
    ("deploy", "deploy_state"),
    ("mvp.architecture", "architecture_state"),
    ("mvp.plan", "plan_state"),
    ("feature.init", "feature_init_state"),
    ("feature.plan", "feature_plan_state"),
)


def _get_snapshot_defaults() -> dict[str, Callable[[], dict[str, Any]]]:
    defaults = get_all_stage_defaults()
    defaults["progress"] = _default_progress_state
    return defaults


_RECORD_STREAM_PATHS = {
    "decision_log": "decision_log",
    "events": "events",
    "facts": "facts",
    "decisions": "decisions",
    "contracts": "contracts",
}


def bootstrap_branch_canonical_state(project_path: Path, branch_name: str) -> bool:
    from .sync import sync_branch_memory_to_store, sync_generated_artifacts

    ensure_system_memory_layout(project_path)
    store = MemoryStore(project_path)
    store.ensure_branch_runtime_state(branch_name)
    if store.branch_has_canonical_state(branch_name):
        return False
    sync_branch_memory_to_store(project_path, branch_name)
    sync_generated_artifacts(project_path, branch_name)
    return True


def load_canonical_branch_state(project_path: Path, branch_name: str) -> CanonicalBranchState:
    ensure_system_memory_layout(project_path)
    bootstrap_branch_canonical_state(project_path, branch_name)
    store = MemoryStore(project_path)
    runtime_revision = store.fetch_branch_revision(branch_name)
    present_snapshots = frozenset(
        item["snapshot_key"]
        for item in store.list_stage_snapshots(branch=branch_name, limit=len(_SNAPSHOT_SPECS) + 8)
    )

    snapshots = {
        snapshot_key: _load_snapshot_payload(store, branch_name, snapshot_key)
        for snapshot_key, _ in _SNAPSHOT_SPECS
    }
    active_session = store.fetch_session(branch=branch_name, session_key=SYSTEM_SESSION_KEY)
    if active_session is None:
        active_session = default_session_payload(branch_name=branch_name, session_key=SYSTEM_SESSION_KEY)

    record_streams = {
        record_stream: store.list_records_by_stream(branch=branch_name, record_stream=record_stream, limit=5000)
        for record_stream in _RECORD_STREAM_PATHS
    }
    return CanonicalBranchState(
        runtime_revision=runtime_revision,
        progress=snapshots["progress"],
        active_session=active_session,
        snapshots=snapshots,
        present_snapshots=present_snapshots,
        record_streams=record_streams,
    )


def refresh_branch_file_projections(project_path: Path, branch_name: str) -> list[Path]:
    paths = get_memory_paths(project_path, branch_name)
    state = load_canonical_branch_state(project_path, branch_name)
    created: list[Path] = []

    progress_path = getattr(paths, "progress")
    _write_json_projection(progress_path, state.snapshots["progress"])
    created.append(progress_path)

    for snapshot_key, path_attr in _SNAPSHOT_SPECS[1:]:
        path = getattr(paths, path_attr)
        if snapshot_key in state.present_snapshots:
            _write_json_projection(path, state.snapshots[snapshot_key])
            created.append(path)
        elif path.exists():
            path.unlink()

    _write_json_projection(paths.active_session, state.active_session)
    created.append(paths.active_session)

    for record_stream, path_attr in _RECORD_STREAM_PATHS.items():
        path = getattr(paths, path_attr)
        _write_jsonl_projection(path, state.record_streams[record_stream])
        created.append(path)

    return created


def refresh_branch_projections(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
) -> tuple[list[Path], list[Path]]:
    from ...projection.materialize import consolidate_branch_memory

    memory_paths = refresh_branch_file_projections(project_path, branch_name)
    generated_paths = consolidate_branch_memory(project_path, branch_name, stage=stage, full=full)
    return memory_paths, generated_paths


def build_runtime_snapshot_specs(project_path: Path, branch_name: str, snapshots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    paths = get_memory_paths(project_path, branch_name)
    path_map = {
        "progress": paths.progress,
        "mvp.concept": paths.concept_state,
        "mvp.design": paths.design_state,
        "mvp.tech": paths.tech_state,
        "deploy": paths.deploy_state,
        "mvp.architecture": paths.architecture_state,
        "mvp.plan": paths.plan_state,
        "feature.init": paths.feature_init_state,
        "feature.plan": paths.feature_plan_state,
    }
    return [
        {
            "snapshot_key": snapshot_key,
            "payload": payload,
            "source_path": str(path_map[snapshot_key].relative_to(project_path)),
        }
        for snapshot_key, payload in snapshots.items()
    ]


def tag_records_for_stream(records: list[dict[str, Any]], record_stream: str) -> list[dict[str, Any]]:
    tagged: list[dict[str, Any]] = []
    for record in records:
        item = dict(record)
        item["record_stream"] = record_stream
        tagged.append(item)
    return tagged


def _load_snapshot_payload(store: MemoryStore, branch_name: str, snapshot_key: str) -> dict[str, Any]:
    payload = store.fetch_snapshot(branch_name, snapshot_key)
    if payload is None:
        return _get_snapshot_defaults()[snapshot_key]()
    payload.pop("_snapshot_key", None)
    payload.pop("_content_hash", None)
    payload.pop("_stage", None)
    return payload


def _write_json_projection(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl_projection(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return
    lines = [json.dumps(record, ensure_ascii=False) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
