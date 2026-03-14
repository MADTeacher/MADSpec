# `madspec memory`

Группа `madspec memory` - это рабочий интерфейс к структурированной памяти в MADSpec. Через нее инициализируется основное хранилище, читается контекст стадий, фиксируются решения, продвигается состояние планирования и реализации и валидируются производные представления.

## Когда Использовать

- чтобы посмотреть текущее состояние процесса в ветке
- чтобы зафиксировать факты, решения, контракты и состояние конкретной стадии
- чтобы ратифицировать неитеративную стадию
- чтобы регистрировать и продвигать шаги планирования или реализации
- чтобы пересобирать и валидировать производные файлы

## Группы Команд

### Инициализация И Обслуживание Ветки

| Команда | Назначение |
| --- | --- |
| `madspec memory init` | Создать структуру memory и производные представления для ветки |
| `madspec memory status` | Показать, существуют ли ключевые memory-файлы и потоки записей |
| `madspec memory consolidate` | Пересобрать производные Markdown-файлы из основного состояния memory |
| `madspec memory validate` | Провалидировать основное состояние memory и производные файлы |
| `madspec memory promote` | Перенести подтвержденные записи в семантическую память |
| `madspec memory learn --input ...` | Превратить результаты тестов или review в обучающие записи |

### Команды Для Состояния Стадии

| Команда | Назначение |
| --- | --- |
| `madspec memory retrieve --stage ...` | Получить минимальный контекст для стадии или шага |
| `madspec memory capture --stage ...` | Добавить факты и обновить основное состояние стадии |
| `madspec memory checkpoint --stage ... --summary ...` | Ратифицировать неитеративную стадию и пересобрать производные файлы |

### Команды Планирования

| Команда | Назначение |
| --- | --- |
| `madspec memory next-step --stage ...` | Выбрать следующий исполнимый шаг или проверить кандидата |
| `madspec memory register-step --stage ...` | Зарегистрировать запланированный шаг и обновить метаданные покрытия |

### Команды Выполнения Для Реализации

| Команда | Назначение |
| --- | --- |
| `madspec memory start-step --stage ...` | Запустить шаг реализации |
| `madspec memory checkpoint-step --stage ...` | Зафиксировать промежуточное состояние шага, включая TDD-checkpoints |
| `madspec memory complete-step --stage ... --summary ...` | Завершить текущий шаг и продвинуть текущее состояние выполнения |

## Рекомендуемый Паттерн Использования

Для разных фаз MADSpec использует разные наборы команд:

- неитеративные стадии вроде `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `feature.init`, `feature.plan`, `review` и `security` используют `retrieve`, `capture` и `checkpoint`
- Процесс планирования использует `next-step` и `register-step` для поддержки каталога шагов и состояния покрытия
- Процесс реализации использует `start-step`, `checkpoint-step` и `complete-step` для управления текущим состоянием шага и TDD-доказательствами
- `consolidate` и `validate` поддерживают синхронность производных файлов и основных записей

## Общие Опции

У многих `memory`-команд есть:

- `--branch <name>`: явно выбрать ветку для операции
- `--json-output`: вывести JSON в удобном для автоматической обработки виде
- `--from-file <path>`: прочитать все аргументы из JSON-файла вместо командной строки

### Передача аргументов через файл (`--from-file`)

Команды `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step` и `complete-step` поддерживают опцию `--from-file <path>`. Когда она указана, CLI читает аргументы из JSON-файла вместо разбора командной строки.

Это решает проблему ограничения длины командной строки на Windows (~8191 символов в cmd.exe), которая возникает при большом количестве параметров (например, `memory capture` для архитектуры).

**Формат JSON-файла:**

```json
{
  "stage": "mvp.concept",
  "summary": "Концепция утверждена",
  "facts": ["факт 1", "факт 2"],
  "decisions": ["решение 1"],
  "project_name": "MyProject",
  "system_overview": "Краткое описание системы",
  "audiences": ["разработчики"],
  "status": "validated"
}
```

Предпочтительный формат - canonical internal keys, которые соответствуют именам полей в словаре `options` конкретной команды. Поля верхнего уровня (`stage`, `branch`, `json_output`, `status`, `summary`) извлекаются отдельно.

CLI также принимает alias-ключи в стиле флагов, включая `snake_case` и `hyphen-case`. Например:

- `audience` -> `audiences`
- `pain` -> `pain_points`
- `pending-action` -> `pending_actions`
- `related-artifact` -> `related_artifacts`

Если в JSON одновременно указаны canonical key и его alias, canonical key имеет приоритет. Неизвестные поля CLI отклоняет с понятной ошибкой вместо traceback.

**Пример использования:**

```bash
madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output
```

При использовании `--from-file` CLI-параметры, переданные в командной строке, служат значениями по умолчанию — значения из файла имеют приоритет.

У `retrieve` дополнительно есть:

- `--step-id`
- `--limit`
- `--include-obsolete`
- `--include-conflicted`
- `--full-artifact`
- `--include-history`

## Слои Памяти

`madspec memory` использует несколько слоев памяти с разной ролью. Это помогает отделить операционную историю работы от канонических branch-level знаний.

| Слой | Что хранит | Кто пишет | Когда читается | Роль |
| --- | --- | --- | --- | --- |
| `episodes/events.jsonl` | События хода работы | `start-step`, `checkpoint-step`, `complete-step`, `memory learn` | `memory retrieve` для implementation, review и security; для ранних planning-stage стадий только с `--include-history` | Операционная история |
| `working/decision-log.jsonl` | Кандидаты решений, checkpoint notes, procedural hints | `memory capture`, `memory checkpoint`, `memory learn` | `memory retrieve`, `memory promote` | Буфер решений и learning-кандидатов |
| `semantic/facts.jsonl` | Подтвержденные факты | `complete-step` и `memory promote` | retrieval и сборка производных представлений | Каноническое знание |
| `semantic/decisions.jsonl` | Подтвержденные решения | `complete-step` и `memory promote` | retrieval и сборка производных представлений | Каноническое знание |
| `semantic/contracts.jsonl` | Подтвержденные контракты и обязательства | `complete-step` и `memory promote` | retrieval и сборка производных представлений | Каноническое знание |

Практически это означает:

- `episodes` отвечает на вопрос "что происходило по ходу работы"
- `decision_log` отвечает на вопрос "что еще нужно осмыслить, утвердить или продвинуть"
- `semantic/*` отвечает на вопрос "что уже считается подтвержденной истиной для ветки и стадии"

## Как Двигаются Записи Между Слоями

Типичный поток выглядит так:

1. `start-step`, `checkpoint-step` и `complete-step` пишут операционные события в `episodes`.
2. `capture`, `checkpoint` и `memory learn` добавляют заметки и кандидаты в `decision_log`.
3. `complete-step` может сразу записать подтвержденные `facts`, `decisions` и `contracts` в `semantic/*`.
4. `memory promote` просматривает validated записи из `episodes` и `decision_log` и переносит их в `semantic/*`, если они еще не были продвинуты.

Из этого следуют два правила чтения:

- Для `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `feature.init` и `feature.plan` история по умолчанию не подмешивается в `retrieve`; используйте `--include-history`, если нужен `episodes` и `decision_log`.
- Для implementation, `review` и `security` история обычно важна для продолжения работы, поэтому `retrieve` включает ее автоматически.

## Типовые Сценарии Использования

### Посмотреть состояние стадии перед продолжением

```bash
madspec memory retrieve --stage mvp.plan --json-output
```

### Зафиксировать состояние стадии и ратифицировать его

```bash
madspec memory capture --stage mvp.tech --stack-overview "Веб-стек для быстрой поставки MVP"
madspec memory checkpoint --stage mvp.tech --summary "Технологический стек утвержден"
```

### Зарегистрировать шаг планирования

```bash
madspec memory next-step --stage mvp.plan
madspec memory register-step \
  --stage mvp.plan \
  --step-id step-01-auth \
  --step-kind code \
  --covers "Аутентификация пользователя"
```

### Продвинуть шаг реализации

```bash
madspec memory start-step --stage feature.implement
madspec memory checkpoint-step --stage feature.implement --tdd-phase red --red-evidence "Добавлен падающий тест"
madspec memory complete-step --stage feature.implement --summary "Форма биллинга реализована"
```

### Пересобрать и провалидировать производные файлы

```bash
madspec memory consolidate
madspec memory validate
```

## Что Обновляют Эти Команды

В зависимости от команды CLI обновляет:

- `.madspec/<branch>/memory/stages/*.json`
- `.madspec/<branch>/memory/progress.json`
- `.madspec/<branch>/memory/working/active-session.json`
- `.madspec/<branch>/memory/working/decision-log.jsonl`
- `.madspec/<branch>/memory/episodes/events.jsonl`
- `.madspec/<branch>/memory/semantic/*.jsonl`
- производные файлы вроде `concept.md`, `architecture.md`, `implementation-plan.md`, `review.md` и `security-audit.md`

## Связанные Документы

- [Индекс CLI-документации](README.md)
- [Обзор процесса работы](../README.md)
- [MVP-процесс](../mvp/README.md)
- [Feature-процесс](../feature/README.md)
- [Процессы review и security](../other/README.md)
