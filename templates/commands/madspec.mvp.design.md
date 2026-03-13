---
description: MVP - Этап 1 - Создание storyboard-дизайна пользовательского интерфейса на основе концепции проекта
handoffs:
  - label: Выбрать технологии
    agent: madspec.mvp.tech
    prompt: Выбери технологический стек на основе утвержденного storyboard-дизайна
---

## Пользовательский ввод

```text
$ARGUMENTS
```

Ты **ОБЯЗАН** учитывать пользовательский ввод перед продолжением (если он не пустой).

## Обязательный skill для visual design

- При работе над `madspec.mvp.design`, если проектируются UI/UX-решения, storyboard и HTML/CSS-прототипы, **обязательно** подключай skill `frontend-design` как основной design-skill.
- `frontend-design` отвечает за качество, характер и выразительность визуального решения.
- `.madspec/templates/ui-storyboard-contract.md` задает structural contract, review-навигацию и обязательную структуру storyboard, но **не заменяет** `frontend-design` и не диктует визуальный стиль.
- `madspec memory retrieve/capture/checkpoint/validate` остаются обязательным механизмом для canonical state, coverage и консистентности артефактов.

## Правила диалога (обязательно)

- **Задавай вопросы строго по одному**: в каждом твоем сообщении должен быть **ровно 1 вопрос**, который требует ответа.
- **Не выдавай список вопросов заранее**.
- Если нужен выбор, задай **один вопрос** и предложи **не больше 3–5 вариантов**.
- **Дожидайся ответа** и только затем задавай следующий вопрос.
- Если ответ неполный — задай **один уточняющий вопрос**, а не несколько сразу.

## Structured Memory First (обязательно)

- Каноническое состояние хранится в `.madspec/<BRANCH>/memory/`.
- Реальные данные этапа design хранятся в `.madspec/<BRANCH>/memory/stages/mvp.design.json`.
- `.madspec/<BRANCH>/ui-design.md` и `project-context.md` считаются generated views и не редактируются вручную как источник истины.
- Перед началом и после каждого утвержденного блока по экрану, journey, навигации или платформенному ограничению используй `madspec memory retrieve --stage mvp.design --json-output` и `madspec memory capture --stage mvp.design ...`.
- Используй design-specific flags, когда меняется canonical state: `--design-overview`, `--platform`, `--zone`, `--screen`, `--screen-feature`, `--flow`, `--flow-step`, `--flow-alternative`, `--nav`, `--platform-constraint`, `--screen-data`, `--next-action`.
- Приоритеты `P1/P2/P3` нужны для internal coverage через `--screen-feature`, но **не должны** появляться в user-facing prototype как бейджи или визуальные метки.
- Для этапа design **обязательно** заверши работу командой `madspec memory checkpoint --stage mvp.design ...`.
- Минимальный payload checkpoint:
  - `--summary` — итоговое решение по UI/UX;
  - `--fact/--decision` можно не дублировать, если они уже накоплены через `madspec memory capture --status validated`;
  - `--evidence` — ссылки на `.madspec/<BRANCH>/ui-design.md` и `.madspec/<BRANCH>/ui-prototype/index.html`.
- В обычных ходах диалога опирайся на `design_status`: какие обязательные поля еще пусты, какие concept-функции еще не покрыты экранами, каких prototype-файлов не хватает.
- Полный `artifact_state.design` запрашивай только перед финальной валидацией, итоговым обзором и `checkpoint`, используя `madspec memory retrieve --stage mvp.design --json-output --full-artifact`.

## Работа в нескольких чатах (обязательно)

- Для `mvp.design` многосессионная работа считается штатным сценарием.
- В начале **каждой новой сессии** сначала выполни `madspec memory retrieve --stage mvp.design --json-output`.
- После этого сверь:
  - `.madspec/<BRANCH>/ui-design.md`
  - `.madspec/<BRANCH>/ui-prototype/index.html`
  - остальные файлы в `.madspec/<BRANCH>/ui-prototype/`
  - `.madspec/templates/ui-storyboard-contract.md`
- Не опирайся на историю предыдущего чата как на источник истины, если она расходится с current structured memory и source artifacts.
- Не считай дизайн завершенным, пока пользователь явно не утвердил текущее состояние storyboard-прототипа.

## Изменил UI — проверь документацию (обязательно)

- Любое подтвержденное изменение экрана, flow, review-навигации, platform-specific поведения, состава данных на экране или связи экран ↔ функция должно обновлять не только HTML/CSS, но и canonical design memory.
- После изменения прототипов проверь, не устарели ли:
  - `.madspec/<BRANCH>/ui-design.md`
  - описание navigation
  - review journeys
  - coverage функций из concept
  - ссылки на prototype-файлы
- Рабочий порядок: сначала обнови source artifacts и typed design-state через `madspec memory capture`, затем пересобери generated views через `madspec memory checkpoint` или `madspec memory consolidate`, затем проверь консистентность через `madspec memory validate`.

## Описание

На этом этапе создается **storyboard-прототип** пользовательского интерфейса на основе концепции проекта. Его задача — не показать каталог функций, а дать пользователю кликабельный review-flow, который можно открыть в браузере и пройти по шагам до старта реализации.

Используй `.madspec/templates/ui-storyboard-contract.md` как structural contract. Этот файл задает структуру, обязательную review-навигацию и expectations к прототипу, но **не задает** визуальный стиль. Визуальное решение агент должен придумать сам под домен проекта.

## Цель этапа

Создать кликабельное представление интерфейса, которое:

- решает проблемы, определенные в концепции;
- дает пользователю возможность пройти ключевые сценарии по кликам;
- покрывает все concept features через internal design-state;
- позволяет утвердить финальное UI/UX-видение перед следующей стадией.

## Runtime workflow

0. **Определение текущей ветки**:
   - Перед началом работы определи текущую ветку через `madspec git current-branch`.
   - Все пути к артефактам используй в формате `.madspec/<BRANCH>/...`.
   - Если ни команда, ни файл недоступны, используй значение по умолчанию `main`.

1. **Загрузка контекста**:
   - Прочитай `.madspec/<BRANCH>/concept.md`.
   - Прочитай `.madspec/<BRANCH>/project-context.md`.
   - Загрузи `.madspec/templates/ui-storyboard-contract.md`.
   - Извлеки все concept features и ключевые пользовательские сценарии.
   - Если в concept есть authentication, onboarding, verification или другой access gate, используй его как начало primary review flow.

2. **Определение review journeys**:
   - Выдели primary review flow и дополнительные journeys.
   - Для каждого flow определи entry screen, последовательность экранов и ожидаемый результат.
   - Сгруппируй связанные функции на одном экране только там, где это помогает review story.

3. **Создание storyboard HTML/CSS прототипов**:
   - `index.html` должен быть storyboard entrypoint c блоком "С чего начать", primary review flow и картой journeys.
   - Каждый экранный HTML должен иметь явную review-навигацию `Back / Next / Home`.
   - Создавай визуальное решение с нуля под домен проекта. Не копируй generic dashboard/form/list layout.
   - Допустим minimal vanilla JavaScript для mock-navigation и state toggles.
   - Прототип не требует реальной бизнес-логики, но обязан быть кликабельным по основным review journeys.

4. **Фиксация flows и экранов в memory**:
   - После утверждения каждого куска дизайна записывай `--screen`, `--screen-feature`, `--flow`, `--flow-step`, `--flow-alternative`, `--nav`, `--screen-data`.
   - Используй текущую модель `screens`, `flows`, `navigation` как canonical основу storyboard:
     - `flows[].steps` = порядок прохождения сценария;
     - первый step flow = entry screen journey;
     - первый flow = primary review flow.

5. **Локальный просмотр**:
   - Не спрашивай пользователя, чем запускать preview.
   - Выбери самый простой доступный static server в локальной среде.
   - Создай в `.madspec/<BRANCH>/ui-prototype/README.md` краткую инструкцию по запуску и открытию `index.html`.

6. **Валидация дизайна**:
   - Проверь, что все concept features покрыты экранами или экранными состояниями.
   - Проверь, что primary flow проходится кликами от `index.html` до финального экрана без ручного редактирования URL.
   - Проверь, что у экранов нет тупиков без `Back`, `Next` или `Home`.
   - Проверь соответствие платформам, навигации и данным на экране.
   - Если validation не пройдена — не переходи к checkpoint.

7. **Checkpoint в structured memory**:
   - После явного approval пользователя выполни `madspec memory checkpoint --stage mvp.design`.
   - В `--evidence` укажи `.madspec/<BRANCH>/ui-design.md` и `.madspec/<BRANCH>/ui-prototype/index.html`.

## Важные принципы проектирования

- **ДЕЛАЙ storyboard, а не каталог**: `index.html` должен вести пользователя по сценариям, а не показывать список функций.
- **НЕ ПОКАЗЫВАЙ `P1/P2/P3` в user-facing прототипе**: приоритеты нужны для internal coverage, а не для визуального согласования.
- **СОЗДАВАЙ доменно-специфичный UI** без копирования безликой болванки.
- **ПРОСИ пользователя пройти кликабельный сценарий в браузере** и явно подтвердить соответствие ожиданиям.
- **НЕ ПЕРЕХОДИ** к следующему этапу без утверждения дизайна.

## Выходные артефакты

- `.madspec/templates/ui-storyboard-contract.md` - structural contract для storyboard-прототипов
- `.madspec/<BRANCH>/ui-prototype/` - директория со storyboard HTML/CSS прототипами
  - `index.html` - storyboard entrypoint
  - `[screen-name].html` - отдельные экраны
  - `README.md` - инструкция по просмотру
- `.madspec/<BRANCH>/memory/stages/mvp.design.json` - canonical design state
- `.madspec/<BRANCH>/ui-design.md` - generated artifact дизайна интерфейса
- `.madspec/<BRANCH>/project-context.md` - generated view контекста проекта

## Следующий этап

После утверждения дизайна перейди к `/madspec.mvp.tech` для выбора технологического стека.
