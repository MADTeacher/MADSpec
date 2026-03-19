# `madspec policy`

Группа `madspec policy` управляет единым проектным набором правил в MADSpec. Правила живут в `.madspec/system/policy/` и дополняют память, привязанную к ветке: сами описания правил, предложения и история изменений являются каноническим источником истины, а `.madspec/system/policy.md` и `project-context.md` остаются производными представлениями.

## Команды

| Команда | Назначение |
| --- | --- |
| `madspec policy init` | Инициализировать хранилище правил и производный артефакт |
| `madspec policy show` | Показать действующие правила и ожидающие применения предложения |
| `madspec policy propose` | Создать ожидающее применения предложение с предварительным сравнением |
| `madspec policy set` | Создать и сразу применить предложение |
| `madspec policy apply` | Применить ожидающее применения предложение |
| `madspec policy deprecate` | Вывести пользовательское правило из действия через цикл предложений |
| `madspec policy validate` | Проверить состояние ветки на соответствие действующим правилам |
| `madspec policy history` | Показать предложения и историю применений |
| `madspec policy explain` | Объяснить правило или предложение и его влияние на текущий контекст |
| `madspec policy export` | Пересобрать `.madspec/system/policy.md` |

## Канонические файлы

- `.madspec/system/policy/state.json`
- `.madspec/system/policy/proposals.jsonl`
- `.madspec/system/policy/history.jsonl`
- `.madspec/system/policy.md`

## Что делает слой правил

- хранит единый для проекта набор действующих и выведенных из действия правил
- отделяет цикл предложений от текущего примененного состояния
- добавляет `policy_context` в `madspec memory retrieve`
- использует единый механизм проверки для `madspec policy validate` и точек встраивания в процесс
- пересобирает `.madspec/system/policy.md` и `project-context.md` после применения изменений

## Встроенные проверяемые правила v1

В E1 механизм правил поддерживает только текущие инварианты процесса:

- `code_steps_require_required_tdd`
- `non_code_steps_forbid_required_tdd`
- `non_required_tdd_requires_waived_phase`
- `completed_code_steps_require_tdd_evidence`

Пользовательские правила с неподдерживаемым `ruleType` автоматически нормализуются в рекомендацию с режимом `guideline` и не блокируют изменения состояния процесса.

## Типовой порядок работы

```bash
madspec policy init
madspec policy show --json-output
madspec policy propose \
  --policy-id keep-http-handlers-thin \
  --title "Keep HTTP handlers thin" \
  --description "Move orchestration into services" \
  --applies-to-stage mvp.architecture
madspec policy apply --proposal-id <ID>
madspec policy validate --stage mvp.plan --json-output
```

## Связь с `madspec memory`

- `madspec memory retrieve --stage ... --json-output` теперь возвращает `policy_context`
- `--full-artifact` дополнительно возвращает `artifact_state.policy`
- `madspec memory validate` продолжает проверять согласованность рабочего состояния и представлений и теперь также учитывает слой правил

## Связанные документы

- [Индекс CLI-документации](README.md)
- [Команды структурированной памяти](memory.md)
- [Команда `madspec.policy`](../other/madspec.policy.md)
