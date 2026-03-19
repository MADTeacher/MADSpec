# MADSpec

MADSpec - это фреймворк для разработки программного обеспечения с помощью LLM-агентов. Он дает команде понятную структуру проекта, процесс работы с учетом веток и слой структурированной памяти, чтобы контекст и принятые решения не терялись между сессиями.

## Кому Подходит

- Командам, которые хотят работать с AI-агентами более предсказуемо
- Проектам, где важно сохранять прозрачность архитектурных решений и прогресса реализации
- Пользователям Cursor, GitHub Copilot, opencode, Roo Code, Kilo Code, SourceCraft и Qwen Code, которым нужен единый процесс работы

## Что Дает MADSpec

- MVP-процесс для разработки продукта с нуля: от концепции до реализации
- Feature-процесс для добавления функциональности в существующий код
- Отдельные артефакты по веткам в `.madspec/<branch>/` вместо одного общего состояния проекта
- Проектное хранилище памяти в `.madspec/system/memory/`, артефакты памяти ветки в `.madspec/<branch>/memory/` и автоматически собираемые Markdown-файлы поверх них
- Слой объяснения и диагностики для структурированной памяти: `doctor`, `explain`, `timeline`, `why-next-step`, `conflicts`, `inspect-record`
- Контролируемое сравнение и слияние памяти между ветками с циклом `compare/propose/preview/apply` и продвижением подтвержденных знаний на уровень проекта
- Единый слой правил проекта в `.madspec/system/policy/` с циклом предложения и применения и автоматически собираемым `policy.md`
- Слой управления изменениями в `.madspec/<branch>/change/` с фиксированной базовой точкой сравнения, предложениями, ратифицированным пакетом изменений и переносимым пакетом экспорта
- Слой контрольных проверок в `.madspec/<branch>/gates/` с единым статусом переходов, предложениями на исключения и журналом аудита
- Слой субагентных профилей в `.madspec/system/agents/` с каноническим состоянием ролей, рекомендациями, историей изменений и role-scoped context
- Процессы `review` и `security` для проверки качества после реализации
- Подготовленную структуру команд и файлов для поддерживаемых сред с AI-агентами

## Установка

### Требования

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Git
- Один из поддерживаемых AI-агентов

### Постоянная Установка

```bash
uv tool install madspec-cli --from git+https://github.com/MADTeacher/MADSpec.git
```

Базовое использование:

```bash
madspec init <PROJECT_NAME> --ai cursor-agent
madspec init .
madspec check
```

Если использовать `madspec init .` без `--ai`, MADSpec инициализирует проект в текущей директории и предложит вручную выбрать AI-среду во время запуска.

Обновление:

```bash
uv tool install madspec-cli --force --from git+https://github.com/MADTeacher/MADSpec.git
```

### Одноразовый Запуск

```bash
uvx --from git+https://github.com/MADTeacher/MADSpec.git madspec init <PROJECT_NAME>
```

## Поддерживаемые AI-Агенты

| Агент | Тип | Директория | Нужен CLI | Субагенты |
| --- | --- | --- | --- | --- |
| [Cursor](https://cursor.sh/) | IDE | `.cursor/commands/` | Нет | Да, native (`.cursor/agents/`) |
| [opencode](https://opencode.ai/) | CLI | `.opencode/commands/` | Да | Да, native (`.opencode/agents/`) |
| [Kilo Code](https://github.com/Kilo-Org/kilocode) | IDE | `.kilocode/rules/` | Нет | Fallback через rules/skills |
| [Roo Code](https://roocode.com/) | IDE | `.roo/rules/` | Нет | Fallback через rules/skills |
| [SourceCraft](https://sourcecraft.dev/) | IDE | `.codeassistant/commands/` | Нет | Fallback через commands/skills |
| [Qwen Code](https://github.com/QwenLM/qwen-code) | CLI | `.qwen/commands/` | Да | Да, native (`.qwen/agents/`) |
| [GitHub Copilot](https://github.com/features/copilot) | IDE | `.github/agents/` | Нет | Да, native (`.github/agents/`) |

## Как Работать С MADSpec

Все сгенерированные команды со слешем `madspec.*` должны начинаться с чтения и применения навыка `madspec-cli-operator`. Для `madspec.mvp.design` дополнительно обязателен навык `frontend-design`.

### MVP-Процесс

Используйте команды `madspec.mvp.*`, когда создаете продукт с нуля:

Базовый порядок стадий:

1. Если хотите сразу создать новый проект вместе с MADSpec, используйте `madspec init <PROJECT_NAME> --ai <agent>`.
2. Если директория проекта уже существует, используйте `madspec init .`; при необходимости AI-среду можно передать через `--ai <agent>` или выбрать вручную во время запуска.
3. `/madspec.mvp.concept` - зафиксировать идею проекта, целевую аудиторию, сценарии и ключевые функции.
4. `/madspec.mvp.design` - описать пользовательский опыт, экраны и прототипы интерфейса; на этой стадии агент обязан использовать оба навыка: `madspec-cli-operator` как базовый навык процесса и CLI, а `frontend-design` - для визуального проектирования интерфейса.
5. `/madspec.mvp.tech` - выбрать стек технологий и зафиксировать технические решения.
6. `/madspec.mvp.architecture` - формализовать структуру проекта, модель данных и контракты.

После этого можно работать по одному из двух сценариев.

Для легкой задачи или маленькой MVP-итерации агент должен предпочитать один полный planning-step, а не дробить работу на искусственные микро-шаги. Отдельные шаги нужны только там, где есть реальные зависимости, разные риски, самостоятельные точки проверки или явная просьба пользователя идти подробнее.

#### Вариант 1: сначала полностью допланировать, потом реализовывать

1. Повторять `/madspec.mvp.plan`, пока план не будет готов полностью.
2. Запустить `/madspec.mvp.implement` для текущего запланированного шага.
3. После каждого прохода `implement` разработчик вручную запускает софт и проверяет результат.
4. Если текущий шаг реализован некорректно, разработчик возвращается к агенту и просит исправить именно этот шаг.
5. Если текущий шаг реализован корректно, разработчик смотрит, завершены ли все уже запланированные шаги.
6. Если не завершены, снова запускается `/madspec.mvp.implement` для следующего шага.
7. Когда все запланированные шаги завершены, можно переходить к `/madspec.review` и `/madspec.security`.

#### Вариант 2: идти итерациями plan -> implement

1. Запланировать следующий шаг через `/madspec.mvp.plan`.
2. Сразу реализовать этот шаг через `/madspec.mvp.implement`.
3. После `implement` разработчик вручную запускает софт и проверяет результат.
4. Если текущий шаг реализован некорректно, разработчик возвращается к агенту и добивается исправления текущего шага.
5. Если текущий шаг реализован корректно, разработчик решает, завершена ли разработка.
6. Если разработка не завершена, процесс снова идет на `/madspec.mvp.plan` для следующего шага.
7. Если разработка завершена, можно переходить к `/madspec.review` и `/madspec.security`.

```bash
# если хотите сразу создать новый проект
madspec init <PROJECT_NAME> --ai <agent>

# если проект уже существует в текущей директории
madspec init .
/madspec.mvp.concept "Идея проекта"
/madspec.mvp.design
/madspec.mvp.tech
/madspec.mvp.architecture
/madspec.mvp.plan
/madspec.mvp.implement
```

Подробности по каждой стадии есть в [документации MVP-процесса](docs/mvp/README.md).

### Feature-Процесс

Используйте команды `madspec.feature.*`, когда добавляете функциональность в существующий проект:

Базовый порядок:

1. Если проект еще не был инициализирован через MADSpec, сначала выполнить `madspec init . --ai <agent>` в корне существующего проекта.
2. Работать в существующем проекте и нужной ветке.
3. Запустить `/madspec.feature.init`, чтобы зафиксировать контекст новой функции.

После `feature.init` тоже возможны два сценария работы.

Для небольшой feature агент должен предпочитать один полный planning-step, если изменение можно реализовать и проверить как единое целое. Не нужно разносить код, тесты, документацию и валидацию по отдельным шагам без реальной зависимости между ними.

#### Вариант 1: сначала полностью допланировать feature, потом реализовывать

1. Повторять `/madspec.feature.plan`, пока feature-план не будет готов полностью.
2. Запустить `/madspec.feature.implement` для текущего запланированного шага.
3. После каждого прохода `implement` разработчик вручную запускает софт и проверяет результат.
4. Если текущий шаг реализован некорректно, разработчик возвращается к агенту и просит исправить именно этот шаг.
5. Если текущий шаг реализован корректно, разработчик смотрит, завершены ли все уже запланированные шаги.
6. Если не завершены, снова запускается `/madspec.feature.implement` для следующего шага.
7. Когда все запланированные шаги завершены, можно переходить к `/madspec.review` и `/madspec.security`.

#### Вариант 2: идти итерациями plan -> implement

1. Запланировать следующий шаг через `/madspec.feature.plan`.
2. Сразу реализовать этот шаг через `/madspec.feature.implement`.
3. После `implement` разработчик вручную запускает софт и проверяет результат.
4. Если текущий шаг реализован некорректно, разработчик возвращается к агенту и добивается исправления текущего шага.
5. Если текущий шаг реализован корректно, разработчик решает, завершена ли работа над feature.
6. Если feature еще не завершена, процесс снова идет на `/madspec.feature.plan` для следующего шага.
7. Если feature завершена, можно переходить к `/madspec.review` и `/madspec.security`.


```bash
# если проект еще не инициализирован через MADSpec
madspec init . --ai <agent>

/madspec.feature.init "Описание новой функции"
/madspec.feature.plan
/madspec.feature.implement
```

Подробности по этому сценарию есть в [документации Feature-процесса](docs/feature/README.md).

### Роль Разработчика

MADSpec не предполагает слепого выполнения всего процесса агентом без участия человека.

- После каждого прохода `implement` разработчик должен запустить софт и посмотреть, работает ли он так, как ожидалось
- Если результат не устраивает, разработчик возвращается к агенту с корректировками и направляет его дальше
- Если результат устраивает, разработчик либо переходит к следующему шагу, либо завершает работу через `review` и `security`
- Чем меньше доверия к агенту в конкретной задаче, тем важнее ручная проверка и коррекция после реализации

### Общие Команды

Эти команды можно запускать после заметных изменений в любом режиме:

```bash
/madspec.memory
/madspec.merge
/madspec.policy
/madspec.change
/madspec.gate
/madspec.agents
/madspec.review
/madspec.security
```

## Структурированная Память

MADSpec хранит основное проектное состояние в `.madspec/system/memory/`, `.madspec/system/policy/` и `.madspec/system/agents/`, а артефакты процесса, привязанные к ветке, — в `.madspec/<branch>/memory/`, `.madspec/<branch>/change/` и `.madspec/<branch>/gates/`. Файлы вроде `concept.md`, `tech-stack.md`, `architecture.md`, `implementation-plan.md`, `change-summary.md`, `.madspec/system/policy.md` и `.madspec/system/agents.md` собираются автоматически и не являются основным источником истины. Производные артефакты ветки теперь материализуются по стадиям: feature- и MVP-стадии создают только релевантный минимум, а полный набор пересобирается через `madspec memory init`, `madspec memory consolidate` и `madspec memory validate`.

Такой подход упрощает возобновление длинной работы и отделяет контекст разных веток друг от друга.

## Дополнительно

### Навыки Агента

Во время инициализации MADSpec также копирует навыки агента в целевую среду из каталога `skills/`, включая:

- [`madspec-cli-operator`](skills/madspec-cli-operator/SKILL.md) — базовый операторский навык, который должны читать все команды `madspec.*`
- [`memory-explain`](skills/memory-explain/SKILL.md) — навык объяснения и диагностики для `madspec.memory` и навигации по структурированной памяти
- [`merge-assistant`](skills/merge-assistant/SKILL.md) — навык для межветочного сравнения памяти, подготовки предложений на слияние и продвижения подтвержденных знаний на уровень проекта
- [`policy-engine`](skills/policy-engine/SKILL.md) — навык для жизненного цикла проектных правил через `madspec policy ...`: просмотр, предложение, применение, вывод из действия и проверка влияния правил на процесс
- [`change-engine`](skills/change-engine/SKILL.md) — навык для жизненного цикла `madspec change ...` и разговорной команды `/madspec.change`
- [`gate-orchestrator`](skills/gate-orchestrator/SKILL.md) — навык для `madspec gate ...`, блокировок, исключений и статуса ратификации
- [`subagent-role-advisor`](skills/subagent-role-advisor/SKILL.md) — навык для `madspec agents ...`, профилей субагентов и role-scoped context
- [`frontend-design`](skills/frontend-design/SKILL.md) — навык для проектирования выразительных UI и frontend-артефактов с упором на сильное визуальное направление, рабочий код и отказ от шаблонной «AI-эстетики»
- [`generate-agents-md`](skills/generate-agents-md/SKILL.md) — навык для создания и обновления `AGENTS.md` и родственных agent-instructions файлов как краткого операционного контракта для coding-агентов

### Субагенты

MADSpec хранит каноническое состояние субагентных ролей в `.madspec/system/agents/` и экспортирует role-scoped context через `madspec agents subagents context`.

Основные файлы:

- `.madspec/system/agents/state.json` — активная среда, профиль и `enabledSubagentIds`
- `.madspec/system/agents/catalog.json` — project-defined роли и project overrides встроенных ролей
- `.madspec/system/agents/bodies/` — Markdown-тела project roles и overrides

Через `madspec agents subagents create/update/remove` можно добавлять собственные проектные роли, не меняя built-in каталог фреймворка напрямую.

Во встроенный starter set входят роли:

- `architecture`
- `developer`
- `contracts-data`
- `testing`
- `security`
- `research`
- `docs`

- Для Cursor, GitHub Copilot, OpenCode и Qwen Code MADSpec генерирует native agent/subagent-файлы в средовые директории проекта.
- Для Kilo Code, Roo Code и SourceCraft v1 использует fallback-адаптеры на базе rules/commands/skills без собственного runtime.
- Сам MADSpec не является scheduler-ом субагентов: параллельность и последовательность остаются возможностями целевой агентной среды.

## Документация

- [Быстрый старт](QUICKSTART.md)
- [Общая документация по процессу работы](docs/README.md)
- [CLI-документация](docs/cli/README.md)
- [MVP-процесс](docs/mvp/README.md)
- [Feature-процесс](docs/feature/README.md)
- [Процессы review и security](docs/other/README.md)

## Поддержка

Если у вас есть вопросы или идеи по улучшению фреймворка, создайте issue в репозитории.
