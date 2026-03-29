# AGENTS.md

Назначение: `system_store` — канонический SQLite/vector слой для runtime, индексации, proposals и retrieval.

Стабильные точки входа:
- `store.py` — совместимый фасад `MemoryStore`.
- `db.py` — schema/bootstrap/connect layer.
- `runtime_store.py`, `task_store.py`, `proposal_store.py`, `index_store.py` — owning bounded contexts.
- `sync.py` — sync/reindex/db-status orchestration.
- `canonical_state.py` и `retrieval.py` — canonical projections и retrieval orchestration.

Переходные правила:
- `__init__.py` — только узкий package surface; не расширяй его новыми helper-реэкспортами.
- Session/layout/vector/model helper-ы импортируй из конкретных модулей: `sessions.py`, `layout.py`, `vector.py`, `model_bootstrap.py`.
- Новый код должен предпочитать owning store module, а не добавлять методы обратно в фасад.

Локальные документы:
- `docs/cli/memory.md`
- `dev/madspec-cli-agentic-refactor-rfc.md`
