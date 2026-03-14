from __future__ import annotations

import json
from pathlib import Path

import typer


def read_args_file(path: str) -> dict:
    """Read CLI arguments from a JSON file.

    Used to bypass OS command-line length limits (e.g. ~8 KiB on Windows
    cmd.exe) by letting agents write arguments to a file instead.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise typer.BadParameter(f"File not found: {path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise typer.BadParameter(f"Cannot read file {path}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise typer.BadParameter(f"Expected a JSON object in {path}, got {type(data).__name__}")

    return data
