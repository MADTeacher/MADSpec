# Feature Workflow

Раздел описывает workflow разработки новой функциональности в уже существующем проекте. Здесь framework не переизобретает продукт с нуля, а строит planning и implementation вокруг анализа текущего codebase.

Все feature-команды должны начинать с чтения и применения skill `madspec-cli-operator`.

## Рекомендуемый порядок

1. [`feature.init`](madspec.feature.init.md)
2. [`feature.plan`](madspec.feature.plan.md)
3. [`feature.implement`](madspec.feature.implement.md)

## Общие stage-state и артефакты

- `feature.init` — `.madspec/<BRANCH>/memory/stages/feature.init.json`, производные `project-analysis.md`, `feature-context.md`, `tech-stack.md`, `architecture.md`
- `feature.plan` — `.madspec/<BRANCH>/memory/stages/feature.plan.json` + `progress.json`, generated `implementation-plan.md`, `planning-context-cache.md`
- `feature.implement` — runtime-state в `progress.json` и `working/active-session.json`, generated step contexts и branch context

## Ленивая материализация

- Feature workflow больше не материализует весь набор артефактов ветки заранее.
- `feature.init` создает только свое каноническое состояние, минимальный runtime-набор ветки и связанные производные представления.
- Артефакты `feature.plan`, review/security и несвязанных MVP-стадий появляются только при первом входе в соответствующую стадию или через команды полной пересборки `madspec memory init`, `madspec memory consolidate`, `madspec memory validate`.

## Особенности режима

- feature IDs и integration file mappings становятся основой для planning coverage
- `project-analysis.md` и `feature-context.md` — generated references поверх `feature.init.json`
- implementation работает теми же step-командами, что и MVP, но с feature-specific branch intent
