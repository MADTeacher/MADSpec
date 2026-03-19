---
name: gate-orchestrator
description: Операционный навык для слоя контрольных проверок в MADSpec. Использовать, когда нужно показать статус через `madspec gate status`, объяснить блокировку перехода, выполнить аудируемую проверку или управлять предложениями на исключения через `madspec gate ...`.
---

# `gate-orchestrator`

## Когда использовать

Используй этот навык, когда пользователь просит:

- объяснить, почему переход стадии или шага блокируется
- проверить готовность перед `register-step`, `start-step`, `checkpoint-step`, `complete-step`
- посмотреть статус `review` или `security`
- предложить или применить исключение для допускающей исключение проверки
- понять активные исключения и историю запусков общего вычислителя проверок

## Язык и стиль

- В русскоязычных ответах не смешивай русский и английский без явной необходимости.
- Английский используй только для имен команд, путей, файлов, API и других точных идентификаторов.
- Перед завершением обязательно перечитай ответ и убери неуместные англицизмы, кальки и смешанные конструкции.

## Канонический порядок работы

1. Сначала прочитай текущее состояние через `madspec gate status --json-output` или `madspec gate explain --json-output`.
2. Для конкретного перехода используй `madspec gate run --stage ... --operation ... --json-output`.
3. Если нужно исключение, сначала создай предложение через `madspec gate propose-waiver`.
4. Покажи пользователю предварительное представление предложения и дождись явного подтверждения.
5. Применяй исключение только через `madspec gate apply-waiver`.

## Источник истины

- `.madspec/<BRANCH>/gates/state.json`
- `.madspec/<BRANCH>/gates/proposals.jsonl`
- `.madspec/<BRANCH>/gates/history.jsonl`

В `state.json` хранится только состояние примененных исключений и ревизия. Снимки состояния контрольных проверок всегда вычисляются из памяти, `progress`, рабочего состояния, записей контрольных точек и правил проекта.

## Ограничения E4

- Исключение привязано к ветке и не имеет срока действия в E4 v1
- Исключение не меняет память, код, правила проекта и не завершает переход автоматически
- Ошибки целостности, битые зависимости шагов и встроенные TDD-инварианты нельзя ослаблять через исключение
- `review status` и `security status` — это только алиасы для чтения над общим вычислителем проверок

## Полезные команды

```bash
madspec gate status --stage mvp.implement --operation complete-step --json-output
madspec gate run --stage review --operation validate --json-output
madspec gate explain --stage feature.plan --operation register-step --step-id step-02-auth --json-output
madspec gate propose-waiver --stage review --gate-id <GATE_ID> --reason "..." --json-output
madspec gate apply-waiver --proposal-id <PROPOSAL_ID> --json-output
madspec review status --json-output
madspec security status --json-output
```
