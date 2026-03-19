from __future__ import annotations

from pathlib import Path

import httpx

from .initializer_core import download_and_extract_template, handle_vscode_settings, merge_json_files


def install_template_archive(
    project_path: Path,
    ai_assistant: str,
    *,
    is_current_dir: bool = False,
    verbose: bool = True,
    emit_progress=None,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
) -> Path:
    return download_and_extract_template(
        project_path,
        ai_assistant,
        is_current_dir,
        verbose=verbose,
        emit_progress=emit_progress,
        client=client,
        debug=debug,
        github_token=github_token,
    )


__all__ = ["handle_vscode_settings", "install_template_archive", "merge_json_files"]
