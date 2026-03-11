# Документация MADSpec Workflow

Эта директория описывает фактический `memory-first` workflow MADSpec, а не только пользовательские prompt-команды. Источник истины для поведения команд здесь: шаблоны в `templates/commands/`, stage-state и validation rules в `src/madspec_cli/memory/stages/`, а также сборка generated artifacts в `src/madspec_cli/memory/projection/views.py`.

## Карта разделов

- [`mvp/`](mvp/README.md) — команды для разработки нового проекта: `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `mvp.implement`
- [`feature/`](feature/README.md) — команды для добавления новой функциональности: `feature.init`, `feature.plan`, `feature.implement`
- [`other/`](other/README.md) — branch-aware quality workflows: `review`, `security`

## Карта команд

| Команда | Раздел | Назначение |
| --- | --- | --- |
| `madspec.mvp.concept` | MVP | Фиксация product intent, аудитории, боли и приоритизированных функций |
| `madspec.mvp.design` | MVP | Описание UX/UI структуры, экранов, потоков и prototype coverage |
| `madspec.mvp.tech` | MVP | Выбор технологического стека и code organization |
| `madspec.mvp.architecture` | MVP | Формализация структуры проекта, модели данных и API-контрактов |
| `madspec.mvp.plan` | MVP | Построение step catalog и синхронизация плана с `progress.json` |
| `madspec.mvp.implement` | MVP | Выполнение шагов реализации через runtime-state и TDD checkpoints |
| `madspec.feature.init` | Feature | Анализ существующего проекта и рамок новой функциональности |
| `madspec.feature.plan` | Feature | Планирование feature-изменений и регистрация шагов |
| `madspec.feature.implement` | Feature | Реализация feature-шагов поверх существующего branch context |
| `madspec.review` | Other | Branch-aware review качества реализации и improvement backlog |
| `madspec.security` | Other | Pragmatic security/privacy audit по коду, зависимостям и артефактам |

## Общие принципы

- canonical state живет в `.madspec/<BRANCH>/memory/`
- generated views пересобираются из structured memory и не являются primary source
- `madspec memory retrieve` используется для чтения stage context
- `madspec memory capture` фиксирует подтвержденные facts/decisions/contracts и stage-specific state
- `madspec memory checkpoint` ратифицирует stage-level состояние и инициирует consolidate + validate
- implementation workflows используют отдельные step-команды: `start-step`, `checkpoint-step`, `complete-step`

## Что не входит в покрытие

- `madspec.deploy` намеренно не включен: в репозитории нет шаблона команды в `templates/commands/`, поэтому этот workflow не документируется как актуальная команда

