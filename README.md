# Caspian Intelligence — Stages 1–10

Рабочая региональная maritime intelligence-платформа версии `0.10.0`: LIVE-карта Каспия, provider-neutral AIS gateway, история позиций, current state, рейсы, playback, индивидуальные baseline-профили, объяснимые Event Detection и Risk Engine, Advanced Analytics, multi-port Smart Port, grounded AI Assistant с Investigation Cases, Environmental Intelligence и Caspian Network.

Полное руководство по всем работающим пользовательским функциям, API, ролям, сценариям и ограничениям: [`docs/FUNCTIONALITY.md`](docs/FUNCTIONALITY.md).

## Быстрый запуск интерфейса

```bash
npm install
npm run dev
```

Откройте `http://localhost:5173`. Демо-данные для входа уже заполнены.

## API

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt
.venv/Scripts/uvicorn backend.app.main:app --reload
```

Документация API: `http://localhost:8000/docs`. Для защищённых маршрутов сначала вызовите `POST /api/v1/auth/login`, затем передавайте токен в заголовке `Authorization: Bearer <token>`.

WebSocket флота: `ws://localhost:8000/ws/vessels?token=ci-demo-analyst`. Портовый поток: `ws://localhost:8000/ws/ports/aktau?token=ci-demo-analyst`. Экологический поток для `ADMIN`/`ANALYST`: `ws://localhost:8000/ws/environment?token=ci-demo-analyst`. Региональный scope-filtered поток: `ws://localhost:8000/ws/network?token=ci-demo-analyst`.

Ключевые маршруты второго этапа:

- `POST /api/v1/ais/ingest` — приём сообщения от любого AIS-адаптера;
- `GET /api/v1/vessels/live` — текущее состояние флота;
- `GET /api/v1/vessels/{id}/track` — траектория за период;
- `POST /api/v1/spatial-search` — суда в географической области и временном диапазоне;
- `GET /api/v1/data-quality` — метрики приёма и валидации;
- `/ws/vessels` — поток `position_update`.

Ключевые маршруты третьего этапа:

- `GET /api/v1/vessels/{id}/behavior` — полный цифровой baseline;
- `GET /api/v1/vessels/{id}/behavior/routes` — повторяющиеся маршруты и коридоры;
- `GET /api/v1/vessels/{id}/behavior/speed` — скорость по фазам рейса;
- `GET /api/v1/vessels/{id}/behavior/ports` — обычные и редкие порты;
- `GET /api/v1/vessels/{id}/behavior/stops` — исторические зоны остановок;
- `GET /api/v1/vessels/{id}/behavior/draught` — история осадки;
- `GET /api/v1/vessels/{id}/behavior/activity` — пространственные и временные паттерны;
- `GET /api/v1/vessels/{id}/connections` — историческое совместное присутствие;
- `POST /api/v1/vessels/{id}/behavior/recalculate` — обновление агрегированного baseline.

## Docker

```bash
docker compose up --build
```

Интерфейс будет доступен на `http://localhost:8080`. Compose поднимает FastAPI, PostgreSQL/PostGIS и Redis. При первом старте PostGIS автоматически создаёт таблицы raw AIS, исторических позиций, current state, рейсов, геозон, событий, аудируемых risk-оценок, Advanced Analytics, портового контура, Assistant grounding/audit, Investigation Cases и Environmental Intelligence из `backend/schema.sql`.

## Режим данных

Встроенный demo-provider публикует реалистичные AIS-позиции каждые три секунды. Они проходят ту же очередь, нормализацию и валидацию, что и сообщения будущего коммерческого или берегового провайдера. Источник можно заменить адаптером без изменений REST/WebSocket-контракта.

Текущий runtime работает с демонстрационными данными и in-memory аналитическими состояниями. Коммерческий AIS, портовые, таможенные, топливные, погодные и корпоративные реестры фактически не подключены. `backend/schema.sql` и REST-контракты подготовлены для постоянного PostgreSQL/PostGIS-хранения, но наличие схемы не следует понимать как уже выполненную production-интеграцию с внешним источником.

Behavior Engine использует объяснимые агрегаты: каждый диапазон сопровождается количеством рейсов и периодом наблюдения. Низкая `behavior confidence` означает недостаток индивидуальной истории, а не риск. В третьем этапе Event Detection и Risk Engine намеренно не смешивались с baseline; они реализованы как отдельные последующие слои.

## Event Detection

Четвёртый этап добавляет шесть независимых детекторов:

- отклонение от индивидуального маршрутного коридора;
- разрыв AIS с настраиваемыми периодами и возможной областью движения;
- остановка вне порта, якорной и исторически обычной зоны;
- скорость вне профиля конкретной фазы рейса;
- продолжительное сближение судов при низкой скорости;
- изменение заявленной осадки.

События коррелируются в группы одного рейса, но не преобразуются в итоговый Risk Score. `Severity` описывает значимость наблюдаемого факта, `confidence` — уверенность классификации, а `status` хранит результат человеческого review.

API четвёртого этапа:

- `GET /api/v1/events` и `GET /api/v1/events/{id}`;
- `PATCH /api/v1/events/{id}/status`;
- `GET /api/v1/vessels/{id}/events`;
- `GET /api/v1/voyages/{id}/events`;
- `GET /api/v1/encounters`;
- `GET /api/v1/event-groups`;
- WebSocket-сообщения `event_created`, `event_updated`, `event_resolved`.

Запуск тестов детекторов:

```bash
.venv/Scripts/python -m unittest backend.tests.test_event_engine -v
```

## Risk Engine

Пятый этап не меняет факты, найденные Event Detection Engine, а строит над ними отдельную версионируемую оценку приоритета. Поток обработки выглядит так:

`AIS → Behavior baseline → Detected events → Risk factors → Correlation + decay → Current assessment + history`

Используется модель `CI-RISK-1.0`. Правила и пределы вкладов хранятся в `risk_rule_config`, поэтому изменение конфигурации не требует переписывать историю: каждый snapshot сохраняет свою версию модели. Границы уровня фиксированы:

- `0–24` — `LOW`;
- `25–49` — `MODERATE`;
- `50–74` — `HIGH`;
- `75–100` — `CRITICAL`.

Оценка контекстная, а не простая сумма severity событий. Для каждого `RiskFactor` сохраняются исходное и скорректированное значения, confidence, источник-событие, доказательства, объяснение и жизненный цикл `ACTIVE → RECENT → HISTORICAL`. Корреляционные правила имеют общий cap и не учитывают один и тот же сигнал дважды. В демонстрационном сценарии CASPIAN STAR итог `84` полностью раскладывается на факторы `69` (`22 + 18 + 17 + 12`) и ограниченный correlation bonus `15`.

Risk Score служит только для очередности проверки. Он не доказывает нарушение, намерение или виновность. Коррелированный сценарий отображается формулировкой **PATTERN REQUIRES REVIEW**, а экран «WHY HIGH?» ведёт от каждого вклада к наблюдаемому событию. Аналитик может отметить фактор как `CONFIRMED RELEVANT`, `NORMAL OPERATION`, `FALSE POSITIVE` или `NEEDS MORE DATA`; автор, время и комментарий сохраняются в отдельном audit trail.

API пятого этапа:

- `GET /api/v1/risk/vessels` — текущая оценка всех судов с фильтрацией по уровню;
- `GET /api/v1/risk/high-priority` — приоритетная очередь `CRITICAL`/`HIGH`;
- `GET /api/v1/risk/notifications` — только значимые переходы и быстрые изменения;
- `GET /api/v1/risk/rules` — активная конфигурация и версия модели;
- `GET /api/v1/vessels/{vessel_id}/risk` — объяснимая vessel-level оценка;
- `GET /api/v1/vessels/{vessel_id}/risk/history` — временной ряд изменения риска;
- `GET /api/v1/vessels/{vessel_id}/risk/voyages` — оценки последних рейсов судна;
- `GET /api/v1/voyages/{voyage_id}/risk` — отдельная оценка конкретного рейса;
- `GET /api/v1/voyages/{voyage_id}/risk/factors` — факторы рейса и ссылки на evidence;
- `PATCH /api/v1/risk/factors/{factor_id}/review` — решение аналитика по фактору.

WebSocket `/ws/vessels` дополнительно публикует `risk_updated` с `previous_score`, `current_score`, `level` и объяснимым `reason`. Уведомления создаются только при переходах `MODERATE → HIGH`, `HIGH → CRITICAL`, росте не менее чем на 20 пунктов за час или появлении критического фактора.

Модель `CI-RISK-1.0` остаётся воспроизводимой базовой моделью пятого этапа. Шестой этап передаёт в Risk Engine новые confidence-weighted факторы через версию `CI-RISK-2.0`, не изменяя исходные события и не перезаписывая исторические snapshots.

Запуск всех backend-тестов этапов 4–6 из корня проекта:

```bash
.venv/Scripts/python -m unittest backend.tests.test_event_engine backend.tests.test_risk_engine backend.tests.test_advanced_analytics -v
```

## Advanced Analytics

Шестой этап добавляет второй аналитический контур, который проверяет согласованность заявленных и наблюдаемых данных:

`Cargo Engine + vessel-specific Draught Model + Fuel Engine + Voyage Economics + Link Engine → Advanced Correlation → CI-RISK-2.0`

Risk Engine пятого этапа не заменён: Advanced Analytics создаёт новые объяснимые события и факторы, а действующие confidence, lifecycle, correlation cap и защита от двойного учёта продолжают применяться. Основные модули:

- `CargoDeclaration`, позиции декларации и cargo timeline связывают груз с конкретным судном и рейсом;
- cargo profiles показывают исторические типы и диапазоны груза отдельно для судна и маршрута;
- draught model строится только для конкретного судна и хранит количество исторических операций, версию и confidence — универсальная формула «тонны → метры» не используется;
- cargo/draught evaluation различает `CARGO_DRAUGHT_MISMATCH`, обратный сценарий `UNEXPLAINED_LOAD_CHANGE`, согласованные данные и `INSUFFICIENT_DATA` при слабой модели;
- Fuel Engine учитывает профиль судна, маршрут, скорость, осадку, ожидание и маневрирование, затем применяет погодную и операционную коррекции;
- Voyage Economics сопоставляет заявленную стоимость груза с оценкой топлива, портовых сборов, экипажа, обработки и эксплуатационных расходов;
- Link Engine агрегирует встречи и показывает направленные связи `VESSEL / COMPANY / OWNER / OPERATOR / PORT / CARGO / VOYAGE` вместе с причиной, периодом наблюдения и evidence;
- Advanced Correlation объединяет факторы по временной последовательности, снижает вклад слабых моделей и не учитывает один источник дважды.

### Демонстрационный сценарий

Для рейса CASPIAN STAR `Baku → Aktau` зафиксирован воспроизводимый demo-набор:

- заявлено `5 000 t` стали (`REPORTED`), оценочная стоимость — `$250 000` (`ESTIMATED`);
- оценка стоимости рейса — `$320 000`, отношение стоимости груза к расходам — `0.78` при историческом диапазоне `2.4–4.8`;
- ожидаемое изменение осадки — около `1.2 m`, наблюдаемое — `0.3 m`;
- ожидаемый расход топлива — `38–44 t`, сообщённый/оценённый фактический — `61 t`, то есть примерно `+38%` относительно верхней границы;
- с TURAN найдено `14` предыдущих встреч, из которых `11` произошли вне портов.

Базовый subtotal событий Stage 5 равен `84`. Сырые аналитические strengths (`13` cargo/draught, `9` fuel, `6` economics, `5` historical connection) не складываются с ним напрямую: после confidence weighting, коррекции качества источников, устранения общего evidence и correlation cap текущий Advanced Context даёт `+7`. Итог демонстрационного сценария: `84 + 7 = 91 / 100` по модели `CI-RISK-2.0`.

### Provenance и качество данных

Каждое аналитическое наблюдение и событие хранит `source`, `source_timestamp`, `confidence` и `verification_status`. Статусы имеют строго разные значения:

- `REPORTED` — значение сообщено документом, системой или участником, но не подтверждено платформой независимо;
- `ESTIMATED` — значение рассчитано моделью; рядом всегда должны отображаться confidence, версия модели и входные данные;
- `VERIFIED` — значение подтверждено независимым доверенным источником либо зафиксированным решением аналитика.

`NOT_AVAILABLE` в API означает отсутствие подтверждающего наблюдения (например, bunker receipt ещё не получен), а не четвёртый тип достоверности; в постоянном хранилище это представляется отсутствием связанной записи.

Интерфейс и API не должны представлять `ESTIMATED` как официальный факт, а `REPORTED` — как независимое подтверждение. Низкая confidence приводит к снижению аналитического вклада или статусу `INSUFFICIENT DATA`, а не к усилению риска.

Ни отдельная аномалия, ни Risk Score не доказывают незаконный груз, сокрытие маршрута, связь между намерениями участников, нарушение или виновность. Формулировки `CARGO / DRAUGHT MISMATCH`, `FUEL ANOMALY`, `ECONOMIC ANOMALY`, `UNUSUAL CONNECTION` и **PATTERN REQUIRES REVIEW** обозначают только объяснимые индикаторы для проверки человеком.

### API шестого этапа

- `GET /api/v1/voyages/{id}/cargo` — декларации, позиции груза и timeline с provenance;
- `GET /api/v1/voyages/{id}/fuel` — профиль, ожидаемый диапазон, фактическое/заявленное значение и коррекции;
- `GET /api/v1/voyages/{id}/economics` — разбивка оценки стоимости и исторический диапазон;
- `GET /api/v1/voyages/{id}/intelligence` — единое досье рейса: route, events, cargo, draught, fuel, economics, correlations, risk и explanation;
- `GET /api/v1/vessels/{id}/connections` — агрегированные встречи с объяснением strength;
- `GET /api/v1/vessels/{id}/network` — граф соседних судов, компаний, портов, грузов и рейсов;
- `GET /api/v1/companies/{id}` — карточка компании, provenance, рейсы, типы событий, risk history и связи;
- `GET /api/v1/companies/{id}/vessels` — суда компании с ролью и периодом владения/эксплуатации.

Ответы Stage 6 в текущем приложении основаны на демонстрационном in-memory сценарии. Нормализованные SQL-таблицы, ограничения, индексы и API-контракты предназначены для последующего подключения постоянного хранения и реальных провайдеров без выдачи этих интеграций за уже работающие.

### Границы этапа

В границы Stage 6 исторически не входили berth optimization, управление очередями, port congestion и симуляция порта — они добавлены отдельным Stage 7. Grounded Assistant и Investigation Cases добавлены отдельным Stage 8. Структурированное Voyage Summary этапа 6 по-прежнему формируется детерминированными правилами; юридические выводы система не делает.

## Smart Port Aktau

Седьмой этап добавляет операционный контур порта Актау поверх морской аналитики первых шести этапов:

`Voyage + Vessel Intelligence + Events + Risk → PortCall → ETA + Berth compatibility + Service time → Queue + Load forecast → Human decision → Actuals + feedback`

`Voyage` описывает движение судна между портами, а `PortCall` — отдельный операционный визит с подходом, ожиданием, назначением причала, сервисом и выходом. Это разные сущности с независимой историей. Расчёты выполняются объяснимыми детерминированными моделями `CI-PORT-1.0`, `CI-ETA-1.0` и `CI-SERVICE-1.0`.

### Реализованные модули

- Port Control Center показывает текущую операционную загрузку, подходы, суда в порту, ожидание, выходы, состояние причалов и high-risk arrivals;
- Arrival Board сравнивает заявленный ETA с прогнозом, вероятным окном и confidence;
- Berth Compatibility проверяет длину, осадку, тип груза, оснащение, ограничения и время доступности;
- Service Time Prediction отдельно объясняет грузовую обработку, документы, другие операции и погодную поправку;
- Dynamic Queue пересчитывает порядок по ETA, совместимости, времени сервиса, погоде и операционному приоритету;
- Port Load Forecast показывает именно будущий спрос на обработку, отдельно от текущей утилизации;
- Pre-Arrival Report объединяет ETA, причал, груз, сервис, Risk `91`, семь значимых событий и действия до прибытия;
- WHAT IF выполняется в изолированной копии расписания и не меняет рабочее состояние;
- Actual vs Predicted записывает ошибки ETA/сервиса и независимые портовые наблюдения в feedback loop без перезаписи исходной декларации.

### Воспроизводимый demo-сценарий

В текущей картине порта операционная утилизация равна `68%`: прибывают `7`, находятся в порту `5`, ожидают `3`, готовятся к выходу `2`, среднее ожидание — `1h 42m`, доступны `3` из `8` причалов. Прогнозный показатель нагрузки на обработку имеет другую семантику и растёт `42 → 58 → 74 → 91%` на горизонте шести часов.

Для CASPIAN STAR заявлен ETA `14:30`, объяснимый прогноз — `15:05` (`+35 min`), вероятное окно — `14:52–15:18`, confidence — `87%`. Причал `#5` совместим и доступен с `14:45`; причал `#2` исключён из-за ограничения осадки. Сервис `5h 00m` раскладывается на `4h` обработки, `35 min` документов и `25 min` других операций, confidence — `82%`, освобождение — `20:05`. При ветре `22 m/s` погодная поправка `+80 min` даёт `6h 20m` и освобождение в `21:25`.

Прогноз выявляет узкое окно `16:00–19:00`: причалы `#3–#5` достигают `91%`, четыре судна приходят за `75 min`. Рекомендация перенести BAKU EXPRESS с `#5` на `#7` снижает среднее ожидание на `42 min` и пиковую нагрузку `91 → 76%`. Система только предлагает действие: `ACCEPT`, `CHANGE_BERTH` или `DEFER` всегда фиксирует авторизованный диспетчер, а SQL-ограничения не допускают автоматического назначения.

В WHAT IF сценарии задержка CASPIAN STAR на два часа меняет очередь на `TURAN → BAKU EXPRESS → CASPIAN STAR → CASPIAN WIND`, среднее ожидание `1h 42m → 2h 31m`, congestion `+18 п.п.` и затрагивает два судна. Результат имеет `state_changed=false`.

### API седьмого этапа

- `GET /api/v1/ports/{port_id}/overview` — Port Control Center;
- `GET /api/v1/ports/{port_id}/arrivals` — табло подходов;
- `GET /api/v1/ports/{port_id}/berths` — причалы, оснащение и доступность;
- `GET /api/v1/ports/{port_id}/queue` — текущая динамическая очередь;
- `GET /api/v1/ports/{port_id}/load-forecast` — прогноз обработки и bottleneck;
- `GET /api/v1/vessels/{vessel_id}/eta` — объяснимый ETA и история факторов;
- `GET /api/v1/port-calls/{port_call_id}/pre-arrival` — единый отчёт до прибытия;
- `GET /api/v1/port-calls/{port_call_id}/berth-recommendation` — рекомендуемый причал и совместимость;
- `POST /api/v1/berth-assignments` — аудируемое решение диспетчера;
- `POST /api/v1/simulations` — изолированный WHAT IF;
- `POST /api/v1/ports/{port_id}/weather/recalculate` — распространение погодной задержки;
- `POST /api/v1/port-calls/{port_call_id}/actuals` — фактические данные и feedback;
- `/ws/ports/{port_id}` — `port_state_updated`, berth/weather/decision/simulation/feedback updates.

### Проверка и границы

Запуск всех backend-тестов этапов 4–7 из корня проекта:

```bash
.venv/Scripts/python -m unittest backend.tests.test_event_engine backend.tests.test_risk_engine backend.tests.test_advanced_analytics backend.tests.test_port_operations -v
```

Runtime Stage 7 использует воспроизводимый in-memory сценарий. SQL-схема, ограничения, индексы, REST и WebSocket-контракты подготовлены, но реальная интеграция с Port Aktau, TOS/PCS, диспетчерскими журналами и производственной метеостанцией не заявляется как уже подключённая. В этап не входят автоматическое управление оборудованием, весь Каспий, экологический мониторинг и автономные решения без человека.

## Grounded AI Assistant & Investigation

Восьмой этап предоставляет единый natural-language интерфейс к результатам уже существующих модулей. Архитектура runtime:

`Question + page context → deterministic intent planner → RBAC → Caspian read tools → structured result → FACT / ESTIMATE / INFERENCE → evidence links`

Planner не является отдельным источником морских фактов. Названия судов, оценки риска, факторы, события, ETA, очередь и связи всегда читаются из Vessel, Voyage, Behavior, Event, Risk, Advanced Analytics и Port Operations. Если обязательного объекта или записи нет, ответ имеет `no_data=true`; отсутствующие данные не дополняются предположениями. В текущем demo внешний генеративный провайдер не подключён: ограниченный deterministic planner выбран для воспроизводимости и защиты от галлюцинаций, при этом все значения в ответах приходят из реальных service/API-контрактов приложения, а не из frontend-заглушек.

### Assistant Chat и контекст

- `/app/assistant` хранит историю текущего диалога и показывает вызванные tools, аргументы и число прочитанных записей;
- плавающий Assistant доступен на карте, в профиле судна, Risk Center, Network, Voyage Intelligence и Port Aktau;
- frontend передаёт `current_page`, `vessel_id`, `voyage_id`, `port_id`, `investigation_id` и выбранный прямоугольник карты с временным окном;
- conversation state запоминает последнее судно, рейс, связанное судно и Case, поэтому после `Почему CASPIAN STAR?` работают вопросы `С кем оно встречалось?` и `Они встречались раньше?`;
- все значимые утверждения разделены на `FACT`, `ESTIMATE` и `INFERENCE` и содержат внутреннюю ссылку на Event, Risk Factor, Network, ETA, PortCall или Case.

### Tool Layer

Автоматические read-tools:

- `get_vessel`, `get_current_voyage`, `get_vessel_events`;
- `get_vessel_risk`, `get_risk_factors`, `get_behavior_profile`;
- `get_encounters`, `get_cargo_analysis`, `get_fuel_analysis`, `get_vessel_network`;
- `search_vessels`, `search_events`, `search_area`;
- `get_port_status`, `get_arrivals`, `get_port_forecast`, `get_eta`, `get_pre_arrival`.

Отдельные write-tools `create_investigation`, `add_case_evidence`, `update_investigation`, `add_case_note`, `assign_berth`, `change_port_queue` и `close_event` объявлены отдельно от чтения и всегда имеют `requires_confirmation=true`. В реализованном demo-разговоре исполняются Case actions; портовые и event-действия остаются отдельными подтверждаемыми контрактами соответствующих модулей.

### Investigation Case

Подтверждённая команда `Создай расследование по CASPIAN STAR` создаёт `CASE CI-2026-00421` со статусом `OPEN`, приоритетом `HIGH`, судном, рейсом Baku → Aktau, назначенным аналитиком и полной timeline. Case изначально не получает evidence автоматически. Команда `Добавь AIS gap и встречу в доказательства` сначала возвращает pending action, а после отдельного подтверждения добавляет только `EV-2802` и `EV-2803`. Повторное добавление идемпотентно.

AI Case Summary использует только evidence данного Case. При пустой коллекции система возвращает `INSUFFICIENT DATA`; после добавления источников каждое предложение связано с ними. Notes и изменения Case также являются подтверждаемыми write-операциями и попадают в audit trail.

### RBAC, audit и безопасность

- `ADMIN` и `ANALYST` имеют доступ к Investigation и security intelligence;
- `VIEWER` работает только с разрешённым read-контуром;
- `PORT_DISPATCHER` видит порт, ETA, карту и безопасную risk summary, но не получает Risk Factors, encounter intelligence, cargo/fuel security details или Investigation Cases;
- pending action привязан к пользователю, который его запросил, не может подтверждаться другим аналитиком и не может исполняться повторно;
- audit сохраняет `user`, `role`, `question`, `timestamp`, `tools_called`, `data_accessed`, `answer`, `actions` и outcome;
- аномалия, встреча или Risk Score описываются как признак для человеческой проверки, а не доказательство нарушения или намерения.

### API восьмого этапа

- `GET /api/v1/assistant/tools` — read/write catalogue с RBAC и признаком confirmation;
- `POST /api/v1/assistant/chat` — grounded answer и продолжение conversation;
- `GET /api/v1/assistant/conversations` и `GET /api/v1/assistant/conversations/{id}` — история;
- `GET /api/v1/assistant/audit` — аудит для разрешённых ролей;
- `GET|POST /api/v1/investigations` — очередь и создание Case;
- `GET|PATCH /api/v1/investigations/{id}` — карточка и контролируемое обновление;
- `POST /api/v1/investigations/{id}/evidence` — evidence collection;
- `POST /api/v1/investigations/{id}/notes` — analyst note;
- `POST /api/v1/investigations/{id}/summarize` — evidence-only summary;
- `POST /api/v1/assistant/actions/{id}/confirm` и `/reject` — отдельное решение по write action.

### Воспроизводимый demo-сценарий

Grounded ответы отражают текущее состояние API: приоритетная очередь — `CASPIAN STAR 91`, `TURAN 71`, `BAKU EXPRESS 63`. CASPIAN STAR объясняется восемью текущими Risk Factors модели `CI-RISK-2.0`; это фактическое число факторов в Risk Engine, а не заранее заданная формулировка. `EV-2803` фиксирует встречу с TURAN на минимальной дистанции `174 m` в течение `167 min` (`2h 47m`), Network возвращает `14` исторических встреч и `18h 42m` суммарного времени. ETA в Актау — `15:05`, окно `14:52–15:18`, confidence `87%`; Pre-Arrival рекомендует совместимый причал `#5` и отдельные проверки груза, осадки и рейса.

Map Assistant вызывает spatial tool только при наличии области. Port Assistant объясняет рост handling pressure через ETA, `7` подходов, занятые причалы, прогноз и bottleneck; текущая утилизация `68%` не смешивается с прогнозными `74%` через четыре часа.

### Проверка и границы

```bash
.venv/Scripts/python -m unittest discover -s backend/tests -v
npm run build
```

## Реальная географическая карта

Операционные карты используют `MapLibre GL JS 6.2.0` и векторную подложку OpenFreeMap вместо нарисованной схемы. Единый компонент отображает порты, суда, AIS-треки, маршруты, risk/events, environmental polygons, coverage и пользовательские области как GeoJSON-слои с реальными координатами. Масштабирование, перемещение, выбор объектов, фильтры слоёв, fit-to-bounds и spatial selection работают через географический API карты.

- `VITE_MAP_STYLE_URL` — необязательный URL собственного MapLibre style JSON; по умолчанию используется `https://tiles.openfreemap.org/styles/liberty`;
- `VITE_MAP_SATELLITE_STYLE_URL` — URL лицензированной спутниковой подложки. Пока он не задан, кнопка «Спутник» отключена, чтобы обычная карта не выдавалась за спутниковую;
- attribution OpenStreetMap/OpenFreeMap сохраняется на карте;
- при недоступности внешней подложки интерфейс включает локальный нейтральный style и сохраняет рабочими собственные GeoJSON-слои и переходы к объектам.

Для production с требованиями SLA рекомендуется указать собственный/self-hosted style через `VITE_MAP_STYLE_URL`; код слоёв и бизнес-функции при смене провайдера не меняются.

Stage 8 runtime, как и предыдущие этапы, использует in-memory demo state; PostgreSQL/PostGIS-схема содержит нормализованное хранение conversations, messages, tool calls, data access, claims/evidence, actions, audit, Cases, evidence, notes, timeline и summaries, но подключение runtime к production database не заявляется как выполненное. Для произвольного языка за пределами проверенных intents потребуется подключить LLM к тому же permissioned Tool Layer; модель не должна получать прямой обход tools или самостоятельно выполнять write actions.

## Environmental Intelligence

Девятый этап добавляет экологический контур без подмены наблюдений выводами о виновности:

`provider input → raw observation → normalized Environmental Event → wind/current reconstruction → historical AIS search → possible vessel associations → human review / Investigation`.

Environmental Data Gateway не привязан к конкретному поставщику. Он принимает внешний API-ответ, предварительно обработанный спутниковый продукт, ручную запись или demo payload через один нормализующий контракт и хранит исходный payload отдельно от события. Runtime содержит воспроизводимый in-memory demo provider; реальный спутниковый оператор, собственная CV-модель и production PostGIS не заявляются как подключённые. SQL-контур подготовлен для `Polygon`/`MultiPolygon`, пространственных индексов, raw provenance и последующей замены адаптера.

### Environmental Center и карточка события

- `/app/environment` показывает очередь: `4` активных события, `1` high priority, `2` в расследовании и `17` resolved;
- `/app/environment/events/ENV-2026-00142` объединяет текущий pollution polygon, расчётную origin area, три исторических трека, ветер и течение;
- слои `Environmental Events` и `Pollution Areas` доступны на основной карте;
- вкладка `Экология` в профиле судна показывает историю возможных связей с экологическими событиями;
- timeline и replay разделяют наблюдаемые спутниковые данные, расчётную реконструкцию и выводы association-модели.

Детализированный demo-event `ENV-2026-00142` (`ENV-142`) — обнаруженная 14 мая 2026 года в `08:40` область возможного нефтяного загрязнения площадью `3.4 km²`, confidence `87%`, статус `UNDER REVIEW`. Backward reconstruction по наблюдениям ветра, течения и погоды возвращает не точку, а вероятный origin interval `03:20–05:40` и несколько изменяющихся полигонов.

Historical spatial search сначала рассматривает `12` судов, находившихся в расширенном пространственно-временном коридоре, после чего оставляет три объяснимых candidate association:

- `CASPIAN STAR` — `0.8 km`, temporal overlap `94%`, наблюдался AIS gap, relevance `HIGH`;
- `TURAN` — `2.4 km`, overlap `72%`, relevance `MEDIUM`;
- `BAKU EXPRESS` — `7.1 km`, overlap `31%`, relevance `LOW`.

Ранг использует расстояние, временное пересечение, направление движения, тип и скорость судна, маршрут, AIS gaps, остановки и доступную историю. Encounter, draught, cargo и fuel могут отображаться только как отдельный контекст. Association означает возможную пространственно-временную связь и не устанавливает источник загрязнения, намерение или нарушение.

### Risk, review и Investigation

Для CASPIAN STAR модель `CI-ENV-RISK-1.0` показывает текущий maritime risk `91` и объяснимый environmental context `+8`, то есть contextual priority `99/100`. Вклад раскрывается через четыре отдельных фактора: `ENVIRONMENTAL_PROXIMITY +3`, `ENVIRONMENTAL_TIME_OVERLAP +2`, `ENVIRONMENTAL_ROUTE_MATCH +1` и `ENVIRONMENTAL_ASSOCIATION +2`. Канонический морской score не переписывается скрыто: экологический контекст помечен как `UNDER REVIEW`, связан с `ENV-2026-00142` и candidate evidence и требует решения аналитика. Так один и тот же признак не превращается автоматически в заключение о причинности.

Human review разделяет два независимых решения:

- классификация события: `CONFIRMED POLLUTION`, `LIKELY POLLUTION`, `UNCERTAIN` или `FALSE POSITIVE`;
- установленность источника: `UNKNOWN` или `VERIFIED EXTERNAL FINDING`.

Создание environmental Case — отдельная подтверждаемая write-операция. `ENV-2026-0041` получает спутниковое обнаружение, affected polygon, погоду, течение, reconstruction, AIS tracks, candidate records, AIS gaps и связанные voyage events как отдельные evidence с типами `FACT`, `ESTIMATE` и `INFERENCE`. Даже подтверждение факта загрязнения само по себе не подтверждает его источник.

Assistant получил permissioned read-tools `get_environmental_event`, `get_environmental_candidates`, `get_environmental_reconstruction` и `get_environmental_timeline`. Вопросы `Что известно про ENV-142?`, `Какие суда могли быть связаны?` и `Почему CASPIAN STAR первый кандидат?` читают Environmental API и возвращают внутренние evidence links; при отсутствии записи Assistant сообщает об отсутствии данных.

### API девятого этапа

- `GET|POST /api/v1/environment/events` — очередь и provider-neutral ingest;
- `GET /api/v1/environment/events/{id}` — событие, geometry, provenance и текущий review;
- `GET /api/v1/environment/events/{id}/candidates` — relevant или extended historical candidates;
- `GET /api/v1/environment/events/{id}/reconstruction` — origin interval и weather/current inputs;
- `GET /api/v1/environment/events/{id}/timeline` — единая evidence timeline;
- `GET /api/v1/environment/events/{id}/replay` — синхронные pollution areas и vessel states;
- `GET /api/v1/environment/events/{id}/raw` — разрешённый raw source record;
- `GET /api/v1/environment/events/{id}/risk-context/{vessel_id}` — объяснимый environmental risk context;
- `GET /api/v1/environment/events/{id}/reviews` — история решений и классификаций источника;
- `GET /api/v1/vessels/{vessel_id}/environment` — история экологических associations судна;
- `POST /api/v1/environment/events/{id}/review` — аудируемое решение аналитика;
- `POST /api/v1/environment/events/{id}/investigation` — подтверждаемое создание Case;
- `/ws/environment` — `environmental_event_detected`, `environmental_event_updated`, `environmental_candidate_updated`.

### Проверка и границы

```bash
.venv/Scripts/python -m unittest discover -s backend/tests -v
npm run build
```

Stage 9 не содержит автономного обвинительного вывода, автоматического взыскания, достоверного определения источника по одному совпадению и не выдаёт demo satellite input за production feed. Все последствия остаются human-in-the-loop, а значимые оценки сопровождаются provenance и ссылкой на исходное наблюдение или модельный результат.

## Caspian Network

Десятый этап превращает локальный контур вокруг Актау в общую multi-country / multi-port архитектуру. Актау больше не является специальным типом объекта: `Aktau`, `Baku`, `Turkmenbashi`, `Kuryk`, `Alat`, `Astrakhan`, `Makhachkala`, `Anzali` и `Amirabad` находятся в едином Port Registry и используют один контракт `Port + Configuration + Adapter`. Воспроизводимый runtime демонстрирует полные операции как минимум для Актау, Баку и Туркменбаши; остальные узлы показывают запланированный или частичный integration status.

Новые интерфейсы:

- `/app/caspian` — `Caspian Traffic`: `482` active vessels, `127` voyages, `84` port calls, `11` high-risk vessels, `23` AIS gaps, `17` encounters и `2` environmental events;
- `/app/ports` и `/app/ports/{port_id}/{section}` — единый реестр и generic port pages для overview, arrivals, berths, queue, forecast, configuration и integration;
- `/app/caspian/risk` — региональная очередь `CASPIAN STAR 91`, `TURAN 84`, `VOLGA MARINE 78` с фильтрами страны, порта, маршрута и уровня;
- `/app/caspian/routes` — Route Intelligence, включая Baku ↔ Aktau: `284` рейса за 30 дней, средняя длительность `29h 14m`, задержка `42 min`, `17` AIS gaps и `8` high-risk voyages;
- `/app/caspian/verification` — Cross-Port Intelligence с отдельными departure/arrival records и provenance;
- `/app/caspian/network` — evidence-grounded regional graph судов, компаний, портов, грузов и маршрутов;
- `/app/caspian/search` — глобальный поиск по vessels, companies, ports, voyages, events, Cases, environmental events и cargo;
- `/app/caspian/data-health` и `/app/caspian/scope` — источник/покрытие/latency, observability, organization role, data scope и access audit.

### Глобальная идентичность и provenance

`CI-VESSEL-000184` остаётся одним объектом для `caspian-star`, `vessel_184`, `ship_782`, исторических MMSI и названий. Resolver использует IMO, MMSI, call sign, нормализованное имя, размеры, владельца, оператора и identity history; конфликт сильных признаков запрещает автоматическое подтверждение. Аналогично `CASPIAN SHIPPING LTD`, `Caspian Shipping Limited` и `Caspian Shipping Ltd.` разрешаются в `CI-COMPANY-00421`.

Источник не перезаписывает другой источник. Каждое значимое значение хранит source, UTC receive time, quality и статус `OBSERVED`, `REPORTED`, `VERIFIED`, `ESTIMATED` или `INFERRED`. Несовместимые assertions формируют отдельный `DATA CONFLICT`, доступный для review. В демосценарии Baku сообщает `5,000 t / 5.2 m`, Aktau проверяет `4,920 t / 5.1 m`; разница `−80 t` находится внутри настроенного допуска, а обе записи сохраняются. Следующий рейс Aktau → Turkmenbashi продолжает тот же цифровой профиль.

### Organization scope, время и языки

Effective access вычисляется как `USER → ORGANIZATION → ROLE → PERMISSIONS → DATA SCOPE`. `ANALYST` получает региональный read-контур; `PORT_DISPATCHER` Актау видит внутренние операции Актау и подходящие суда, но запрос внутренних данных Baku получает `403`. Доступ и изменения записываются в audit с user, organization, resource, UTC timestamp, decision и фактическим scope.

Backend хранит и возвращает timestamps в UTC (`Z`). Port Registry содержит IANA timezone и UTC offset, а frontend явно подписывает local port time. Архитектура localizations поддерживает `ru-KZ`, `kk-KZ` и `en`; полный перевод всех экранов не заявляется критерием прототипа.

### API десятого этапа

- `GET /api/v1/network/overview`, `/map`, `/risk`, `/routes`, `/routes/{route_id}`;
- `GET /api/v1/network/ports`, `/ports/compare`, `/ports/{port_id}`;
- `GET /api/v1/ports/{port_id}/overview|arrivals|departures|berths|queue|forecast|configuration|integration-status|intelligence`;
- `GET /api/v1/network/vessels/{id}/identity|identity/history|voyages`;
- `POST /api/v1/network/identity/vessels/resolve` и `/identity/companies/resolve`;
- `GET /api/v1/network/companies/{id}` и `/voyages/{id}/cross-port`;
- `GET /api/v1/network/graph`, `/search`, `/data-sources`, `/provenance/{type}/{id}`, `/conflicts`;
- `GET /api/v1/network/data-health`, `/coverage`, `/adapters`, `/observability`, `/audit`, `/access/me`.

Assistant Tool Layer дополнен `get_regional_overview`, `get_regional_risk`, `search_caspian`, `get_global_vessel_identity`, `get_global_vessel_voyages`, `get_route_intelligence`, `get_cross_port_verification`, `get_regional_network` и `get_regional_data_health`. Ответы про весь Каспий вызывают эти tools, учитывают organization scope и возвращают internal evidence links; отсутствующие данные не дополняются предположениями.

### Production readiness и честные границы

SQL-схема добавляет конфигурационные Port Adapters, source records, global identities и history, provenance/conflicts, organization memberships и scopes, regional routes/statistics, cross-port verifications, access audit, transactional outbox/inbox, dead letters, retention policies и observability. Высокообъёмные audit/events/metrics подготовлены к UTC range partitioning; PostGIS geometry имеет spatial indexes. Логический Event Bus допускает Kafka, Redpanda или эквивалент, но runtime прототипа остаётся детерминированным in-memory процессом.

Версия `0.10.0` не заявляет реальные подключения государственных систем пяти стран, production OIDC/JWT provider, Kafka/Redpanda cluster, secrets vault, постоянную PostGIS-БД или сотни миллионов реальных AIS points. Реальные адаптеры должны реализовать стандартные `fetch_arrivals`, `fetch_departures`, `fetch_berths`, `fetch_cargo`, `fetch_documents`, `push_eta` и `push_alert` без изменения потребителей платформы.

Проверка:

```bash
.venv/Scripts/python -m unittest discover -s backend/tests -v
npm run build
```
