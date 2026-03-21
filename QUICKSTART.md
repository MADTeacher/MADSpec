# Быстрый старт с MADSpec

MADSpec помогает вести разработку с помощью LLM-агентов через понятный процесс, веточный контекст и структурированную память. Каноническое состояние проекта хранится в `.madspec/system/`, а рабочие артефакты конкретной ветки — в `.madspec/<branch>/`.

Все сгенерированные команды `madspec.*` должны начинаться с чтения и применения навыка `madspec-cli-operator`. Для `madspec.mvp.design` дополнительно обязателен навык `frontend-design`.

Подробная документация:

- [`README.md`](/Users/madteacher/Documents/GitHub/MADSpec/README.md)
- [`docs/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/README.md)
- [`docs/cli/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/cli/README.md)
- [`docs/mvp/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/README.md)
- [`docs/feature/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/README.md)
- [`docs/other/README.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/README.md)

## Установка CLI

```bash
uv tool install madspec-cli --from git+https://github.com/MADTeacher/MADSpec.git
```

Проверка установки:

```bash
madspec --help
madspec check
```

## Инициализация проекта

Создать новый проект:

```bash
madspec init my-project --ai cursor-agent
cd my-project
```

Подключить MADSpec к текущему репозиторию:

```bash
madspec init . --ai sourcecraft
```

Поддерживаемые значения `--ai`:

- `cursor-agent`
- `opencode`
- `kilocode`
- `roo`
- `sourcecraft`
- `qwen`
- `copilot`

Что делает `madspec init`:

- загружает и распаковывает актуальный шаблон проекта
- создает `.madspec/config.json` и выбирает `agentEnvironment`
- инициализирует проектное хранилище памяти в `.madspec/system/memory/`
- создает слой субагентов в `.madspec/system/agents/`
- создает структуру памяти текущей ветки в `.madspec/<branch>/memory/`
- создает начальный артефакт развертывания `deployment.md` для текущей ветки
- генерирует команды и навыки для выбранной AI-среды

## Если вы начинаете новый продукт: MVP

Рекомендуемый порядок работы:

1. `madspec init <PROJECT_NAME> --ai <agent>` или `madspec init .`
2. `madspec.mvp.concept`
3. `madspec.mvp.design`
4. `madspec.mvp.tech`
5. `madspec.mvp.architecture`
6. `madspec.deploy`
7. `madspec.mvp.plan`
8. `madspec.mvp.implement`
9. `madspec.review`
10. `madspec.security`

Коротко о стадиях:

- `madspec.mvp.concept` фиксирует идею продукта, аудиторию и ключевые сценарии
- `madspec.mvp.design` описывает UX, экраны и прототипы интерфейса
- `madspec.mvp.tech` закрепляет стек и технические решения
- `madspec.mvp.architecture` оформляет структуру системы, данные и контракты
- `madspec.deploy` фиксирует окружения, CI/CD, секреты, миграции, наблюдаемость, релиз и откат
- `madspec.mvp.plan` строит план реализации
- `madspec.mvp.implement` выполняет текущий шаг реализации

Для небольшой MVP-итерации обычно достаточно одного содержательного шага в `madspec.mvp.plan`. Дробить работу на микро-шаги стоит только там, где есть реальные зависимости, разные риски или отдельные точки проверки.

## Если вы добавляете функцию: Feature

Рекомендуемый порядок работы:

1. `madspec.feature.init "что нужно добавить"`
2. `madspec.feature.plan`
3. `madspec.feature.implement`
4. `madspec.review`
5. `madspec.security`

Пример:

```bash
madspec.feature.init "система платежей через Stripe"
```

Что происходит дальше:

- `madspec.feature.init` фиксирует контекст новой функции и собирает минимально нужные артефакты ветки
- `madspec.feature.plan` строит шаги реализации
- `madspec.feature.implement` выполняет текущий шаг через runtime-память ветки

Если задача большая, `feature.plan` и `feature.implement` повторяют несколько раз, пока не будет закрыт весь объем работы.

## Общие команды после инициализации

Эти команды можно запускать в любом процессе, когда нужен дополнительный контроль:

- `madspec.memory` — понять состояние структурированной памяти и выбор следующего шага
- `madspec.merge` — сравнить память текущей ветки с другой веткой и подготовить слияние знаний
- `madspec.policy` — посмотреть и изменить правила проекта
- `madspec.change` — собрать и ратифицировать пакет изменений ветки
- `madspec.gate` — проверить блокировки, предупреждения и исключения
- `madspec.agents` — управлять профилями субагентов и их контекстом
- `madspec.review` — провести проверку качества реализации
- `madspec.security` — провести аудит безопасности и приватности
- `madspec.deploy` — уточнить или обновить план развертывания

## Что читать дальше

- [`docs/cli/init.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/cli/init.md)
- [`docs/mvp/madspec.mvp.concept.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/madspec.mvp.concept.md)
- [`docs/mvp/madspec.mvp.plan.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/mvp/madspec.mvp.plan.md)
- [`docs/feature/madspec.feature.init.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.init.md)
- [`docs/feature/madspec.feature.plan.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/feature/madspec.feature.plan.md)
- [`docs/other/madspec.deploy.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/madspec.deploy.md)
- [`docs/other/madspec.review.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/madspec.review.md)
- [`docs/other/madspec.security.md`](/Users/madteacher/Documents/GitHub/MADSpec/docs/other/madspec.security.md)

## Напоминание по языку

В русскоязычных пояснениях используйте русский как основной язык. Английский оставляйте только для точных идентификаторов: команд, путей, имен файлов, ключей конфигурации, названий продуктов и других технических сущностей без естественной замены.
