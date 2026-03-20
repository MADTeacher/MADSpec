---
description: Подбор, активация и объяснение субагентных ролей через канонические `madspec agents ...` команды
---

## Пользовательский ввод

```text
$ARGUMENTS
```

## Обязательные навыки

- Перед началом работы обязательно найди и прочитай навык `madspec-cli-operator`.
- Затем найди и прочитай навык `subagent-role-advisor`.

## Назначение

`madspec.agents` — это разговорный слой над каноническими командами `madspec agents ...`.
Он помогает выбрать профиль субагентов, понять, какие роли активны в текущей среде, создать или изменить проектные роли и получить объяснение по native/fallback-режиму, но не подменяет канонический state.

## Канонический источник истины

- `.madspec/config.json`
- `.madspec/system/agents/state.json`
- `.madspec/system/agents/catalog.json`
- `.madspec/system/agents/bodies/`
- `.madspec/system/agents/proposals.jsonl`
- `.madspec/system/agents/history.jsonl`
- `.madspec/system/agents.md`

## Порядок работы

1. Сначала посмотри текущий профиль через `madspec agents profile --json-output`.
2. Для базовой рекомендации используй `madspec agents recommend --json-output`.
3. Для просмотра effective catalog используй `madspec agents subagents list --json-output` и `madspec agents subagents show --subagent-id ... --json-output`.
4. Для создания проектной роли используй `madspec agents subagents create --subagent-id ... --from-file ... --body-file ... --json-output`.
5. Для изменения project role или override built-in роли используй `madspec agents subagents update --subagent-id ... --from-file ... [--body-file ...] --json-output`.
6. Для удаления project role или project override используй `madspec agents subagents remove --subagent-id ... [--force] --json-output`.
7. Для изменения набора активных ролей сначала создай proposal через `madspec agents propose-profile --json-output`.
8. Применяй профиль только через `madspec agents apply-profile --proposal-id ... --json-output`.
9. Для точечного включения и отключения ролей используй `madspec agents subagents enable` и `disable`.
10. Для любой роли извлекай канонический контекст через `madspec agents subagents context --subagent-id ... --toon-output`, а `--json-output` оставляй только для случаев, когда нужен именно JSON-контракт.

## Правила

- Не определяй активную среду только по наличию директорий, если `.madspec/config.json` уже задает `agentEnvironment`.
- Не редактируй `.madspec/system/agents/*.json*` вручную.
- Не редактируй `.madspec/system/agents/bodies/*.md` как источник истины в обход `create/update`, если нужно сохранить согласованный каталог роли.
- Не обещай единый runtime субагентов там, где среда его не предоставляет нативно.
- Если среда использует fallback-адаптер, явно объясни это пользователю.
