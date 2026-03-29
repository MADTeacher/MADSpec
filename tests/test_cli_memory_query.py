from __future__ import annotations

import json

from madspec_cli.memory import get_memory_paths
from madspec_cli.memory.shared.records import make_record
from madspec_cli.memory.shared.storage import append_jsonl
from madspec_cli.memory.shared.system_store.model_bootstrap import resolve_model_cache_root
from tests.support import sync_branch_state, write_madspec_config


def test_memory_commands_support_validation_and_retrieve_json(
    make_madspec_project,
    invoke_cli,
    write_concept_markdown,
    create_step_artifacts,
) -> None:
    project_path = make_madspec_project()
    branch_dir = project_path / ".madspec" / "main"
    branch_dir.mkdir(parents=True, exist_ok=True)
    write_concept_markdown(branch_dir, variant="auth_sessions")

    result = invoke_cli(["memory", "init", "--branch", "main"])
    assert result.exit_code == 0, result.stdout
    create_step_artifacts(branch_dir, "step-01-bootstrap")
    create_step_artifacts(branch_dir, "step-02-auth-flow")

    capture_result = invoke_cli(
        [
            "memory",
            "capture",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--decision",
            "Validated planning decision",
            "--evidence",
            "README.md",
            "--json-output",
        ]
    )
    assert capture_result.exit_code == 0, capture_result.stdout

    validate_result = invoke_cli(["memory", "validate", "--branch", "main", "--json-output"])
    assert validate_result.exit_code == 0, validate_result.stdout
    assert json.loads(validate_result.stdout)["valid"] is True

    db_status_result = invoke_cli(["memory", "db-status", "--branch", "main", "--json-output"])
    assert db_status_result.exit_code == 0, db_status_result.stdout
    db_status_payload = json.loads(db_status_result.stdout)
    assert db_status_payload["sqlite_path"] == ".madspec/system/memory/memory.sqlite"
    assert db_status_payload["stage_snapshots"] >= 1
    assert db_status_payload["vector_backend"] == "lancedb"
    assert db_status_payload["vector_root_dir"] == ".madspec/system/memory/lancedb"
    assert db_status_payload["active_vector_namespace"] == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert db_status_payload["active_vector_provider"] == "hash"
    assert db_status_payload["active_vector_model"] == "default"
    assert db_status_payload["active_vector_revision"] == "current"
    assert db_status_payload["active_vector_dimension"] == 64
    assert db_status_payload["known_vector_namespaces"] == [
        {
            "provider": "hash",
            "model": "default",
            "revision": "current",
            "dimension": 64,
            "path": ".madspec/system/memory/lancedb/hash/default/current/64",
        }
    ]
    assert db_status_payload["configured_embeddings"]["provider"] == "hash"
    assert db_status_payload["configured_embeddings"]["status"] == "not_required"
    assert db_status_payload["configured_embeddings"]["ready"] is True
    assert db_status_payload["index_state"]["reindexRequired"] is True
    assert db_status_payload["index_state"]["reason"] == "not_confirmed"

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout
    reindex_payload = json.loads(reindex_result.stdout)
    assert reindex_payload["lease_acquired"] is True
    assert reindex_payload["processed"] >= 1
    assert reindex_payload["target_namespace"] == {
        "provider": "hash",
        "model": "default",
        "revision": "current",
        "dimension": 64,
        "path": ".madspec/system/memory/lancedb/hash/default/current/64",
    }

    db_status_after_reindex_result = invoke_cli(["memory", "db-status", "--branch", "main", "--json-output"])
    assert db_status_after_reindex_result.exit_code == 0, db_status_after_reindex_result.stdout
    db_status_after_reindex = json.loads(db_status_after_reindex_result.stdout)
    assert db_status_after_reindex["index_state"]["reindexRequired"] is False
    assert db_status_after_reindex["index_state"]["reason"] == "current"

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--disable-semantic",
            "--json-output",
        ]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    payload = json.loads(retrieve_result.stdout)
    assert payload["runtime_revision"] >= 0
    assert payload["semantic"]["decisions"][0]["summary"] == "Validated planning decision"
    assert payload["recall"]["resolved_query"] == "Validated planning decision"
    assert payload["recall"]["semantic_enabled"] is False
    assert payload["recall"]["semantic_runtime"]["semantic_outcome"] == "disabled"
    assert payload["recall"]["semantic_runtime"]["configured_embeddings"]["provider"] == "hash"
    assert payload["recall"]["merged"][0]["summary"] == "Validated planning decision"
    assert payload["observability"]["shared_branch_state"]["runtime_revision"] >= 0
    assert payload["observability"]["embeddings"]["configured_embeddings"]["provider"] == "hash"
    assert payload["observability"]["summary"]["projection_status"] in {"ok", "warn", "error"}
    assert payload["observability"]["summary"]["semantic_integrity_status"] in {"ok", "warn", "error"}
    assert payload["observability"]["summary"]["semantic_integrity_project_issue_count"] >= 0

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Validated planning decision",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["runtime_revision"] >= 0
    assert search_payload["exact_matches"]
    assert search_payload["semantic_runtime"]["configured_embeddings"]["provider"] == "hash"
    assert search_payload["semantic_runtime"]["semantic_outcome"] == "used"
    assert search_payload["merged"][0]["summary"] == "Validated planning decision"
    assert search_payload["observability"]["embeddings"]["semantic_outcome"] == "used"
    assert search_payload["observability"]["summary"]["pending_proposal_count"] >= 0
    assert "current_session_state" in search_payload["observability"]

    next_step_candidate = invoke_cli(
        [
            "memory",
            "next-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--candidate-step",
            "step-02-auth-flow",
            "--depends-on",
            "step-01-bootstrap",
            "--json-output",
        ]
    )
    assert next_step_candidate.exit_code == 1, next_step_candidate.stdout

    register_first = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-01-bootstrap",
            "--step-kind",
            "code",
            "--covers",
            "Authentication",
            "--json-output",
        ]
    )
    assert register_first.exit_code == 0, register_first.stdout

    register_second = invoke_cli(
        [
            "memory",
            "register-step",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--step-id",
            "step-02-auth-flow",
            "--step-kind",
            "code",
            "--covers",
            "Sessions",
            "--depends-on",
            "step-01-bootstrap",
            "--json-output",
        ]
    )
    assert register_second.exit_code == 0, register_second.stdout

    start_result = invoke_cli(
        ["memory", "start-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert start_result.exit_code == 0, start_result.stdout
    assert json.loads(start_result.stdout)["step_id"] == "step-01-bootstrap"

    checkpoint_result = invoke_cli(
        [
            "memory",
            "checkpoint-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-bootstrap",
            "--tdd-phase",
            "red",
            "--summary",
            "Bootstrap test is red",
            "--red-evidence",
            "uv run pytest tests/test_bootstrap.py -q",
            "--json-output",
        ]
    )
    assert checkpoint_result.exit_code == 0, checkpoint_result.stdout

    complete_result = invoke_cli(
        [
            "memory",
            "complete-step",
            "--branch",
            "main",
            "--stage",
            "mvp.implement",
            "--step-id",
            "step-01-bootstrap",
            "--summary",
            "Bootstrap completed",
            "--green-evidence",
            "uv run pytest tests/test_bootstrap.py -q",
            "--refactor-note",
            "No refactor needed.",
            "--json-output",
        ]
    )
    assert complete_result.exit_code == 0, complete_result.stdout

    next_step_select = invoke_cli(
        ["memory", "next-step", "--branch", "main", "--stage", "mvp.implement", "--json-output"]
    )
    assert next_step_select.exit_code == 0, next_step_select.stdout
    next_step_payload = json.loads(next_step_select.stdout)
    assert next_step_payload["selected_step"] == "step-02-auth-flow"


def test_memory_bootstrap_model_prepares_dense_cache_without_reindex(tmp_path, monkeypatch, invoke_cli) -> None:
    project_path = tmp_path / "dense-bootstrap"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    config_path = write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
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

    def fake_download(spec, cache_root, revision):
        del spec, revision
        snapshot_dir = cache_root / "snapshot"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        (snapshot_dir / "model.onnx").write_text("placeholder", encoding="utf-8")
        return snapshot_dir, "current"

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.model_bootstrap._download_model_snapshot",
        fake_download,
    )

    result = invoke_cli(["memory", "bootstrap-model", "--json-output"])

    assert result.exit_code == 0, result.stdout
    bootstrap_payload = json.loads(result.stdout)
    assert bootstrap_payload["provider"] == "local-hf-onnx"
    assert bootstrap_payload["model"] == "multilingual-e5-small"
    assert bootstrap_payload["ready"] is True
    assert bootstrap_payload["downloaded"] is True
    assert bootstrap_payload["next_action"] == "Run `madspec memory reindex` to rebuild the active vector namespace."

    cache_root = resolve_model_cache_root(project_path, ".madspec/system/models", "multilingual-e5-small", None)
    assert (cache_root / "manifest.json").exists()

    db_status_result = invoke_cli(["memory", "db-status", "--branch", "main", "--json-output"])
    assert db_status_result.exit_code == 0, db_status_result.stdout
    db_status_payload = json.loads(db_status_result.stdout)
    assert db_status_payload["configured_embeddings"]["ready"] is True
    assert db_status_payload["index_state"]["reindexRequired"] is True


def test_memory_bootstrap_model_requires_force_for_corrupted_cache(tmp_path, monkeypatch, invoke_cli) -> None:
    project_path = tmp_path / "dense-corrupted"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    config_path = write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
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

    failed = invoke_cli(["memory", "bootstrap-model", "--json-output"])
    assert failed.exit_code == 1, failed.stdout
    assert "bootstrap-model --force" in json.loads(failed.stdout)["message"]

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

    forced = invoke_cli(["memory", "bootstrap-model", "--force"])
    assert forced.exit_code == 0, forced.stdout
    assert "Next step:" in forced.stdout


def test_memory_retrieve_and_explain_support_toon_output(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths["decision_log"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Choose staged rollout",
                status="validated",
                evidence=["docs/cli/memory.md"],
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--toon-output"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    assert "branch: main" in retrieve_result.stdout
    assert "policy_context:" in retrieve_result.stdout
    assert "semantic:" in retrieve_result.stdout
    assert "semantic_runtime:" in retrieve_result.stdout

    explain_result = invoke_cli(
        ["memory", "explain", "--branch", "main", "--stage", "mvp.plan", "--toon-output"]
    )
    assert explain_result.exit_code == 0, explain_result.stdout
    assert "branch: main" in explain_result.stdout
    assert "runtime_revision:" in explain_result.stdout
    assert "summary:" in explain_result.stdout
    assert "gate_summary:" in explain_result.stdout


def test_memory_search_and_retrieve_text_show_embeddings_runtime(make_madspec_project, invoke_cli) -> None:
    project_path = make_madspec_project()

    init_result = invoke_cli(["memory", "init", "--branch", "main"])
    assert init_result.exit_code == 0, init_result.stdout

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths["decisions"],
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Searchable planning decision",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )

    search_result = invoke_cli(
        ["memory", "search", "--branch", "main", "--stage", "mvp.plan", "--query", "Searchable planning decision"]
    )
    assert search_result.exit_code == 0, search_result.stdout
    assert "Embeddings:" in search_result.stdout
    assert "Active namespace:" in search_result.stdout

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--query", "Searchable planning decision"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    assert "Embeddings:" in retrieve_result.stdout
    assert "Active namespace:" in retrieve_result.stdout


def test_memory_search_and_retrieve_return_structured_provider_error(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = tmp_path / "provider-error"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    config_path = project_path / ".madspec" / "config.json"
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
    init_memory_branch(branch="main", project_path=project_path)
    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths.decisions,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Dense search error",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )
    sync_branch_state(project_path, "main")

    search_result = invoke_cli(
        [
            "memory",
            "search",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Dense search error",
            "--json-output",
        ]
    )
    assert search_result.exit_code == 1, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["kind"] == "embedding_provider_error"
    assert search_payload["provider"] == "local-hf-onnx"
    assert search_payload["bootstrap"]["status"] == "missing"

    retrieve_result = invoke_cli(
        [
            "memory",
            "retrieve",
            "--branch",
            "main",
            "--stage",
            "mvp.plan",
            "--query",
            "Dense search error",
            "--toon-output",
        ]
    )
    assert retrieve_result.exit_code == 1, retrieve_result.stdout
    assert "kind: embedding_provider_error" in retrieve_result.stdout
    assert "provider: local-hf-onnx" in retrieve_result.stdout


def test_memory_search_and_retrieve_use_pinned_active_namespace(
    tmp_path,
    monkeypatch,
    invoke_cli,
    init_memory_branch,
) -> None:
    project_path = tmp_path / "pinned-revision"
    project_path.mkdir()
    monkeypatch.chdir(project_path)
    write_madspec_config(project_path, branch="main", agent_environment="cursor-agent")
    config_path = project_path / ".madspec" / "config.json"
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
    init_memory_branch(branch="main", project_path=project_path)

    cache_root = project_path / ".madspec" / "system" / "models" / "multilingual-e5-small" / "hf-pin-123"
    snapshot_dir = cache_root / "snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "model.onnx").write_text("placeholder", encoding="utf-8")
    (cache_root / "manifest.json").write_text(
        json.dumps(
            {
                "providerKind": "local-hf-onnx",
                "modelKey": "multilingual-e5-small",
                "requestedRevision": "hf-pin-123",
                "resolvedRevision": "hf-pin-123",
                "hfRepoId": "intfloat/multilingual-e5-small",
                "dimension": 384,
                "localPath": str(snapshot_dir.relative_to(project_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    paths = get_memory_paths(project_path, "main")
    append_jsonl(
        paths.decisions,
        [
            make_record(
                "main",
                "mvp.plan",
                "agent",
                "Pinned revision decision",
                status="validated",
                semantic_kind="decision",
                record_type="decision",
            )
        ],
    )
    sync_branch_state(project_path, "main")

    class FakeDenseProvider:
        provider_kind = "local-hf-onnx"
        model_key = "multilingual-e5-small"
        dimension = 384

        def embed_query(self, text: str) -> list[float]:
            return [1.0] + [0.0] * 383

        def embed_passage(self, text: str) -> list[float]:
            return [1.0] + [0.0] * 383

        def embed_text(self, text: str) -> list[float]:
            return self.embed_passage(text)

    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.sync.build_embedding_provider",
        lambda *_args, **_kwargs: FakeDenseProvider(),
    )
    monkeypatch.setattr(
        "madspec_cli.memory.shared.system_store.retrieval.build_embedding_provider",
        lambda *_args, **_kwargs: FakeDenseProvider(),
    )

    reindex_result = invoke_cli(["memory", "reindex", "--branch", "main", "--json-output"])
    assert reindex_result.exit_code == 0, reindex_result.stdout
    assert json.loads(reindex_result.stdout)["target_namespace"]["path"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    )

    search_result = invoke_cli(
        ["memory", "search", "--branch", "main", "--stage", "mvp.plan", "--query", "Pinned revision decision", "--json-output"]
    )
    assert search_result.exit_code == 0, search_result.stdout
    search_payload = json.loads(search_result.stdout)
    assert search_payload["semantic_runtime"]["active_vector_namespace"]["path"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    )
    assert search_payload["semantic_runtime"]["runtime_provider"]["namespacePath"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    )

    retrieve_result = invoke_cli(
        ["memory", "retrieve", "--branch", "main", "--stage", "mvp.plan", "--query", "Pinned revision decision", "--json-output"]
    )
    assert retrieve_result.exit_code == 0, retrieve_result.stdout
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert retrieve_payload["recall"]["semantic_runtime"]["active_vector_namespace"]["path"] == (
        ".madspec/system/memory/lancedb/local-hf-onnx/multilingual-e5-small/hf-pin-123/384"
    )
