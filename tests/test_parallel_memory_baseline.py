from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path

from madspec_cli.memory.shared.system_store.constants import SYSTEM_SESSION_KEY


def _load_manifest(repo_root: Path) -> dict[str, object]:
    manifest_path = repo_root / "dev" / "parallel-memory-contracts.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _invoke_help(invoke_cli, command: str):
    args = command.split()[1:] + ["--help"]
    return invoke_cli(args)


def test_parallel_memory_contract_manifest_matches_runtime_baseline(repo_root, invoke_cli) -> None:
    manifest = _load_manifest(repo_root)

    assert manifest["epic"] == "epic-7-proposal-based-commit-flow"
    assert manifest["roadmap_document"] == "dev/parallel-memory-roadmap.md"
    assert manifest["scope"] == "docs+contracts+behavior"
    assert manifest["behavior_change"] is True
    assert manifest["default_session_key"] == SYSTEM_SESSION_KEY == "active"

    all_commands = sorted(
        set(manifest["session_scoped_commands"]) | set(manifest["revision_aware_mutating_commands"])
    )
    revision_aware_commands = set(manifest["revision_aware_mutating_commands"])
    for command in all_commands:
        result = _invoke_help(invoke_cli, command)
        assert result.exit_code == 0, result.stdout
        assert "--session-key" in result.stdout
        if command in revision_aware_commands:
            assert "--expected-revision" in result.stdout
        else:
            assert "--expected-revision" not in result.stdout
    explain_help = _invoke_help(invoke_cli, "madspec memory explain")
    assert explain_help.exit_code == 0, explain_help.stdout
    assert "--session-key" in explain_help.stdout
    context_help = _invoke_help(invoke_cli, "madspec agents subagents context")
    assert context_help.exit_code == 0, context_help.stdout
    assert "--task-id" in context_help.stdout
    assert "--work-item-id" in context_help.stdout
    claim_help = _invoke_help(invoke_cli, "madspec memory work-items claim")
    assert claim_help.exit_code == 0, claim_help.stdout
    assert "--session-key" in claim_help.stdout
    release_help = _invoke_help(invoke_cli, "madspec memory work-items release")
    assert release_help.exit_code == 0, release_help.stdout
    assert "--session-key" in release_help.stdout
    proposal_publish_help = _invoke_help(invoke_cli, "madspec memory proposals publish")
    assert proposal_publish_help.exit_code == 0, proposal_publish_help.stdout
    assert "--base-revision" in proposal_publish_help.stdout
    proposal_apply_help = _invoke_help(invoke_cli, "madspec memory proposals apply")
    assert proposal_apply_help.exit_code == 0, proposal_apply_help.stdout


def test_parallel_memory_contract_manifest_imports_request_models(repo_root) -> None:
    manifest = _load_manifest(repo_root)

    for dotted_path in manifest["internal_extension_points"]["request_models"]:
        module_name, _, attr_name = dotted_path.rpartition(".")
        module = importlib.import_module(module_name)
        obj = getattr(module, attr_name)
        assert inspect.isclass(obj)
        assert hasattr(obj, "__dataclass_fields__")
        if attr_name in {"CaptureStageRequest", "CheckpointStageRequest", "RegisterStepRequest", "ImplementationStepRequest"}:
            assert "expected_revision" in obj.__dataclass_fields__

    for dotted_path in manifest["coordination_commands"]:
        assert dotted_path.startswith("madspec memory ")


def test_parallel_memory_roadmap_and_manifest_stay_in_sync(repo_root) -> None:
    manifest = _load_manifest(repo_root)
    roadmap = (repo_root / manifest["roadmap_document"]).read_text(encoding="utf-8")

    for heading in (
        "Embedded ADR — Epic 0 Lock",
        "Accepted decisions",
        "Rejected alternatives",
        "Architectural invariants",
        "Current subsystem to target responsibility",
        "Reserved public CLI contract",
        "Internal extension points",
        "Ownership scopes and lease scope patterns",
        "Phase 1 compatibility matrix",
        "Glossary",
        "Rollout order",
    ):
        assert heading in roadmap

    for command in manifest["session_scoped_commands"]:
        assert command in roadmap
    for command in manifest["revision_aware_mutating_commands"]:
        assert command in roadmap
    for command in manifest["coordination_commands"]:
        assert command in roadmap
    for scope_name in manifest["ownership_scopes"]:
        assert f"`{scope_name}`" in roadmap
    for lease_name in manifest["lease_scope_patterns"]:
        assert f"`{lease_name}`" in roadmap
    for payload_kind in manifest["reserved_payload_kinds"]:
        assert f"`{payload_kind}`" in roadmap
    for rollout_step in manifest["rollout_order"]:
        assert rollout_step in roadmap or rollout_step.replace("SQLite", "`SQLite`") in roadmap


def test_parallel_memory_docs_describe_current_runtime_truth(repo_root) -> None:
    memory_docs = (repo_root / "docs" / "cli" / "memory.md").read_text(encoding="utf-8")
    agents_docs = (repo_root / "docs" / "cli" / "agents.md").read_text(encoding="utf-8")
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    operator_skill = (repo_root / "skills" / "madspec-cli-operator" / "SKILL.md").read_text(encoding="utf-8")
    cutover = (repo_root / "dev" / "phase2-cutover-roadmap.md").read_text(encoding="utf-8")

    assert "все mutating runtime-команды теперь сначала коммитят изменения в `SQLite`" in memory_docs
    assert "branch `memory/*.json`, `memory/*.jsonl` и generated markdown остаются rebuildable projections" in memory_docs
    assert "`parallelRuntime.phase2Enabled`" in memory_docs
    assert "opt-in" in memory_docs
    assert "`--session-key`" in memory_docs
    assert "`--expected-revision`" in memory_docs
    assert "`runtime_revision`" in memory_docs
    assert "`scope_busy`" in memory_docs
    assert "writer lease" in memory_docs
    assert "session `active`" in memory_docs
    assert "реализация текущего шага и параллельное планирование следующего" in memory_docs
    assert "`madspec memory explain`" in memory_docs
    assert "`madspec memory tasks create`" in memory_docs
    assert "`madspec memory work-items claim`" in memory_docs
    assert "`madspec memory proposals publish`" in memory_docs
    assert "`runtime_proposals`" in memory_docs
    assert "`coordination`" in memory_docs
    assert "Базовый слой координации с `task` и `work-item` уже реализован" in agents_docs
    assert "`proposal_summary`" in agents_docs
    assert "`parallelRuntime.phase2Enabled`" in agents_docs
    assert "`--session-key`" in agents_docs
    assert "`--task-id`" in agents_docs
    assert "`--work-item-id`" in agents_docs
    assert "`scope_busy`" in agents_docs
    assert "`madspec memory explain --session-key`" in agents_docs
    assert "`parallelRuntime.phase2Enabled`" in readme
    assert "opt-in" in readme
    assert "`parallelRuntime.phase2Enabled`" in operator_skill
    assert "opt-in" in operator_skill
    assert "Phase 2 уже существует в кодовой базе, но пока работает только как opt-in режим." in cutover
    assert "phase2Enabled" in cutover
    assert "набор проверок для двух режимов" in cutover
    assert "stop/go" in cutover
