from __future__ import annotations

import importlib.metadata
import platform
import tomllib
from pathlib import Path

from madspec_cli.shared.infra.github_client import create_http_client, fetch_latest_release_info


def execute() -> dict[str, str]:
    cli_version = "unknown"
    try:
        cli_version = importlib.metadata.version("madspec-cli")
    except Exception:
        pyproject_path = Path(__file__).resolve().parents[4] / "pyproject.toml"
        if pyproject_path.exists():
            data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            cli_version = data.get("project", {}).get("version", "unknown")

    template_version = "unknown"
    release_date = "unknown"
    try:
        release_data = fetch_latest_release_info(
            "MADTeacher",
            "madspec",
            client=create_http_client(),
        )
        template_version = release_data.get("tag_name", "unknown")
        if template_version.startswith("v"):
            template_version = template_version[1:]
        release_date = release_data.get("published_at", "unknown")
        if release_date != "unknown":
            release_date = release_date.split("T", 1)[0]
    except Exception:
        pass

    return {
        "cli_version": cli_version,
        "template_version": template_version,
        "release_date": release_date,
        "python": platform.python_version(),
        "platform": platform.system(),
        "architecture": platform.machine(),
        "os_version": platform.version(),
    }
