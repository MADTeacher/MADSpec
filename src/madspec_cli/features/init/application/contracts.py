from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from madspec_cli.memory.shared.system_store.embedding_registry import list_embedding_models


@dataclass(frozen=True)
class InitProgressEvent:
    action: str
    step: str
    detail: str | None = None


class InitProgressReporter(Protocol):
    def handle(self, event: InitProgressEvent) -> None:
        ...


@dataclass(frozen=True)
class InitMemoryModelOption:
    model_key: str
    label: str
    provider_kind: str
    dimension: int
    approx_download_size_mb: int
    recommendation_badge: str
    default_download_policy: str
    languages: tuple[str, ...]
    status: str


INIT_MEMORY_MODEL_CATALOG: dict[str, InitMemoryModelOption] = {
    spec.model_key: InitMemoryModelOption(
        model_key=spec.model_key,
        label=spec.label,
        provider_kind=spec.provider_kind,
        dimension=spec.dimension,
        approx_download_size_mb=spec.approx_download_size_mb,
        recommendation_badge=spec.recommendation_badge,
        default_download_policy="on-init",
        languages=spec.languages,
        status=spec.status,
    )
    for spec in list_embedding_models()
}


@dataclass(frozen=True)
class InitMemorySelection:
    provider: str
    model: str | None
    download_policy: str
    cache_dir: str = ".madspec/system/models"
    revision: str | None = None

    @property
    def is_dense(self) -> bool:
        return self.provider == "local-hf-onnx"

    def to_config_payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "model": self.model,
            "downloadPolicy": self.download_policy,
            "cacheDir": self.cache_dir,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class InitializeProjectRequest:
    project_path: Path
    selected_ai: str
    memory_selection: InitMemorySelection
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
    memory_bootstrap: dict[str, object] | None = None


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
