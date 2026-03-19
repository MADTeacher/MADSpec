# `madspec change`

Группа `madspec change` управляет слоем изменений ветки в MADSpec. Каноническое состояние живет в `.madspec/<branch>/change/`: там фиксируется базовая точка сравнения ветки, хранится активный пакет изменений, предложения и история применения. `change-summary.md` и пакет экспорта остаются производными представлениями.

## Команды

| Команда | Назначение |
| --- | --- |
| `madspec change init` | Инициализировать хранилище изменений ветки и зафиксировать базовую точку сравнения |
| `madspec change propose` | Собрать ожидающий применения пакет изменений из текущего состояния ветки |
| `madspec change diff` | Показать вычисленный набор различий относительно базовой точки сравнения |
| `madspec change preview` | Показать полное предложение перед применением |
| `madspec change apply` | Ратифицировать предложение и обновить каноническое состояние пакета изменений |
| `madspec change export` | Собрать переносимый пакет `bundle.json`, `summary.md`, `spec.md`, `plan.md`, `tasks.md` |
| `madspec change verify` | Проверить расхождения между активным пакетом изменений и текущим состоянием ветки |
| `madspec change summary` | Показать активный пакет изменений и его краткие показатели |

## Канонические файлы

- `.madspec/<branch>/change/state.json`
- `.madspec/<branch>/change/proposals.jsonl`
- `.madspec/<branch>/change/history.jsonl`
- `.madspec/<branch>/change/export/`
- `.madspec/<branch>/change-summary.md`

## Что делает слой изменений

- фиксирует `base_branch` и `base_revision` при `init`; повторная инициализация с другой базой запрещена
- считает различия по git, памяти ветки и состоянию процесса относительно зафиксированной базовой точки сравнения
- хранит только один активный пакет изменений на ветку в E3 v1
- отделяет ожидающее применения предложение от уже примененного пакета изменений
- не меняет код и память ветки при `apply`: команда только ратифицирует пакет изменений и пересобирает производные представления
- требует git-репозиторий; без git команды завершаются ошибкой

## Типовой порядок работы

```bash
madspec change init --base-branch main
madspec change propose \
  --title "Auth flow update" \
  --summary "Bundle auth flow code and memory changes." \
  --json-output
madspec change preview --proposal-id <ID> --json-output
madspec change apply --proposal-id <ID> --json-output
madspec change export --json-output
madspec change verify --json-output
```

`madspec change diff` можно запускать отдельно для просмотра текущего набора различий без создания нового предложения. `madspec change summary` удобен для чтения уже примененного пакета изменений.

## Основные JSON-поля

| Команда | Ключевые поля ответа |
| --- | --- |
| `init` | `branch`, `base_branch`, `base_revision`, `state_file`, `bundle_id` |
| `propose`, `preview` | `proposalId`, `bundleId`, `before`, `after`, `diff`, `warnings` |
| `diff` | `branch`, `bundleId`, `baseline`, `git_diff`, `memory_diff`, `workflow_diff` |
| `apply` | `revision`, `bundle`, `proposal`, `generated_artifacts` |
| `export` | `bundleId`, `revision`, `export_dir`, `files` |
| `verify` | `valid`, `drift`, `missing_exports`, `warnings` |
| `summary` | `bundle`, `highlights` |

## Связь с `madspec memory`

- `madspec memory retrieve --stage review --json-output` и `madspec memory retrieve --stage security --json-output` возвращают `change_context`
- `madspec memory explain --stage ... --json-output` учитывает активный пакет изменений как отдельный фактор контекста
- `--full-artifact` дополнительно возвращает `artifact_state.change`
- `review.md` и `security-audit.md` включают краткую секцию активного пакета изменений, если он ратифицирован

## Связанные документы

- [Индекс CLI-документации](README.md)
- [Команды структурированной памяти](memory.md)
- [Команда `madspec.change`](../other/madspec.change.md)
