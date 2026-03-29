# AGENTS.md

Назначение: пакет `features/change` управляет canonical change bundle для ветки, baseline/diff и экспортом change artifacts.

Стабильные точки входа:
- `cli.py` — пользовательские команды `madspec change ...`.
- `application/` — use case-модули для init/propose/diff/preview/apply/export/verify/summary.
- `infrastructure/service.py`, `repository.py`, `snapshot.py`, `rendering.py`, `export.py`, `git_ops.py` — owning modules по ответственности.

Переходные правила:
- `infrastructure/storage.py` — только узкий compatibility facade для внешних вызовов; не возвращай туда git/render/export helper-ы.
- Внутренний код feature должен импортировать напрямую из owning modules.
- Для внешних memory call site допустимы только согласованные entry points вроде `build_change_context`, `build_snapshot_diff`, `ensure_change_layout`, `resolve_default_base_branch`.

Локальные документы:
- `docs/cli/change.md`
- `dev/madspec-cli-agentic-refactor-rfc.md`
