from __future__ import annotations

from ..domain.models import InitRepoRequest
from ..infrastructure.git_repository import GitRepository


def execute(request: InitRepoRequest, repository: GitRepository | None = None):
    repo = repository or GitRepository()
    return repo.init_repo(request.project_path, request.commit_message)
