from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EmbeddingModelStatus = Literal["ga", "beta"]


@dataclass(frozen=True)
class EmbeddingModelSpec:
    model_key: str
    provider_kind: str
    hf_repo_id: str
    dimension: int
    languages: tuple[str, ...]
    query_prefix: str
    passage_prefix: str
    approx_download_size_mb: int
    recommended: bool
    status: EmbeddingModelStatus

    @property
    def recommendation_badge(self) -> str:
        return "recommended" if self.recommended else "advanced"

    @property
    def label(self) -> str:
        return f"Local semantic: {self.model_key}"


_EMBEDDING_MODELS: dict[str, EmbeddingModelSpec] = {
    "multilingual-e5-small": EmbeddingModelSpec(
        model_key="multilingual-e5-small",
        provider_kind="local-hf-onnx",
        hf_repo_id="intfloat/multilingual-e5-small",
        dimension=384,
        languages=("ru", "en", "multilingual"),
        query_prefix="query: ",
        passage_prefix="passage: ",
        approx_download_size_mb=470,
        recommended=True,
        status="ga",
    ),
    "bge-m3": EmbeddingModelSpec(
        model_key="bge-m3",
        provider_kind="local-hf-onnx",
        hf_repo_id="BAAI/bge-m3",
        dimension=1024,
        languages=("ru", "en", "multilingual"),
        query_prefix="",
        passage_prefix="",
        approx_download_size_mb=2300,
        recommended=False,
        status="beta",
    ),
}


def get_embedding_model(model_key: str) -> EmbeddingModelSpec:
    try:
        return _EMBEDDING_MODELS[model_key]
    except KeyError as exc:
        allowed = ", ".join(sorted(_EMBEDDING_MODELS))
        raise ValueError(f"Unknown embedding model '{model_key}'. Expected one of: {allowed}") from exc


def list_embedding_models(provider_kind: str | None = None) -> list[EmbeddingModelSpec]:
    models = list(_EMBEDDING_MODELS.values())
    if provider_kind is not None:
        models = [model for model in models if model.provider_kind == provider_kind]
    return sorted(models, key=lambda item: (not item.recommended, item.approx_download_size_mb, item.model_key))


def get_recommended_embedding_model(provider_kind: str) -> EmbeddingModelSpec:
    for model in list_embedding_models(provider_kind):
        if model.recommended:
            return model
    raise ValueError(f"No recommended embedding model configured for provider '{provider_kind}'")
