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

У `retrieve` дополнительно есть:

- `--step-id`
- `--limit`
- `--include-obsolete`
- `--include-conflicted`
- `--full-artifact`
- `--include-history`

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
