---
description: Feature - Реализация новой функциональности - пошаговая реализация с валидацией и отслеживанием прогресса
---

## Пользовательский ввод

```text
$ARGUMENTS
```

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее** (никаких длинных анкет/чек-листов вопросов за раз).
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3–5 вариантов** (или попроси свободный ответ).
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный — задай **один уточняющий вопрос**, а не несколько сразу.

## Structured Memory First (обязательно)

- `progress.json`, `active-session.json`, decision log и episodes — канонический workflow state.
- `implementation-context.md` и `project-context.md` являются generated views.
- Перед началом шага сначала получай контекст через `madspec memory retrieve --stage feature.implement --json-output`.
- Для старта шага используй `madspec memory start-step --stage feature.implement`.
- Для промежуточных TDD checkpoint используй `madspec memory checkpoint-step --stage feature.implement`.
- Для завершения шага и продвижения workflow используй `madspec memory complete-step --stage feature.implement`.

## Описание

Этап **MADSpec (MADSpec Framework)** для пошаговой реализации новой функциональности. Каждый шаг:

- Выполняется последовательно (с учетом зависимостей)
- Валидируется через тесты
- Отмечается в `progress.json`
- Может быть возобновлен с любого шага

**Источники контекста:**
- `project-analysis.md` — функции P1/P2/P3 + точки интеграции
- `architecture.md` — как вписываемся в архитектуру
- `tech-stack.md` — технологии
- `steps/step-[NN]-[name]/` — описание текущего шага
- `concept.md` — опционально, дополнительный контекст

## Предварительные условия

Должен существовать `.madspec/feature/<feature-branch>/`:
- `project-analysis.md` — ключевой (функции P1/P2/P3, точки интеграции)
- `architecture.md` — архитектура
- `tech-stack.md` — технологии
- `memory/progress.json` — с запланированными шагами
- Директория `steps/` с хотя бы одним шагом
- `concept.md` — опционально, дополнительный контекст

Если условия не выполнены, предложи:
- Выполнить `/madspec.feature.init` если нет артефактов
- Выполнить `/madspec.feature.plan` если нет шагов

## Цель этапа

Реализовать функциональность по шагам:
- Выполнять задачи из шага
- Валидировать через тесты
- Отслеживать прогресс
- Обновлять артефакты

0. **Определение текущей ветки**:
   - **ВАЖНО**: Перед началом работы определи текущую ветку, выполнив `madspec git current-branch` из корня проекта
   - Команда возвращает имя ветки через stdout
   - Используй результат выполнения команды (имя ветки) для формирования путей к артефактам
   - Все пути к артефактам должны быть в формате `.madspec/<BRANCH>/...`, где `<BRANCH>` - это имя ветки, полученное из команды
   - Если ни команда, ни файл недоступны, используй значение по умолчанию `main`
   - Сохрани имя ветки для использования в дальнейших шагах

1. **Загрузка контекста:**

   Сначала выполни `madspec memory retrieve --stage feature.implement --json-output` и используй ответ как канонический workflow state.

   Прочитай:
   - `.madspec/feature/<feature-branch>/project-analysis.md` — **ключевой**:
     - Функции P1/P2/P3 которые реализуем
     - Какие файлы модифицировать
     - Какие файлы создать
     - Как интегрироваться с существующим кодом
   - `.madspec/feature/<feature-branch>/architecture.md` — как вписываемся
   - `.madspec/feature/<feature-branch>/tech-stack.md` — технологии
   - `.madspec/feature/<feature-branch>/memory/progress.json` — полное состояние workflow, если нужно сверить детали
   - `.madspec/feature/<feature-branch>/concept.md` — опционально, контекст
   - Текущий шаг:
     - `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/description.md`
     - `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/tasks.md`
     - `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/tests.md`
     - `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/validation.md`
     - `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/planning-context.md`
   - Из `progress.json` прочитай `stepMetadata["step-[NN]-[name]"]` и определи:
     - `code + required` -> шаг выполняется строго по циклу `red -> green -> refactor`
     - `non-code + waived|not-applicable` -> TDD оформлен waiver-ом, а не молчаливым обходом

2. **Определение начального шага:**

   - Если пользователь указал шаг в `$ARGUMENTS`, проверь его зависимости и запусти `madspec memory start-step --stage feature.implement --step-id <step-id>`
   - Иначе запусти `madspec memory start-step --stage feature.implement --json-output` и используй выбранный шаг из ответа

3. **Выполнение шага:**

   **3.1. Модификация файлов (из tasks.md + project-analysis.md):**
   
   Для каждого файла из tasks.md:
   - Прочитай существующий файл
   - Внеси необходимые изменения
   - Учитывай паттерны из project-analysis.md (как устроен существующий код)
   - Соблюдай контракты из architecture.md

   **3.2. Создание новых файлов (из tasks.md + project-analysis.md):**
   
   Для каждого нового файла:
   - Используй паттерны из существующего кода (из project-analysis.md)
   - Соблюдай структуру из architecture.md
   - Называй согласно конвенциям проекта

   **3.3. Интеграция (из project-analysis.md):**
   
   - Свяжи новый код с существующими модулями
   - Проверь зависимости
   - Соблюди интерфейсы

   **3.4. Отметь выполненные задачи в tasks.md:**
   ```
   - [x] Задача выполнена
   - [ ] Задача не выполнена
   ```

   **3.5. TDD цикл для code-step:**
   - Сначала подготовь focused test из секции `Red`
   - Зафиксируй failing run через `madspec memory checkpoint-step --stage feature.implement --step-id <step-id> --tdd-phase red --red-evidence "<command>"`
   - Сделай минимальную реализацию для green
   - Зафиксируй passing run через `madspec memory checkpoint-step --stage feature.implement --step-id <step-id> --tdd-phase green --green-evidence "<command>"`
   - Выполни refactor и сохрани итог через `madspec memory checkpoint-step --stage feature.implement --step-id <step-id> --tdd-phase refactor --refactor-note "<note>"`
   - Повтори focused test и `Relevant Suite`
   - Только после этого завершай шаг через `madspec memory complete-step --stage feature.implement ...`

   **3.6. Non-code waiver path:**
   - Для `non-code` шага не редактируй `progress.json` вручную
   - Проверь, что `stepMetadata.waiverReason` заполнен при `tddPolicy=waived`, затем заверши шаг через `madspec memory complete-step`

4. **Валидация шага:**

   **Обязательная валидация перед коммитом:**

   - [ ] **Все задачи из tasks.md выполнены**
     - Проверь файл шага
     - Все чекбоксы `[x]`
   
   - [ ] **Файлы созданы/модифицированы согласно tasks.md**
     - Проверь существование файлов
     - Проверь содержимое
   
   - [ ] **Интеграция из project-analysis.md выполнена**
     - Проверь связи с существующим кодом
     - Проверь зависимости
   
   - [ ] **Критерии из validation.md выполнены**
     - Проверь каждый критерий

   - [ ] **Соответствует architecture.md**
     - Структура файлов
     - Паттерны и подходы

   - [ ] **Тесты описаны (из tests.md)**
     - Если тесты требуются — они должны быть
     - Автоматические тесты проходят

   - [ ] **TDD состояние зафиксировано в structured memory**
     - Проверь ответ `madspec memory retrieve --stage feature.implement --step-id <step-id> --json-output`
     - Для `code + required`: `tddPhase=completed`, заполнены `redEvidence`, `greenEvidence`, `refactorNote`
     - Для `non-code`: `tddPhase=waived`, а при `tddPolicy=waived` есть причина

   **Если валидация не пройдена:**
   - Укажи что не выполнено
   - Предложи исправления
   - **НЕ коммить** до прохождения валидации

5. **Обновление progress.json:**

   После успешной валидации не редактируй `progress.json` вручную.

   Используй:
   
   ```bash
   madspec memory complete-step \
     --stage feature.implement \
     --step-id <step-id> \
     --summary "<что завершено>" \
     --red-evidence "<focused red command>" \
     --green-evidence "<focused green command>" \
     --refactor-note "<что было отрефакторено>"
   ```

   Если по шагу появились факты/решения/контракты, сохраняй их сразу:

   ```bash
   madspec memory complete-step \
     --stage feature.implement \
     --step-id <step-id> \
     --summary "<что завершено>" \
     --fact "<validated fact>" \
     --decision "<validated decision>" \
     --contract "<validated constraint>"
   ```

   Команда сама обновляет `completedSteps`, `stepStatus`, `currentImplementStep`, step-level records и generated views.

6. **Создание implementation-context.md:**

   Использовать шаблон из `templates/feature/feature-implementation-context-template.md` для создания `.madspec/feature/<feature-branch>/steps/step-[NN]-[name]/implementation-context.md`:

   Скопировать содержимое шаблона и заполнить:
   - Что сделано
   - Отклонения от плана
   - Ключевые решения
   - Проблемы
   - Изменения в архитектуре
   - Созданные/измененные файлы
   - Результаты тестирования
   - Информация о коммите (заполняется после коммита)

7. **Коммит изменений:**

   После успешной валидации:
   ```
   madspec git commit --message "feat(step-[NN]): реализован шаг [название]"
   ```

   После коммита обнови `implementation-context.md`:
   ```
   ## Информация о коммите
   - Хеш: [git log -1 --format=%H]
   - Сообщение: [git log -1 --format=%s]
   - Дата: [дата]
   ```

8. **Обновление project-context.md:**

   ```markdown
   ## Текущий этап
   - **Этап**: `implement`
   - **Текущий шаг**: step-[NN]-[name]
   
   ## Шаги реализации
   - Запланировано: [N]
   - Завершено: [M]
   - В процессе: [текущий]
   
   ## Прогресс
   [M/N] шагов завершено
   ```

9. **Отчет о прогрессе:**

   ```
   ✅ Шаг [NN] завершен: [название]
   
   Прогресс реализации:
   - Завершено: [X/Y] шагов
   - Следующий шаг: [название] или "Все шаги завершены"
   
   Последний коммит: [хеш]
   ```

10. **Переход к следующему шагу:**

    - Если есть следующий шаг → спроси "Перейти к следующему шагу?"
    - Если "да" → попроси запустить `/madspec.feature.implement` заново
    - Если "начать тестирование" → выполни автоматизированные тесты + опиши ручную проверку
    - Если "все" → заверши работу

11. **Завершение всех шагов:**

   - Выведи финальный отчет
   - Поздравь с завершением
   - Предложи финальную валидацию

## Правила

- **ВЫПОЛНЯЙ** задачи из tasks.md
- **ВАЛИДИРУЙ** каждый шаг перед коммитом
- **ОБНОВЛЯЙ** progress.json после валидации
- **ДЛЯ CODE-STEP** не коммить до полного цикла `red -> green -> refactor`
- **КОММИТЬ** после успешной валидации
- **ИСПОЛЬЗУЙ** project-analysis.md для понимания функций и интеграции
- **СЛЕДУЙ** паттернам из существующего кода

## Обработка ошибок

- Шаг не выполняется → остановись, сообщи проблему
- Предложи варианты решения
- Задокументируй изменения плана если нужны

## Выходные артефакты

- Реализованный код
- Обновленный `progress.json`
- `implementation-context.md` для каждого шага
- Коммиты в git
- Обновленный `project-context.md`

## Завершение

После всех шагов:
- Финальная проверка функций
- Демонстрация
- Рефлексия
