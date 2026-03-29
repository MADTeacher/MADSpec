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
7. Для вопросов про семантический поиск и состояние провайдера агент использует `madspec memory search` или `madspec memory retrieve`, потому что именно они возвращают `semantic_runtime` и структурированную ошибку `kind="embedding_provider_error"` при проблемах с локальной семантической моделью.
8. Если пользователь менял `memory.embeddings`, агент дополнительно проверяет `madspec memory status`, `madspec memory db-status` или `madspec memory doctor`, при необходимости запускает `madspec memory bootstrap-model`, и только потом проверяет, подтверждено ли активное пространство индекса переиндексацией.
9. Если пользователь хочет очистить semantic knowledge или project-level знания, агент использует `madspec memory semantic retrieve`, `madspec memory semantic prune` и `madspec memory semantic replace`, а не ручное редактирование `semantic/*.jsonl` или `SQLite`. Эти команды работают с записями со статусами `validated`, `obsolete`, `conflicted`. Для branch-scoped cleanup в claimed `Phase 2` session агент ожидает auto-publish proposal и затем применяет его через `madspec memory proposals apply`.
10. Если вопрос именно про semantic inconsistencies, агент смотрит `madspec memory doctor --json-output` и использует новый блок `semantic_integrity`, а не пытается выводить состояние semantic layer по косвенным признакам.
11. Если `semantic_integrity` показывает residue только в неактивных пространствах индекса, агент сначала использует `madspec memory gc vector-namespaces --dry-run`, а не запускает полный `reindex` по инерции.

## Что считается каноническим

- `.madspec/system/memory/memory.sqlite`
- `.madspec/system/memory/lancedb/` как корень векторного хранилища и активное пространство индекса внутри него
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
- если кэш локальной семантической модели не готов или `doctor`/`db-status` показывают `reindex required`, не считать конфиг самодостаточным: сначала нужно выполнить `madspec memory bootstrap-model`, затем `madspec memory reindex`

## Полезные команды

```bash
madspec memory doctor --json-output
madspec memory bootstrap-model --json-output
madspec memory semantic retrieve --scope branch --branch main --json-output
madspec memory gc vector-namespaces --dry-run --json-output
madspec memory explain --stage mvp.plan --toon-output
madspec memory why-next-step --stage mvp.implement --json-output
madspec memory timeline --json-output
madspec memory conflicts --json-output
madspec memory inspect-record --id <RECORD_ID> --json-output
```
