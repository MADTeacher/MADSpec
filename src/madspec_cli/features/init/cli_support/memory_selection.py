from __future__ import annotations

import sys
from collections.abc import Callable

from madspec_cli.shared.cli.banners import select_with_arrows
from madspec_cli.shared.infra.project_config import (
    DEFAULT_MEMORY_EMBEDDINGS_CACHE_DIR,
    SUPPORTED_MEMORY_DOWNLOAD_POLICIES,
    SUPPORTED_MEMORY_EMBEDDING_PROVIDERS,
)

from ..application.contracts import INIT_MEMORY_MODEL_CATALOG, InitMemorySelection


def can_prompt_for_memory_selection() -> bool:
    return bool(getattr(sys.stdin, "isatty", lambda: False)() and getattr(sys.stdout, "isatty", lambda: False)())


def memory_selection_summary(selection: InitMemorySelection) -> str:
    if selection.is_dense and selection.model:
        return f"{selection.model} ({selection.download_policy})"
    return selection.provider


def resolve_memory_selection_from_flags(
    *,
    provider: str | None,
    model: str | None,
    download_policy: str | None,
) -> InitMemorySelection:
    provider = provider.strip() if isinstance(provider, str) else provider
    model = model.strip() if isinstance(model, str) else model
    download_policy = download_policy.strip() if isinstance(download_policy, str) else download_policy

    if provider is None:
        extras = [name for name, value in {"--memory-model": model, "--memory-download-policy": download_policy}.items() if value]
        if extras:
            raise ValueError(f"{', '.join(extras)} requires --memory-provider")
        return InitMemorySelection(provider="hash", model=None, download_policy="none")

    if provider not in SUPPORTED_MEMORY_EMBEDDING_PROVIDERS:
        allowed = ", ".join(sorted(SUPPORTED_MEMORY_EMBEDDING_PROVIDERS))
        raise ValueError(f"Unknown --memory-provider '{provider}'. Expected one of: {allowed}")

    if download_policy is not None and download_policy not in SUPPORTED_MEMORY_DOWNLOAD_POLICIES:
        allowed = ", ".join(sorted(SUPPORTED_MEMORY_DOWNLOAD_POLICIES))
        raise ValueError(f"Unknown --memory-download-policy '{download_policy}'. Expected one of: {allowed}")

    if provider == "hash":
        if model:
            raise ValueError("--memory-model is only valid with --memory-provider local-hf-onnx")
        if download_policy not in (None, "none"):
            raise ValueError("--memory-download-policy must be 'none' when --memory-provider=hash")
        return InitMemorySelection(provider="hash", model=None, download_policy="none")

    if not model:
        raise ValueError("--memory-provider local-hf-onnx requires --memory-model")
    if model not in INIT_MEMORY_MODEL_CATALOG:
        allowed_models = ", ".join(sorted(INIT_MEMORY_MODEL_CATALOG))
        raise ValueError(f"Unknown --memory-model '{model}'. Expected one of: {allowed_models}")
    model_option = INIT_MEMORY_MODEL_CATALOG[model]
    if model_option.provider_kind != provider:
        raise ValueError(f"--memory-model '{model}' is not supported by provider '{provider}'")
    return InitMemorySelection(
        provider=provider,
        model=model,
        download_policy=download_policy or model_option.default_download_policy,
    )


def choose_memory_embeddings_interactively(
    *,
    select_fn: Callable[[dict[str, str], str, str | None], str] = select_with_arrows,
) -> InitMemorySelection:
    cache_dir = DEFAULT_MEMORY_EMBEDDINGS_CACHE_DIR
    model_options = {
        "hash": f"Standard hash (0 MB download, compatibility mode, cache: {cache_dir})",
    }
    for model_key, option in INIT_MEMORY_MODEL_CATALOG.items():
        languages = "/".join(option.languages)
        model_options[model_key] = (
            f"{option.label} ({option.recommendation_badge}, {languages}, "
            f"{option.dimension} dim, ~{option.approx_download_size_mb} MB, cache: {cache_dir})"
        )

    selected_key = select_fn(model_options, "Choose memory embeddings:", "hash")
    if selected_key == "hash":
        return InitMemorySelection(provider="hash", model=None, download_policy="none")

    selected_model = INIT_MEMORY_MODEL_CATALOG[selected_key]
    policy = select_fn(
        {
            "on-init": f"Download now ({selected_model.recommendation_badge}, ~{selected_model.approx_download_size_mb} MB, cache: {cache_dir})",
            "on-first-use": f"Download on first use (defer ~{selected_model.approx_download_size_mb} MB download, cache: {cache_dir})",
        },
        "Choose model download policy:",
        selected_model.default_download_policy,
    )
    return InitMemorySelection(
        provider=selected_model.provider_kind,
        model=selected_model.model_key,
        download_policy=policy,
    )


def resolve_memory_selection(
    *,
    provider: str | None,
    model: str | None,
    download_policy: str | None,
) -> InitMemorySelection:
    if any(value is not None for value in (provider, model, download_policy)):
        return resolve_memory_selection_from_flags(
            provider=provider,
            model=model,
            download_policy=download_policy,
        )
    if can_prompt_for_memory_selection():
        return choose_memory_embeddings_interactively()
    return InitMemorySelection(provider="hash", model=None, download_policy="none")
