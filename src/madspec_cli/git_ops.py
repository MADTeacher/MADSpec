from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .ui import StepTracker, console


def run_command(
    cmd: list[str],
    check_return: bool = True,
    capture: bool = False,
    shell: bool = False,
) -> str | None:
    try:
        if capture:
            result = subprocess.run(
                cmd,
                check=check_return,
                capture_output=True,
                text=True,
                shell=shell,
            )
            return result.stdout.strip()

        subprocess.run(cmd, check=check_return, shell=shell)
        return None
    except subprocess.CalledProcessError as exc:
        if check_return:
            console.print(f"[red]Error running command:[/red] {' '.join(cmd)}")
            console.print(f"[red]Exit code:[/red] {exc.returncode}")
            if getattr(exc, "stderr", None):
                console.print(f"[red]Error output:[/red] {exc.stderr}")
            raise
        return None


def check_tool(tool: str, tracker: StepTracker | None = None) -> bool:
    found = shutil.which(tool) is not None
    if tracker:
        if found:
            tracker.complete(tool, "available")
        else:
            tracker.error(tool, "not found")
    return found


def is_git_repo(path: Path | None = None) -> bool:
    target_path = path or Path.cwd()
    if not target_path.is_dir():
        return False
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            cwd=target_path,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
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


def get_current_branch(project_path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=project_path,
            capture_output=True,
            text=True,
            check=False,
        )
        branch = result.stdout.strip()
        if branch:
            return branch
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return _configured_branch(project_path) or "main"


def init_git_repo(project_path: Path, quiet: bool = False) -> tuple[bool, str | None]:
    try:
        if not quiet:
            console.print("[cyan]Initializing git repository...[/cyan]")
        subprocess.run(
            ["git", "init"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from MADSpec template"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            console.print("[green]✓[/green] Git repository initialized")
        return True, None
    except subprocess.CalledProcessError as exc:
        error_msg = f"Command: {' '.join(exc.cmd)}\nExit code: {exc.returncode}"
        if exc.stderr:
            error_msg += f"\nError: {exc.stderr.strip()}"
        elif exc.stdout:
            error_msg += f"\nOutput: {exc.stdout.strip()}"
        if not quiet:
            console.print(f"[red]Error initializing git repository:[/red] {exc}")
        return False, error_msg
