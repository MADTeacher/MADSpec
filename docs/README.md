# Документация MADSpec

Эта директория описывает фактический `memory-first` процесс работы в MADSpec, а не только пользовательские команды. Источником истины для поведения команд здесь служат шаблоны в `templates/commands/`, состояние стадий и правила валидации в `src/madspec_cli/memory/stages/`, а также сборка производных артефактов в `src/madspec_cli/memory/projection/views.py`.

## Карта разделов

- [`mvp/`](mvp/README.md) — команды для разработки нового проекта: `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `mvp.implement`
- [`feature/`](feature/README.md) — команды для добавления новой функциональности: `feature.init`, `feature.plan`, `feature.implement`
- [`other/`](other/README.md) — команды качества и безопасности: `review`, `security`
- [`cli/`](cli/README.md) — справка по терминальному `madspec` CLI: `init`, `git`, `memory`, `check`, `migrate`, `version`

## Как читать эту документацию

- Документация по процессу работы описывает поведение сгенерированных агентских команд вроде `madspec.mvp.*`, `madspec.feature.*`, `madspec.review`, `madspec.security`
- Документация CLI описывает текущее устройство терминального интерфейса `madspec ...`, его команды, аргументы и сценарии использования
- Оба слоя опираются на одну и ту же структуру `.madspec/<BRANCH>/memory/`, но решают разные задачи

## Карта команд

| Команда | Раздел | Назначение |
| --- | --- | --- |
| `madspec.mvp.concept` | MVP | Фиксация product intent, аудитории, боли и приоритизированных функций |
| `madspec.mvp.design` | MVP | Описание UX/UI-структуры, экранов, пользовательских потоков и покрытия прототипами |
| `madspec.mvp.tech` | MVP | Выбор технологического стека и code organization |
| `madspec.mvp.architecture` | MVP | Формализация структуры проекта, модели данных и API-контрактов |
| `madspec.mvp.plan` | MVP | Построение каталога шагов и синхронизация плана с `progress.json` |
| `madspec.mvp.implement` | MVP | Выполнение шагов реализации через текущее состояние и TDD-checkpoints |
| `madspec.feature.init` | Feature | Анализ существующего проекта и рамок новой функциональности |
| `madspec.feature.plan` | Feature | Планирование feature-изменений и регистрация шагов |
| `madspec.feature.implement` | Feature | Реализация feature-шагов поверх существующего branch context |
| `madspec.review` | Other | Branch-aware review качества реализации и improvement backlog |
| `madspec.security` | Other | Pragmatic security/privacy audit по коду, зависимостям и артефактам |

## Общие принципы

- Основное состояние живет в `.madspec/<BRANCH>/memory/`
- Производные представления пересобираются из структурированной памяти и не являются основным источником данных
- Все сгенерированные команды `madspec.*` должны начинать с чтения и применения skill `madspec-cli-operator`
- `madspec memory retrieve` используется для чтения stage context
- `madspec memory capture` фиксирует подтвержденные факты, решения, контракты и состояние конкретной стадии
- `madspec memory checkpoint` ратифицирует stage-level состояние и инициирует consolidate + validate
- Команды реализации используют отдельные step-команды: `start-step`, `checkpoint-step`, `complete-step`

## Что не входит в покрытие

- `madspec.deploy` намеренно не включен: в репозитории нет шаблона команды в `templates/commands/`, поэтому этот процесс не документируется как актуальная команда
