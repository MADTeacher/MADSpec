from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CurrentBranchRequest:
    project_path: Path


@dataclass(frozen=True)
class InitRepoRequest:
    project_path: Path
    commit_message: str


@dataclass(frozen=True)
class CreateBranchRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class SetBranchRequest:
    project_path: Path
    branch_name: str


@dataclass(frozen=True)
class CommitAllRequest:
    project_path: Path
    message: str


@dataclass(frozen=True)
class ListBranchesRequest:
    project_path: Path
