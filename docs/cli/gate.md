# `madspec gate`

Группа `madspec gate` управляет слоем контрольных проверок для ветки MADSpec. Она не дублирует память, `progress.json` или правила проекта, а собирает их результаты в единый машиночитаемый статус, хранит примененные исключения и ведет аудит запусков.

## Команды

| Команда | Назначение |
| --- | --- |
| `madspec gate status` | Показать вычисленный статус проверок без аудита запуска |
| `madspec gate run` | Вычислить проверки для конкретного перехода и записать событие аудита |
| `madspec gate explain` | Показать детали результатов вместе с предложениями и историей |
| `madspec gate propose-waiver` | Создать ожидающее применения предложение на исключение для допускающей исключение проверки |
| `madspec gate apply-waiver` | Применить ожидающее предложение и активировать исключение |
| `madspec review status` | Алиас для `madspec gate status --stage review` |
| `madspec security status` | Алиас для `madspec gate status --stage security` |

## Канонические файлы

- `.madspec/<branch>/gates/state.json`
- `.madspec/<branch>/gates/proposals.jsonl`
- `.madspec/<branch>/gates/history.jsonl`

В `state.json` хранятся только примененные исключения и ревизия слоя. Команды `status` и `explain` пересчитывают снимки состояния на лету и не используют отдельный сохраненный статус-файл.

## Что делает слой проверок

- нормализует результаты проверок к форме `gateId`, `family`, `scope`, `subjectId`, `blocking`, `waivable`, `status`, `message`, `sourceIds`
- собирает проверки из валидации рабочего состояния памяти, предварительных инвариантов planning/implementation и пользовательских правил проекта
- показывает единый итоговый статус: `passed`, `warning`, `pending` или `blocked`
- позволяет предложить и применить исключение только для допускающих это проверок
- пишет журнал аудита для `madspec gate run`

## Каталог проверок v1

- `dependency_readiness` — готовность зависимостей шага
- `runtime_validity` — целостность `progress` и рабочего состояния, а также предварительные инварианты
- `policy_compliance` — результаты проверки обязательных и рекомендательных правил проекта
- `stage_ratification` — статус ратификации `review` и `security`

## Статусы и агрегирование

Отдельная проверка может быть в одном из состояний:

- `passed`
- `failed`
- `warning`
- `pending`
- `waived`
- `not_applicable`

Итоговый статус вычисляется так:

- любая блокирующая проверка со статусом `failed` -> `blocked`
- иначе любой `pending` -> `pending`
- иначе любой `warning` -> `warning`
- иначе -> `passed`

## Процесс исключений

Типовой порядок работы:

```bash
madspec gate status --stage mvp.implement --operation complete-step --json-output
madspec gate explain --stage mvp.implement --operation complete-step --json-output
madspec gate propose-waiver \
  --stage review \
  --gate-id <GATE_ID> \
  --reason "Команда временно принимает риск до отдельной доработки" \
  --json-output
madspec gate apply-waiver --proposal-id <PROPOSAL_ID> --json-output
```

`apply-waiver` меняет только состояние слоя проверок внутри ветки. Он не правит память, код, правила проекта и не завершает переход автоматически.

## Связь с `madspec memory`

- `madspec memory register-step`, `start-step`, `checkpoint-step`, `complete-step` и `checkpoint --stage review|security` выполняют предварительную проверку через общий вычислитель контрольных проверок
- `madspec memory explain` и `madspec memory why-next-step` возвращают `gate_summary`
- `project-context.md`, step contexts, `review.md` и `security-audit.md` теперь включают сводку проверок и активных исключений

## Связанные документы

- [Индекс CLI-документации](README.md)
- [Команды структурированной памяти](memory.md)
- [Команда `madspec.gate`](../other/madspec.gate.md)
