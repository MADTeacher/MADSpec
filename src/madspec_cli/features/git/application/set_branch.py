from __future__ import annotations

from ..domain.models import SetBranchRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: SetBranchRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.set_branch(request.project_path, request.branch_name)
