# MVP Tech

Актуальная документация по тому, как сейчас работает `madspec.mvp.tech` в MADSpec после перехода на memory-first pipeline.

## Источник истины

Для `mvp.tech` реальные данные этапа хранятся здесь:

- `.madspec/<BRANCH>/memory/stages/mvp.tech.json`

Derived artifacts:

- `.madspec/<BRANCH>/tech-stack.md`
- `.madspec/<BRANCH>/project-context.md`

`tech-stack.md` является generated artifact. Его нельзя считать основным файлом хранения данных и нельзя редактировать вручную.

## Рабочий цикл

1. В начале сессии агент выполняет `madspec memory retrieve --stage mvp.tech --json-output`
2. В обычной работе агент опирается на `tech_status`
3. После каждого подтвержденного trade-off агент вызывает `madspec memory capture --stage mvp.tech ...`
4. Перед завершением агент запрашивает полный `artifact_state.tech` через `--full-artifact`
5. Этап завершается `madspec memory checkpoint --stage mvp.tech --summary ... --evidence .madspec/<BRANCH>/tech-stack.md`

## Что попадает в `mvp.tech.json`

- `projectType`
- `stackOverview`
- `requirements`
- `preferences`
- `constraints`
- `components`
- `libraries`
- `codeOrganization`
- `alternatives`
- `nextActions`
- `checkpointSummary`
- `revision`
- `ratifiedAt`
- `updatedAt`

## Поведение `memory retrieve`

По умолчанию `madspec memory retrieve --stage mvp.tech --json-output` возвращает:

- краткий `tech_status`
- stage-level semantic context
- пустые `episodes` и `decision_log`, если не был запрошен history
- `artifact_state.tech = null`

Полный `artifact_state.tech` возвращается только по `--full-artifact`.

## Обязательные поля для checkpoint

Checkpoint `mvp.tech` не проходит, если отсутствует хотя бы одно из следующих полей:

- `projectType`
- `stackOverview`
- хотя бы один component со slot `language`
- хотя бы один component со slot `build`
- хотя бы один testing component со slot `unit-testing`, `integration-testing`, `e2e-testing` или `testing`
- `codeOrganization`

## Инварианты

- Сначала обновляется structured memory, потом пересобираются generated views, потом выполняется validation.
- `tech-stack.md` всегда должен совпадать с render из `mvp.tech.json`.
- Любой ручной drift в `tech-stack.md` должен ловиться через `madspec memory validate`.
