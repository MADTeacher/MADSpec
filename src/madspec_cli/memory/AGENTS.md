# AGENTS.md

Назначение: пакет `memory` хранит сценарные точки входа для capture/checkpoint/workflow и общий каркас branch memory.

Сначала прочитай корневой `AGENTS.md`, затем работай от owning module, а не от широких фасадов.

Стабильные точки входа:
- `memory/__init__.py` — только совместимый сценарный API для внешних вызовов и тестов.
- `views.py` — `consolidate_branch_memory`, `retrieve_memory_context`.
- `workflow/planning.py` и `workflow/implementation.py` — правила и операции workflow.
- `shared/storage.py` и `shared/validation.py` — layout, JSON I/O и проверка branch memory.
- `application/` — orchestration, branch state, diagnostics, projections.

Переходные правила:
- Не добавляй новые внутренние импорты через `memory/__init__.py`.
- Helper-ы вроде `make_record`, `write_json`, `append_jsonl` импортируются только из owning modules в `memory/shared/`.
- Для semantic-пайплайна входи через `semantic/` payload/builder modules, а не через старые совместимые фасады.

Локальные документы:
- `docs/cli/memory.md`
- `dev/madspec-cli-agentic-refactor-rfc.md`
