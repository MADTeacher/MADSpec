# `madspec.change`

`madspec.change` — разговорный слой над каноническими командами `madspec change ...`. Он помогает работать с пакетом изменений в свободной форме, но любые изменения состояния обязаны проходить через CLI и явное подтверждение пользователя перед `apply`.

## Канонический источник истины

- `.madspec/<BRANCH>/change/state.json`
- `.madspec/<BRANCH>/change/proposals.jsonl`
- `.madspec/<BRANCH>/change/history.jsonl`

`change-summary.md` и пакеты экспорта в `.madspec/<BRANCH>/change/export/` являются производными представлениями.

## Порядок работы

1. Сначала определи текущую ветку через `madspec git current-branch` или используй явный `--branch`.
2. Если change store еще не создан, запусти `madspec change init --json-output`.
3. Для подготовки изменения создай предложение через `madspec change propose --json-output`.
4. Покажи пользователю `preview`, `diff.changedFields`, предупреждения и влияние на шаги реализации.
5. Применяй пакет изменений только после явного подтверждения через `madspec change apply --proposal-id <ID>`.
6. После применения при необходимости выполни `madspec change export` и `madspec change verify`.

## Правила

- не редактируй `state.json`, `proposals.jsonl`, `history.jsonl` и export-файлы вручную
- не применяй пакет изменений без предварительного `preview`
- не используй `change-summary.md` как источник истины
- если git не инициализирован, сначала объясни это пользователю и предложи `madspec git init`

## Связь с другими командами

- для проверки влияния пакета изменений на `review` и `security` читай `change_context` через `madspec memory retrieve --stage review|security --json-output`
- для общего объяснения состояния можно использовать `madspec change summary --json-output`
- для проверки расхождений без изменения состояния используй `madspec change verify --json-output`
