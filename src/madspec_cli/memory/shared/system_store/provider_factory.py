from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from madspec_cli.shared.infra.project_config import read_madspec_config

from .constants import DEFAULT_EMBEDDING_DIMENSION
from .embedding_registry import EmbeddingModelSpec, get_embedding_model
from .model_bootstrap import ModelAvailability, ensure_model_available, inspect_model_availability
from .vector import BaseEmbeddingProvider, HashEmbeddingProvider, LocalHfOnnxEmbeddingProvider


class EmbeddingProviderRuntimeError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        provider: str,
        model: str | None,
        status: str | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.model = model
        self.status = status


@dataclass(frozen=True)
class ResolvedEmbeddingSelection:
    provider: str
    model: str | None
    download_policy: str
    cache_dir: str
    revision: str | None
    dimension: int
    registry_entry: EmbeddingModelSpec | None
    bootstrap_status: ModelAvailability
    is_ready: bool

    def to_config_payload(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "downloadPolicy": self.download_policy,
            "cacheDir": self.cache_dir,
            "revision": self.revision,
        }

    def to_status_payload(self, project_path: Path) -> dict[str, Any]:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "downloadPolicy": self.download_policy,
            "cacheDir": self.cache_dir,
            "revision": self.revision,
            "dimension": self.dimension,
            "status": self.bootstrap_status.status,
            "ready": self.is_ready,
            "bootstrap": self.bootstrap_status.to_payload(project_path),
        }
        if self.registry_entry is not None:
            payload["registry"] = {
                "providerKind": self.registry_entry.provider_kind,
                "hfRepoId": self.registry_entry.hf_repo_id,
                "languages": list(self.registry_entry.languages),
                "queryPrefix": self.registry_entry.query_prefix,
                "passagePrefix": self.registry_entry.passage_prefix,
                "approxDownloadSizeMb": self.registry_entry.approx_download_size_mb,
                "recommended": self.registry_entry.recommended,
                "status": self.registry_entry.status,
            }
        return payload


def resolve_configured_embeddings(project_path: Path) -> ResolvedEmbeddingSelection:
    config = read_madspec_config(project_path)
    embeddings = ((config.get("memory") or {}).get("embeddings") or {})
    provider = str(embeddings.get("provider") or "hash")
    model = embeddings.get("model")
    download_policy = str(embeddings.get("downloadPolicy") or "none")
    cache_dir = str(embeddings.get("cacheDir") or ".madspec/system/models")
    revision = embeddings.get("revision")

    if provider == "hash":
        bootstrap_status = inspect_model_availability(project_path, embeddings)
        return ResolvedEmbeddingSelection(
            provider=provider,
            model=None,
            download_policy=download_policy,
            cache_dir=cache_dir,
            revision=revision,
            dimension=DEFAULT_EMBEDDING_DIMENSION,
            registry_entry=None,
            bootstrap_status=bootstrap_status,
            is_ready=bootstrap_status.ready,
        )

    registry_entry = get_embedding_model(str(model))
    bootstrap_status = inspect_model_availability(project_path, embeddings)
    return ResolvedEmbeddingSelection(
        provider=provider,
        model=str(model),
        download_policy=download_policy,
        cache_dir=cache_dir,
        revision=revision,
        dimension=registry_entry.dimension,
        registry_entry=registry_entry,
        bootstrap_status=bootstrap_status,
        is_ready=bootstrap_status.ready,
    )


def build_embedding_provider(
    project_path: Path,
    *,
    allow_bootstrap: bool = False,
) -> BaseEmbeddingProvider:
    selection = resolve_configured_embeddings(project_path)
    if selection.provider == "hash":
        return HashEmbeddingProvider(dimension=selection.dimension)

    if (
        not selection.is_ready
        and allow_bootstrap
        and selection.provider == "local-hf-onnx"
        and selection.download_policy == "on-first-use"
    ):
        ensure_model_available(project_path, selection.to_config_payload(), allow_download=True)
        selection = resolve_configured_embeddings(project_path)

    if selection.registry_entry is None or selection.bootstrap_status.local_path is None or not selection.is_ready:
        message = (
            f"Configured embeddings provider '{selection.provider}'"
            f" (model={selection.model or 'n/a'}) is not ready"
        )
        if selection.bootstrap_status.status:
            message += f": {selection.bootstrap_status.status}"
        if selection.bootstrap_status.message:
            message += f" - {selection.bootstrap_status.message}"
        raise EmbeddingProviderRuntimeError(
            message,
            provider=selection.provider,
            model=selection.model,
            status=selection.bootstrap_status.status,
        )

    return LocalHfOnnxEmbeddingProvider(
        model_spec=selection.registry_entry,
        local_path=selection.bootstrap_status.local_path,
    )
