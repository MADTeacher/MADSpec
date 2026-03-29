---
description: Контролируемое сравнение и слияние памяти между ветками через канонический поток compare -> propose -> preview -> resolve -> merge
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательные навыки

- Перед началом работы обязательно найди и прочитай `madspec-cli-operator`.
- Затем найди и прочитай `madspec-merge-assistant`.

## Язык и стиль

- В русскоязычных ответах не смешивай русский и английский без явной необходимости.
- Английский используй только для имен команд, путей, файлов, API и других точных идентификаторов.
- Перед завершением обязательно перечитай ответ и убери неуместные англицизмы, кальки и смешанные конструкции.

## Назначение

`madspec.merge` — разговорный слой над каноническими командами `madspec memory compare-branches`, `propose-merge`, `preview-merge`, `resolve-conflict`, `merge-branches` и `promote-branch-knowledge`.

Команда помогает:

1. объяснить различия памяти между ветками;
2. подготовить предложение на слияние;
3. разобрать конфликты и выбрать стратегию;
4. продвинуть подтвержденные знания на уровень проекта.

## Канонический источник истины

- `.madspec/system/memory/memory.sqlite`
- `.madspec/<BRANCH>/memory/`
- проектные записи знаний в `records` с branch `__project__`

Производные Markdown-файлы в `.madspec/<BRANCH>/` не являются источником истины для merge-операций.

## Порядок работы

1. Сначала сравни ветки через `madspec memory compare-branches --json-output`.
2. Если пользователь хочет готовить merge, создай предложение через `madspec memory propose-merge --json-output`.
3. Перед любым применением обязательно покажи `madspec memory preview-merge --proposal-id ... --json-output`.
4. Если есть конфликты, разрешай их только через `madspec memory resolve-conflict`.
5. Применяй merge только через `madspec memory merge-branches --proposal-id ... --json-output`.
6. Для переноса подтвержденных знаний на уровень проекта используй `madspec memory promote-branch-knowledge --json-output`.

## Правила

- Не редактируй `.madspec/<BRANCH>/memory/*.json*` и `.jsonl` вручную ради merge.
- Не пропускай `preview-merge` перед `merge-branches`.
- Не применяй merge без явного подтверждения пользователя.
- Не подменяй канонический merge разговорным объяснением: чат может только подготовить решение, но не выполнить его вслепую.
