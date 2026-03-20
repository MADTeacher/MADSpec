# `madspec.memory`

## Назначение команды

`madspec.memory` — разговорный интерфейс над каноническими командами объяснения и диагностики `madspec memory ...`. Он нужен, когда пользователь хочет спросить обычным языком, почему выбран следующий шаг, какие записи влияют на контекст, где есть конфликт или каково общее состояние структурированной памяти.

## Базовый порядок работы

1. Агент читает и использует навык `madspec-cli-operator`.
2. Агент дополнительно читает навык `memory-explain`.
3. Для общей проверки состояния агент использует `madspec memory doctor`.
4. Для объяснения контекста агент использует `madspec memory explain`.
5. Для объяснения выбора шага агент использует `madspec memory why-next-step`.
6. Для истории и конфликтов агент использует `madspec memory timeline`, `madspec memory conflicts` и `madspec memory inspect-record`.

## Что считается каноническим

- `.madspec/system/memory/memory.sqlite`
- `.madspec/system/memory/lancedb/`
- `.madspec/<BRANCH>/memory/`

## Что считается производным представлением

- `.madspec/<BRANCH>/project-context.md`
- `.madspec/<BRANCH>/planning-context-cache.md`
- `.madspec/<BRANCH>/steps/*/planning-context.md`
- `.madspec/<BRANCH>/steps/*/implementation-context.md`

## Обязательные правила

- не редактировать файлы памяти и производные представления вручную ради “быстрой диагностики”
- не обходить `madspec memory doctor` и `madspec memory explain` самодельными выводами о слое хранения
- не лечить состояние автоматически: в E2 этот слой только объясняет и диагностирует
- помнить, что `madspec memory conflicts` в E2 показывает только явные записи со статусом `conflicted` и формальные проблемы целостности

## Полезные команды

```bash
madspec memory doctor --json-output
madspec memory explain --stage mvp.plan --toon-output
madspec memory why-next-step --stage mvp.implement --json-output
madspec memory timeline --json-output
madspec memory conflicts --json-output
madspec memory inspect-record --id <RECORD_ID> --json-output
```
