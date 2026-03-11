from __future__ import annotations

from ..domain.models import CommitAllRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: CommitAllRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.commit_all(request.project_path, request.message)
