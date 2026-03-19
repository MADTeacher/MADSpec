---
name: change-engine
description: Операционный навык для слоя изменений ветки в MADSpec. Использовать, когда нужно инициализировать базовую точку сравнения ветки, предложить, показать, применить, экспортировать или проверить пакет изменений через `madspec change ...`.
---

# `change-engine`

## Когда использовать

Используй этот навык, когда пользователь просит:

- подготовить пакет изменений для текущей ветки
- показать текущее предложение или активный пакет изменений
- зафиксировать базовую точку сравнения ветки перед передачей результата или `review`
- экспортировать пакет `summary/spec/plan/tasks`
- проверить расхождения через `madspec change verify`

## Язык и стиль

- В русскоязычных ответах не смешивай русский и английский без явной необходимости.
- Английский используй только для имен команд, путей, файлов, API и других точных идентификаторов.
- Перед завершением обязательно перечитай ответ и убери неуместные англицизмы, кальки и смешанные конструкции.

## Канонический порядок работы

1. Если change store еще не существует, запусти `madspec change init --json-output`.
2. Для нового пакета изменений создай предложение через `madspec change propose`.
3. Перед любым применением покажи `madspec change preview --proposal-id ... --json-output`.
4. Применяй пакет изменений только через `madspec change apply --proposal-id ...`.
5. После применения при необходимости запускай `madspec change export` и `madspec change verify`.

## Источник истины

- `.madspec/<branch>/change/state.json`
- `.madspec/<branch>/change/proposals.jsonl`
- `.madspec/<branch>/change/history.jsonl`

`change-summary.md` и `.madspec/<branch>/change/export/` — производные представления.

## Ограничения E3

- слой изменений требует git-репозиторий
- базовая точка сравнения фиксируется при `init` и не должна тихо переопределяться
- в E3 v1 на ветку поддерживается только один активный пакет изменений
- `apply` не делает `merge`, не накатывает `patch` и не меняет код; он только ратифицирует пакет изменений

## Полезные команды

```bash
madspec change init --base-branch main --json-output
madspec change propose --title ... --summary ... --json-output
madspec change preview --proposal-id ... --json-output
madspec change diff --json-output
madspec change apply --proposal-id ... --json-output
madspec change export --json-output
madspec change verify --json-output
madspec change summary --json-output
```

## Связь с памятью и качеством

- `madspec memory retrieve --stage review|security --json-output` возвращает `change_context`
- `madspec memory explain --stage ... --json-output` учитывает активный пакет изменений в объяснении контекста
- `review.md` и `security-audit.md` используют активный пакет изменений как краткую сводку ратифицированных изменений
