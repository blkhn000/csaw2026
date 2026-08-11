# Caspian Intelligence — руководство по функциональности

Версия документа: `1.0`  
Версия платформы: `0.10.0`  
Статус: рабочий демонстрационный контур этапов 1–10

## 1. Назначение платформы

Caspian Intelligence объединяет мониторинг судов, рейсов, портов, событий, рисков, грузов, топлива, экологической обстановки и региональных связей в одном интерфейсе. Платформа предназначена для ситуационной осведомлённости и поддержки решений оператора или аналитика.

Система обнаруживает признаки, показывает их происхождение и предлагает приоритет проверки. Она не устанавливает факт нарушения, виновность или намерение автоматически.

Основной поток данных:

```text
AIS и внешние источники
  → нормализация и контроль качества
  → текущее положение и история
  → профиль поведения судна
  → обнаруженные события
  → объяснимая оценка риска
  → расширенная аналитика
  → портовый и региональный контекст
  → ИИ-помощник и расследования
```

## 2. Быстрый запуск

### 2.1. Интерфейс

Требуется Node.js и npm.

```bash
npm install
npm run dev
```

Интерфейс: `http://localhost:5173`.

Production-сборка:

```bash
npm run build
npm run preview
```

### 2.2. Backend API

```powershell
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
.venv\Scripts\uvicorn backend.app.main:app --reload
```

API: `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`  
OpenAPI: `http://localhost:8000/openapi.json`  
Проверка состояния: `GET /health`

### 2.3. Docker

```bash
docker compose up --build
```

После запуска:

- интерфейс — `http://localhost:8080`;
- FastAPI работает внутри compose-сети;
- PostgreSQL/PostGIS получает схему из `backend/schema.sql`;
- Redis доступен backend-контейнеру.

## 3. Авторизация и роли

Демонстрационный вход принимает любую непустую пару email/password. Роль выбирается по началу email:

| Начало email | Роль | Токен |
|---|---|---|
| `admin...` | `ADMIN` | `ci-demo-admin` |
| `viewer...` | `VIEWER` | `ci-demo-viewer` |
| `port...` или `dispatcher...` | `PORT_DISPATCHER` | `ci-demo-port-dispatcher` |
| остальные адреса | `ANALYST` | `ci-demo-analyst` |

Вызов входа:

```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "analyst@caspian.int",
  "password": "demo"
}
```

Для защищённых запросов:

```http
Authorization: Bearer ci-demo-analyst
```

Права:

- `ADMIN` — полный демонстрационный доступ;
- `ANALYST` — региональная аналитика, чувствительные данные, аудит и расследования;
- `VIEWER` — просмотр разрешённых публичных региональных данных;
- `PORT_DISPATCHER` — операции Актау и суда, подходящие к Актау; внутренние данные других портов ограничены.

Изменяющие действия ИИ не выполняются сразу: система создаёт ожидающее действие, проверяет право и требует отдельного подтверждения.

## 4. Общая навигация

После авторизации доступны следующие основные разделы:

| Экран | Маршрут | Назначение |
|---|---|---|
| Сеть Каспия | `/app/caspian` | Региональная сводка пяти стран |
| Карта | `/app/map` | Реальная карта, суда, маршруты и события |
| Суда | `/app/vessels` | Реестр флота и поиск |
| Рейсы | `/app/voyages` | Активные и завершённые рейсы |
| История | `/app/history` | Воспроизведение движения и событий |
| Риск-центр | `/app/risk` | Приоритетная очередь и объяснение риска |
| События | `/app/events` | Детекторы и решения аналитика |
| Экология | `/app/environment` | Экологические события и реконструкция |
| ИИ-помощник | `/app/assistant` | Работа с платформой обычным языком |
| Расследования | `/app/investigations` | Кейсы, доказательства и выводы |
| Разбор рейса | `/app/voyages/voy-001/intelligence` | Груз, осадка, топливо и экономика |
| Сеть связей | `/app/network` | Граф объектов и доказуемых связей |
| Порты | `/app/ports` | Региональный реестр портов |
| Центр Актау | `/app/port/aktau` | Операционный Smart Port |
| Аналитика | `/app/analytics` | Сводные показатели региона |
| Настройки | `/app/settings` | Профиль и параметры интерфейса |

Глобальный поиск открывается из верхней панели. Он ищет суда по названию, IMO и MMSI, а также порты. Из результата можно перейти к региональному поиску.

## 5. Реальная карта Каспия

Карта построена на `MapLibre GL JS 6.2.0` и OpenFreeMap. Это географическая векторная карта, а не нарисованная схема.

Рабочие функции:

- масштабирование и перемещение;
- возврат к исходному виду;
- русские географические подписи при наличии `name:ru` у провайдера;
- отображение портов и судов по реальным координатам;
- кластеризация судов;
- AIS-треки и маршруты;
- слои событий, риска и экологических областей;
- фильтр уровней риска;
- выбор судна, порта или события;
- информационная панель выбранного объекта;
- режим реального времени и исторический режим;
- воспроизведение трека;
- выделение географической области для запроса ИИ;
- обновление судов через WebSocket и демонстрационный поток;
- сохранение операционных GeoJSON-слоёв при недоступности внешней подложки.

Переменные окружения:

```env
VITE_MAP_STYLE_URL=https://tiles.openfreemap.org/styles/liberty
VITE_MAP_SATELLITE_STYLE_URL=
VITE_API_BASE=http://localhost:8000/api/v1
```

Спутниковый режим включается только при заданном лицензированном `VITE_MAP_SATELLITE_STYLE_URL`. Платформа не выдаёт обычную подложку за спутниковую.

## 6. Суда и цифровой профиль

### 6.1. Реестр судов

Экран `/app/vessels` предоставляет:

- поиск по названию, IMO и MMSI;
- фильтрацию навигационного статуса;
- тип и флаг судна;
- скорость, курс, пункт назначения и ETA;
- время последнего обновления;
- переход в карточку судна.

### 6.2. Карточка судна

Маршрут: `/app/vessels/{vessel_id}`.

Вкладки карточки:

- `Обзор` — основные характеристики, позиция и текущие показатели;
- `Текущий рейс` — маршрут, пройденное и оставшееся расстояние, ETA;
- `Трек` — исторические координаты и график движения;
- `История` — предыдущие рейсы;
- `Поведение` — индивидуальный baseline;
- `События` — события текущего рейса;
- `Риск` — оценка, факторы и история;
- `Экология` — возможные связи с экологическими событиями;
- `Связи` — связанные суда и объекты;
- `Аналитика` — груз, осадка, топливо и экономика.

### 6.3. Behavior Engine

Индивидуальный профиль рассчитывается по истории конкретного судна и содержит:

- повторяющиеся маршруты и коридоры;
- скорость по фазам рейса;
- обычные и редкие порты;
- исторические зоны остановок;
- историю заявленной осадки;
- пространственные и временные паттерны активности;
- повторные встречи и совместное присутствие;
- количество наблюдений и confidence baseline.

Низкая уверенность baseline означает недостаток истории, а не высокий риск.

## 7. Рейсы и история движения

Экран `/app/voyages` показывает демонстрационные активные рейсы, маршрут, время отправления, прогресс, скорость, ETA и статус.

Экран `/app/history` работает как морской видеорегистратор:

- выбор периода и времени;
- выбор судов;
- включение событий рейса;
- воспроизведение по временной шкале;
- скорости `1×`, `2×`, `4×`;
- показ AIS gap и вероятной области перемещения;
- синхронизация позиции и события на карте.

## 8. Автоматическое обнаружение событий

Event Engine реализует следующие детекторы:

1. отклонение от индивидуального маршрутного коридора;
2. отсутствие AIS дольше порога;
3. остановка вне обычной или разрешённой зоны;
4. скорость вне baseline текущей фазы рейса;
5. продолжительная близкая встреча судов;
6. изменение заявленной осадки;
7. расширенные события груза, топлива, экономики и связей.

Для события отображаются:

- тип, severity и confidence;
- статус и время;
- судно и связанный объект;
- наблюдаемые метрики;
- объяснение правила;
- факторы и ссылки на источник;
- группа коррелированных событий;
- решение аналитика.

`Severity`, `confidence` и `status` — разные показатели. Событие само по себе не является доказательством нарушения.

## 9. Risk Engine

Risk Engine формирует объяснимую оценку приоритета `0–100`.

Уровни:

| Диапазон | Уровень |
|---:|---|
| 0–24 | Низкий |
| 25–49 | Умеренный |
| 50–74 | Высокий |
| 75–100 | Критический |

Функции Risk Center:

- очередь судов по приоритету;
- фильтрация уровня риска;
- карта риска;
- декомпозиция итоговой оценки;
- переход от фактора к исходному событию;
- различение риска рейса и исторического риска судна;
- история изменения оценки;
- оценки десяти последних рейсов;
- уведомления о значимом росте;
- review фактора аналитиком;
- lifecycle фактора: `ACTIVE → RECENT → HISTORICAL`;
- снижение вклада со временем;
- версия модели и конфигурация правил.

Модель `CI-RISK-1.0` формирует базовую оценку. `CI-RISK-2.0` добавляет ограниченный и взвешенный расширенный контекст. Сырые значения расширенных факторов не складываются с базой напрямую: учитываются качество данных, confidence, корреляционный предел и защита от двойного учёта.

Демонстрационный snapshot CASPIAN STAR на `2026-08-10 17:46 UTC+5`:

```text
Базовый риск 84 + расширенный контекст 7 = 91
```

Risk lifecycle зависит от времени. При пересчёте после snapshot активные факторы переходят в `RECENT` и оценка может стать ниже `91`; историческая запись `91` при этом сохраняется.

## 10. Расширенная аналитика рейса

Экран `/app/voyages/voy-001/intelligence` объединяет:

- маршрут, AIS и встречи;
- происхождение каждого значения;
- грузовую декларацию и позиции груза;
- cargo timeline;
- модель осадки конкретного судна;
- сравнение ожидаемой и наблюдаемой осадки;
- ожидаемый и сообщённый расход топлива;
- погодную и операционную коррекцию топлива;
- стоимость груза и оценку стоимости рейса;
- экономический коэффициент;
- единую временную шкалу фактов, оценок и выводов;
- передачу объяснимых сигналов в Risk Engine.

Статусы данных:

- `ЗАЯВЛЕНО` (`REPORTED`) — получено из документа или внешней системы;
- `РАСЧЁТ` (`ESTIMATED`) — рассчитано моделью;
- `ПРОВЕРЕНО` (`VERIFIED`) — подтверждено независимым источником.

## 11. Сеть связей

Экран `/app/network` показывает граф:

- судов;
- компаний;
- владельцев;
- операторов;
- портов;
- грузов;
- рейсов.

Связь содержит тип, период, confidence, объяснение и доказательства. Для встреч показываются количество, число встреч в открытом море, средняя дистанция и суммарная длительность. Нажатие на узел или ребро открывает инспектор объекта.

## 12. Smart Port Aktau

### 12.1. Центр управления

Маршрут `/app/port/aktau` содержит:

- текущую загрузку порта;
- ближайшие подходы;
- заявленный и прогнозный ETA;
- вероятное окно прибытия;
- загрузку и совместимость причалов;
- динамическую очередь;
- прогноз нагрузки;
- погодные ограничения;
- операционную рекомендацию;
- сценарии «что если» без автоматического изменения плана.

### 12.2. Табло подходов

Маршрут `/app/port/aktau/arrivals` показывает полную очередь судов, груз, ETA, прогноз, confidence, причал, риск и операционный статус.

### 12.3. Отчёт до прибытия

Маршрут `/app/port-calls/pc-aktau-143` содержит:

- explainable ETA и вероятное окно;
- рекомендацию причала и проверку совместимости;
- оценку времени обработки;
- погодный сценарий;
- рекомендуемые действия персоналу;
- контекст риска;
- фактические и прогнозные значения;
- обратную связь для моделей;
- lifecycle PortCall.

Назначение причала и изменение очереди являются write-операциями и требуют роли и подтверждения.

## 13. Экологический мониторинг

Environmental Intelligence обрабатывает внешнее наблюдение по цепочке:

```text
сырой источник
  → нормализованное экологическое событие
  → полигон наблюдения
  → реконструкция по ветру и течению
  → исторический пространственный поиск
  → возможные связи с судами
  → review или расследование
```

### 13.1. Environmental Center

Маршрут `/app/environment` предоставляет очередь, поиск и фильтр статуса. Карточки показывают тип, время, площадь, confidence и текущий review.

### 13.2. Карточка события

Маршрут `/app/environment/events/{event_id}` содержит:

- исходный контур загрязнения;
- вероятную область происхождения;
- ветер, течение и погодные входы;
- исторические треки судов;
- ранжированных кандидатов;
- расстояние и временное пересечение;
- timeline и replay;
- evidence и provenance;
- экологический контекст риска;
- решение аналитика;
- создание Investigation Case.

Связь судна с экологическим событием является пространственно-временной гипотезой для проверки и не устанавливает источник загрязнения.

Решение разделено на классификацию события и подтверждение источника внешним заключением.

## 14. ИИ-помощник

ИИ-помощник работает поверх существующих сервисов. Он не является отдельным источником фактов.

Функции:

- история текущего диалога;
- контекст открытой страницы, судна, рейса или выделенной области;
- распознавание проверенных намерений;
- вызов разрешённых read-tools;
- структурированный ответ с типами `Факт`, `Оценка`, `Вывод`;
- ссылки на события, факторы, суда, рейсы и доказательства;
- объяснение риска;
- поиск судов и событий обычным языком;
- анализ выделенной области карты;
- объяснение портовой загрузки и ETA;
- региональный поиск;
- отказ от ответа при отсутствии данных;
- аудит вопроса, вызванных инструментов и прочитанных данных.

Read-tools:

```text
get_vessel                     get_current_voyage
get_vessel_events              get_vessel_risk
get_risk_factors               get_behavior_profile
get_encounters                 get_cargo_analysis
get_fuel_analysis              get_vessel_network
search_vessels                 search_events
search_area                    get_port_status
get_arrivals                   get_port_forecast
get_eta                        get_pre_arrival
get_environmental_event        get_environmental_candidates
get_environmental_reconstruction
get_environmental_timeline     get_regional_overview
get_regional_risk              search_caspian
get_global_vessel_identity     get_global_vessel_voyages
get_route_intelligence         get_cross_port_verification
get_regional_network           get_regional_data_health
```

Write-tools:

```text
create_investigation   add_case_evidence
update_investigation   add_case_note
assign_berth           change_port_queue
close_event
```

Каждый write-tool требует отдельного подтверждения через action endpoint. Чтение и запись разделены.

## 15. Расследования

Маршруты:

- `/app/investigations` — список кейсов;
- `/app/investigations/{case_id}` — рабочее пространство кейса.

Investigation Case хранит:

- идентификатор, заголовок, статус и приоритет;
- судно и рейс;
- ответственного;
- события и доказательства;
- связанные суда и компании;
- заметки;
- временную шкалу;
- сводку и заключение.

Поддерживаются создание кейса, добавление выбранного evidence, заметки, изменение workflow-полей и grounded summary только по данным конкретного кейса.

## 16. Caspian Network

Региональный контур объединяет пять прибрежных стран и девять портовых узлов.

### 16.1. Региональная сводка

`/app/caspian` показывает:

- активные суда;
- рейсы и заходы в порты;
- суда высокого риска;
- AIS gaps и встречи;
- экологические события;
- региональную карту;
- очередь внимания;
- пульс портов;
- качество источников;
- текущую область доступа.

### 16.2. Дополнительные региональные экраны

| Маршрут | Функция |
|---|---|
| `/app/ports` | Реестр портов и статус интеграции |
| `/app/ports/{port_id}/{section}` | Универсальная карточка порта |
| `/app/caspian/risk` | Региональная очередь риска |
| `/app/caspian/routes` | Аналитика маршрутов |
| `/app/caspian/verification` | Сверка данных отправления и прибытия |
| `/app/caspian/network` | Региональный граф объектов |
| `/app/caspian/search` | Поиск по единому региональному каталогу |
| `/app/caspian/data-health` | Качество, задержка и покрытие источников |
| `/app/caspian/scope` | Роль, permissions, data scope и аудит |

### 16.3. Глобальная идентичность

Один физический объект получает стабильный `CI-VESSEL-*` или `CI-COMPANY-*` идентификатор. Resolver учитывает IMO, MMSI, call sign, имя, размеры, владельца и историю идентификаторов. Конфликт сильных признаков не подтверждается автоматически.

### 16.4. Provenance и конфликты

Значения разных источников не перезаписывают друг друга. Для каждого утверждения сохраняются источник, время получения в UTC, качество и статус. Несовместимые записи формируют отдельный data conflict для review.

## 17. REST API

Все маршруты ниже имеют префикс `/api/v1`, кроме `/health`.

### 17.1. Авторизация

```text
POST /auth/login
GET  /users/me
```

### 17.2. Суда, позиции и рейсы

```text
GET  /vessels
GET  /vessels/live
GET  /vessels/{vessel_id}
GET  /vessels/{vessel_id}/positions
GET  /vessels/{vessel_id}/track
GET  /vessels/{vessel_id}/voyages
GET  /voyages/{voyage_id}
GET  /map/vessels
POST /ais/ingest
GET  /data-quality
POST /spatial-search
GET  /search
```

### 17.3. Поведение и связи

```text
GET  /vessels/{vessel_id}/behavior
GET  /vessels/{vessel_id}/behavior/routes
GET  /vessels/{vessel_id}/behavior/speed
GET  /vessels/{vessel_id}/behavior/ports
GET  /vessels/{vessel_id}/behavior/stops
GET  /vessels/{vessel_id}/behavior/draught
GET  /vessels/{vessel_id}/behavior/activity
POST /vessels/{vessel_id}/behavior/recalculate
GET  /vessels/{vessel_id}/connections
GET  /vessels/{vessel_id}/network
```

### 17.4. События

```text
GET   /events
GET   /events/{event_id}
PATCH /events/{event_id}/status
GET   /vessels/{vessel_id}/events
GET   /voyages/{voyage_id}/events
GET   /encounters
GET   /event-groups
GET   /event-groups/{group_id}
```

### 17.5. Риск

```text
GET   /risk/vessels
GET   /risk/high-priority
GET   /risk/notifications
GET   /risk/rules
GET   /vessels/{vessel_id}/risk
GET   /vessels/{vessel_id}/risk/history
GET   /vessels/{vessel_id}/risk/voyages
GET   /voyages/{voyage_id}/risk
GET   /voyages/{voyage_id}/risk/factors
PATCH /risk/factors/{factor_id}/review
```

### 17.6. Расширенная аналитика

```text
GET /voyages/{voyage_id}/cargo
GET /voyages/{voyage_id}/fuel
GET /voyages/{voyage_id}/economics
GET /voyages/{voyage_id}/intelligence
GET /companies/{company_id}
GET /companies/{company_id}/vessels
```

### 17.7. Портовые операции

```text
GET  /ports
GET  /ports/{port_id}/vessels
GET  /ports/{port_id}/overview
GET  /ports/{port_id}/arrivals
GET  /ports/{port_id}/departures
GET  /ports/{port_id}/high-risk-arrivals
GET  /ports/{port_id}/berths
GET  /ports/{port_id}/berths/{berth_id}/compatibility
GET  /ports/{port_id}/queue
GET  /ports/{port_id}/load-forecast
GET  /ports/{port_id}/forecast
GET  /ports/{port_id}/configuration
GET  /ports/{port_id}/integration-status
GET  /ports/{port_id}/intelligence
GET  /ports/{port_id}/recommendations
GET  /ports/{port_id}/weather
POST /ports/{port_id}/weather/recalculate
GET  /ports/{port_id}/events
GET  /port-calls/{port_call_id}
GET  /port-calls/{port_call_id}/pre-arrival
GET  /port-calls/{port_call_id}/berth-recommendation
GET  /port-calls/{port_call_id}/events
GET  /port-calls/{port_call_id}/feedback
POST /port-calls/{port_call_id}/actuals
GET  /vessels/{vessel_id}/eta
POST /berth-assignments
POST /simulations
```

### 17.8. Экология

```text
GET  /environment/events
POST /environment/events
GET  /environment/events/{event_id}
GET  /environment/events/{event_id}/candidates
GET  /environment/events/{event_id}/reconstruction
GET  /environment/events/{event_id}/timeline
GET  /environment/events/{event_id}/replay
GET  /environment/events/{event_id}/raw
GET  /environment/events/{event_id}/risk-context/{vessel_id}
GET  /environment/events/{event_id}/reviews
POST /environment/events/{event_id}/review
POST /environment/events/{event_id}/investigation
GET  /vessels/{vessel_id}/environment
```

### 17.9. ИИ и расследования

```text
GET   /assistant/tools
POST  /assistant/chat
GET   /assistant/conversations
GET   /assistant/conversations/{conversation_id}
GET   /assistant/audit
GET   /investigations
POST  /investigations
GET   /investigations/{investigation_id}
PATCH /investigations/{investigation_id}
POST  /investigations/{investigation_id}/evidence
POST  /investigations/{investigation_id}/notes
POST  /investigations/{investigation_id}/summarize
POST  /assistant/actions/{action_id}/confirm
POST  /assistant/actions/{action_id}/reject
```

### 17.10. Региональная сеть

```text
GET  /network/overview
GET  /network/map
GET  /network/risk
GET  /network/routes
GET  /network/routes/{route_id}
GET  /network/ports
GET  /network/ports/compare
GET  /network/ports/{port_id}
GET  /network/vessels/{vessel_id}/identity
GET  /network/vessels/{vessel_id}/identity/history
GET  /network/vessels/{vessel_id}/voyages
POST /network/identity/vessels/resolve
GET  /network/companies/{company_id}
POST /network/identity/companies/resolve
GET  /network/voyages/{voyage_id}/cross-port
GET  /network/graph
GET  /network/search
GET  /network/data-sources
GET  /network/provenance/{entity_type}/{entity_id}
GET  /network/conflicts
GET  /network/data-health
GET  /network/coverage
GET  /network/adapters
GET  /network/observability
GET  /network/audit
GET  /network/access/me
```

Точные query-параметры, request bodies и response schemas всегда доступны в Swagger UI и являются исполняемым контрактом.

## 18. WebSocket

Подключение требует demo-токен в query-параметре.

```text
ws://localhost:8000/ws/vessels?token=ci-demo-analyst
ws://localhost:8000/ws/ports/aktau?token=ci-demo-analyst
ws://localhost:8000/ws/environment?token=ci-demo-analyst
ws://localhost:8000/ws/network?token=ci-demo-analyst
```

Потоки передают обновления позиций, риска, событий, портовой обстановки, экологических событий и региональной сводки. Клиент использует REST snapshot как исходное состояние, а WebSocket — для последующих изменений.

## 19. Хранение данных

`backend/schema.sql` содержит production-oriented схему PostgreSQL/PostGIS для:

- raw AIS и нормализованных сообщений;
- текущего состояния и истории позиций;
- рейсов и геозон;
- behavior baseline;
- событий, групп и evidence;
- risk assessments, factors, history, rules и reviews;
- грузов, осадки, топлива и экономики;
- компаний и связей;
- портов, причалов, очереди, ETA, actuals и feedback;
- диалогов ИИ, tool calls, claims, audit и actions;
- Investigation Cases, заметок и доказательств;
- экологических наблюдений и геометрий;
- глобальной идентичности, provenance и conflicts;
- transactional outbox/inbox, dead letters, retention и observability.

Важно: текущие Python-сервисы в основном работают на детерминированном in-memory demo state. Наличие SQL-схемы не означает, что весь runtime уже переключён на постоянную БД.

## 20. Тестовые данные

Frontend содержит расширенный набор демонстрационных судов, рейсов и событий. Основной сквозной сценарий построен вокруг CASPIAN STAR:

- рейс Баку → Актау;
- AIS gap;
- отклонение маршрута;
- встреча с TURAN;
- изменение осадки;
- грузовая, топливная и экономическая аналитика;
- риск `91`;
- ETA Актау `15:05`;
- рекомендуемый причал `#5`;
- экологическое событие `ENV-2026-00142`;
- Investigation Case и региональная связь.

Демонстрационные значения нужны для воспроизводимости интерфейса и тестов. Их нельзя интерпретировать как реальные сведения о судах или организациях.

## 21. Проверка проекта

Frontend:

```bash
npm run build
```

Полный диагностический запуск backend-тестов:

```powershell
.venv\Scripts\python -m unittest discover -s backend/tests -v
```

Отдельные контуры:

```powershell
.venv\Scripts\python -m unittest backend.tests.test_event_engine -v
.venv\Scripts\python -m unittest backend.tests.test_risk_engine -v
.venv\Scripts\python -m unittest backend.tests.test_advanced_analytics -v
.venv\Scripts\python -m unittest backend.tests.test_port_operations -v
.venv\Scripts\python -m unittest backend.tests.test_assistant -v
.venv\Scripts\python -m unittest backend.tests.test_environmental -v
.venv\Scripts\python -m unittest backend.tests.test_caspian_network -v
```

Текущий статус проверки на `2026-08-11`: frontend-сборка проходит; backend выполняет `70` тестов, из них `64` проходят и `6` time-sensitive assertions не проходят. Причина — тесты ожидают активный risk snapshot `91` от `2026-08-10`, тогда как runtime уже применяет lifecycle decay к его факторам и возвращает более низкую текущую оценку. Это известное ограничение тестовой фикстуры, а не ошибка документации. Перед CI-релизом demo clock необходимо зафиксировать или assertions должны явно передавать `as_of`.

Ручная проверка:

1. войти как аналитик;
2. открыть `/app/caspian` и проверить региональную карту;
3. открыть CASPIAN STAR и пройти все вкладки;
4. в Risk Center открыть факторы и исходные события;
5. запустить воспроизведение истории;
6. открыть аналитику рейса и сеть связей;
7. проверить Smart Port и отчёт до прибытия;
8. открыть `ENV-2026-00142`;
9. задать вопрос ИИ и проверить evidence links;
10. создать расследование и подтвердить добавление доказательств.

## 22. Ограничения текущей версии

В версии `0.10.0` не заявлены как production-ready:

- коммерческий AIS-провайдер;
- реальные портовые, таможенные и государственные интеграции;
- реальный спутниковый провайдер;
- промышленная погодная интеграция;
- production OIDC/JWT;
- secrets vault;
- постоянный runtime поверх PostGIS для всех модулей;
- Kafka/Redpanda cluster;
- произвольный LLM для неограниченного естественного языка;
- автономное принятие юридически или операционно значимых решений.

Также текущая risk test fixture привязана к абсолютному времени демонстрационного сценария `2026-08-10`; без фиксированного demo clock lifecycle decay делает часть точных score assertions зависимой от даты запуска.

При недоступности backend часть интерфейса использует локальный demo snapshot. Источник данных явно помечается как API или демо. Все изменяющие действия должны оставаться human-in-the-loop.

## 23. Основные файлы проекта

| Файл | Назначение |
|---|---|
| `src/App.tsx` | Главная оболочка, маршруты и основные экраны |
| `src/RealCaspianMap.tsx` | Реальная карта и GeoJSON-слои |
| `src/CaspianNetwork.tsx` | Региональная платформа |
| `src/Assistant.tsx` | ИИ-помощник и расследования |
| `src/Environmental.tsx` | Экологический мониторинг |
| `src/PortOperations.tsx` | Smart Port Aktau |
| `src/data.ts` | Frontend demo dataset |
| `src/types.ts` | Типы данных интерфейса |
| `backend/app/main.py` | REST и WebSocket endpoints |
| `backend/app/ais_gateway.py` | Приём и нормализация AIS |
| `backend/app/behavior_engine.py` | Профиль поведения |
| `backend/app/event_engine.py` | Детекторы событий |
| `backend/app/risk_engine.py` | Оценка риска |
| `backend/app/advanced_analytics.py` | Груз, осадка, топливо, экономика и связи |
| `backend/app/port_operations.py` | Портовые расчёты |
| `backend/app/assistant.py` | Tool planner, grounding, cases и audit |
| `backend/app/environmental.py` | Экологические события и реконструкция |
| `backend/app/caspian_network.py` | Региональные identities, ports и scope |
| `backend/schema.sql` | PostgreSQL/PostGIS schema |

## 24. Принципы интерпретации

- Аномалия — это признак для проверки, а не доказательство.
- Risk Score — приоритет внимания, а не вероятность виновности.
- Confidence — качество оценки, а не гарантия результата.
- `REPORTED`, `ESTIMATED` и `VERIFIED` нельзя смешивать.
- Возможная экологическая связь не означает установленный источник.
- Ответ ИИ должен иметь источник или сообщать об отсутствии данных.
- Write-action выполняется только после проверки прав и подтверждения человека.
