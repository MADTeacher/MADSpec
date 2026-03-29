from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from madspec_cli.shared.kernel.result import PayloadResult

from madspec_cli.features.change.infrastructure.git_ops import (
    resolve_base_revision,
    resolve_default_base_branch,
)
from ..infrastructure.service import ensure_change_layout


@dataclass(frozen=True)
class InitChangeRequest:
    project_path: Path
    branch_name: str
    base_branch: str | None


@dataclass(frozen=True)
class InitChangeResult(PayloadResult):
    pass


def execute(request: InitChangeRequest) -> InitChangeResult:
    base_branch = request.base_branch or resolve_default_base_branch(request.project_path)
    base_revision = resolve_base_revision(request.project_path, base_branch=base_branch)
    state, warnings, created = ensure_change_layout(
        request.project_path,
        request.branch_name,
        base_branch=base_branch,
        base_revision=base_revision,
    )
    return InitChangeResult(
        payload={
            "branch": request.branch_name,
            "base_branch": base_branch,
            "base_revision": base_revision,
            "state_file": str(
                (request.project_path / ".madspec" / request.branch_name / "change" / "state.json").relative_to(
                    request.project_path
                )
            ),
            "bundle_id": state["bundleId"],
            "warnings": warnings,
            "created": [str(path.relative_to(request.project_path)) for path in created],
        }
    )
