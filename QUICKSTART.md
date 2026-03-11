# Быстрый старт с MADSpec

MADSpec — фреймворк для быстрой разработки MVP и добавления новых фич в проект. Формирует артефакты, которые делают разработку более осознанной.

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

1. `madspec.feature.init "что добавить"` — анализ проекта + точки интеграции
2. `madspec.feature.plan` — планирование шагов (повторять пока не спланируете все)
3. `madspec.feature.implement` — реализация шагов (повторять пока не реализуете все)
4. `madspec.deploy` — подготовка к деплою (опционально)
5. `madspec.review` — проверка качества (опционально)
6. `madspec.security` — проверка безопасности (опционально)

### Создать проект с нуля → MVP режим

**Последовательность команд:**

1. `madspec.mvp.concept` — что создаем; реальные данные этапа будут сохранены в `.madspec/<branch>/memory/stages/mvp.concept.json`, `madspec memory retrieve --stage mvp.concept` по умолчанию будет возвращать краткий `concept_status`, а `concept.md` будет собран автоматически
2. `madspec.mvp.design` — UI прототипы; canonical state этапа хранится в `.madspec/<branch>/memory/stages/mvp.design.json`, `madspec memory retrieve --stage mvp.design` по умолчанию возвращает краткий `design_status`, а `ui-design.md` пересобирается автоматически
3. `madspec.mvp.tech` — выбор технологий
4. `madspec.mvp.architecture` — архитектура
5. `madspec.mvp.plan` — планирование шагов (повторять пока не спланируете все)
6. `madspec.mvp.implement` — реализация (повторять пока не реализуете все)
7. `madspec.deploy` — подготовка к деплою (опционально)
8. `madspec.review` — проверка качества (опционально)
9. `madspec.security` — проверка безопасности (опционально)

## Feature Workflow (добавление фичи)

Хотите добавить функцию в существующий проект?

**Шаг 1: Начните с анализа**
```bash
madspec.feature.init "система платежей через Stripe"
```

Что происходит: анализ структуры проекта → определение точек интеграции → генерация артефактов

**Шаг 2: Спланируйте шаги**
```bash
madspec.feature.plan
```
Повторяйте пока не спланируете всю функциональность.

**Шаг 3: Реализуйте**
```bash
madspec.feature.implement
```
Повторяйте пока не реализуете всю функциональность.

## Все команды

| Команда | Когда использовать |
|---------|-------------------|
| `madspec.feature.init "спецификация"` | Добавить новую фичу в проект |
| `madspec.feature.plan` | Спланировать шаги Feature |
| `madspec.feature.implement` | Реализовать Feature |
| `madspec.mvp.concept` | Создать проект с нуля — концепция; работает через краткий `concept_status`, по `--full-artifact` возвращает полный концепт и пересобирает `concept.md` |
| `madspec.mvp.design` | Создать проект — UI прототипы; работает через `design_status`, а `ui-design.md` считается generated artifact |
| `madspec.mvp.tech` | Создать проект — выбор технологий |
| `madspec.mvp.architecture` | Создать проект — архитектура |
| `madspec.mvp.plan` | Создать проект — планирование |
| `madspec.mvp.implement` | Создать проект — реализация |
| `madspec.deploy` | Подготовить к деплою |
| `madspec.review` | Проверить качество кода |
| `madspec.security` | Проверить безопасность |

## Агентские навыки

При инициализации MADSpec копирует навыки в вашу среду (например, `.cursor/skills/`):

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
