from __future__ import annotations

import importlib
import inspect
from pathlib import Path

def test_parallel_memory_docs_describe_current_runtime_truth(repo_root) -> None:
    memory_docs = (repo_root / "docs" / "cli" / "memory.md").read_text(encoding="utf-8")
    agents_docs = (repo_root / "docs" / "cli" / "agents.md").read_text(encoding="utf-8")
    operator_skill = (repo_root / "skills" / "madspec-cli-operator" / "SKILL.md").read_text(encoding="utf-8")
    cutover = (repo_root / "dev" / "phase2-cutover-roadmap.md").read_text(encoding="utf-8")

    assert "все mutating runtime-команды теперь сначала коммитят изменения в `SQLite`" in memory_docs
    assert "branch `memory/*.json`, `memory/*.jsonl` и generated markdown остаются rebuildable projections" in memory_docs
    assert "`parallelRuntime.phase2Enabled`" in memory_docs
    assert "включен по умолчанию" in memory_docs
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
    assert "`parallelRuntime.phase2Enabled`" in operator_skill
    assert "включен по умолчанию" in operator_skill
    assert "архив" in cutover.lower()
    assert "выполн" in cutover.lower()
