from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_COMMAND_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CommandExecutionError(RuntimeError):
    command: list[str]
    returncode: int | None
    stderr: str
    stdout: str
    timed_out: bool = False
    timeout_seconds: int | float | None = None

    def __str__(self) -> str:
        parts = [f"Command: {' '.join(self.command)}"]
        if self.timed_out:
            if self.timeout_seconds is not None:
                parts.append(f"Timed out after {self.timeout_seconds} seconds")
            else:
                parts.append("Timed out")
        elif self.returncode is not None:
            parts.append(f"Exit code: {self.returncode}")
        if self.stderr:
            parts.append(f"Error: {self.stderr}")
        elif self.stdout:
            parts.append(f"Output: {self.stdout}")
        return "\n".join(parts)


def run_subprocess(
    command: list[str],
    *,
    cwd: Path | None = None,
    timeout: int | float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandExecutionError(
            command=command,
            returncode=None,
            stderr=(exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            timed_out=True,
            timeout_seconds=timeout,
        ) from exc

    if check and result.returncode != 0:
        raise CommandExecutionError(
            command=command,
            returncode=result.returncode,
            stderr=result.stderr.strip(),
            stdout=result.stdout.strip(),
            timeout_seconds=timeout,
        )
    return result
