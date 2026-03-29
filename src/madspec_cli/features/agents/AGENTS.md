# AGENTS.md

Назначение: пакет `features/agents` управляет профилями субагентов, каталогом ролей и рендерингом файлов среды.

Стабильные точки входа:
- `cli.py` — пользовательские команды `madspec agents ...`.
- `application/` — use case-модули для profile/proposal/subagent lifecycle.
- `infrastructure/state_store.py`, `catalog_store.py`, `render_workspace.py` — owning infra modules.
- `infrastructure/frontmatter_profile_compat.py` и `role_catalog_compat.py` — совместимые адаптеры фронтматтера и каталога.

Переходные правила:
- `infrastructure/storage.py` — только совместимый барьер для внешних вызовов и тестов; не добавляй туда новые внутренние импорты.
- Внутренний код feature должен импортировать напрямую из owning modules, а не из `infrastructure/storage.py`.
- Domain normalizers и builtin role metadata живут в `domain/`; не реэкспортируй их через фасады.

Локальные документы:
- `docs/cli/agents.md`
- `dev/madspec-cli-agentic-refactor-rfc.md`
