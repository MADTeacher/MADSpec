# MADSpec - MADSpec Framework

**MADSpec (MADSpec Framework)** - это экспериментальный фреймворк для разработки программного обеспечения с помощью LLM-агентов, призванный задействовать практически все возможности агентных сред разработки.

## Важно: Субагенты

**Субагенты не поставляются с фреймворком** и должны быть добавлены отдельно в ваш проект. MADSpec CLI создает структуру проекта и команды, но не включает субагентов. Если вы хотите использовать субагентов для расширения возможностей вашего AI-агента, вам необходимо:

1. Изучить документацию вашего AI-агента о поддержке субагентов
2. Добавить субагентов в соответствующие директории вашего проекта (например, `agents/` для некоторых агентов)
3. Настроить интеграцию субагентов

Субагенты могут значительно расширить возможности работы с MADSpec, но их установка и настройка выходит за рамки базовой инициализации проекта. 

Такое решение было принято из-за разрозненного подхода у AI-агентов для добавления этой функциональности, т.к. нет общего стандарта подключения субагентов в агентские среды разработки.

## Зачем нужен MADSpec?

### Проблема ограниченной интеграции

Агентные среды разработки (Cursor, GitHub Copilot, opencode и др.) предоставляют мощные возможности для работы с LLM-агентами, но эти возможности часто используются неэффективно или частично. MADSpec позволяет задействовать практически весь функционал: агентские навыки, субагенты,slash команды, интеграцию с репозиторием и документацией.

### Отсутствие систематического подхода

Без структурированного фреймворка каждый проект разрабатывается хаотично - одни этапы пропускаются, другие выполняются не в том порядке, который нужен для качественного результата. Возможности агентных сред используются эпизодически, без единой стратегии.

## Какую ценность дает MADSpec?

- **Максимальное использование возможностей агентных сред**: Задействование AGENTS.md, агентских навыков, субагентов и всех доступных интеграций
- **Прозрачность решений**: Каждый этап требует явного обоснования выбора - почему выбрана именно эта технология, почему архитектура спроектирована так, а не иначе. Все решения фиксируются в артефактах.
- **Систематический подход**: Четкий порядок этапов (концепция → дизайн → технологии → архитектура → планирование → реализация) гарантирует, что ни один важный шаг не будет пропущен.
- **Автоматическая валидация**: Каждый этап содержит чек-листы валидации, которые обеспечивают, что артефакты созданы качественно и содержат всю необходимую информацию.
- **Отслеживание прогресса**: Возможность возобновить работу с любого этапа, понимать, что уже сделано, и видеть эволюцию решений проекта.
- **Управляемые шаблоны**: Проверенные и оптимизированные шаблоны для каждого этапа разработки, которые можно использовать повторно.
- **Интеграция с Git**: Автоматическая инициализация репозитория, создание .gitignore, коммиты по этапам.

## Кому подходит MADSpec?

- Разработчики, которые хотят максимально эффективно использовать возможности агентных сред разработки
- Команды, которые хотят консистентно документировать архитектурные решения и отслеживать прогресс
- Пользователи Cursor, GitHub Copilot, opencode и других агентных сред, которые ищут структурированный подход к работе с AI-агентами
- Проекты, где важна прозрачность архитектурных решений и возможность быстро понять историю принятия решений

**Ключевой принцип**: В центре внимания не просто получение работающего кода, а систематическое использование возможностей агентных сред разработки и понимание причин, по которым приняты те или иные архитектурные и технологические решения.

---

## Установка

### Требования

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) для управления пакетами
- Git (опционально, рекомендуется)
- Один из поддерживаемых AI агентов

### Вариант 1: Постоянная установка (рекомендуется)

Установите один раз и используйте везде:

```bash
uv tool install madspec-cli --from git+https://github.com/MADTeacher/MADSpec.git
```

Затем используйте инструмент напрямую:

```bash
# Создать новый проект
madspec init <PROJECT_NAME>

# Или инициализировать в существующем проекте
madspec init . --ai cursor-agent
# или
madspec init --here --ai cursor-agent

# Проверить установленные инструменты
madspec check
```

Для обновления MADSpec:

```bash
uv tool install madspec-cli --force --from git+https://github.com/MADTeacher/MADSpec.git
```

**Преимущества постоянной установки:**
- Инструмент остается установленным и доступным в PATH
- Лучшее управление инструментами с `uv tool list`, `uv tool upgrade`, `uv tool uninstall`
- Более чистая конфигурация shell

### Вариант 2: Одноразовое использование

Запустите напрямую без установки:

```bash
uvx --from git+https://github.com/MADTeacher/MADSpec.git madspec init <PROJECT_NAME>
```

---

## Поддерживаемые AI агенты

| Агент | Тип | Директория | Требуется CLI |
|--------|------|------------|---------------|
| [Cursor](https://cursor.sh/) | IDE | `.cursor/commands/` | Нет |
| [opencode](https://opencode.ai/) | CLI | `.opencode/command/` | Да |
| [Kilo Code](https://github.com/Kilo-Org/kilocode) | IDE | `.kilocode/rules/` | Нет |
| [Roo Code](https://roocode.com/) | IDE | `.roo/rules/` | Нет |
| [SourceCraft](https://sourcecraft.dev/) | IDE | `.codeassistant/commands/` | Нет |
| [GitHub Copilot](https://github.com/features/copilot) | IDE | `.github/agents/` | Нет |

### Агентские навыки MADSpec

При инициализации проекта MADSpec копирует агентские навыки в директорию вашей среды (например, `.cursor/skills/`, `.opencode/skills/`):

| Навык | Назначение |
|-------|------------|
| **generate-agents-md** | Генерация AGENTS.md по лучшим практикам (Persona, Architecture, Operations, Code Style, Boundaries & Security) |
| **subagents_orchestrator** | Распределение задач между субагентами — анализ задачи и рекомендации, каких субагентов использовать |

### Особенности

- ✅ Задействует практически все возможности агентных сред разработки (AGENTS.md, агентские навыки, субагенты, интеграции)
- ✅ Начинает с концепции проекта, а не с технических ограничений
- ✅ Дизайн UI перед техническими решениями
- ✅ Обоснованный выбор технологий с обсуждением
- ✅ Пошаговая реализация с автоматической валидацией
- ✅ Отслеживание прогресса (можно возобновить с любого шага)
- ✅ Проверка понимания текущего состояния проекта и принятых архитектурных решений
- ✅ Review и анализ улучшений по итогам реализации

---

## Философия фреймворка

MADSpec построен на следующих принципах:

### Прозрачность решений

Каждый этап разработки сопровождается документацией, объясняющей не только ЧТО сделано, но и ПОЧЕМУ именно так. Это позволяет:

- Понимать причины выбора технологий
- Анализировать архитектурные паттерны и компромиссы
- Сохранять контекст проектных решений
- Быстро восстанавливать историю изменений и договоренностей

### Итеративная разработка

Фреймворк поддерживает итеративный подход к разработке:

1. **Начинаем с концепции** (команда `madspec.mvp.concept`), а не с технических ограничений
2. **Дизайн UI перед принятием технических решений** (команда `madspec.mvp.design`) - создание интерактивных HTML/CSS прототипов, которые можно открыть в браузере и исправить с помощью LLM перед тем, как переходить на следующий шаг
3. **Обоснованный выбор технологий** (команда `madspec.mvp.tech`) - можно предложить стек технологий для проекта, либо обсудить предлагаемые LLM варианты
4. **Обоснованный выбор архитектуры** (команда `madspec.mvp.architecture`) - можно предложить какие архитектурные паттерны и методологии проектирования должны использоваться в последующем процессе разработки проекта и на этапе планирования, либо обсудить предлагаемые LLM варианты
5. **План деплоя** (команда `madspec.deploy`) - согласование того, где и как система будет развернута (окружения, CI/CD, секреты, наблюдаемость). Команда может быть вызвана как до реализации, так и после (аудит готовности и план доработок).
6. **Планирование шагов разработки** (команда `madspec.mvp.plan`) - носит инкрементный подход, который позволяет планировать реализацию каждого последующего шага разработки системы в отдельном чате для сохранения "контекстной чистоты" (рекомендуется завершить все шаги планирования перед переходом к следующему этапу, но никто не запрещает чередовать подход план→реализация→тестирование→план→...)
7. **Пошаговая реализация** (команда `madspec.mvp.implement`) с автоматической валидацией LLM на предмет создания необходимых артефактов и обязательным этапом автоматизированного и ручного тестирования по завершению каждого шага
8. **Тестирование**. На этом этапе необходимо самостоятельно запустить все автоматизированные тесты, проследить, чтобы модель исправила ошибки, не упростив при этом код самой системы, а также выполнить все этапы ручного тестирования.

Отдельно можно выделить функцию, которая стоит особняком и может применяться практически на любом шаге благодаря отслеживанию прогресса:

1. **Review** (команда `madspec.review`) предназначена для анализа созданных артефактов, выявления сильных и слабых сторон реализации и фиксации направлений улучшения процесса разработки и результата.

---

## Режимы работы

MADSpec поддерживает два режима работы:

### MVP режим (разработка с нуля)

Для разработки нового проекта с нуля используйте команды с префиксом `madspec.mvp.*`:

```bash
# 1. Инициализация проекта
madspec init <PROJECT_NAME> --ai <agent>

# 2. Создание концепции
/madspec.mvp.concept "Описание идеи проекта"

# 3. Дизайн UI с прототипами
/madspec.mvp.design

# 4. Выбор технологий
/madspec.mvp.tech

# 5. Архитектура проекта
/madspec.mvp.architecture

# 6. Планирование реализации (инкрементально)
/madspec.mvp.plan
# Повторяйте до планирования всех шагов

# 7. Реализация
/madspec.mvp.implement
# Повторяйте до завершения всех шагов
```

### Feature режим (добавление функциональности)

Для добавления новой функциональности в существующий проект используйте команды с префиксом `madspec.feature.*`:

```bash
# 1. Инициализация работы над функцией
/madspec.feature.init "Описание новой функциональности"

# 2. Планирование реализации (инкрементально)
/madspec.feature.plan
# Повторяйте до планирования всех шагов

# 3. Реализация
/madspec.feature.implement
# Повторяйте до завершения всех шагов
```

### Общие команды

Эти команды работают с любой веткой (MVP или Feature):

```bash
# Планирование деплоя
/madspec deploy
# Может быть вызвана на любом этапе (до или после реализации)

# Review и улучшения (рекомендуется)
/madspec review

# Проверка безопасности (рекомендуется)
/madspec.security
```

---

## CLI команды

### init

Инициализация нового проекта из последнего шаблона.

```bash
madspec init <PROJECT_NAME> [OPTIONS]
```

**Опции:**
- `--ai <agent>` - AI ассистент для использования (cursor-agent, opencode, kilocode, roo, sourcecraft, copilot)
- `--ignore-agent-tools` - Пропустить проверку инструментов AI агента
- `--no-git` - Пропустить инициализацию Git репозитория
- `--here` - Инициализировать проект в текущей директории
- `--force` - Принудительное слияние при использовании --here
- `--skip-tls` - Пропустить проверку SSL/TLS (не рекомендуется)
- `--debug` - Показать диагностическую информацию
- `--github-token <token>` - GitHub токен для API запросов (или GH_TOKEN/GITHUB_TOKEN)

**Примеры:**
```bash
madspec init my-project --ai cursor-agent
madspec init my-project --ai opencode --no-git
madspec init . --ai sourcecraft
madspec init --here --force
```

### git

```bash
madspec git <COMMAND> [OPTIONS]
```

**Команды:**
- `current-branch` - Показать текущую ветку с fallback на `.madspec/config.json`
- `list-branches` - Список всех веток с артефактами
- `set-branch <branch-name>` - Установить рабочую ветку в `.madspec/config.json`
- `ensure-gitignore` - Создать или дополнить `.gitignore`
- `init` - Инициализировать git-репозиторий и сделать initial commit
- `create-branch <branch-name>` - Создать git-ветку и синхронизировать `.madspec`
- `commit --message <msg>` - Добавить все изменения и создать commit

**Примеры:**
```bash
madspec git current-branch
madspec git set-branch feature/new-ui
madspec git create-branch feature/user-auth
madspec git commit --message "feat: add auth"
```

### memory

Управление structured memory и generated views.

```bash
madspec memory init [--branch <name>]
madspec memory status [--branch <name>] [--json-output]
madspec memory consolidate [--branch <name>]
madspec memory validate [--branch <name>] [--json-output]
madspec memory capture --stage <mvp.concept|mvp.design|mvp.tech|mvp.architecture|review|security> [--summary <text>] [--fact <text>] [--decision <text>] [--contract <text>] [--question <text>] [--pending-action <text>] [--project-name <text>] [--audience <text>] [--scenario <text>] [--pain <text>] [--feature-p1 <name::description>] [--feature-p2 <name::description>] [--feature-p3 <name::description>] [--constraint <text>] [--assumption <text>] [--next-action <text>] [--status <proposed|validated|conflicted|obsolete>] [--evidence <path-or-note>] [--json-output]
madspec memory checkpoint --stage <mvp.concept|mvp.design|mvp.tech|mvp.architecture|review|security> --summary <text> [--fact <text>] [--decision <text>] [--contract <text>] [--evidence <path-or-note>] [--question <text>] [--pending-action <text>] [--json-output]
madspec memory retrieve --stage <stage> [--step-id <id>] [--json-output]
madspec memory start-step --stage <mvp.implement|feature.implement> [--step-id <id>] [--summary <text>] [--evidence <path-or-note>] [--json-output]
madspec memory checkpoint-step --stage <mvp.implement|feature.implement> [--step-id <id>] [--summary <text>] [--tdd-phase <phase>] [--red-evidence <text>] [--green-evidence <text>] [--refactor-note <text>] [--evidence <path-or-note>] [--json-output]
madspec memory complete-step --stage <mvp.implement|feature.implement> --summary <text> [--step-id <id>] [--red-evidence <text>] [--green-evidence <text>] [--refactor-note <text>] [--fact <text>] [--decision <text>] [--contract <text>] [--evidence <path-or-note>] [--json-output]
madspec memory next-step --stage <stage> [--candidate-step <id>] [--depends-on <id>] [--json-output]
madspec memory register-step --stage <stage> --step-id <id> --step-kind <code|non-code> [--covers <function>] [--tdd-policy <required|waived|not-applicable>] [--waiver-reason <text>] [--depends-on <id>] [--json-output]
madspec memory promote [--branch <name>] [--json-output]
madspec memory learn --input <file.json|file.jsonl> [--branch <name>] [--json-output]
```

**Назначение команд:**
- `memory init` - создает canonical memory layout и procedural rules
- `memory status` - показывает состояние structured memory
- `memory consolidate` - пересобирает markdown views из memory
- `memory validate` - проверяет schema, state transitions и согласованность views
- `memory capture` - инкрементально сохраняет подтвержденные stage-level facts/decisions/contracts/questions; для `mvp.concept` также обновляет canonical concept state через stage-specific flags
- `memory checkpoint` - канонически фиксирует финал non-iterative stage, обновляет active session и semantic records, затем пересобирает generated views
- `memory retrieve` - возвращает минимальный контекст для stage/step; для `mvp.concept` дополнительно отдает `artifact_state.concept`
- `memory start-step` - канонически переводит implementation step в `in_progress` и делает его текущим шагом
- `memory checkpoint-step` - записывает промежуточный implementation checkpoint, включая TDD phase и evidence
- `memory complete-step` - завершает implementation step, обновляет `completedSteps/currentImplementStep` и сохраняет step-level knowledge в memory
- `memory next-step` - детерминированно выбирает следующий исполнимый шаг или валидирует нового кандидата для planning
- `memory register-step` - канонически регистрирует новый planned step, его TDD metadata и автоматически обновляет coverage metadata в `progress.json`; `--covers` обязателен для `code` шагов и опционален для `non-code`
- `memory promote` - переносит validated records в semantic memory
- `memory learn` - превращает test/review outcomes в learning records

### check

Проверка установленных инструментов.

```bash
madspec check
```

Проверяет наличие:
- Git
- AI агентов (cursor-agent, opencode, kilocode, roo, sourcecraft, copilot)
- Visual Studio Code / VS Code Insiders

### migrate

Миграция существующего проекта от старой структуры `.madspec/` к новой `.madspec/<branch>/`.

```bash
madspec migrate
```

Перемещает артефакты из корня `.madspec/` в `.madspec/<BRANCH>/`, где `<BRANCH>` определяется из git.

### version

Отображение версии и системной информации.

```bash
madspec version
```

Показывает:
- Версию CLI
- Версию шаблона
- Дату релиза шаблона
- Информацию о системе

---

## Этапы разработки

### Этап 0: Концепция проекта (`madspec.mvp.concept`)

Определение проблемы, целевой аудитории и основных функций разрабатываемой программной системы.

**Особенности:**
- Автоматическая инициализация GIT репозитория с детальным `.gitignore` (исключает секреты, зависимости, временные файлы)
- Автоматическая валидация концепции перед переходом к следующему этапу
- Каноническое состояние концепции хранится в `.madspec/<BRANCH>/memory/stages/mvp.concept.json`
- `.madspec/<BRANCH>/concept.md` пересобирается из structured memory и не редактируется вручную
- Обязательный checkpoint через `madspec memory checkpoint --stage mvp.concept`
- Первый коммит в GIT после создания концепции

**Выходные артефакты:**
- `.gitignore` - файл исключений для GIT репозитория
- `.madspec/<BRANCH>/memory/stages/mvp.concept.json` - canonical concept state
- `.madspec/<BRANCH>/concept.md` - generated artifact концепции
- `.madspec/<BRANCH>/project-context.md` - generated view контекста проекта

### Этап 1: Дизайн UI (`madspec.mvp.design`)

Создание интерактивных HTML/CSS прототипов интерфейса на основе концепции. Прототипы можно открыть в браузере (включая встроенный браузер IDE) для визуального просмотра и утверждения.

**Особенности:**
- Прототипы создаются как реальные HTML/CSS файлы, которые можно открыть в браузере
- Прототипы создаются с учетом платформ из концепции - мобильные паттерны для Mobile, десктопные для Desktop, адаптивные для Web
- Создание локального сервера для просмотра прототипов (Go, Python или Node.js)
- Автоматическая валидация дизайна (покрытие функций, логика потоков, соответствие платформам)
- Обязательный checkpoint через `madspec memory checkpoint --stage mvp.design`

**Выходные артефакты:**
- `.madspec/<BRANCH>/ui-prototype/` - директория с HTML/CSS прототипами
  - `index.html` - главный файл с навигацией
  - `[screen-name].html` - HTML файлы для каждого экрана
  - `README.md` - инструкция по запуску локального сервера
  - Локальный сервер (если создан)
- `.madspec/<BRANCH>/ui-design.md` - описание дизайна с ссылками на прототипы
- `.madspec/<BRANCH>/project-context.md` - regenerated view контекста проекта

### Этап 2: Выбор технологий (`madspec.mvp.tech`)

Выбор технологического стека с обоснованием и обсуждением.

**Особенности:**
- Предложение 2-3 вариантов для каждого компонента стека с детальным обоснованием
- Обсуждение каждого выбора
- Консультация по структуре проекта
- Автоматическая валидация выбора технологий
- Обязательный checkpoint через `madspec memory checkpoint --stage mvp.tech`

**Выходные артефакты:**
- `.madspec/<BRANCH>/tech-stack.md` - выбранный стек
- `.madspec/<BRANCH>/project-context.md` - regenerated view контекста проекта

### Этап 3: Архитектура (`madspec.mvp.architecture`)

Проектирование архитектуры, структуры проекта, модели данных и API контрактов на основе HTML прототипов.

**Особенности:**
- Обязательный checkpoint через `madspec memory checkpoint --stage mvp.architecture`
- Архитектурные решения и inventory контрактов фиксируются в semantic memory до регенерации `project-context.md`

**Выходные артефакты:**
- `.madspec/<BRANCH>/architecture.md` - архитектура проекта
- `.madspec/<BRANCH>/data-model.md` - модель данных
- `.madspec/<BRANCH>/contracts/` - API контракты (создаются на основе элементов из прототипов)

**Особенность**: API контракты создаются на основе анализа HTML прототипов - если в прототипе нет элемента, для него не создается эндпоинт.

### Этап 3.5: Деплой (`madspec.deploy`)

Согласование того, **где и как** будет развернута система: окружения, единицы деплоя, CI/CD, секреты/конфигурация, миграции, бэкапы, наблюдаемость, стратегия релиза и отката.

**Выходные артефакты:**
- `.madspec/<BRANCH>/deployment.md` - план деплоя и эксплуатации (с ключевыми решениями)

### Этап 4: План реализации (`madspec.mvp.plan`)

Разбивка проекта на конкретные шаги с зависимостями и тестами.

**Особенности:**
- **Инкрементальный подход**: каждый запуск команды создает только один новый шаг (работа в пределах контекстного окна)
- Автоматическое определение следующего шага на основе зависимостей и приоритетов (P1 → P2 → P3)
- Каждый шаг классифицируется как `code` или `non-code`
- Для `code` шагов обязателен TDD-план `red -> green -> refactor`; для `non-code` шагов обязателен `waiver` или `not-applicable`
- Кэширование контекста планирования (`.madspec/<BRANCH>/planning-context-cache.md`) как generated view поверх semantic memory
- Визуализация прогресса планирования после каждого шага (покрытие функций P1, P2, P3)
- Автоматическое отслеживание метрик покрытия функций по приоритетам
- Запись ключевых решений о подходе к разбивке
- Structured memory first: сначала обновляются canonical memory files, затем выполняются `madspec memory consolidate` и `madspec memory validate`

**Выходные артефакты:**
- `.madspec/<BRANCH>/implementation-plan.md` - план реализации (обновляется инкрементально)
- `.madspec/<BRANCH>/steps/step-[NN]-[name]/` - директория с описаниями шагов (создается по одному за запуск)
- `.madspec/<BRANCH>/memory/progress.json` - файл отслеживания прогресса с метриками планирования
- `.madspec/<BRANCH>/planning-context-cache.md` - generated view кэша контекста планирования
- `.madspec/<BRANCH>/project-context.md` - generated view контекста проекта

### Этап 5: Реализация (`madspec.mvp.implement`)

Пошаговая реализация проекта с автоматической валидацией. HTML прототипы используются как референс для реализации интерфейса.

**Особенности:**
- Последовательное выполнение шагов с учетом зависимостей
- Для `code` шагов обязателен цикл `red -> green -> refactor` до обновления статуса и коммита
- Для `non-code` шагов обход TDD допускается только через явный `waiver` в canonical state
- Использование HTML прототипов из `.madspec/<BRANCH>/ui-prototype/` как визуального гайда при реализации интерфейса
- Автоматическая валидация каждого шага перед переходом к следующему (чек-лист из 7 пунктов)
- **Обязательные коммиты в GIT после каждого успешно завершенного шага** (только после валидации)
- Обновление canonical memory files и последующая консолидация generated views
- Возможность возобновления с любого шага (определение начального шага из `.madspec/<BRANCH>/memory/progress.json`)

**Выходные артефакты:**
- Реализованный код проекта
- Обновленный `.madspec/<BRANCH>/memory/progress.json` (после каждого шага)
- История коммитов GIT с коммитом для каждого завершенного шага

**КРИТИЧНО!!!** После завершения каждого шага реализации вы обязаны самостоятельно запустить все автоматизированные тесты, проследить, чтобы модель исправила ошибки, не упростив при этом код самой системы, а также выполнить все этапы ручного тестирования.

### Этап 6: Review и улучшения (`madspec.review`)

Анализ созданных артефактов, выявление сильных и слабых сторон, сравнение с лучшими практиками и фиксация направлений улучшения.

**Выходные артефакты:**
- `.madspec/<BRANCH>/review.md` - generated view отчета review
- `.madspec/<BRANCH>/improvements.md` - generated view списка улучшений

**Особенность**: Этот этап помогает зафиксировать области для улучшения, подготовить рефакторинг и улучшить качество кода и проектных решений.

### Команда проверки безопасности (`madspec.security`)

Комплексная проверка безопасности кода проекта на соответствие стандартам OWASP и законодательству по персональным данным.

**Особенности:**
- Настраиваемый scope проверки:
  - `basic` (по умолчанию) - OWASP Top 10 + законодательство ПД + зависимости + код
  - `full` - OWASP ASVS + Mobile/API + законодательство ПД + зависимости + код
  - Выборочные проверки: `owasp-top10`, `asvs`, `mobile`, `api`, `privacy`, `dependencies`, `code`
- Юрисдикция по умолчанию: 152-ФЗ РФ (настраивается на GDPR или мультиюрисдикцию)
- Security Score (0-100) с разбивкой по категориям
- Детальный отчет с примерами кода и рекомендациями
- Настраиваемая глубина проверки под текущий этап и потребности проекта

**Примеры использования:**
```bash
/madspec.security                                   # базовая проверка
/madspec.security --scope full                         # полная проверка
/madspec.security --scope owasp-top10                 # только OWASP Top 10
/madspec.security --scope asvs                           # только OWASP ASVS
/madspec.security --scope privacy                         # только законодательство по ПД
/madspec.security --jurisdiction gdpr                    # проверка с GDPR
/madspec.security --scope full --jurisdiction 152fz,gdpr # полная с мультиюрисдикцией
```

**Выходные артефакты:**
- `.madspec/<BRANCH>/security-audit.md` - generated view детального отчета по безопасности с Security Score

**Особенность**: Команда может быть вызвана в любой момент после создания кода проекта. Рекомендуется проводить проверку после каждого значимого изменения кода или перед релизом.

---

## Структура проекта

Структура директории `.madspec/`, которая создается в проектах, использующих MADSpec:

```
.madspec/
├── config.json           # Конфигурация проекта (текущая ветка)
├── procedures/           # Процедурные правила поведения и guardrails
│   ├── next-step-selection.md
│   ├── validation-checks.md
│   ├── promotion-guardrails.md
│   └── learning-rules.md
├── templates/            # Шаблоны для артефактов (общие для всех веток)
│   ├── concept-template.md
│   ├── ui-design-template.md
│   ├── html-prototype-template.html
│   ├── index-prototype-template.html
│   ├── tech-stack-template.md
│   ├── architecture-template.md
│   ├── deployment-template.md
│   ├── implementation-plan-template.md
│   ├── step-template.md
│   ├── step-creation-checklist.md
│   ├── step-validation-template.md
│   ├── review-template.md
│   ├── security-audit-template.md
│   ├── planning-state-template.json
│   ├── active-session-template.json
│   ├── memory-record-example.json
│   ├── planning-context-cache-template.md
│   └── project-context-template.md
├── <branch-name>/        # Артефакты для конкретной ветки (MVP или Feature)
│   ├── ui-prototype/     # HTML/CSS прототипы (создается на этапе design)
│   │   ├── index.html
│   │   ├── [screen-name].html
│   │   ├── README.md     # Инструкция по запуску локального сервера
│   │   └── [local_server] # Локальный сервер (если создан)
│   ├── steps/            # Шаги реализации (создается на этапе plan)
│   │   └── step-[NN]-[name]/ # Директория каждого шага
│   │       ├── description.md        # Описание шага
│   │       ├── tasks.md              # Задачи шага
│   │       ├── tests.md              # Тесты шага
│   │       ├── validation.md         # Критерии валидации
│   │       ├── planning-context.md   # Generated view контекста планирования
│   │       └── implementation-context.md # Generated view контекста реализации
│   ├── contracts/        # API контракты (создаются на этапе architecture)
│   ├── memory/
│   │   ├── progress.json             # Canonical workflow state + stepMetadata + TDD status
│   │   ├── working/
│   │   │   ├── active-session.json   # Активная рабочая память
│   │   │   └── decision-log.jsonl    # Micro-decisions и checkpoints
│   │   ├── episodes/
│   │   │   └── events.jsonl          # История действий и результатов
│   │   └── semantic/
│   │       ├── facts.jsonl           # Подтвержденные факты
│   │       ├── decisions.jsonl       # Подтвержденные решения
│   │       └── contracts.jsonl       # Подтвержденные контракты
│   ├── planning-context-cache.md # Generated view кэша контекста планирования
│   ├── concept.md        # Концепция проекта (с ключевыми решениями)
│   ├── ui-design.md      # Описание дизайна (с ключевыми решениями)
│   ├── tech-stack.md     # Выбранный стек технологий (с ключевыми решениями)
│   ├── architecture.md  # Архитектура проекта (с ключевыми решениями)
│   ├── data-model.md     # Модель данных
│   ├── deployment.md     # План деплоя и эксплуатации (создается командой madspec.deploy)
│   ├── implementation-plan.md # План реализации
│   ├── project-context.md # Generated view навигации по памяти проекта
│   ├── security-audit.md # Отчет по безопасности (с ключевыми решениями)
│   ├── review.md         # Generated view review
│   ├── improvements.md   # Generated view списка улучшений
│   └── feature-context.md # Контекст feature работы (только для Feature режима)
└── main/                 # Пример: артефакты основной ветки (для Feature режима)
    └── [те же артефакты, что и в <branch-name>/]
```

**Важно:**
- Артефакты хранятся в `.madspec/<branch-name>/`, где `<branch-name>` - имя текущей ветки
- Ветка определяется автоматически через `madspec git current-branch` (из git или config.json)
- Шаблоны хранятся в корне `.madspec/templates/` и общие для всех веток
- Конфигурация проекта хранится в `.madspec/config.json`

### Structured Memory First

В новом workflow MADSpec каноническое состояние хранится в `.madspec/<branch-name>/memory/`, а markdown-файлы контекста являются generated views.

**Canonical memory:**
- `memory/progress.json` - состояние workflow
- `memory/stages/mvp.concept.json` - canonical state этапа `mvp.concept`
- `memory/working/active-session.json` - текущая рабочая память
- `memory/working/decision-log.jsonl` - micro-decisions и checkpoints
- `memory/episodes/events.jsonl` - опыт выполнения
- `memory/semantic/*.jsonl` - validated knowledge

**Generated views:**
- `concept.md`
- `project-context.md`
- `planning-context-cache.md`
- `steps/*/planning-context.md`
- `steps/*/implementation-context.md`
- `security-audit.md`
- `review.md`
- `improvements.md`

Базовый цикл:
1. Обновить structured memory
2. Выполнить `madspec memory consolidate`
3. Выполнить `madspec memory validate`

Для ранних MVP-этапов canonical update выполняется командой `madspec memory checkpoint`, которая делает все три шага автоматически.

Для non-iterative стадий `concept/design/tech/architecture/review/security` рекомендуется сначала накапливать знания через `madspec memory capture`, а потом завершать стадию кратким `madspec memory checkpoint --summary ...`. Это убирает необходимость сжимать весь диалог в один финальный payload.

Для `mvp.concept` используйте stage-specific поля `memory capture`, чтобы наполнять canonical state напрямую:

```bash
madspec memory capture \
  --stage mvp.concept \
  --project-name "MVP scheduling assistant" \
  --audience "Freelancers scheduling appointments" \
  --scenario "Create and reschedule appointments from one calendar" \
  --pain "Manual follow-ups cause missed appointments" \
  --feature-p1 "Booking workflow::Create bookings and send reminders" \
  --constraint "Reminder settings must stay editable per booking" \
  --next-action "Proceed to mvp.design"

madspec memory checkpoint \
  --stage mvp.concept \
  --summary "Concept validated for MVP scheduling assistant" \
  --evidence .madspec/<BRANCH>/concept.md
```

Для iterative implementation-этапов canonical update больше не требует ручного редактирования `progress.json`:
- `madspec memory start-step` - выбрать/запустить текущий шаг
- `madspec memory checkpoint-step` - сохранить red/green/refactor progress по ходу шага
- `madspec memory complete-step` - закрыть шаг, продвинуть workflow и записать step-level facts/decisions/contracts

### Новая система контекстов

MADSpec использует модульную систему контекстов:

**Неитеративные этапы** (concept, design, tech, architecture, security, review):
- Ключевые решения встроены в артефакт этапа (в конце файла)
- Записываются 1-3 самых критичных решения с кратким обоснованием
- Для MVP этапов `concept`, `design`, `tech`, `architecture` дополнительно обязателен `madspec memory checkpoint`, который пишет canonical checkpoint в `.madspec/<branch-name>/memory/`

**Итеративные этапы** (plan, implement):
- Каждый шаг имеет собственные контексты:
  - `planning-context.md` - решения, принятые при планировании шага
  - `implementation-context.md` - решения, проблемы и результаты реализации
- Контексты шагов позволяют отслеживать эволюцию проекта пошагово

**Навигационный файл** `project-context.md`:
- Generated view
- Содержит ссылки на все артефакты и summary текущего memory state
- Не является source of truth

---

## Особенности архитектуры

### Определение ветки

Все команды автоматически определяют текущую ветку через `madspec git current-branch`:
- Команда выполняется из корня проекта и возвращает имя ветки через stdout
- Логика определения ветки:
  1. Сначала используется `git branch --show-current` (как наиболее актуальный источник)
  2. Затем проверяется `.madspec/config.json` (если существует и содержит `currentBranch`) как fallback
  3. Fallback на `main` если ни Git, ни config.json недоступны

Артефакты сохраняются в `.madspec/<branch-name>/`, где `<branch-name>` - имя текущей ветки.

### Инкрементальное планирование

Команды планирования (`madspec.mvp.plan`, `madspec.feature.plan`) поддерживают инкрементальный режим:
- Каждый запуск создает только один новый шаг
- Определяет следующий шаг на основе зависимостей и приоритетов
- Кэширует контекст для оптимизации
- Визуализирует прогресс покрытия функций

### Отслеживание прогресса

Файл `.madspec/<branch-name>/memory/progress.json` отслеживает:
- Завершенные шаги реализации
- Метаданные шага: `stepMetadata.kind`, `stepMetadata.tddPolicy`, `stepMetadata.waiverReason`
- TDD состояние шага: `stepStatus.tddPhase`, `redEvidence`, `greenEvidence`, `refactorNote`
- Метрики покрытия функций по приоритетам
- Текущий этап проекта
- История изменений

### Автоматическая валидация

Каждый этап содержит чек-лист валидации, который проверяет:
- Полноту артефактов
- Качество решений
- Соответствие требованиям этапа
- Подготовку к следующему этапу

---

## Быстрый старт

См. [`QUICKSTART.md`](QUICKSTART.md) для быстрого старта.

## Поддержка

Если у вас есть вопросы или предложения по улучшению фреймворка, создайте issue в репозитории проекта.

Удачи в разработке!

С уважением, Станислав [MADTeacher] Чернышев
