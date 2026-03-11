from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..infrastructure.initializer_core import InitResult


@dataclass(frozen=True)
class InitializeProjectRequest:
    project_path: Path
    selected_ai: str
    here: bool
    no_git: bool
    should_init_git: bool
    skip_tls: bool
    debug: bool
    github_token: str | None
    tracker: object | None = None


InitializeProjectResult = InitResult
