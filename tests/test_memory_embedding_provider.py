from __future__ import annotations

import json
import math
import sqlite3
import sys
import types

import pytest

from madspec_cli.memory.application.system_store_ops import bootstrap_configured_model
from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.system_store.store import MemoryStore
from madspec_cli.memory.shared.system_store.sync import run_reindex
from madspec_cli.memory.shared.system_store.embedding_registry import (
    EmbeddingModelSpec,
    get_embedding_model,
    get_recommended_embedding_model,
    list_embedding_models,
)
from madspec_cli.memory.shared.system_store.layout import (
    build_reindex_status,
    get_system_memory_paths,
    list_vector_namespaces,
    resolve_vector_namespace,
)
from madspec_cli.memory.shared.system_store.model_bootstrap import (
    _download_model_snapshot,
    ensure_model_available,
    inspect_model_availability,
    resolve_model_cache_root,
)
from madspec_cli.memory.shared.system_store.provider_factory import (
    EmbeddingProviderRuntimeError,
    build_embedding_provider,
    resolve_configured_embeddings,
)
from madspec_cli.memory.shared.system_store.retrieval import RetrievalOrchestrator
from madspec_cli.memory.shared.system_store.retrieval import RetrievalEmbeddingProviderError
from madspec_cli.memory.shared.system_store.vector import (
    HashEmbeddingProvider,
    LocalHfOnnxEmbeddingProvider,
    VectorMemoryIndex,
    _chunk_source_text,
)
from tests.support import write_madspec_config


def test_embedding_registry_resolves_known_models() -> None:
    model = get_embedding_model("multilingual-e5-small")
    assert model.provider_kind == "local-hf-onnx"
    assert model.dimension == 384
    assert get_recommended_embedding_model("local-hf-onnx").model_key == "multilingual-e5-small"
    assert [item.model_key for item in list_embedding_models("local-hf-onnx")] == [
        "multilingual-e5-small",
        "bge-m3",
    ]


def test_vector_namespace_resolver_supports_hash_and_dense_paths(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()

    hash_namespace = resolve_vector_namespace(
        project_path,
        provider="hash",
        model=None,
        revision=None,
        dimension=64,
    )
    dense_namespace = resolve_vector_namespace(
        project_path,
        provider="local-hf-onnx",
        model="multilingual-e5-small",
        revision=None,
        dimension=384,
    )
    pinned_namespace = resolve_vector_namespace(
        project_path,
        provider="local-hf-onnx",
        model="bge-m3",
        revision="hf-commit-123",
        dimension=1024,
    )

    assert hash_namespace.relative_namespace(project_path) == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert dense_namespace.relative_namespace(project_path) == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/current/384"
    )
    assert pinned_namespace.relative_namespace(project_path) == (
        ".madspec/system/memory/lancedb/local-hf-onnx/bge-m3/hf-commit-123/1024"
    )


def test_hash_config_reports_bootstrap_not_required(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path)

    resolved = resolve_configured_embeddings(project_path)

    assert resolved.provider == "hash"
    assert resolved.bootstrap_status.status == "not_required"
    assert resolved.is_ready is True

    system_paths = get_system_memory_paths(project_path)
    assert system_paths.active_vector_namespace.provider == "hash"
    assert system_paths.active_vector_namespace.model == "default"
    assert system_paths.active_vector_namespace.dimension == 64


def test_dense_config_without_local_files_reports_missing(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    availability = inspect_model_availability(project_path, payload["memory"]["embeddings"])

    assert availability.status == "missing"
    assert availability.ready is False


def test_dense_config_with_invalid_manifest_reports_corrupted(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    embeddings_config = {
        "provider": "local-hf-onnx",
        "model": "multilingual-e5-small",
        "downloadPolicy": "on-first-use",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }
    cache_root = resolve_model_cache_root(project_path, embeddings_config["cacheDir"], embeddings_config["model"], None)
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.json").write_text("{bad json", encoding="utf-8")

    availability = inspect_model_availability(project_path, embeddings_config)

    assert availability.status == "corrupted"
    assert availability.ready is False


def test_dense_config_with_empty_local_model_directory_reports_corrupted(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    embeddings_config = {
        "provider": "local-hf-onnx",
        "model": "multilingual-e5-small",
        "downloadPolicy": "on-first-use",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }
    cache_root = resolve_model_cache_root(project_path, embeddings_config["cacheDir"], embeddings_config["model"], None)
    snapshot_dir = cache_root / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.json").write_text(
        json.dumps(
            {
                "providerKind": "local-hf-onnx",
                "modelKey": "multilingual-e5-small",
                "requestedRevision": None,
                "resolvedRevision": "current",
                "hfRepoId": "intfloat/multilingual-e5-small",
                "dimension": 384,
                "localPath": str(snapshot_dir.relative_to(project_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    availability = inspect_model_availability(project_path, embeddings_config)

    assert availability.status == "corrupted"
    assert availability.ready is False
    assert "empty" in (availability.message or "").lower()


def test_ensure_model_available_is_idempotent(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    embeddings_config = {
        "provider": "local-hf-onnx",
        "model": "multilingual-e5-small",
        "downloadPolicy": "on-init",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }
    calls: list[str] = []

    def fake_download(spec, cache_root, revision):
        del revision
        calls.append(spec.model_key)
        local_path = cache_root / "snapshot"
        local_path.mkdir(parents=True, exist_ok=True)
        (local_path / "model.onnx").write_text("placeholder", encoding="utf-8")
        return local_path, "current"

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.model_bootstrap._download_model_snapshot",
        fake_download,
    )

    first = ensure_model_available(project_path, embeddings_config, allow_download=True)
    second = ensure_model_available(project_path, embeddings_config, allow_download=True)

    assert first.ready is True
    assert second.ready is True
    assert calls == ["multilingual-e5-small"]


def test_bootstrap_configured_model_reports_hash_provider_as_not_required(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path)

    payload = bootstrap_configured_model(project_path)

    assert payload["provider"] == "hash"
    assert payload["ready"] is True
    assert payload["downloaded"] is False
    assert payload["next_action"] is None


def test_bootstrap_configured_model_requires_force_for_corrupted_cache(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    cache_root = resolve_model_cache_root(project_path, ".madspec/system/models", "multilingual-e5-small", None)
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.json").write_text("{broken", encoding="utf-8")

    with pytest.raises(RuntimeError, match="bootstrap-model --force"):
        bootstrap_configured_model(project_path)


def test_bootstrap_configured_model_can_rebuild_corrupted_cache_with_force(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    cache_root = resolve_model_cache_root(project_path, ".madspec/system/models", "multilingual-e5-small", None)
    cache_root.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.json").write_text("{broken", encoding="utf-8")
    (cache_root / "stale.tmp").write_text("stale", encoding="utf-8")

    def fake_download(spec, target_cache_root, revision):
        del spec, revision
        snapshot_dir = target_cache_root / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "model.onnx").write_text("placeholder", encoding="utf-8")
        return snapshot_dir, "current"

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.model_bootstrap._download_model_snapshot",
        fake_download,
    )

    result = bootstrap_configured_model(project_path, force=True)

    assert result["ready"] is True
    assert result["downloaded"] is True
    assert result["status"] == "ready"
    assert result["next_action"] == "Run `madspec memory reindex` to rebuild the active vector namespace."
    assert not (cache_root / "stale.tmp").exists()


def test_download_model_snapshot_uses_hf_token_when_available(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_snapshot_download(**kwargs):
        captured.update(kwargs)
        return str(tmp_path / "snapshot")

    monkeypatch.setenv("HF_TOKEN", "secret-token")
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=fake_snapshot_download),
    )

    spec = get_embedding_model("multilingual-e5-small")
    local_path, resolved_revision = _download_model_snapshot(spec, tmp_path / "cache", None)

    assert local_path == tmp_path / "snapshot"
    assert resolved_revision == "current"
    assert captured["token"] == "secret-token"


def test_download_model_snapshot_uses_explicit_anonymous_mode_without_token(tmp_path, monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_snapshot_download(**kwargs):
        captured.update(kwargs)
        return str(tmp_path / "snapshot")

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        types.SimpleNamespace(snapshot_download=fake_snapshot_download),
    )

    spec = get_embedding_model("multilingual-e5-small")
    _download_model_snapshot(spec, tmp_path / "cache", None)

    assert captured["token"] is False


def test_provider_factory_exposes_dense_bootstrap_metadata(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    resolved = resolve_configured_embeddings(project_path)

    assert resolved.provider == "local-hf-onnx"
    assert resolved.dimension == 384
    assert resolved.bootstrap_status.status == "missing"
    assert resolved.to_status_payload(project_path)["registry"]["hfRepoId"] == "intfloat/multilingual-e5-small"


def test_build_embedding_provider_returns_hash_provider(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path)

    provider = build_embedding_provider(project_path)

    assert isinstance(provider, HashEmbeddingProvider)
    assert provider.dimension == 64


def test_list_vector_namespaces_reports_created_namespaces(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    hash_namespace = resolve_vector_namespace(
        project_path,
        provider="hash",
        model=None,
        revision=None,
        dimension=64,
    )
    dense_namespace = resolve_vector_namespace(
        project_path,
        provider="local-hf-onnx",
        model="multilingual-e5-small",
        revision=None,
        dimension=384,
    )
    hash_namespace.namespace_dir.mkdir(parents=True, exist_ok=True)
    dense_namespace.namespace_dir.mkdir(parents=True, exist_ok=True)

    namespaces = list_vector_namespaces(project_path)

    assert [item.relative_namespace(project_path) for item in namespaces] == [
        ".madspec/system/memory/lancedb/hash/default/current/64",
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/current/384",
    ]


def test_reindex_rebuilds_only_target_namespace(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Reindex me",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    hash_result = run_reindex(project_path, "main", limit=200)

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    class FakeDenseProvider(HashEmbeddingProvider):
        def __init__(self) -> None:
            super().__init__(dimension=384)
            self.provider_kind = "local-hf-onnx"
            self.model_key = "multilingual-e5-small"

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.sync.build_embedding_provider",
        lambda project_root, allow_bootstrap=False: FakeDenseProvider(),
    )

    dense_result = run_reindex(project_path, "main", limit=200)
    namespaces = [item.relative_namespace(project_path) for item in list_vector_namespaces(project_path)]

    assert hash_result["target_namespace"]["path"] == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert dense_result["target_namespace"]["path"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/current/384"
    )
    assert namespaces == [
        ".madspec/system/memory/lancedb/hash/default/current/64",
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/current/384",
    ]

    hash_index = VectorMemoryIndex(
        project_path / ".madspec" / "system" / "memory" / "lancedb" / "hash" / "default" / "current" / "64",
        provider_kind="hash",
        model_key="default",
        revision="current",
        dimension=64,
    )
    dense_index = VectorMemoryIndex(
        project_path
        / ".madspec"
        / "system"
        / "memory"
        / "lancedb"
        / "local-hf-onnx"
        / "multilingual-e5-small"
        / "current"
        / "384",
        provider_kind="local-hf-onnx",
        model_key="multilingual-e5-small",
        revision="current",
        dimension=384,
    )
    assert hash_index.count_chunks("memory_chunks") >= 1
    assert dense_index.count_chunks("memory_chunks") >= 1


def test_reindex_status_tracks_confirmation_and_namespace_switch(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    store = MemoryStore(project_path)
    store.ensure_schema()

    before_reindex = build_reindex_status(project_path)
    assert before_reindex["reindexRequired"] is True
    assert before_reindex["reason"] == "not_confirmed"

    run_reindex(project_path, "main", limit=200)

    after_reindex = build_reindex_status(project_path)
    assert after_reindex["reindexRequired"] is False
    assert after_reindex["reason"] == "current"
    assert after_reindex["lastIndexedNamespace"]["path"] == ".madspec/system/memory/lancedb/hash/default/current/64"

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    switched = build_reindex_status(project_path)
    assert switched["reindexRequired"] is True
    assert switched["reason"] == "namespace_mismatch"
    assert switched["lastIndexedNamespace"]["path"] == ".madspec/system/memory/lancedb/hash/default/current/64"


def test_build_embedding_provider_rejects_unready_dense_model(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "none",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(EmbeddingProviderRuntimeError, match="is not ready"):
        build_embedding_provider(project_path)


def test_build_embedding_provider_bootstraps_on_first_use(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    created: dict[str, object] = {}

    def fake_bootstrap(project_root, embeddings_config, *, allow_download):
        assert project_root == project_path
        assert allow_download is True
        cache_root = resolve_model_cache_root(
            project_root,
            embeddings_config["cacheDir"],
            embeddings_config["model"],
            embeddings_config["revision"],
        )
        snapshot_dir = cache_root / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        (snapshot_dir / "model.onnx").write_text("binary placeholder", encoding="utf-8")
        (cache_root / "manifest.json").write_text(
            json.dumps(
                {
                    "providerKind": "local-hf-onnx",
                    "modelKey": "multilingual-e5-small",
                    "requestedRevision": None,
                    "resolvedRevision": "current",
                    "hfRepoId": "intfloat/multilingual-e5-small",
                    "dimension": 384,
                    "downloadedAt": "2026-03-27T12:00:00+00:00",
                    "status": "ready",
                    "localPath": str(snapshot_dir.relative_to(project_root)),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        created["cache_root"] = cache_root
        return None

    class FakeDenseProvider:
        def __init__(self, *, model_spec, local_path):
            self.model_spec = model_spec
            self.local_path = local_path

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.provider_factory.ensure_model_available",
        fake_bootstrap,
    )
    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.provider_factory.LocalHfOnnxEmbeddingProvider",
        FakeDenseProvider,
    )

    provider = build_embedding_provider(project_path, allow_bootstrap=True)

    assert isinstance(provider, FakeDenseProvider)
    assert provider.model_spec.model_key == "multilingual-e5-small"
    assert provider.local_path == created["cache_root"] / "snapshot"


def test_local_onnx_provider_applies_query_and_passage_prefixes(tmp_path) -> None:
    class FakeEncoding:
        def __init__(self, ids):
            self.ids = ids
            self.attention_mask = [1] * len(ids)
            self.type_ids = [0] * len(ids)

    class FakeTokenizer:
        def __init__(self) -> None:
            self.seen: list[str] = []

        def encode(self, text: str):
            self.seen.append(text)
            return FakeEncoding([1, 2, 3])

    class FakeInput:
        def __init__(self, name: str, shape) -> None:
            self.name = name
            self.shape = shape

    class FakeSession:
        def get_inputs(self):
            return [
                FakeInput("input_ids", [None, 4]),
                FakeInput("attention_mask", [None, 4]),
                FakeInput("token_type_ids", [None, 4]),
            ]

        def run(self, _outputs, _feed):
            return [
                [
                    [
                        [1.0, 0.0, 0.0],
                        [0.0, 1.0, 0.0],
                        [0.0, 0.0, 1.0],
                        [0.0, 0.0, 0.0],
                    ]
                ]
            ]

    spec = EmbeddingModelSpec(
        model_key="fixture-model",
        provider_kind="local-hf-onnx",
        hf_repo_id="fixtures/provider",
        dimension=3,
        languages=("ru",),
        query_prefix="query: ",
        passage_prefix="passage: ",
        approx_download_size_mb=1,
        recommended=False,
        status="beta",
    )
    tokenizer = FakeTokenizer()
    provider = LocalHfOnnxEmbeddingProvider(
        model_spec=spec,
        local_path=tmp_path,
        tokenizer=tokenizer,
        session=FakeSession(),
    )

    query_vector = provider.embed_query("hello")
    passage_vector = provider.embed_passage("world")
    blank_vector = provider.embed_query("   ")

    expected = [1.0 / math.sqrt(3.0)] * 3
    assert tokenizer.seen == ["query: hello", "passage: world"]
    assert query_vector == pytest.approx(expected)
    assert passage_vector == pytest.approx(expected)
    assert blank_vector == [0.0, 0.0, 0.0]


def test_vector_index_uses_passage_embeddings_for_chunks_and_query_embeddings_for_search(tmp_path, monkeypatch) -> None:
    from madspec_cli.memory.shared.system_store import vector as vector_module

    class RecordingProvider(HashEmbeddingProvider):
        def __init__(self) -> None:
            super().__init__(dimension=4)
            self.queries: list[str] = []
            self.passages: list[str] = []

        def embed_query(self, text: str) -> list[float]:
            self.queries.append(text)
            return [1.0, 0.0, 0.0, 0.0]

        def embed_passage(self, text: str) -> list[float]:
            self.passages.append(text)
            return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr(vector_module, "lancedb", None)
    monkeypatch.setattr(vector_module, "pa", None)

    provider = RecordingProvider()
    chunks = _chunk_source_text(
        source_type="record",
        source_id="rec-1",
        branch="main",
        stage="mvp.plan",
        step_id=None,
        scope="branch",
        status="validated",
        kind="decision",
        content_hash="abc",
        text="Relevant decision text",
        provider=provider,
        table_name="memory_chunks",
    )
    index = VectorMemoryIndex(tmp_path / "index", provider=provider)
    index.upsert_chunks("memory_chunks", chunks)

    results = index.search(
        "Relevant decision query",
        branch="main",
        stage="mvp.plan",
        scope="branch",
        limit=5,
    )

    assert provider.passages == ["Relevant decision text"]
    assert provider.queries == ["Relevant decision query"]
    assert results


def test_retrieval_orchestrator_uses_configured_dense_provider_for_semantic_lane(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Dense semantic decision",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    class FakeDenseProvider(HashEmbeddingProvider):
        def __init__(self) -> None:
            super().__init__(dimension=384)
            self.provider_kind = "local-hf-onnx"
            self.model_key = "multilingual-e5-small"

    created: list[FakeDenseProvider] = []

    def fake_build_embedding_provider(project_root, *, allow_bootstrap=False):
        assert project_root == project_path
        assert allow_bootstrap is True
        provider = FakeDenseProvider()
        created.append(provider)
        return provider

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.retrieval.build_embedding_provider",
        fake_build_embedding_provider,
    )

    orchestrator = RetrievalOrchestrator(project_path)
    payload = orchestrator.search(
        branch="main",
        stage="mvp.plan",
        step_id=None,
        query="Dense semantic decision",
        scope="branch",
        recall_limit=5,
    )

    assert len(created) == 1
    assert payload["semantic_enabled"] is True
    assert payload["semantic_matches"]
    assert orchestrator.index is not None
    assert orchestrator.index.provider_kind == "local-hf-onnx"
    assert orchestrator.index.model_key == "multilingual-e5-small"
    assert orchestrator.index.root_dir == (
        project_path
        / ".madspec"
        / "system"
        / "memory"
        / "lancedb"
        / "local-hf-onnx"
        / "multilingual-e5-small"
        / "current"
        / "384"
    )


def test_retrieval_orchestrator_uses_active_namespace_for_pinned_revision(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": "hf-pin-123",
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Pinned semantic decision",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    class FakeDenseProvider(HashEmbeddingProvider):
        def __init__(self) -> None:
            super().__init__(dimension=384)
            self.provider_kind = "local-hf-onnx"
            self.model_key = "multilingual-e5-small"

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.retrieval.build_embedding_provider",
        lambda *_args, **_kwargs: FakeDenseProvider(),
    )

    payload = RetrievalOrchestrator(project_path).search(
        branch="main",
        stage="mvp.plan",
        step_id=None,
        query="Pinned semantic decision",
        scope="branch",
        recall_limit=5,
    )

    expected_path = ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    assert payload["semantic_runtime"]["active_vector_namespace"]["path"] == expected_path
    assert payload["semantic_runtime"]["runtime_provider"]["namespacePath"] == expected_path


def test_retrieval_orchestrator_skips_dense_bootstrap_when_semantic_disabled(tmp_path, monkeypatch) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Dense semantic decision",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.retrieval.build_embedding_provider",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("dense provider should not be built")),
    )

    orchestrator = RetrievalOrchestrator(project_path)
    payload = orchestrator.search(
        branch="main",
        stage="mvp.plan",
        step_id=None,
        query="Dense semantic decision",
        scope="branch",
        recall_limit=5,
        disable_semantic=True,
    )

    assert payload["semantic_enabled"] is False
    assert payload["semantic_matches"] == []
    assert orchestrator.index is None


def test_retrieval_orchestrator_reports_semantic_runtime_for_hash_provider(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path)
    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Hash semantic decision",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    payload = RetrievalOrchestrator(project_path).search(
        branch="main",
        stage="mvp.plan",
        step_id=None,
        query="Hash semantic decision",
        scope="branch",
        recall_limit=5,
    )

    assert payload["semantic_enabled"] is True
    assert payload["semantic_runtime"] == {
        "configured_embeddings": payload["semantic_runtime"]["configured_embeddings"],
        "active_vector_namespace": {
            "provider": "hash",
            "model": "default",
            "revision": "current",
            "dimension": 64,
            "path": ".madspec/system/memory/lancedb/hash/default/current/64",
        },
        "semantic_requested": True,
        "semantic_used": True,
        "semantic_outcome": "used",
        "runtime_provider": {
            "provider": "hash",
            "model": "default",
            "revision": "current",
            "dimension": 64,
            "namespacePath": ".madspec/system/memory/lancedb/hash/default/current/64",
        },
        "provider_error": None,
    }
    assert payload["semantic_runtime"]["configured_embeddings"]["status"] == "not_required"
    retrieval_runs = store.list_retrieval_runs(branch="main", limit=1)
    assert retrieval_runs[0]["provider"] == "hash"
    assert retrieval_runs[0]["semantic_outcome"] == "used"
    assert retrieval_runs[0]["error_kind"] is None


def test_retrieval_orchestrator_raises_structured_provider_error_without_fallback(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "none",
            "cacheDir": ".madspec/system/models",
            "revision": None,
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    store = MemoryStore(project_path)
    store.ensure_schema()
    store.upsert_record(
        make_record(
            "main",
            "mvp.plan",
            "agent",
            "Dense semantic decision",
            status="validated",
            semantic_kind="decision",
            record_type="decision",
        )
    )

    with pytest.raises(RetrievalEmbeddingProviderError) as exc_info:
        RetrievalOrchestrator(project_path).search(
            branch="main",
            stage="mvp.plan",
            step_id=None,
            query="Dense semantic decision",
            scope="branch",
            recall_limit=5,
        )

    payload = exc_info.value.payload
    assert payload["kind"] == "embedding_provider_error"
    assert payload["provider"] == "local-hf-onnx"
    assert payload["model"] == "multilingual-e5-small"
    assert payload["status"] == "missing"
    assert payload["bootstrap"]["status"] == "missing"
    assert "hash" not in payload["message"]

    retrieval_runs = store.list_retrieval_runs(branch="main", limit=1)
    assert retrieval_runs[0]["semantic_enabled"] is False
    assert retrieval_runs[0]["semantic_outcome"] == "provider_error"
    assert retrieval_runs[0]["error_kind"] == "embedding_provider_error"
    assert retrieval_runs[0]["provider"] == "local-hf-onnx"


def test_memory_store_migrates_legacy_retrieval_runs_schema(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    write_madspec_config(project_path)
    store = MemoryStore(project_path)
    store.paths.memory_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(store.paths.sqlite_file) as conn:
        conn.execute(
            """
            CREATE TABLE retrieval_runs (
                run_id TEXT PRIMARY KEY,
                branch TEXT NOT NULL,
                stage TEXT NOT NULL,
                step_id TEXT,
                query TEXT,
                semantic_enabled INTEGER NOT NULL,
                triggers_json TEXT NOT NULL,
                exact_count INTEGER NOT NULL,
                lexical_count INTEGER NOT NULL,
                semantic_count INTEGER NOT NULL,
                merged_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO retrieval_runs (
                run_id, branch, stage, step_id, query, semantic_enabled, triggers_json,
                exact_count, lexical_count, semantic_count, merged_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "legacy-run",
                "main",
                "mvp.plan",
                None,
                "legacy query",
                0,
                "[]",
                1,
                1,
                0,
                1,
                "2026-03-27T12:00:00+00:00",
            ),
        )

    store.ensure_schema()

    with store.connect_read_only() as conn:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(retrieval_runs)").fetchall()
        }
    assert {
        "provider",
        "model",
        "revision",
        "dimension",
        "namespace_path",
        "bootstrap_status",
        "semantic_outcome",
        "error_kind",
        "error_message",
    } <= columns

    rows = store.list_retrieval_runs(branch="main", limit=1)
    assert rows[0]["run_id"] == "legacy-run"
    assert rows[0]["provider"] is None
    assert rows[0]["semantic_outcome"] is None


def test_process_pending_jobs_without_explicit_namespace_uses_active_revision(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    config_path = write_madspec_config(project_path)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["memory"] = {
        "embeddings": {
            "provider": "local-hf-onnx",
            "model": "multilingual-e5-small",
            "downloadPolicy": "on-first-use",
            "cacheDir": ".madspec/system/models",
            "revision": "hf-pin-123",
        }
    }
    config_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    class FakeDenseProvider(HashEmbeddingProvider):
        def __init__(self) -> None:
            super().__init__(dimension=384)
            self.provider_kind = "local-hf-onnx"
            self.model_key = "multilingual-e5-small"

    store = MemoryStore(project_path)
    store.ensure_schema()

    result = store.process_pending_jobs(provider=FakeDenseProvider(), rebuild=False)

    assert result["target_namespace"]["path"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    )
