# Other Workflows

Этот раздел описывает cross-cutting команды, которые могут запускаться после появления заметного change set и branch context.

## Команды

- [`review`](madspec.review.md) — change-aware анализ качества реализации, соответствия intent ветки и improvement backlog
- [`security`](madspec.security.md) — pragmatic security/privacy audit по коду, зависимостям, архитектуре и обработке данных

## Общие свойства

- обе команды branch-aware и опираются на `.madspec/<BRANCH>/memory/`
- generated artifacts не блокируют выполнение, но используются как дополнительные evidence sources
- основным результатом работы являются validated records, questions, decisions и pending actions в structured memory
