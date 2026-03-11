from __future__ import annotations

from ..domain.models import ListBranchesRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: ListBranchesRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.list_branches(request.project_path)
