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

    assert manifest["epic"] == "epic-2-sqlite-first-canonical-writes"
    assert manifest["roadmap_document"] == "dev/parallel-memory-roadmap.md"
    assert manifest["scope"] == "docs+contracts+behavior"
    assert manifest["behavior_change"] is True
    assert manifest["default_session_key"] == SYSTEM_SESSION_KEY == "active"

    all_commands = sorted(
        set(manifest["session_scoped_commands"]) | set(manifest["revision_aware_mutating_commands"])
    )
    for command in all_commands:
        result = _invoke_help(invoke_cli, command)
        assert result.exit_code == 0, result.stdout
        assert "--session-key" in result.stdout
        assert "--expected-revision" not in result.stdout


def test_parallel_memory_contract_manifest_imports_request_models(repo_root) -> None:
    manifest = _load_manifest(repo_root)

    for dotted_path in manifest["internal_extension_points"]["request_models"]:
        module_name, _, attr_name = dotted_path.rpartition(".")
        module = importlib.import_module(module_name)
        obj = getattr(module, attr_name)
        assert inspect.isclass(obj)
        assert hasattr(obj, "__dataclass_fields__")


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

    assert "все mutating runtime-команды теперь сначала коммитят изменения в `SQLite`" in memory_docs
    assert "branch `memory/*.json`, `memory/*.jsonl` и generated markdown остаются rebuildable projections" in memory_docs
    assert "`--session-key`" in memory_docs
    assert "session `active`" in memory_docs
    assert "не является встроенным координатором выполнения" in agents_docs
    assert "Оркестрация с `task`, `work-item` и `proposal`" in agents_docs
    assert "`--session-key`" in agents_docs
