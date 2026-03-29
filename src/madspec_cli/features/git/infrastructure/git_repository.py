from __future__ import annotations

from pathlib import Path

from .operations import (
    _run_git,
    commit_all,
    create_branch,
    ensure_gitignore,
    get_current_branch_info,
    init_repo,
    list_madspec_branches,
)


class GitRepository:
    def current_branch(self, project_path: Path):
        return get_current_branch_info(project_path)

    def init_repo(self, project_path: Path, commit_message: str):
        return init_repo(project_path, commit_message=commit_message)

    def create_branch(self, project_path: Path, branch_name: str):
        return create_branch(project_path, branch_name)

    def commit_all(self, project_path: Path, message: str):
        return commit_all(project_path, message)

    def list_branches(self, project_path: Path):
        return list_madspec_branches(project_path)

    def ensure_gitignore(self, project_path: Path):
        return ensure_gitignore(project_path)

    def run(self, project_path: Path, args: list[str], *, check: bool = True):
        return _run_git(project_path, args, check=check)
