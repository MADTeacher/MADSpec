# AGENTS.md

Назначение: пакет `features/policy` управляет состоянием политик проекта, proposal/history lifecycle и policy context для других подсистем.

Стабильные точки входа:
- `cli.py` — пользовательские команды `madspec policy ...`.
- `application/` — use case-модули для init/show/propose/apply/export/validate.
- `infrastructure/service.py`, `queries.py`, `paths.py` — основные owning modules для orchestration, context и layout.

Переходные правила:
- `infrastructure/storage.py` — только узкий compatibility facade; не добавляй туда новые helper-реэкспорты.
- Внутренний код feature должен брать state/proposal I/O из `repository.py`, markdown из `rendering.py`, sync из `sync.py`.
- Memory и другие feature-пакеты могут использовать только утверждённые entry points, например `ensure_policy_layout` и `build_policy_context`.

Локальные документы:
- `docs/cli/policy.md`
- `dev/madspec-cli-agentic-refactor-rfc.md`
