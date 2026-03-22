from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from madspec_cli.shared.infra.subprocess_tools import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    CommandExecutionError,
    run_subprocess,
)

from ..domain.constants import GITIGNORE_SECTIONS


GIT_COMMAND_TIMEOUT_SECONDS = DEFAULT_COMMAND_TIMEOUT_SECONDS


@dataclass(frozen=True)
class GitOperationError(RuntimeError):
    command: list[str]
    returncode: int
    stderr: str
    stdout: str

    def __str__(self) -> str:
        parts = [f"Command: {' '.join(self.command)}", f"Exit code: {self.returncode}"]
        if self.stderr:
            parts.append(f"Error: {self.stderr}")
        elif self.stdout:
            parts.append(f"Output: {self.stdout}")
        return "\n".join(parts)


@dataclass(frozen=True)
class BranchInfo:
    branch: str
    source: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class GitignoreResult:
    path: str
    created: bool
    updated: bool
    added_patterns: int

    def as_dict(self) -> dict[str, str | bool | int]:
        return asdict(self)


@dataclass(frozen=True)
class BranchSyncResult:
    branch: str
    config_path: str
    branch_dir: str
    memory_dir: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RepoInitResult:
    initialized: bool
    already_initialized: bool
    gitignore: GitignoreResult
    commit_message: str | None

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["gitignore"] = self.gitignore.as_dict()
        return payload


@dataclass(frozen=True)
class BranchCreateResult:
    branch: str
    sync: BranchSyncResult

    def as_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["sync"] = self.sync.as_dict()
        return payload


@dataclass(frozen=True)
class CommitResult:
    message: str
    commit_hash: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class BranchListResult:
    branches: list[dict[str, str | int]]

    def as_dict(self) -> dict[str, list[dict[str, str | int]]]:
        return {"branches": self.branches}


def _run_git(project_path: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["git", *args]
    try:
        return run_subprocess(
            command,
            cwd=project_path,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            check=check,
        )
    except CommandExecutionError as exc:
        raise GitOperationError(
            command=exc.command,
            returncode=exc.returncode or 1,
            stderr=exc.stderr,
            stdout=exc.stdout,
        ) from exc


def is_git_repo(path: Path | None = None) -> bool:
    target_path = path or Path.cwd()
    if not target_path.is_dir():
        return False
    try:
        _run_git(target_path, ["rev-parse", "--is-inside-work-tree"])
        return True
    except (GitOperationError, FileNotFoundError):
        return False


def _configured_branch(project_path: Path) -> str | None:
    config_path = project_path / ".madspec" / "config.json"
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    branch = config.get("currentBranch")
    return branch if isinstance(branch, str) and branch else None


def get_current_branch_info(project_path: Path) -> BranchInfo:
    try:
        result = _run_git(project_path, ["branch", "--show-current"], check=False)
        branch = result.stdout.strip()
        if branch:
            return BranchInfo(branch=branch, source="git")
    except (GitOperationError, FileNotFoundError):
        pass

    configured_branch = _configured_branch(project_path)
    if configured_branch:
        return BranchInfo(branch=configured_branch, source="config")

    return BranchInfo(branch="main", source="default")


def get_current_branch(project_path: Path) -> str:
    return get_current_branch_info(project_path).branch


def _render_gitignore() -> list[str]:
    lines = [
        "# Managed by madspec git ensure-gitignore",
        "# Safe defaults for secrets, dependencies, build artifacts, and local caches.",
    ]
    for title, patterns in GITIGNORE_SECTIONS.items():
        lines.append("")
        lines.append(f"# {title}")
        lines.extend(patterns)
    lines.append("")
    return lines


def ensure_gitignore(project_path: Path) -> GitignoreResult:
    gitignore_path = project_path / ".gitignore"
    rendered_lines = _render_gitignore()
    if not gitignore_path.exists():
        gitignore_path.write_text("\n".join(rendered_lines), encoding="utf-8")
        return GitignoreResult(
            path=str(gitignore_path),
            created=True,
            updated=True,
            added_patterns=sum(len(patterns) for patterns in GITIGNORE_SECTIONS.values()),
        )

    existing_text = gitignore_path.read_text(encoding="utf-8")
    existing_lines = {line.strip() for line in existing_text.splitlines() if line.strip()}

    append_lines = [line for line in rendered_lines if line and line not in existing_lines]
    if append_lines:
        prefix = "\n" if existing_text and not existing_text.endswith("\n") else ""
        gitignore_path.write_text(
            existing_text + prefix + "\n".join(["", *append_lines, ""]),
            encoding="utf-8",
        )

    return GitignoreResult(
        path=str(gitignore_path),
        created=False,
        updated=bool(append_lines),
        added_patterns=sum(1 for line in append_lines if not line.startswith("#")),
    )


def set_branch_config(project_path: Path, branch_name: str) -> BranchSyncResult:
    from madspec_cli.memory import consolidate_branch_memory, ensure_memory_layout
    from madspec_cli.shared.infra.project_config import create_madspec_config, ensure_branch_dir

    create_madspec_config(project_path, branch_name)
    branch_dir = ensure_branch_dir(project_path, branch_name)
    ensure_memory_layout(project_path, branch_name)
    consolidate_branch_memory(project_path, branch_name)
    return BranchSyncResult(
        branch=branch_name,
        config_path=str(project_path / ".madspec" / "config.json"),
        branch_dir=str(branch_dir),
        memory_dir=str(branch_dir / "memory"),
    )


def init_repo(project_path: Path, *, commit_message: str = "Initial commit from MADSpec template") -> RepoInitResult:
    gitignore = ensure_gitignore(project_path)
    if is_git_repo(project_path):
        return RepoInitResult(
            initialized=False,
            already_initialized=True,
            gitignore=gitignore,
            commit_message=None,
        )

    _run_git(project_path, ["init"])
    _run_git(project_path, ["add", "-A"])
    _run_git(project_path, ["commit", "-m", commit_message])
    return RepoInitResult(
        initialized=True,
        already_initialized=False,
        gitignore=gitignore,
        commit_message=commit_message,
    )


def init_git_repo(project_path: Path, quiet: bool = False) -> tuple[bool, str | None]:
    try:
        result = init_repo(project_path)
        return True, None if result else None
    except (GitOperationError, OSError) as exc:
        return False, str(exc)


def create_branch(project_path: Path, branch_name: str) -> BranchCreateResult:
    _run_git(project_path, ["checkout", "-b", branch_name])
    sync = set_branch_config(project_path, branch_name)
    return BranchCreateResult(branch=branch_name, sync=sync)


def commit_all(project_path: Path, message: str) -> CommitResult:
    _run_git(project_path, ["add", "-A"])
    _run_git(project_path, ["commit", "-m", message])
    commit_hash = _run_git(project_path, ["rev-parse", "HEAD"]).stdout.strip()
    return CommitResult(message=message, commit_hash=commit_hash)


def list_madspec_branches(project_path: Path) -> BranchListResult:
    madspec_dir = project_path / ".madspec"
    if not madspec_dir.exists():
        return BranchListResult(branches=[])

    branches: list[dict[str, str | int]] = []
    branch_dirs = {
        progress_file.parent.parent
        for progress_file in madspec_dir.rglob("memory/progress.json")
        if progress_file.is_file()
    }
    for branch_dir in sorted(branch_dirs):
        if "templates" in branch_dir.relative_to(madspec_dir).parts:
            continue
        artifact_count = sum(1 for sub_item in branch_dir.rglob("*") if sub_item.is_file())
        branches.append(
            {
                "name": branch_dir.relative_to(madspec_dir).as_posix(),
                "artifact_count": artifact_count,
            }
        )
    return BranchListResult(branches=branches)
