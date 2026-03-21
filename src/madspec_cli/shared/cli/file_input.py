from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import typer


def _exit_with_file_error(message: str) -> None:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(2)


def _normalize_key(raw_key: str) -> str:
    return raw_key.replace("-", "_")


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
    except ValueError:
        return False
    return True


def should_cleanup_args_file(path: str, *, project_path: Path | None = None) -> bool:
    base_path = project_path or Path.cwd()
    temp_root = (base_path / ".madspec" / ".tmp").resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base_path / candidate
    return _is_relative_to(candidate.resolve(), temp_root)


@dataclass(frozen=True)
class ArgsFileLifecycle:
    path: Path
    cleanup_on_success: bool

    @classmethod
    def from_path(cls, path: str, *, project_path: Path | None = None) -> "ArgsFileLifecycle":
        base_path = project_path or Path.cwd()
        raw_path = Path(path)
        resolved_path = raw_path if raw_path.is_absolute() else base_path / raw_path
        return cls(
            path=resolved_path,
            cleanup_on_success=should_cleanup_args_file(path, project_path=base_path),
        )

    def cleanup_after_success(self) -> None:
        if not self.cleanup_on_success:
            return
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            return


def normalize_args_file(
    data: Mapping[str, Any],
    *,
    aliases: Mapping[str, str] | None = None,
    allowed_keys: set[str] | None = None,
) -> dict[str, Any]:
    aliases = aliases or {}

    snake_case_data: dict[str, Any] = {}
    for raw_key, value in data.items():
        normalized_key = _normalize_key(raw_key)
        # Prefer explicit snake_case keys over hyphenated aliases when both exist.
        if normalized_key not in snake_case_data or raw_key == normalized_key:
            snake_case_data[normalized_key] = value

    normalized: dict[str, Any] = {}
    for key, value in snake_case_data.items():
        canonical_key = aliases.get(key, key)
        if canonical_key in normalized:
            # Prefer canonical keys over aliases when both are present.
            if canonical_key == key:
                normalized[canonical_key] = value
            continue
        normalized[canonical_key] = value

    if allowed_keys is not None:
        unknown_keys = sorted(key for key in normalized if key not in allowed_keys)
        if unknown_keys:
            fields = ", ".join(unknown_keys)
            raise typer.BadParameter(f"Unsupported fields in args file: {fields}")

    return normalized


def read_args_file(
    path: str,
    *,
    aliases: Mapping[str, str] | None = None,
    allowed_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Read CLI arguments from a JSON file.

    Used to bypass OS command-line length limits (e.g. ~8 KiB on Windows
    cmd.exe) by letting agents write arguments to a file instead.
    """
    file_path = Path(path)
    if not file_path.exists():
        _exit_with_file_error(f"File not found: {path}")

    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        _exit_with_file_error(f"Cannot read file {path}: {exc}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        _exit_with_file_error(f"Invalid JSON in {path}: {exc}")

    if not isinstance(data, dict):
        _exit_with_file_error(f"Expected a JSON object in {path}, got {type(data).__name__}")

    try:
        return normalize_args_file(data, aliases=aliases, allowed_keys=allowed_keys)
    except typer.BadParameter as exc:
        _exit_with_file_error(str(exc))
