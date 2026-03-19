---
description: Управление пакетом изменений ветки через цикл инициализации, предложения, подтверждения, применения и проверки
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательные навыки

- Перед началом работы обязательно найди и прочитай `madspec-cli-operator`.
- Затем найди и прочитай `change-engine`.

## Язык и стиль

- В русскоязычных ответах не смешивай русский и английский без явной необходимости.
- Английский используй только для имен команд, путей, файлов, API и других точных идентификаторов.
- Перед завершением обязательно перечитай ответ и убери неуместные англицизмы, кальки и смешанные конструкции.

## Назначение

`madspec.change` — это разговорный слой над каноническими командами `madspec change ...`. Ты можешь принимать намерение пользователя в свободной форме, но любое изменение состояния слоя изменений обязано пройти через:

1. `madspec change init` при отсутствии change store
2. `madspec change propose`
3. `madspec change preview`
4. явное подтверждение пользователя
5. `madspec change apply`

`madspec change export`, `madspec change verify` и `madspec change summary` используются как отдельные шаги после применения или для проверки без изменения состояния.

## Канонический источник истины

- `.madspec/<BRANCH>/change/state.json`
- `.madspec/<BRANCH>/change/proposals.jsonl`
- `.madspec/<BRANCH>/change/history.jsonl`

`change-summary.md` и файлы в `.madspec/<BRANCH>/change/export/` являются производными представлениями, а не основным источником истины.

## Порядок работы

1. Сначала определи ветку через `madspec git current-branch` или используй явный `--branch`.
2. Если пользователь хочет только увидеть текущее состояние, используй `madspec change summary`, `madspec change diff` и `madspec change verify`.
3. Если пользователь хочет подготовить или обновить пакет изменений:
   - проверь, инициализирован ли слой через `madspec change init --json-output`
   - создай предложение через `madspec change propose`
   - покажи `diff.changedFields`, предупреждения и влияние на шаги
   - дождись явного подтверждения
   - затем выполни `madspec change apply --proposal-id <ID>`
4. После применения при необходимости выполни `madspec change export --json-output`.

## Правила

- Не редактируй `state.json`, `proposals.jsonl`, `history.jsonl`, `change-summary.md` и export-файлы вручную.
- Не пропускай `preview` перед `apply`.
- Не используй `change-summary.md` как источник истины.
- Если git не инициализирован, сначала объясни это пользователю и предложи `madspec git init`.
