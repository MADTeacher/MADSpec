# Быстрый старт с MADSpec

MADSpec — фреймворк для быстрой разработки MVP и добавления новых фич в проект. Основа workflow: project-local memory backend в `.madspec/system/memory/`, branch-aware compatibility artifacts в `.madspec/<branch>/memory/` и generated artifacts, которые пересобираются из canonical state.

Все сгенерированные команды `madspec.*` должны начинаться с чтения и применения skill `madspec-cli-operator`. Для `madspec.mvp.design` дополнительно обязателен skill `frontend-design`.

Подробная workflow-документация:

- [`docs/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/README.md)
- [`docs/mvp/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/README.md)
- [`docs/feature/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/README.md)
- [`docs/other/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/README.md)

## Установка

```bash
uv tool install madspec-cli --from git+https://github.com/MADTeacher/MADSpec.git
```

Проверьте работу:
```bash
madspec --help
```

## Что вам нужно?

### Добавить новую функцию в существующий проект → Feature режим

**Последовательность команд:**

1. `madspec.feature.init "что добавить"` — анализ проекта и запись canonical state в `.madspec/<branch>/memory/stages/feature.init.json`
2. `madspec.feature.plan` — планирование шагов через `.madspec/<branch>/memory/stages/feature.plan.json`
3. `madspec.feature.implement` — реализация шагов через runtime memory workflow (`progress.json`, `active-session.json`, step records)
4. `madspec.review` — quality review после изменений (опционально)
5. `madspec.security` — security/privacy audit по коду и ПД 152-ФЗ (опционально)

### Создать проект с нуля → MVP режим

**Последовательность команд:**

1. `madspec.mvp.concept` — что создаем; реальные данные этапа будут сохранены в `.madspec/<branch>/memory/stages/mvp.concept.json`, `madspec memory retrieve --stage mvp.concept` по умолчанию будет возвращать краткий `concept_status`, а `concept.md` будет собран автоматически
2. `madspec.mvp.design` — UI прототипы; canonical state этапа хранится в `.madspec/<branch>/memory/stages/mvp.design.json`, `madspec memory retrieve --stage mvp.design` по умолчанию возвращает краткий `design_status`, а `ui-design.md` пересобирается автоматически
3. `madspec.mvp.tech` — выбор технологий; canonical state этапа хранится в `.madspec/<branch>/memory/stages/mvp.tech.json`, `madspec memory retrieve --stage mvp.tech` по умолчанию возвращает краткий `tech_status`, а `tech-stack.md` пересобирается автоматически
4. `madspec.mvp.architecture` — архитектура
5. `madspec.mvp.plan` — планирование шагов (повторять пока не спланируете все)
6. `madspec.mvp.implement` — реализация (повторять пока не реализуете все)
7. `madspec.review` — quality review после изменений (опционально)
8. `madspec.security` — security/privacy audit по коду и ПД 152-ФЗ (опционально)

## Feature Workflow (добавление фичи)

Хотите добавить функцию в существующий проект?

**Шаг 1: Начните с анализа**
```bash
madspec.feature.init "система платежей через Stripe"
```

Что происходит: анализ структуры проекта → запись канонического состояния `feature.init` → автогенерация `project-analysis.md`, `feature-context.md`, `tech-stack.md`, `architecture.md` и сводки ветки. Несвязанные MVP- и review/security-артефакты на этом шаге не создаются заранее.

**Шаг 2: Спланируйте шаги**
```bash
madspec.feature.plan
```
Повторяйте, пока не заполните `feature.plan.json` и не покроете все нужные function IDs.

**Шаг 3: Реализуйте**
```bash
madspec.feature.implement
```
Повторяйте через `memory retrieve/start-step/checkpoint-step/complete-step`, пока не реализуете всю функциональность.

Основные reference docs:

- [`docs/feature/madspec.feature.init.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.init.md)
- [`docs/feature/madspec.feature.plan.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.plan.md)
- [`docs/feature/madspec.feature.implement.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.implement.md)

## Все команды

| Команда | Когда использовать |
|---------|-------------------|
| `madspec.feature.init "спецификация"` | Добавить новую фичу в проект |
| `madspec.feature.plan` | Спланировать шаги Feature |
| `madspec.feature.implement` | Реализовать Feature |
| `madspec.mvp.concept` | Создать проект с нуля — концепция; работает через краткий `concept_status`, по `--full-artifact` возвращает полный концепт и пересобирает `concept.md` |
| `madspec.mvp.design` | Создать проект — UI прототипы; работает через `design_status`, а `ui-design.md` считается generated artifact |
| `madspec.mvp.tech` | Создать проект — выбор технологий; работает через `tech_status`, а `tech-stack.md` считается generated artifact |
| `madspec.mvp.architecture` | Создать проект — архитектура |
| `madspec.mvp.plan` | Создать проект — планирование |
| `madspec.mvp.implement` | Создать проект — реализация |
| `madspec.review` | Проверить качество изменений и собрать backlog улучшений |
| `madspec.security` | Проверить security/privacy риски и обработку ПД по 152-ФЗ |

## Что почитать после quickstart

- [`docs/mvp/madspec.mvp.concept.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/madspec.mvp.concept.md)
- [`docs/mvp/madspec.mvp.plan.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/madspec.mvp.plan.md)
- [`docs/feature/madspec.feature.init.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.init.md)
- [`docs/other/madspec.review.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/madspec.review.md)
- [`docs/other/madspec.security.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/madspec.security.md)

## Агентские навыки

При инициализации MADSpec копирует навыки в вашу среду (например, `.cursor/skills/`):

- **madspec-cli-operator** — базовый operational skill для всех команд `madspec.*`
- **frontend-design** — обязательный visual/UI/UX skill для `madspec.mvp.design`
- **generate-agents-md** — генерация AGENTS.md по лучшим практикам

## Что вы получаете

- **Структурированный проект** — понятная организация кода
- **Понимание архитектуры** — решения задокументированы
- **Работающий код** — протестированная реализация
- **Документацию** — все решения задокументированы

Артефакты сохраняются в `.madspec/<branch-name>/` для каждой ветки.

## Помощь

```bash
madspec --help
```
