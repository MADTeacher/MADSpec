from __future__ import annotations

from madspec_cli.memory.application.branch_state import (
    BootstrapBranchStateRequest,
    bootstrap_branch_state,
)

from ..domain.models import SetBranchRequest
from ..infrastructure.operations import BranchSyncResult


def execute(request: SetBranchRequest) -> BranchSyncResult:
    bootstrap = bootstrap_branch_state(
        BootstrapBranchStateRequest(
            project_path=request.project_path,
            branch_name=request.branch_name,
        )
    )
    return BranchSyncResult(
        branch=bootstrap.branch,
        config_path=str(bootstrap.config_path),
        branch_dir=str(bootstrap.branch_dir),
        memory_dir=str(bootstrap.memory_dir),
    )
