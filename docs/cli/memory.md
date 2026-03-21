# `madspec memory`

Группа `madspec memory` - это рабочий интерфейс структурированной памяти в MADSpec. Через нее создается проектное хранилище памяти, читается контекст стадий, фиксируются решения, продвигается состояние планирования и реализации и проверяются производные представления.

Для изменяющих состояние переходов этот интерфейс теперь опирается на общий слой контрольных проверок: preflight-проверки planning и implementation, а также `checkpoint` для `review` и `security`, выполняются через `madspec gate`.

Команды, привязанные к стадии (`retrieve`, `capture`, `checkpoint`, planning и implementation operations), материализуют только минимально необходимый набор артефактов ветки для текущей стадии. Полная пересборка всех производных файлов ветки остается задачей `madspec memory init`, `madspec memory consolidate` и `madspec memory validate`.

Начиная с `Memory v2`, MADSpec использует смешанную модель хранения:

- `SQLite` в `.madspec/system/memory/memory.sqlite` — проектное хранилище записей, снимков стадий, сеансов, полнотекстового индекса и очереди индексирования
- `lancedb/` в `.madspec/system/memory/lancedb/` — локальный каталог векторного индекса для семантического поиска
- `.madspec/<branch>/memory/` — структура памяти, привязанная к ветке, и служебные производные файлы для совместимости и материализации контекста ветки

Важно для текущего состояния реализации:

- сеансы рантайма теперь читаются и обновляются через `SQLite`, а таблица `sessions` считается каноническим источником session-local state;
- файл `.madspec/<branch>/memory/working/active-session.json` больше не считается источником истины и поддерживается только как производная проекция для session `active`;
- для `retrieve`, `search`, `capture`, `checkpoint`, `register-step`, `start-step`, `checkpoint-step`, `complete-step` и связанных вызовов субагентного контекста доступен `--session-key`, по умолчанию используется `active`;
- переход всех изменяющих состояние команд `madspec memory` на `SQLite`-first path относится к `dev/parallel-memory-roadmap.md`;
- остальные runtime-артефакты ветки, включая `progress`, снимки стадий, `episodes` и `semantic/*`, пока остаются на file-first path и будут канонизированы позже.

## Когда Использовать

- чтобы посмотреть текущее состояние процесса в ветке
- чтобы зафиксировать факты, решения, контракты и состояние конкретной стадии
- чтобы ратифицировать неитеративную стадию
- чтобы регистрировать и продвигать шаги планирования или реализации
- чтобы пересобирать и валидировать производные файлы
- чтобы понять, почему выбран следующий шаг и какие записи влияют на контекст
- чтобы диагностировать дрейф производных представлений, проблемы индексирования и явные конфликты памяти

## Группы Команд

### Инициализация И Обслуживание Ветки

| Команда | Назначение |
| --- | --- |
| `madspec memory init` | Создать структуру памяти и производные представления для ветки |
| `madspec memory status` | Показать, существуют ли ключевые файлы памяти и потоки записей |
| `madspec memory db-status` | Показать состояние проектного `SQLite` и векторного индекса |
| `madspec memory reindex` | Обработать ожидающие задания индексирования для семантического поиска |
| `madspec memory consolidate` | Пересобрать производные Markdown-файлы из основного состояния памяти |
| `madspec memory validate` | Проверить основное состояние памяти и производные файлы |
| `madspec memory promote` | Перенести подтвержденные записи в семантическую память |
| `madspec memory learn --input ...` | Превратить результаты тестов или ревью в обучающие записи |

### Диагностика И Объяснение

| Команда | Назначение |
| --- | --- |
| `madspec memory doctor` | Провести диагностическую проверку без изменения памяти ветки, слоя `SQLite`, векторного индекса и производных представлений |
| `madspec memory explain --stage ...` | Объяснить текущий контекст стадии, влияние правил и результатов поиска по смыслу |
| `madspec memory timeline` | Показать объединенную историю записей, снимков состояния и `retrieval_runs` |
| `madspec memory why-next-step --stage ...` | Показать, почему выбран следующий шаг и почему остальные заблокированы |
| `madspec memory conflicts` | Показать явные записи со статусом `conflicted` и конфликты целостности |
| `madspec memory inspect-record --id ...` | Подробно показать каноническую запись, ее исходный файл и состояние индексирования |

### Межветочное Сравнение И Merge

| Команда | Назначение |
| --- | --- |
| `madspec memory compare-branches` | Сравнить снимки стадий, progress и подтвержденные записи знаний двух веток |
| `madspec memory propose-merge` | Подготовить предложение на слияние из ветки-источника в целевую ветку |
| `madspec memory preview-merge` | Показать предварительный просмотр предложения на слияние перед применением |
| `madspec memory resolve-conflict` | Зафиксировать решение по конфликту внутри предложения на слияние |
| `madspec memory merge-branches` | Применить ранее подготовленное предложение на слияние |
| `madspec memory promote-branch-knowledge` | Поднять подтвержденные знания из ветки на уровень проекта |

### Команды Для Состояния Стадии

| Команда | Назначение |
| --- | --- |
| `madspec memory retrieve --stage ...` | Получить минимальный контекст для стадии или шага |
| `madspec memory search --stage ... --query ...` | Посмотреть кандидатов из точного, полнотекстового и семантического поиска без полного контекста стадии |
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
| `madspec memory checkpoint-step --stage ...` | Зафиксировать промежуточное состояние шага, включая контрольные точки TDD |
| `madspec memory complete-step --stage ... --summary ...` | Завершить текущий шаг и продвинуть текущее состояние выполнения |

## Рекомендуемая Схема Использования

Для разных фаз MADSpec использует разные наборы команд:

- неитеративные стадии вроде `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `feature.init`, `feature.plan`, `review` и `security` используют `retrieve`, `capture` и `checkpoint`
- Процесс планирования использует `next-step` и `register-step` для поддержки каталога шагов и состояния покрытия
- Процесс реализации использует `start-step`, `checkpoint-step` и `complete-step` для управления текущим состоянием шага и TDD-доказательствами
- `consolidate` и `validate` поддерживают синхронность производных файлов и основных записей
- stage-scoped операции не обязаны заранее создавать несвязанные артефакты других стадий

## Общие Опции

У многих команд группы `memory` есть:

- `--branch <name>`: явно выбрать ветку для операции
- `--session-key <key>`: выбрать session-local runtime-контекст; по умолчанию используется `active`
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

Предпочтительный формат - канонические внутренние ключи, которые соответствуют именам полей в словаре `options` конкретной команды. Поля верхнего уровня (`stage`, `branch`, `json_output`, `status`, `summary`) извлекаются отдельно.

Для session-scoped операций в JSON также можно передать верхнеуровневый ключ `session_key`. Если он не указан, команда использует session `active`.

CLI также принимает ключи-псевдонимы в стиле флагов, включая `snake_case` и `hyphen-case`. Например:

- `audience` -> `audiences`
- `pain` -> `pain_points`
- `pending-action` -> `pending_actions`
- `related-artifact` -> `related_artifacts`

Если в JSON одновременно указаны канонический ключ и его псевдоним, канонический ключ имеет приоритет. Неизвестные поля CLI отклоняет с понятной ошибкой вместо трассировки исключения.

**Пример использования:**

```bash
madspec memory capture --from-file .madspec/.tmp/capture-args.json --json-output
```

При использовании `--from-file` CLI-параметры, переданные в командной строке, служат значениями по умолчанию — значения из файла имеют приоритет.

У `retrieve` дополнительно есть:

- `--session-key`
- `--step-id`
- `--limit`
- `--query`
- `--disable-semantic`
- `--recall-limit`
- `--scope <step|stage|branch|project>`
- `--include-obsolete`
- `--include-conflicted`
- `--full-artifact`
- `--include-history`

Ответ `retrieve` теперь также содержит:

- top-level `session_key`
- `policy_context.required[]`
- `policy_context.advisory[]`
- `policy_context.pending_proposals_count`
- `artifact_state.policy` при `--full-artifact`

Поле `active_session` пока остается в ответе как совместимый псевдоним для уже разрешенной session payload, чтобы не ломать существующих потребителей.

У `search` есть:

- `--session-key` — выбрать сеанс, из которого берутся `active_goal`, `open_questions` и `current_hypotheses` для автодополнения запроса
- `--query` — обязательный поисковый запрос
- `--scope <step|stage|branch|project>` — область поиска
- `--recall-limit` — сколько кандидатов брать из каждого канала поиска
- `--disable-semantic` — отключить семантический поиск по векторному индексу и оставить только `SQLite` с точным и полнотекстовым поиском

## Слои Памяти

`madspec memory` использует несколько слоев памяти с разной ролью. Это помогает отделить каноническое проектное хранилище от памяти, привязанной к ветке, и от разных типов знаний.

## Stage-aware materialization

- Общий минимальный runtime-набор ветки включает `progress.json`, проекцию `active-session.json`, `decision-log.jsonl`, `events.jsonl` и `semantic/*.jsonl`.
- Операции, привязанные к стадии, дополнительно создают каноническое состояние и производные представления только для текущей стадии.
- Отсутствие нерелевантных производных артефактов не считается ошибкой, пока соответствующая стадия еще не была инициализирована.
- `madspec memory validate` в своем полном сценарии по-прежнему проверяет полный набор материализованных артефактов ветки.

## Связь с контрольными проверками

- `register-step`, `start-step`, `checkpoint-step`, `complete-step` и `checkpoint --stage review|security` сначала вычисляют общий `gate_summary`
- если общий статус равен `blocked`, команда завершается ошибкой до изменения памяти
- `madspec memory explain --json-output` возвращает top-level `gate_summary` и включает его в `context`
- `madspec memory retrieve --toon-output` и `madspec memory explain --toon-output` возвращают тот же канонический payload в TOON-представлении для прямой передачи агенту
- `madspec memory why-next-step --json-output` возвращает `gate_summary` для каждого шага вместо прежнего `policy_notes`
- `project-context.md`, `implementation-context.md`, `review.md` и `security-audit.md` показывают производную сводку проверок и активных исключений

| Слой | Что хранит | Кто пишет | Когда читается | Роль |
| --- | --- | --- | --- | --- |
| `.madspec/system/memory/memory.sqlite` | записи, снимки стадий, сеансы, задания индексирования, истории извлечения, FTS | все `memory`-команды через общий слой хранения | при каждом чтении и изменении | Каноническое проектное состояние |
| `.madspec/system/memory/lancedb/` | векторные фрагменты для памяти и артефактов | `memory reindex`, фоновое индексирование при извлечении | при семантическом поиске | Семантическое расширение контекста |
| `episodes/events.jsonl` | События хода работы | `start-step`, `checkpoint-step`, `complete-step`, `memory learn` | `memory retrieve` для стадий реализации, `review` и `security`; для ранних стадий планирования только с `--include-history` | Операционная история |
| `working/decision-log.jsonl` | Кандидаты решений, заметки контрольных точек, процедурные подсказки | `memory capture`, `memory checkpoint`, `memory learn` | `memory retrieve`, `memory promote` | Буфер решений и кандидатов на обучение |
| `working/active-session.json` | Производная проекция канонического session state только для session `active` | session access layer поверх `SQLite` | совместимость веточного runtime-контекста и производных представлений | Совместимость и материализация |
| `semantic/facts.jsonl` | Подтвержденные факты | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |
| `semantic/decisions.jsonl` | Подтвержденные решения | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |
| `semantic/contracts.jsonl` | Подтвержденные контракты и обязательства | `complete-step` и `memory promote` | извлечение контекста и сборка производных представлений | Каноническое знание |

Знания уровня проекта после `promote-branch-knowledge` хранятся в таблице `records` проектного `SQLite` с branch `__project__`. При `retrieve/search --scope project` эти записи поднимаются раньше сырых межветочных совпадений.

Практически это означает:

- `SQLite` отвечает на вопросы "какое состояние сейчас каноническое", "что индексировать дальше" и "что подходит под точный и полнотекстовый поиск"
- `SQLite` также хранит session-local runtime state для всех `session_key`, а файловая проекция поддерживается только для `active`
- `lancedb/` отвечает на вопрос "что еще семантически похоже и стоит подтянуть в рабочий контекст"
- `episodes` отвечает на вопрос "что происходило по ходу работы"
- `decision_log` отвечает на вопрос "что еще нужно осмыслить, утвердить или продвинуть"
- `semantic/*` отвечает на вопрос "что уже считается подтвержденной истиной для ветки и стадии"

## Как Двигаются Записи Между Слоями

Типичный поток выглядит так:

1. `start-step`, `checkpoint-step` и `complete-step` пишут операционные события в `episodes`.
2. `capture`, `checkpoint` и `memory learn` добавляют заметки и кандидаты в `decision_log`.
3. `complete-step` может сразу записать подтвержденные `facts`, `decisions` и `contracts` в `semantic/*`.
4. Все эти операции параллельно синхронизируются в `SQLite`, а изменившиеся записи, снимки и артефакты ставятся в `index_jobs`.
5. `memory reindex` или фоновое индексирование при извлечении забирает ожидающие задания, обновляет векторные фрагменты и помечает их как `indexed`.
6. `memory promote` просматривает проверенные записи из `episodes` и `decision_log` и переносит их в `semantic/*`, если они еще не были продвинуты.

Из этого следуют два правила чтения:

- Для `mvp.concept`, `mvp.design`, `mvp.tech`, `mvp.architecture`, `mvp.plan`, `feature.init` и `feature.plan` история по умолчанию не подмешивается в `retrieve`; используйте `--include-history`, если нужен `episodes` и `decision_log`.
- Для стадий реализации, `review` и `security` история обычно важна для продолжения работы, поэтому `retrieve` включает ее автоматически.
- `retrieve` всегда может дополнительно собрать найденный контекст: точный и полнотекстовый поиск из `SQLite` и семантический поиск из векторного индекса, если сработали триггеры или передан `--query`

## Типовые Сценарии Использования

### Посмотреть состояние стадии перед продолжением

```bash
madspec memory retrieve --stage mvp.plan --json-output
madspec memory retrieve --stage mvp.plan --session-key planner --json-output
```

Если этот контекст должен читать агент, можно сразу использовать TOON:

```bash
madspec memory retrieve --stage mvp.plan --toon-output
```

### Посмотреть результаты поиска по явному запросу

```bash
madspec memory search --stage mvp.plan --query "billing step dependencies" --json-output
madspec memory search --stage mvp.plan --session-key impl --query "billing step dependencies" --json-output
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

### Обновить векторный индекс и посмотреть состояние хранилища

```bash
madspec memory db-status --json-output
madspec memory reindex --json-output
```

### Сравнить ветки и подготовить слияние памяти

```bash
madspec memory compare-branches \
  --source-branch feature/auth \
  --target-branch main \
  --json-output

madspec memory propose-merge \
  --source-branch feature/auth \
  --target-branch main \
  --json-output

madspec memory preview-merge --proposal-id <PROPOSAL_ID> --json-output
madspec memory resolve-conflict --proposal-id <PROPOSAL_ID> --conflict-id <CONFLICT_ID> --resolution take_source --json-output
madspec memory merge-branches --proposal-id <PROPOSAL_ID> --json-output
```

### Продвинуть подтвержденные знания на уровень проекта

```bash
madspec memory promote-branch-knowledge --source-branch feature/auth --json-output
```

### Проверить здоровье памяти и объяснить контекст

```bash
madspec memory doctor --json-output
madspec memory explain --stage mvp.plan --json-output
madspec memory why-next-step --stage mvp.implement --json-output
madspec gate status --stage mvp.implement --operation complete-step --json-output
```

Для агентского чтения того же контекста:

```bash
madspec memory explain --stage mvp.plan --toon-output
madspec gate status --stage mvp.implement --operation complete-step --toon-output
```

### Посмотреть историю, конфликты и конкретную запись

```bash
madspec memory timeline --stage mvp.plan --json-output
madspec memory conflicts --json-output
madspec memory inspect-record --id <RECORD_ID> --json-output
```

## Что Обновляют Эти Команды

В зависимости от команды CLI обновляет:

- `.madspec/system/memory/memory.sqlite`
- `.madspec/system/memory/lancedb/`
- `.madspec/system/memory/schema-version.json`
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
- [Команда `madspec.memory`](../other/madspec.memory.md)
- [Процессы review и security](../other/README.md)
