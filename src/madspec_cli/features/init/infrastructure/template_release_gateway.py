from __future__ import annotations

from pathlib import Path

import httpx

from .initializer_core import download_template_from_github


def fetch_template_release(
    ai_assistant: str,
    download_dir: Path,
    *,
    verbose: bool = True,
    show_progress: bool = True,
    client: httpx.Client | None = None,
    debug: bool = False,
    github_token: str | None = None,
):
    return download_template_from_github(
        ai_assistant,
        download_dir,
        verbose=verbose,
        show_progress=show_progress,
        client=client,
        debug=debug,
        github_token=github_token,
    )
