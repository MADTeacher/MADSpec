# Процесс Feature

Раздел описывает процесс разработки новой функциональности в уже существующем проекте. Здесь фреймворк не переизобретает продукт с нуля, а выстраивает планирование и реализацию вокруг анализа текущей кодовой базы.

Все feature-команды должны начинать с чтения и применения навыка `madspec-cli-operator`.

## Рекомендуемый порядок

1. [`feature.init`](madspec.feature.init.md)
2. [`feature.plan`](madspec.feature.plan.md)
3. [`feature.implement`](madspec.feature.implement.md)

## Общие состояния стадий и артефакты

- `feature.init` — `.madspec/<BRANCH>/memory/stages/feature.init.json`, производные `project-analysis.md`, `feature-context.md`, `tech-stack.md`, `architecture.md`
- `feature.plan` — `.madspec/<BRANCH>/memory/stages/feature.plan.json` + `progress.json`, производные `implementation-plan.md`, `planning-context-cache.md`
- `feature.implement` — текущее состояние выполнения в `progress.json` и `working/active-session.json`, производные пошаговые контексты и контекст ветки

## Ленивая материализация

- Процесс feature больше не материализует весь набор артефактов ветки заранее.
- `feature.init` создает только свое каноническое состояние, минимальный runtime-набор ветки и связанные производные представления.
- Артефакты `feature.plan`, review/security и несвязанных MVP-стадий появляются только при первом входе в соответствующую стадию или через команды полной пересборки `madspec memory init`, `madspec memory consolidate`, `madspec memory validate`.

## Особенности режима

- идентификаторы feature и привязки файлов интеграции становятся основой для покрытия плана
- `project-analysis.md` и `feature-context.md` — производные справочные представления поверх `feature.init.json`
- реализация работает теми же пошаговыми командами, что и MVP, но с намерением ветки, специфичным для feature
