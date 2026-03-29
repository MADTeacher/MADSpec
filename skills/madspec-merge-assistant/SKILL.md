---
name: madspec-merge-assistant
description: Операционный навык для межветочного сравнения, подготовки предложений на слияние, разрешения конфликтов и продвижения знаний на уровень проекта через `madspec memory ...`.
---

# `madspec-merge-assistant`

## Когда использовать

Используй этот навык, когда пользователь просит:

- сравнить память двух веток;
- перенести подтвержденные факты, решения или контракты из одной ветки в другую;
- объяснить конфликты перед слиянием памяти;
- продвинуть подтвержденные знания на уровень проекта.

## Язык и стиль

- В русскоязычных ответах не смешивай русский и английский без явной необходимости.
- Английский используй только для имен команд, путей, файлов, API и других точных идентификаторов.
- Перед завершением обязательно перечитай ответ и убери неуместные англицизмы, кальки и смешанные конструкции.

## Канонический порядок работы

1. Сначала выполни `madspec memory compare-branches --json-output`.
2. Для подготовки слияния создай предложение через `madspec memory propose-merge --json-output`.
3. Перед применением всегда покажи `madspec memory preview-merge --proposal-id ... --json-output`.
4. Если есть конфликты, меняй только предложение через `madspec memory resolve-conflict`.
5. Применяй слияние только через `madspec memory merge-branches --proposal-id ... --json-output`.
6. Для переноса подтвержденных знаний в память проекта используй `madspec memory promote-branch-knowledge --json-output`.

## Источник истины

- `.madspec/system/memory/memory.sqlite`
- `.madspec/<BRANCH>/memory/`
- проектные записи знаний с branch `__project__`

`project-context.md`, `planning-context-cache.md`, `implementation-context.md` и другие Markdown-файлы остаются производными представлениями.

## Ограничения E5

- слияние памяти не делает `git merge` и не меняет git refs
- слияние применяется только к структурированной памяти и ее производным представлениям
- по умолчанию переносится только подтвержденное знание
- разговорный слой не имеет права применять слияние без явного `preview -> confirmation -> merge-branches`

## Полезные команды

```bash
madspec memory compare-branches --source-branch feature/auth --target-branch main --json-output
madspec memory propose-merge --source-branch feature/auth --target-branch main --json-output
madspec memory preview-merge --proposal-id <PROPOSAL_ID> --json-output
madspec memory resolve-conflict --proposal-id <PROPOSAL_ID> --conflict-id <CONFLICT_ID> --resolution take_source --json-output
madspec memory merge-branches --proposal-id <PROPOSAL_ID> --json-output
madspec memory promote-branch-knowledge --source-branch feature/auth --json-output
```
