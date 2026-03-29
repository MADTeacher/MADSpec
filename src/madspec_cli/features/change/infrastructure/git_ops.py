from __future__ import annotations

from pathlib import Path

from madspec_cli.shared.infra.subprocess_tools import run_subprocess


def ensure_git_change_support(project_path: Path) -> None:
    from madspec_cli.features.git.infrastructure.operations import is_git_repo

    if not is_git_repo(project_path):
        raise ValueError("change layer requires a git repository; initialize git first")


def resolve_default_base_branch(project_path: Path) -> str:
    ensure_git_change_support(project_path)
    try:
        remote_head = _run_git(project_path, ["symbolic-ref", "refs/remotes/origin/HEAD"])
        if remote_head.startswith("refs/remotes/origin/"):
            return remote_head.rsplit("/", 1)[-1]
    except ValueError:
        pass

    branches = set(_run_git(project_path, ["branch", "--format", "%(refname:short)"]).splitlines())
    for candidate in ("main", "master"):
        if candidate in branches:
            return candidate
    return "main"


def resolve_base_revision(project_path: Path, *, base_branch: str) -> str:
    ensure_git_change_support(project_path)
    current_revision = current_git_revision(project_path)
    if not base_branch:
        return current_revision
    try:
        return _run_git(project_path, ["merge-base", "HEAD", base_branch])
    except ValueError:
        return current_revision


def current_git_revision(project_path: Path) -> str:
    ensure_git_change_support(project_path)
    return _run_git(project_path, ["rev-parse", "HEAD"])


def current_git_branch(project_path: Path) -> str:
    from madspec_cli.features.git.infrastructure.operations import get_current_branch

    return get_current_branch(project_path)


def build_git_diff(project_path: Path, *, base_revision: str) -> dict:
    ensure_git_change_support(project_path)
    current_branch = current_git_branch(project_path)
    name_lines = _run_git(project_path, ["diff", "--name-status", "-M", base_revision]).splitlines()
    stat_lines = _run_git(project_path, ["diff", "--numstat", "-M", base_revision]).splitlines()
    stat_map: dict[str, dict[str, int | None]] = {}
    for line in stat_lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        additions = None if parts[0] == "-" else int(parts[0])
        deletions = None if parts[1] == "-" else int(parts[1])
        key = parts[-1]
        stat_map[key] = {"additions": additions, "deletions": deletions}

    files: list[dict] = []
    summary = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0, "untracked": 0}
    for line in name_lines:
        if not line.strip():
            continue
        parts = line.split("\t")
        status = parts[0]
        if status.startswith("R"):
            old_path = parts[1]
            new_path = parts[2]
            if _is_ignored_change_artifact(new_path, current_branch):
                continue
            summary["renamed"] += 1
            stats = stat_map.get(new_path, {})
            files.append(
                {
                    "path": new_path,
                    "status": "renamed",
                    "old_path": old_path,
                    "additions": stats.get("additions"),
                    "deletions": stats.get("deletions"),
                }
            )
            continue
        path = parts[1] if len(parts) > 1 else ""
        if _is_ignored_change_artifact(path, current_branch):
            continue
        normalized_status = {
            "A": "added",
            "M": "modified",
            "D": "deleted",
        }.get(status, "modified")
        summary[normalized_status] += 1
        stats = stat_map.get(path, {})
        files.append(
            {
                "path": path,
                "status": normalized_status,
                "additions": stats.get("additions"),
                "deletions": stats.get("deletions"),
            }
        )

    untracked = [
        line.strip()
        for line in _run_git(project_path, ["ls-files", "--others", "--exclude-standard"]).splitlines()
        if line.strip() and not _is_ignored_change_artifact(line.strip(), current_branch)
    ]
    for path in untracked:
        files.append({"path": path, "status": "untracked", "additions": None, "deletions": None})
    summary["untracked"] = len(untracked)
    return {
        "baseRevision": base_revision,
        "currentRevision": current_git_revision(project_path),
        "worktreeDirty": bool(files),
        "summary": summary,
        "files": files,
        "untrackedFiles": untracked,
    }


def _run_git(project_path: Path, args: list[str]) -> str:
    try:
        result = run_subprocess(["git", *args], cwd=project_path)
    except Exception as exc:
        raise ValueError(str(exc)) from exc
    return result.stdout.strip()


def _is_ignored_change_artifact(path: str, branch_name: str) -> bool:
    normalized = path.strip()
    branch_prefix = f".madspec/{branch_name}/"
    return (
        normalized.startswith(".madspec/system/memory/")
        or normalized == f"{branch_prefix}change-summary.md"
        or normalized.startswith(f"{branch_prefix}change/")
    )


__all__ = [
    "build_git_diff",
    "current_git_branch",
    "current_git_revision",
    "ensure_git_change_support",
    "resolve_base_revision",
    "resolve_default_base_branch",
]
