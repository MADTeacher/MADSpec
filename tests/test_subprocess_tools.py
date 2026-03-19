from __future__ import annotations

import pytest

from madspec_cli.shared.infra.subprocess_tools import CommandExecutionError, run_subprocess


def test_run_subprocess_returns_completed_process() -> None:
    result = run_subprocess(["/bin/sh", "-c", "printf ok"])

    assert result.stdout == "ok"
    assert result.returncode == 0


def test_run_subprocess_raises_for_non_zero_exit() -> None:
    with pytest.raises(CommandExecutionError) as exc_info:
        run_subprocess(["/bin/sh", "-c", "printf boom >&2; exit 7"])

    assert exc_info.value.returncode == 7
    assert exc_info.value.stderr == "boom"


def test_run_subprocess_raises_timeout_error() -> None:
    with pytest.raises(CommandExecutionError) as exc_info:
        run_subprocess(["/bin/sh", "-c", "sleep 1"], timeout=0.01)

    assert exc_info.value.timed_out is True
    assert exc_info.value.timeout_seconds == 0.01


def test_run_subprocess_preserves_stdout_and_stderr() -> None:
    with pytest.raises(CommandExecutionError) as exc_info:
        run_subprocess(["/bin/sh", "-c", "printf out; printf err >&2; exit 2"])

    assert exc_info.value.stdout == "out"
    assert exc_info.value.stderr == "err"
