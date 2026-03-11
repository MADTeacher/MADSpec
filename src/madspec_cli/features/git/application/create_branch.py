from __future__ import annotations

from ..domain.models import CreateBranchRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: CreateBranchRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.create_branch(request.project_path, request.branch_name)
