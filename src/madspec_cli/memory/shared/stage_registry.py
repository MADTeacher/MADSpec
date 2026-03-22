from __future__ import annotations

from typing import Any, Callable

_STAGE_DEFAULT_FACTORIES: dict[str, Callable[[], dict[str, Any]]] = {}
_STAGE_LOADERS: dict[str, Callable] = {}
_STAGE_VALIDATORS: dict[str, dict[str, Callable]] = {}
_STAGE_RENDERERS: dict[str, dict[str, Callable]] = {}


def register_stage_default(stage_key: str, factory: Callable[[], dict[str, Any]]) -> None:
    _STAGE_DEFAULT_FACTORIES[stage_key] = factory


def get_stage_default(stage_key: str) -> Callable[[], dict[str, Any]]:
    return _STAGE_DEFAULT_FACTORIES[stage_key]


def get_all_stage_defaults() -> dict[str, Callable[[], dict[str, Any]]]:
    return dict(_STAGE_DEFAULT_FACTORIES)


def register_stage_loader(stage_key: str, loader: Callable) -> None:
    _STAGE_LOADERS[stage_key] = loader


def get_stage_loader(stage_key: str) -> Callable:
    return _STAGE_LOADERS[stage_key]


def register_stage_validators(stage_key: str, **validators: Callable) -> None:
    _STAGE_VALIDATORS[stage_key] = validators


def get_stage_validators(stage_key: str) -> dict[str, Callable]:
    return _STAGE_VALIDATORS.get(stage_key, {})


def register_stage_renderers(stage_key: str, **renderers: Callable) -> None:
    _STAGE_RENDERERS[stage_key] = renderers


def get_stage_renderer(stage_key: str, renderer_name: str) -> Callable | None:
    return _STAGE_RENDERERS.get(stage_key, {}).get(renderer_name)
