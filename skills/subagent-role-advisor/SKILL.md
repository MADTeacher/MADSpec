---
name: subagent-role-advisor
description: Навык выбора, объяснения и безопасного применения субагентных ролей поверх канонического `madspec agents ...` механизма.
---

# `subagent-role-advisor`

## Когда использовать

Используй этот навык, когда пользователь хочет:

- понять, какие субагенты доступны в текущем проекте
- создать новую проектную роль субагента
- изменить project role или override встроенной роли
- удалить project role или override built-in роли
- включить или отключить встроенную или проектную роль субагента
- разобраться, есть ли в текущей среде native subagents или только fallback-режим
- получить роль-специфический контекст без ручного чтения нескольких MADSpec-слоев

## Принцип

Этот навык не является runtime-диспетчером субагентов.

Его задача:

1. объяснить, как субагентный слой работает в текущей среде;
2. показать effective catalog ролей, их происхождение и активность;
3. вызвать канонические команды `madspec agents ...`;
4. направить роль к `madspec agents subagents context`, а не к ручному чтению state-файлов.

## Канонические команды

- `madspec agents profile`
- `madspec agents recommend`
- `madspec agents propose-profile`
- `madspec agents apply-profile`
- `madspec agents subagents list`
- `madspec agents subagents show`
- `madspec agents subagents create`
- `madspec agents subagents update`
- `madspec agents subagents remove`
- `madspec agents subagents enable`
- `madspec agents subagents disable`
- `madspec agents subagents context`

## Правила

- Не редактируй `.madspec/system/agents/state.json` вручную.
- Не редактируй `.madspec/system/agents/catalog.json` и `.madspec/system/agents/bodies/*.md` вручную, если изменение должно попасть в каноническую историю ролей.
- Не подменяй `agentEnvironment` эвристикой по директориям, если явное состояние уже записано в конфиге.
- Не обещай параллельное исполнение, если текущая среда использует fallback-адаптер.
- Для любого role-specific анализа сначала извлекай контекст через `madspec agents subagents context --subagent-id ... --toon-output`; `--json-output` оставляй только для машинной интеграции.
