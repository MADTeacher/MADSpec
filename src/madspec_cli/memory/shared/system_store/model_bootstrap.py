from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from .embedding_registry import EmbeddingModelSpec, get_embedding_model

BootstrapStatus = Literal["not_required", "missing", "ready", "corrupted"]


@dataclass(frozen=True)
class ModelAvailability:
    status: BootstrapStatus
    ready: bool
    cache_root: Path | None
    manifest_path: Path | None
    local_path: Path | None
    requested_revision: str | None = None
    resolved_revision: str | None = None
    message: str | None = None

    def to_payload(self, project_path: Path) -> dict[str, Any]:
        return {
            "status": self.status,
            "ready": self.ready,
            "cacheRoot": _display_path(project_path, self.cache_root),
            "manifestPath": _display_path(project_path, self.manifest_path),
            "localPath": _display_path(project_path, self.local_path),
            "requestedRevision": self.requested_revision,
            "resolvedRevision": self.resolved_revision,
            "message": self.message,
        }


@dataclass(frozen=True)
class BootstrapResult:
    availability: ModelAvailability
    downloaded: bool

    @property
    def status(self) -> BootstrapStatus:
        return self.availability.status

    @property
    def ready(self) -> bool:
        return self.availability.ready

    def to_payload(self, project_path: Path) -> dict[str, Any]:
        payload = self.availability.to_payload(project_path)
        payload["downloaded"] = self.downloaded
        return payload


def resolve_model_cache_root(
    project_path: Path,
    cache_dir: str,
    model_key: str,
    revision: str | None,
) -> Path:
    return project_path / cache_dir / model_key / _revision_segment(revision)


def inspect_model_availability(project_path: Path, embeddings_config: dict[str, Any]) -> ModelAvailability:
    provider = embeddings_config.get("provider")
    if provider == "hash":
        return ModelAvailability(
            status="not_required",
            ready=True,
            cache_root=None,
            manifest_path=None,
            local_path=None,
            message="Hash provider does not require model bootstrap.",
        )

    model_key = str(embeddings_config.get("model") or "")
    spec = get_embedding_model(model_key)
    revision = embeddings_config.get("revision")
    cache_root = resolve_model_cache_root(project_path, str(embeddings_config["cacheDir"]), model_key, revision)
    manifest_path = cache_root / "manifest.json"
    if not cache_root.exists():
        return ModelAvailability(
            status="missing",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=None,
            requested_revision=revision,
            resolved_revision=revision or "current",
            message="Model cache is missing.",
        )
    if not manifest_path.exists():
        if any(cache_root.iterdir()):
            return ModelAvailability(
                status="corrupted",
                ready=False,
                cache_root=cache_root,
                manifest_path=manifest_path,
                local_path=None,
                requested_revision=revision,
                resolved_revision=revision or "current",
                message="Model cache exists but manifest.json is missing; the cache may be only partially prepared.",
            )
        return ModelAvailability(
            status="missing",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=None,
            requested_revision=revision,
            resolved_revision=revision or "current",
            message="Model cache is empty.",
        )

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ModelAvailability(
            status="corrupted",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=None,
            requested_revision=revision,
            resolved_revision=revision or "current",
            message="manifest.json is not valid JSON.",
        )

    manifest_error = _validate_manifest(spec, manifest, requested_revision=revision)
    local_path = _deserialize_local_path(project_path, manifest.get("localPath"))
    if manifest_error is not None:
        return ModelAvailability(
            status="corrupted",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=local_path,
            requested_revision=revision,
            resolved_revision=str(manifest.get("resolvedRevision") or revision or "current"),
            message=manifest_error,
        )
    if local_path is None or not local_path.exists():
        return ModelAvailability(
            status="corrupted",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=local_path,
            requested_revision=revision,
            resolved_revision=str(manifest.get("resolvedRevision") or revision or "current"),
            message="Local model path recorded in manifest does not exist.",
        )
    local_path_error = _validate_local_model_path(local_path)
    if local_path_error is not None:
        return ModelAvailability(
            status="corrupted",
            ready=False,
            cache_root=cache_root,
            manifest_path=manifest_path,
            local_path=local_path,
            requested_revision=revision,
            resolved_revision=str(manifest.get("resolvedRevision") or revision or "current"),
            message=local_path_error,
        )

    return ModelAvailability(
        status="ready",
        ready=True,
        cache_root=cache_root,
        manifest_path=manifest_path,
        local_path=local_path,
        requested_revision=revision,
        resolved_revision=str(manifest.get("resolvedRevision") or revision or "current"),
        message="Model cache is ready.",
    )


def ensure_model_available(
    project_path: Path,
    embeddings_config: dict[str, Any],
    *,
    allow_download: bool,
    force_repair: bool = False,
) -> BootstrapResult:
    availability = inspect_model_availability(project_path, embeddings_config)
    if availability.ready or availability.status == "not_required":
        return BootstrapResult(availability=availability, downloaded=False)
    if not allow_download:
        return BootstrapResult(availability=availability, downloaded=False)

    model_key = str(embeddings_config.get("model") or "")
    spec = get_embedding_model(model_key)
    revision = embeddings_config.get("revision")
    cache_root = resolve_model_cache_root(project_path, str(embeddings_config["cacheDir"]), model_key, revision)
    if availability.status == "corrupted":
        if not force_repair:
            return BootstrapResult(availability=availability, downloaded=False)
        _reset_model_cache_root(cache_root)
    cache_root.mkdir(parents=True, exist_ok=True)
    try:
        local_path, resolved_revision = _download_model_snapshot(spec, cache_root, revision)
    except Exception as exc:
        raise RuntimeError(f"Failed to bootstrap embedding model '{model_key}': {exc}") from exc

    manifest_payload = {
        "providerKind": spec.provider_kind,
        "modelKey": spec.model_key,
        "requestedRevision": revision,
        "resolvedRevision": resolved_revision or revision or "current",
        "hfRepoId": spec.hf_repo_id,
        "dimension": spec.dimension,
        "downloadedAt": datetime.now(tz=UTC).isoformat(),
        "status": "ready",
        "localPath": _store_local_path(project_path, local_path),
    }
    (cache_root / "manifest.json").write_text(
        json.dumps(manifest_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return BootstrapResult(
        availability=inspect_model_availability(project_path, embeddings_config),
        downloaded=True,
    )


def _download_model_snapshot(
    spec: EmbeddingModelSpec,
    cache_root: Path,
    revision: str | None,
) -> tuple[Path, str | None]:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "huggingface_hub is not installed; install project dependencies before using dense model bootstrap."
        ) from exc

    local_path = Path(
        snapshot_download(
            repo_id=spec.hf_repo_id,
            revision=revision,
            local_dir=str(cache_root),
            token=_resolve_hf_token(),
        )
    )
    return local_path, revision or "current"


def _validate_manifest(
    spec: EmbeddingModelSpec,
    manifest: Any,
    *,
    requested_revision: str | None,
) -> str | None:
    if not isinstance(manifest, dict):
        return "manifest.json must contain an object payload."
    if manifest.get("providerKind") != spec.provider_kind:
        return "Manifest providerKind does not match configured model."
    if manifest.get("modelKey") != spec.model_key:
        return "Manifest modelKey does not match configured model."
    if manifest.get("hfRepoId") != spec.hf_repo_id:
        return "Manifest hfRepoId does not match registry."
    if int(manifest.get("dimension") or 0) != spec.dimension:
        return "Manifest dimension does not match registry."
    if manifest.get("requestedRevision") != requested_revision:
        return "Manifest requestedRevision does not match configured revision."
    if not isinstance(manifest.get("localPath"), str) or not str(manifest.get("localPath")).strip():
        return "Manifest localPath must be a non-empty string."
    return None


def _revision_segment(revision: str | None) -> str:
    if revision is None:
        return "current"
    safe = revision.strip().replace("/", "__")
    return safe or "current"


def _store_local_path(project_path: Path, local_path: Path) -> str:
    try:
        return str(local_path.resolve().relative_to(project_path.resolve()))
    except ValueError:
        return str(local_path.resolve())


def _deserialize_local_path(project_path: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return project_path / candidate


def _display_path(project_path: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(project_path.resolve()))
    except ValueError:
        return str(path.resolve())


def _validate_local_model_path(path: Path) -> str | None:
    if not path.is_dir():
        return "Local model path recorded in manifest is not a directory."
    try:
        if not any(path.iterdir()):
            return "Local model path exists but is empty; the cache may be only partially prepared."
    except OSError as exc:
        return f"Failed to inspect local model path: {exc}"
    return None


def _resolve_hf_token() -> str | bool:
    for env_name in ("HF_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        value = os.getenv(env_name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # Passing False opts into an explicit anonymous request path instead of
    # relying on library-side heuristics and warning text.
    return False


def _reset_model_cache_root(cache_root: Path) -> None:
    if not cache_root.exists():
        return
    if cache_root.is_file():
        cache_root.unlink()
        return
    shutil.rmtree(cache_root)
