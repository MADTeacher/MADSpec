from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.infra.project_config import create_madspec_config, ensure_branch_dir

from ..projection.materialize import consolidate_branch_memory
from ..shared.storage import ensure_memory_layout
from ..shared.system_store.sync import sync_branch_memory_to_store, sync_generated_artifacts

_UNSET = object()


def refresh_branch_state(
    project_path: Path,
    branch_name: str,
    *,
    stage: str | None = None,
    full: bool = False,
) -> list[Path]:
    sync_branch_memory_to_store(project_path, branch_name)
    generated = consolidate_branch_memory(project_path, branch_name, stage=stage, full=full)
    sync_generated_artifacts(project_path, branch_name)
    return generated


@dataclass(frozen=True)
class BootstrapBranchStateRequest:
    project_path: Path
    branch_name: str
    agent_environment: str | None = None
    memory_embeddings: object = _UNSET


@dataclass(frozen=True)
class BootstrapBranchStateResult:
    branch: str
    config_path: Path
    branch_dir: Path
    memory_dir: Path
    created_paths: list[Path]
    generated_paths: list[Path]


def bootstrap_branch_state(request: BootstrapBranchStateRequest) -> BootstrapBranchStateResult:
    create_kwargs = {"agent_environment": request.agent_environment}
    if request.memory_embeddings is not _UNSET:
        create_kwargs["memory_embeddings"] = request.memory_embeddings
    create_madspec_config(
        request.project_path,
        request.branch_name,
        **create_kwargs,
    )
    branch_dir = ensure_branch_dir(request.project_path, request.branch_name)
    created_paths = ensure_memory_layout(request.project_path, request.branch_name, full=True)
    generated_paths = refresh_branch_state(request.project_path, request.branch_name, full=True)
    return BootstrapBranchStateResult(
        branch=request.branch_name,
        config_path=request.project_path / ".madspec" / "config.json",
        branch_dir=branch_dir,
        memory_dir=branch_dir / "memory",
        created_paths=created_paths,
        generated_paths=generated_paths,
    )
