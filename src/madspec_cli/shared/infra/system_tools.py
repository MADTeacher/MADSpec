from __future__ import annotations

import shutil
import subprocess

from ..cli.banners import StepTracker, console


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
