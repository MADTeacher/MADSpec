from __future__ import annotations

import json

import pytest

from madspec_cli.features.init.infrastructure import initializer_core
from madspec_cli.features.init.cli import (
    _choose_memory_embeddings_interactively,
    _resolve_memory_selection_from_flags,
)
from madspec_cli.memory import get_memory_paths
from madspec_cli.shared.infra.project_config import read_madspec_config, update_madspec_config


def _fake_bootstrap(project_path, embeddings_config, *, allow_download):
    assert allow_download is True
    cache_root = project_path / embeddings_config["cacheDir"] / embeddings_config["model"] / "current"
    cache_root.mkdir(parents=True, exist_ok=True)
    local_path = cache_root / "snapshot"
    local_path.mkdir(parents=True, exist_ok=True)
    (cache_root / "manifest.json").write_text(
        json.dumps(
            {
                "providerKind": "local-hf-onnx",
                "modelKey": embeddings_config["model"],
                "requestedRevision": embeddings_config.get("revision"),
                "resolvedRevision": "current",
                "hfRepoId": "intfloat/multilingual-e5-small"
                if embeddings_config["model"] == "multilingual-e5-small"
                else "BAAI/bge-m3",
                "dimension": 384 if embeddings_config["model"] == "multilingual-e5-small" else 1024,
                "downloadedAt": "2026-03-27T12:00:00+00:00",
                "status": "ready",
                "localPath": str(local_path.relative_to(project_path)),
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_init_creates_structured_memory_layout(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(["init", "demo", "--ai", "cursor-agent", "--no-git"])

    assert result.exit_code == 0, result.stdout
    project_path = tmp_path / "demo"
    paths = get_memory_paths(project_path, "main")
    assert paths["progress"].exists()
    assert paths["active_session"].exists()
    assert paths["design_state"].exists()
    assert paths["tech_state"].exists()
    assert paths["architecture_state"].exists()
    assert paths["plan_state"].exists()
    assert (project_path / ".madspec" / "procedures" / "next-step-selection.md").exists()
    assert (project_path / ".madspec" / "main" / "project-context.md").exists()
    assert (project_path / ".madspec" / "main" / "implementation-plan.md").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "memory.sqlite").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "schema-version.json").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "lancedb").exists()
    assert (project_path / ".madspec" / "system" / "memory" / "lancedb" / "hash" / "default" / "current" / "64").exists()
    schema_payload = json.loads(
        (project_path / ".madspec" / "system" / "memory" / "schema-version.json").read_text(encoding="utf-8")
    )
    assert schema_payload["vectorRootDir"] == ".madspec/system/memory/lancedb"
    assert schema_payload["vectorIndexDir"] == ".madspec/system/memory/lancedb/hash/default/current/64"
    assert schema_payload["activeVectorNamespace"]["provider"] == "hash"
    assert schema_payload["activeVectorNamespace"]["model"] == "default"
    config = json.loads((project_path / ".madspec" / "config.json").read_text(encoding="utf-8"))
    assert config["agentEnvironment"] == "cursor-agent"
    assert config["agentsSchemaVersion"] == 1
    assert config["parallelRuntime"] == {
        "phase1Enabled": True,
        "phase2Enabled": True,
    }
    assert config["memory"]["embeddings"] == {
        "provider": "hash",
        "model": None,
        "downloadPolicy": "none",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }
    assert paths["deploy_state"].exists()
    assert (project_path / ".madspec" / "main" / "deployment.md").exists()
    assert (project_path / ".madspec" / "system" / "agents" / "state.json").exists()
    assert "/madspec.gate" in result.stdout
    assert "/madspec.deploy" in result.stdout


def test_init_accepts_qwen_agent(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(["init", "demo", "--ai", "qwen", "--no-git", "--ignore-agent-tools"])

    assert result.exit_code == 0, result.stdout
    assert "Selected AI assistant:" in result.stdout
    assert "qwen" in result.stdout


def test_init_rejects_unknown_agent_and_lists_qwen(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    result = invoke_cli(["init", "demo", "--ai", "unknown-agent", "--no-git"])

    assert result.exit_code == 1
    assert "Invalid AI assistant 'unknown-agent'" in result.stdout
    assert "qwen" in result.stdout


def test_init_here_cancel_keeps_existing_directory(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# existing\n", encoding="utf-8")

    result = invoke_cli(["init", "--here", "--ai", "cursor-agent", "--no-git"], input="n\n")

    assert result.exit_code == 0, result.stdout
    assert "Operation cancelled" in result.stdout
    assert not (tmp_path / ".madspec").exists()


def test_init_warns_when_git_is_missing(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)
    monkeypatch.setattr("madspec_cli.features.init.application.preflight.check_tool", lambda tool: False)

    result = invoke_cli(["init", "demo", "--ai", "cursor-agent", "--ignore-agent-tools"])

    assert result.exit_code == 0, result.stdout
    assert "Git not found - will skip repository initialization" in result.stdout


def test_init_fails_when_required_agent_cli_is_missing(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_check_tool(tool: str) -> bool:
        return tool == "git"

    monkeypatch.setattr("madspec_cli.features.init.application.preflight.check_tool", fake_check_tool)

    result = invoke_cli(["init", "demo", "--ai", "qwen", "--no-git"])

    assert result.exit_code == 1, result.stdout
    assert "Agent Detection Error" in result.stdout
    assert "qwen" in result.stdout


def test_read_madspec_config_normalizes_legacy_memory_embeddings(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps({"currentBranch": "main", "version": "1.0.0"}) + "\n",
        encoding="utf-8",
    )

    config = read_madspec_config(project_path)

    assert config["memory"]["embeddings"]["provider"] == "hash"
    assert config["memory"]["embeddings"]["model"] is None
    assert config["memory"]["embeddings"]["downloadPolicy"] == "none"


def test_read_madspec_config_normalizes_hash_model_to_null(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {
                    "embeddings": {
                        "provider": "hash",
                        "model": "multilingual-e5-small",
                        "downloadPolicy": "none",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    config = read_madspec_config(project_path)

    assert config["memory"]["embeddings"]["provider"] == "hash"
    assert config["memory"]["embeddings"]["model"] is None


def test_read_madspec_config_normalizes_hash_revision_to_null(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {
                    "embeddings": {
                        "provider": "hash",
                        "model": None,
                        "downloadPolicy": "none",
                        "revision": "should-be-ignored",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    config = read_madspec_config(project_path)

    assert config["memory"]["embeddings"]["provider"] == "hash"
    assert config["memory"]["embeddings"]["revision"] is None


def test_read_madspec_config_rejects_dense_provider_without_model(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {"embeddings": {"provider": "local-hf-onnx"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="requires a non-empty model"):
        read_madspec_config(project_path)


def test_read_madspec_config_rejects_unknown_provider_and_policy(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {"embeddings": {"provider": "mystery-provider"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown memory.embeddings provider"):
        read_madspec_config(project_path)

    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {
                    "embeddings": {
                        "provider": "local-hf-onnx",
                        "model": "multilingual-e5-small",
                        "downloadPolicy": "later",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Unknown memory.embeddings downloadPolicy"):
        read_madspec_config(project_path)


def test_update_madspec_config_preserves_existing_memory_embeddings(tmp_path) -> None:
    project_path = tmp_path / "project"
    project_path.mkdir()
    madspec_dir = project_path / ".madspec"
    madspec_dir.mkdir()
    (madspec_dir / "config.json").write_text(
        json.dumps(
            {
                "currentBranch": "main",
                "version": "1.0.0",
                "memory": {
                    "embeddings": {
                        "provider": "local-hf-onnx",
                        "model": "multilingual-e5-small",
                        "downloadPolicy": "on-first-use",
                        "cacheDir": ".madspec/system/models",
                        "revision": None,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    updated = update_madspec_config(project_path, agentEnvironment="cursor-agent")

    assert updated["agentEnvironment"] == "cursor-agent"
    assert updated["memory"]["embeddings"] == {
        "provider": "local-hf-onnx",
        "model": "multilingual-e5-small",
        "downloadPolicy": "on-first-use",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }


def test_init_accepts_dense_memory_selection_from_flags(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)
    monkeypatch.setattr(initializer_core, "ensure_model_available", _fake_bootstrap)

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-provider",
            "local-hf-onnx",
            "--memory-model",
            "multilingual-e5-small",
        ]
    )

    assert result.exit_code == 0, result.stdout
    config = json.loads((tmp_path / "demo" / ".madspec" / "config.json").read_text(encoding="utf-8"))
    assert config["memory"]["embeddings"] == {
        "provider": "local-hf-onnx",
        "model": "multilingual-e5-small",
        "downloadPolicy": "on-init",
        "cacheDir": ".madspec/system/models",
        "revision": None,
    }
    assert "Memory Embeddings" in result.stdout
    assert "Bootstrap status:" in result.stdout
    assert "ready" in result.stdout


def test_init_accepts_dense_memory_download_policy_override(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-provider",
            "local-hf-onnx",
            "--memory-model",
            "bge-m3",
            "--memory-download-policy",
            "on-first-use",
        ]
    )

    assert result.exit_code == 0, result.stdout
    config = json.loads((tmp_path / "demo" / ".madspec" / "config.json").read_text(encoding="utf-8"))
    assert config["memory"]["embeddings"]["downloadPolicy"] == "on-first-use"
    assert config["memory"]["embeddings"]["model"] == "bge-m3"
    assert "deferred" in result.stdout


def test_init_fails_when_dense_bootstrap_fails(tmp_path, monkeypatch, invoke_cli, fake_template_download) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(initializer_core, "download_and_extract_template", fake_template_download)

    def fail_bootstrap(project_path, embeddings_config, *, allow_download):
        del project_path, embeddings_config, allow_download
        raise RuntimeError("download failed")

    monkeypatch.setattr(initializer_core, "ensure_model_available", fail_bootstrap)

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-provider",
            "local-hf-onnx",
            "--memory-model",
            "multilingual-e5-small",
        ]
    )

    assert result.exit_code == 1
    assert "download failed" in result.stdout


def test_init_rejects_invalid_memory_flag_combinations_before_template_download(tmp_path, monkeypatch, invoke_cli) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_download(*args, **kwargs):
        raise AssertionError("template download should not be called for invalid memory flags")

    monkeypatch.setattr(initializer_core, "download_and_extract_template", fail_download)

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-model",
            "multilingual-e5-small",
        ]
    )
    assert result.exit_code == 1
    assert "--memory-provider" in result.stdout

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-provider",
            "hash",
            "--memory-download-policy",
            "on-init",
        ]
    )
    assert result.exit_code == 1
    assert "--memory-download-policy" in result.stdout

    result = invoke_cli(
        [
            "init",
            "demo",
            "--ai",
            "cursor-agent",
            "--no-git",
            "--memory-provider",
            "local-hf-onnx",
            "--memory-model",
            "unknown-model",
        ]
    )
    assert result.exit_code == 1
    assert "Unknown --memory-model" in result.stdout


def test_memory_selection_helpers_cover_hash_and_dense_paths() -> None:
    responses = iter(["hash"])
    hash_selection = _choose_memory_embeddings_interactively(
        select_fn=lambda options, prompt, default: next(responses)
    )
    assert hash_selection.provider == "hash"
    assert hash_selection.model is None
    assert hash_selection.download_policy == "none"

    responses = iter(["multilingual-e5-small", "on-init"])
    dense_selection = _choose_memory_embeddings_interactively(
        select_fn=lambda options, prompt, default: next(responses)
    )
    assert dense_selection.provider == "local-hf-onnx"
    assert dense_selection.model == "multilingual-e5-small"
    assert dense_selection.download_policy == "on-init"

    responses = iter(["bge-m3", "on-first-use"])
    advanced_selection = _choose_memory_embeddings_interactively(
        select_fn=lambda options, prompt, default: next(responses)
    )
    assert advanced_selection.model == "bge-m3"
    assert advanced_selection.download_policy == "on-first-use"


def test_memory_selection_flag_helper_validates_supported_values() -> None:
    selection = _resolve_memory_selection_from_flags(
        provider="local-hf-onnx",
        model="multilingual-e5-small",
        download_policy=None,
    )
    assert selection.model == "multilingual-e5-small"
    assert selection.download_policy == "on-init"
