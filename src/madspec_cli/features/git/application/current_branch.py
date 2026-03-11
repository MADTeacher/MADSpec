from __future__ import annotations

from ..domain.models import CurrentBranchRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: CurrentBranchRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.current_branch(request.project_path)
