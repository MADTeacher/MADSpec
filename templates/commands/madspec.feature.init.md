---
description: Feature - Инициализация новой функциональности через memory-first workflow
---

## Пользовательский ввод

```text
$ARGUMENTS
```

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением, если он не пустой.

## Правила диалога

- Задавай вопросы строго по одному.
- Не выдавай длинный список вопросов заранее.
- Сначала исследуй репозиторий, затем спрашивай только то, что нельзя восстановить из кода и артефактов.

## Structured Memory First

- Каноническое состояние этапа init хранится в `.madspec/<BRANCH>/memory/stages/feature.init.json`.
- `project-analysis.md`, `feature-context.md`, `tech-stack.md`, `architecture.md` и `project-context.md` являются generated views.
- В обычных ходах диалога сначала используй `madspec memory retrieve --stage feature.init --json-output`.
- Для накопления состояния используй `madspec memory capture --stage feature.init ...`.
- Для завершения этапа используй `madspec memory checkpoint --stage feature.init --summary ...`.
- После любого изменения memory workflow views должны пересобираться через `madspec memory consolidate` и проходить `madspec memory validate`.

## Цель этапа

Подготовить feature-ветку и зафиксировать в canonical memory:

- цель фичи, проблему и ожидаемый результат;
- каталог функций `P1/P2/P3` с явными `ID`;
- анализ проекта и точки интеграции;
- технический и архитектурный контекст, достаточный для `madspec.feature.plan`.

## Порядок работы

1. Определи текущую ветку через `madspec git current-branch`.
2. Если пользователь ещё не работает в feature-ветке, создай её через `madspec git create-branch feature/<short-name>`.
3. Работай только с branch-aware путями `.madspec/<BRANCH>/...`.
4. Проанализируй проект:
   - стек, фреймворки, package managers, test runners, CI;
   - структуру директорий и ключевые модули;
   - существующие точки интеграции для новой фичи;
   - файлы для изменения и новые файлы.
5. Если пользовательский ввод не покрывает продуктовую цель, задай один уточняющий вопрос.
6. Сохрани результат анализа в canonical state через `madspec memory capture --stage feature.init`:
   - `--feature-goal`
   - `--problem`
   - `--expected-outcome`
   - `--project-type`
   - `--framework`
   - `--structure-note`
   - `--feature-p1/--feature-p2/--feature-p3` в формате `<id>::<title>::<description>`
   - `--existing-module`
   - `--modified-file`
   - `--new-file`
   - `--interface-contract`
   - `--dependency`
   - `--risk`
   - `--recommendation`
   - `--tech-note`
   - `--architecture-note`
   - `--next-action`
7. Повтори `madspec memory retrieve --stage feature.init --json-output` и проверь `feature_init_status`.
8. Перед завершением при необходимости запроси `madspec memory retrieve --stage feature.init --json-output --full-artifact`.
9. Зафиксируй этап через `madspec memory checkpoint --stage feature.init --summary "<validated summary>"`.

## Что считается результатом

- `.madspec/<BRANCH>/memory/stages/feature.init.json` заполнен и ratified.
- Generated views пересобраны автоматически:
  - `.madspec/<BRANCH>/project-analysis.md`
  - `.madspec/<BRANCH>/feature-context.md`
  - `.madspec/<BRANCH>/tech-stack.md`
  - `.madspec/<BRANCH>/architecture.md`
  - `.madspec/<BRANCH>/project-context.md`
- В `project-analysis.md` функции используют явные `ID`, а не только текстовые labels.
- Ветка готова к `madspec.feature.plan`.

## Важные запреты

- Не считай `project-analysis.md` или `feature-context.md` source of truth.
- Не создавай и не редактируй generated views вручную, если то же изменение должно быть выражено через memory-команды.
- Не хардкодь имя feature-ветки в путях; используй только `.madspec/<BRANCH>/...`.

## Завершение

После завершения предложи следующий шаг: `/madspec.feature.plan`.
