# `madspec.policy`

## Назначение команды

`madspec.policy` — разговорный интерфейс над каноническим `madspec policy ...`. Команда помогает собрать намерение пользователя, превратить его в предложение, показать различия и применить изменение только после явного подтверждения.

## Базовый порядок работы

1. Агент читает и использует `madspec-cli-operator`.
2. Агент дополнительно читает `policy-engine`.
3. Агент показывает текущее состояние действующих правил через `madspec policy show`.
4. Любое изменение проходит через `madspec policy propose`.
5. Перед изменением состояния агент показывает предварительное сравнение и ждет подтверждения.
6. Применение выполняется только через `madspec policy apply` или `madspec policy set`.
7. После применения агент может прогнать `madspec policy validate` и показать обновленный `.madspec/system/policy.md`.

## Что считается каноническим

- `.madspec/system/policy/state.json`
- `.madspec/system/policy/proposals.jsonl`
- `.madspec/system/policy/history.jsonl`

## Что считается производным представлением

- `.madspec/system/policy.md`
- сводка правил внутри `.madspec/<BRANCH>/project-context.md`

## Обязательные правила

- не редактировать `.madspec/system/policy/state.json` вручную ради быстрого обхода команд
- не применять изменение без предварительного сравнения
- не обходить `madspec policy apply` прямым редактированием файлов
- неподдерживаемый `ruleType` трактовать как рекомендацию с режимом `guideline`

## Полезные команды

```bash
madspec policy show --json-output
madspec policy propose --policy-id ... --title ... --description ...
madspec policy apply --proposal-id ...
madspec policy validate --stage mvp.plan --toon-output
madspec policy explain --policy-id ... --json-output
```
