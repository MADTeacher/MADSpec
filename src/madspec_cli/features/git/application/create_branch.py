from __future__ import annotations

from madspec_cli.memory.application.branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
)

from ..domain.models import CreateBranchRequest
from ..infrastructure.git_repository import GitRepository
from ..infrastructure.operations import BranchCreateResult, BranchSyncResult


def execute(request: CreateBranchRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    branch_name = repo.create_branch(request.project_path, request.branch_name)
    bootstrap = bootstrap_branch_state(
        BootstrapBranchStateRequest(
            project_path=request.project_path,
            branch_name=branch_name,
        )
    )
    return BranchCreateResult(
        branch=branch_name,
        sync=BranchSyncResult(
            branch=bootstrap.branch,
            config_path=str(bootstrap.config_path),
            branch_dir=str(bootstrap.branch_dir),
            memory_dir=str(bootstrap.memory_dir),
        ),
    )
