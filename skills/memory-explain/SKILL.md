---
name: memory-explain
description: Операционный навык для объяснения и диагностики структурированной памяти в MADSpec. Использовать, когда нужно понять, почему выбран следующий шаг, какие записи влияют на текущий контекст, где появились конфликты, или как проверить состояние памяти через `madspec memory ...`.
---

# `memory-explain`

## Когда использовать

Используй этот навык, когда пользователь просит:

- объяснить, почему система выбрала следующий шаг
- показать, какие записи и результаты поиска по смыслу влияют на текущий контекст
- посмотреть историю изменений контекста по ветке или стадии
- диагностировать рассинхронизацию представлений, проблемы индексирования или поломку памяти
- инспектировать конкретную запись памяти по `record_id`

## Канонический порядок работы

1. Прочитай текущее рабочее состояние через `madspec memory retrieve --stage ... --toon-output`, если этот контекст будет читать агент; `--json-output` оставляй только для машинной интеграции.
2. Для общей диагностики запускай `madspec memory doctor --json-output`.
3. Для объяснений используй только канонические команды:
   - `madspec memory explain`
   - `madspec memory why-next-step`
   - `madspec memory timeline`
   - `madspec memory conflicts`
   - `madspec memory inspect-record`
4. Не редактируй `.madspec/<BRANCH>/memory/*`, `.madspec/system/memory/*` и производные представления вручную ради “быстрой починки”.

## Источник истины

- `.madspec/system/memory/memory.sqlite`
- `.madspec/system/memory/lancedb/` как корень векторного хранилища и его активное пространство индекса `provider/model/revision/dimension`
- `.madspec/<BRANCH>/memory/progress.json`
- `.madspec/<BRANCH>/memory/stages/*.json`
- `.madspec/<BRANCH>/memory/working/*.json*`
- `.madspec/<BRANCH>/memory/episodes/*.jsonl`
- `.madspec/<BRANCH>/memory/semantic/*.jsonl`

`project-context.md`, `implementation-context.md`, `planning-context-cache.md` и другие Markdown-файлы остаются производными представлениями.

## Ограничения E2

- `madspec memory doctor` диагностирует, но не лечит состояние автоматически
- `madspec memory conflicts` в E2 показывает только явные записи со статусом `conflicted` и формальные проблемы целостности
- `madspec memory inspect-record` работает только с каноническим `record_id`, а не с идентификатором снимка или артефакта
- разговорный слой может задавать вопросы и объяснять, но не должен обходить канонические команды памяти

## Полезные команды

```bash
madspec memory doctor --json-output
madspec memory explain --stage mvp.plan --toon-output
madspec memory why-next-step --stage mvp.implement --json-output
madspec memory timeline --stage mvp.plan --json-output
madspec memory conflicts --json-output
madspec memory inspect-record --id <RECORD_ID> --json-output
```
