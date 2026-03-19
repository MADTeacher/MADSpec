from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class InitProgressEvent:
    action: str
    step: str
    detail: str | None = None


class InitProgressReporter(Protocol):
    def handle(self, event: InitProgressEvent) -> None:
        ...


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
    progress_reporter: InitProgressReporter | None = None


@dataclass(frozen=True)
class InitializeProjectResult:
    project_path: Path
    selected_ai: str
    branch_name: str | None
    git_error_message: str | None
    config_error_message: str | None


@dataclass(frozen=True)
class InitializeProjectPreflightRequest:
    selected_ai: str
    no_git: bool
    ignore_agent_tools: bool


@dataclass(frozen=True)
class InitializeProjectPreflightResult:
    selected_ai: str
    should_init_git: bool
    git_warning_message: str | None
    missing_agent_tool: bool
    agent_install_url: str | None
    agent_display_name: str
