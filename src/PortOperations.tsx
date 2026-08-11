import { useMemo, useState } from 'react'
import {
  Activity, Anchor, ArrowLeft, ArrowRight, BarChart3, Check, ChevronRight,
  CircleCheck, Clock3, CloudRain, FileCheck2, Gauge, Info, ListFilter,
  Package, Route, ShieldAlert, Ship, SlidersHorizontal, TimerReset,
  TriangleAlert, Waves,
} from 'lucide-react'
import { aktauPortOperations } from './data'
import type { PortRecommendationStatus } from './types'

function go(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function PortBadge({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'good' | 'warn' | 'danger' | 'info' }) {
  return <span className={`port-badge ${tone}`}>{children}</span>
}

function MetricCard({ label, value, note, icon, tone }: { label: string; value: string | number; note: string; icon: React.ReactNode; tone?: string }) {
  return <div className={`port-metric ${tone || ''}`}><div className="port-metric-icon">{icon}</div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
}

const scenarios = {
  delay: {
    label: 'CASPIAN STAR задерживается на 2 часа',
    description: 'Пересчитать очередь, ожидание и пересечение сервисных окон.',
    wait: '2 ч 31 мин', congestion: '+18 п.п.', affected: '2 судна', peak: '100%',
    queue: ['TURAN', 'BAKU EXPRESS', 'CASPIAN STAR', 'CASPIAN WIND'],
    explanation: 'BAKU EXPRESS проходит раньше CASPIAN STAR; два последующих окна требуют повторной проверки диспетчером.',
  },
  berth: {
    label: 'Причал #5 недоступен 3 часа',
    description: 'Проверить резервные совместимые причалы и рост ожидания.',
    wait: '2 ч 48 мин', congestion: '+22 п.п.', affected: '3 судна', peak: '100%',
    queue: ['TURAN', 'BAKU EXPRESS', 'CASPIAN WIND', 'CASPIAN STAR'],
    explanation: 'Для стали остаётся #7, однако возникает конфликт с BAKU EXPRESS и CASPIAN WIND.',
  },
  weather: {
    label: 'Ветер усиливается до 22 м/с',
    description: 'Применить погодное ограничение к обработке и расписанию.',
    wait: '2 ч 16 мин', congestion: '+14 п.п.', affected: '2 судна', peak: '96%',
    queue: ['TURAN', 'CASPIAN STAR', 'BAKU EXPRESS', 'CASPIAN WIND'],
    explanation: 'Обработка CASPIAN STAR увеличивается с 5 ч 00 мин до 6 ч 20 мин, освобождение #5 смещается на 21:25.',
  },
  service: {
    label: 'Обработка BAKU EXPRESS +1 час',
    description: 'Оценить влияние на CASPIAN WIND и загрузку причала #7.',
    wait: '2 ч 12 мин', congestion: '+11 п.п.', affected: '2 судна', peak: '97%',
    queue: ['TURAN', 'CASPIAN STAR', 'BAKU EXPRESS', 'CASPIAN WIND'],
    explanation: 'Окно CASPIAN WIND смещается; назначение причала не меняется автоматически.',
  },
  newVessel: {
    label: 'Внеплановое судно прибывает в 16:35',
    description: 'Добавить временный заход в порт и оценить доступные окна без изменения рабочего плана.',
    wait: '2 ч 04 мин', congestion: '+9 п.п.', affected: '2 судна', peak: '96%',
    queue: ['TURAN', 'CASPIAN STAR', 'BAKU EXPRESS', 'CASPIAN WIND', 'НОВОЕ ПРИБЫТИЕ'],
    explanation: 'Новое прибытие помещено в изолированную очередь; причал и приоритет должен подтвердить диспетчер.',
  },
} as const

type ScenarioKey = keyof typeof scenarios

export function PortControlCenterPage() {
  const port = aktauPortOperations
  const [decision, setDecision] = useState<PortRecommendationStatus>('PENDING')
  const [scenario, setScenario] = useState<ScenarioKey>('delay')
  const [simulated, setSimulated] = useState(false)
  const scenarioResult = scenarios[scenario]

  return <div className="content-page port-page">
    <section className="port-hero">
      <div className="port-hero-copy"><span className="port-kicker"><i/>УМНЫЙ ПОРТ · АКТАУ</span><h1>Центр управления портом</h1><p>Единая операционная картина прибытия, причалов, очереди и прогнозной нагрузки.</p><div className="port-live"><span/> Операционный контур активен <em>{port.updatedAt}</em></div></div>
      <div className="port-hero-load"><div className="port-load-ring" style={{'--port-load': `${port.operationalLoad * 3.6}deg`} as React.CSSProperties}><span><strong>{port.operationalLoad}%</strong><small>текущая загрузка</small></span></div><p><b>5</b> причалов занято · <b>3</b> доступны</p></div>
      <div className="port-hero-actions"><button className="port-light-button" onClick={() => go('/app/port/aktau/arrivals')}><ListFilter size={16}/>Табло подходов</button><button className="port-outline-button" onClick={() => go('/app/port-calls/pc-aktau-143')}><ShieldAlert size={16}/>До прибытия: 1</button></div>
    </section>

    <div className="port-metrics">
      <MetricCard label="Прибывают" value={port.arriving} note="в ближайшие 6 часов" icon={<Route size={18}/>} />
      <MetricCard label="В порту" value={port.inPort} note="идёт обработка" icon={<Anchor size={18}/>} tone="good" />
      <MetricCard label="Ожидают" value={port.waiting} note="на рейде / в очереди" icon={<Clock3 size={18}/>} tone="warn" />
      <MetricCard label="Отправляются" value={port.departing} note="готовы к выходу" icon={<Ship size={18}/>} />
      <MetricCard label="Среднее ожидание" value={port.averageWaiting} note="текущая очередь" icon={<TimerReset size={18}/>} />
      <MetricCard label="Высокий риск" value={port.highRiskArrivals} note="нужна проверка" icon={<ShieldAlert size={18}/>} tone="danger" />
    </div>

    <div className="port-main-grid">
      <section className="card port-arrivals-card">
        <div className="port-card-head"><div><span className="page-eyebrow">ТАБЛО ПОДХОДОВ</span><h2>Ближайшие подходы</h2></div><button className="port-text-link" onClick={() => go('/app/port/aktau/arrivals')}>Все 7 судов <ArrowRight size={14}/></button></div>
        <div className="port-table-scroll"><table className="port-table"><thead><tr><th>Судно</th><th>ETA заявл.</th><th>Прогноз</th><th>Окно</th><th>Причал</th><th>Риск</th><th/></tr></thead><tbody>{port.arrivals.slice(0, 4).map((arrival) => <tr key={arrival.id} className={arrival.risk >= 75 ? 'attention' : ''}><td><button className="port-vessel-link" onClick={() => arrival.portCallId === port.portCall.id && go(`/app/port-calls/${arrival.portCallId}`)}><span><Ship size={15}/></span><div><strong>{arrival.vesselName}</strong><small>IMO {arrival.imo} · {arrival.cargo}</small></div></button></td><td className="mono">{arrival.reportedEta}</td><td><strong className="mono">{arrival.predictedEta}</strong><small className="port-delay">+{arrival.delayMinutes} мин</small></td><td><span className="mono port-window">{arrival.likelyWindow}</span><small>достоверность {arrival.etaConfidence}%</small></td><td><PortBadge tone={arrival.berth === '#5' ? 'info' : 'neutral'}>{arrival.berth}</PortBadge></td><td><PortBadge tone={arrival.risk >= 75 ? 'danger' : arrival.risk >= 25 ? 'warn' : 'good'}>{arrival.risk}</PortBadge></td><td>{arrival.portCallId === port.portCall.id && <button className="port-row-open" onClick={() => go(`/app/port-calls/${arrival.portCallId}`)} aria-label="Открыть заход в порт"><ChevronRight size={17}/></button>}</td></tr>)}</tbody></table></div>
      </section>

      <section className="card port-attention-card">
        <div className="port-card-head"><div><span className="page-eyebrow">ВНИМАНИЕ ДО ПРИБЫТИЯ</span><h2>CASPIAN STAR</h2></div><div className="port-risk-score">91<small>/100</small></div></div>
        <p className="port-caution"><TriangleAlert size={16}/>Высокий приоритет означает необходимость проверки, а не установленное нарушение.</p>
        <div className="port-attention-route"><span>Баку</span><i/><Ship size={16}/><i/><span>Актау</span></div>
        <div className="port-attention-facts"><div><span>Прогноз ETA</span><strong>15:05</strong><small>окно 14:52–15:18</small></div><div><span>Рекомендуемый причал</span><strong>#5</strong><small>совместим · с 14:45</small></div><div><span>Обработка</span><strong>5 ч 00 мин</strong><small>достоверность 82%</small></div></div>
        <button className="primary-button port-full-button" onClick={() => go('/app/port-calls/pc-aktau-143')}>Открыть отчёт до прибытия <ArrowRight size={15}/></button>
      </section>
    </div>

    <section className="card port-berth-board">
      <div className="port-card-head"><div><span className="page-eyebrow">ГРАФИК ПРИЧАЛОВ · 14:00–22:00</span><h2>Причалы и сервисные окна</h2></div><div className="port-legend"><span><i className="busy"/>занят</span><span><i className="planned"/>запланирован</span><span><i className="attention"/>требует внимания</span></div></div>
      <div className="port-gantt"><div className="port-gantt-scale"><span/><span>14:00</span><span>16:00</span><span>18:00</span><span>20:00</span><span>22:00</span></div>{port.berths.map((berth, index) => <div className="port-gantt-row" key={berth.id}><div className="port-berth-label"><strong>{berth.name}</strong><small>{berth.maxDraught}m · {berth.cargoTypes.join(' / ')}</small></div><div className="port-gantt-track">{berth.currentVessel && <span className="port-gantt-block busy" style={{left: '1%', width: `${[28,0,8,8,0,3,5,0][index]}%`}}><b>{berth.currentVessel}</b></span>}{berth.nextVessel && <span className={`port-gantt-block planned ${berth.nextVessel === 'CASPIAN STAR' ? 'attention' : ''}`} style={{left: `${[34,0,10,15,0,53,0,48][index]}%`, width: `${[26,0,12,59,34,32,0,37][index]}%`}}><b>{berth.nextVessel}</b></span>}<em className="port-now-line"/></div><PortBadge tone={berth.status === 'AVAILABLE' ? 'good' : berth.status === 'LIMITED' ? 'warn' : 'neutral'}>{berth.availableFrom}</PortBadge></div>)}</div>
    </section>

    <div className="port-operations-grid">
      <section className="card port-queue-card"><div className="port-card-head"><div><span className="page-eyebrow">ДИНАМИЧЕСКАЯ ОЧЕРЕДЬ</span><h2>Очередь обслуживания</h2></div><PortBadge tone="info">4 активных</PortBadge></div><div className="port-queue-list">{port.queue.map(item => <div key={item.position} className={item.priority === 'HIGH' ? 'high' : ''}><span className="port-queue-number">{item.position}</span><div><strong>{item.vesselName}</strong><small>{item.eta} · {item.cargo}</small></div><span className="port-queue-berth">{item.berth}</span><p>{item.reason}</p></div>)}</div><p className="port-model-note"><Info size={14}/>Порядок учитывает ETA, совместимость, длительность сервиса и приоритет проверки. Изменение подтверждает диспетчер.</p></section>

      <section className="card port-forecast-card"><div className="port-card-head"><div><span className="page-eyebrow">ПРОГНОЗ ЗАГРУЗКИ ПОРТА</span><h2>Спрос на обработку</h2></div><PortBadge tone="neutral">CI-PORT-1.0</PortBadge></div><div className="port-current-load"><span>Текущая операционная утилизация</span><strong>68%</strong></div><div className="port-forecast-bars">{port.loadForecast.map(point => <div key={point.offset}><div><span style={{height: `${point.load}%`}} className={point.level.toLowerCase()}><b>{point.load}%</b></span></div><strong>{point.time}</strong><small>{point.offset}</small></div>)}</div><div className="port-bottleneck"><TriangleAlert size={17}/><div><strong>Узкое окно · 16:00–19:00</strong><span>Причалы #3–#5 до 91% · четыре прибытия за 75 минут</span></div></div></section>

      <section className="card port-weather-card"><div className="port-card-head"><div><span className="page-eyebrow">ПОГОДА И ОГРАНИЧЕНИЯ</span><h2>Погодный контекст</h2></div><CloudRain size={21}/></div><div className="port-weather-now"><strong>12.4 <small>м/с</small></strong><span>Ветер сейчас<small>волна 0.8 м · достоверность 94%</small></span></div><div className="port-weather-status"><CircleCheck size={16}/><span><strong>Ограничений нет</strong><small>Портовая метеостанция · ЗАЯВЛЕНО</small></span></div><div className="port-weather-impact"><span>При ветре 22 м/с</span><strong>5 ч 00 мин <ArrowRight size={14}/> 6 ч 20 мин</strong><small>+80 минут · освобождение #5 в 21:25</small></div></section>
    </div>

    <section className={`card port-recommendation ${decision.toLowerCase()}`}>
      <div className="port-rec-icon"><SlidersHorizontal size={22}/></div><div className="port-rec-main"><span className="page-eyebrow">ОПЕРАЦИОННАЯ РЕКОМЕНДАЦИЯ</span><h2>{port.recommendation.title}: {port.recommendation.fromBerth} <ArrowRight size={16}/> {port.recommendation.toBerth}</h2><p>{port.recommendation.explanation}</p><div className="port-rec-factors">{port.recommendation.factors.map(factor => <span key={factor}><Check size={12}/>{factor}</span>)}</div></div><div className="port-rec-impact"><div><span>Ожидание</span><strong>{port.recommendation.waitingEffect}</strong></div><div><span>Пиковая нагрузка</span><strong>{port.recommendation.loadBefore}% <ArrowRight size={13}/> {port.recommendation.loadAfter}%</strong></div></div><div className="port-rec-actions">{decision === 'PENDING' ? <><button className="primary-button" onClick={() => setDecision('ACCEPTED')}><Check size={15}/>Принять</button><button className="secondary-button" onClick={() => setDecision('CHANGED')}>Изменить</button><button className="port-text-button" onClick={() => setDecision('DEFERRED')}>Отложить</button></> : <><PortBadge tone={decision === 'ACCEPTED' ? 'good' : decision === 'DEFERRED' ? 'warn' : 'info'}>{decision === 'ACCEPTED' ? 'ПРИНЯТО ДИСПЕТЧЕРОМ' : decision === 'CHANGED' ? 'ОТПРАВЛЕНО НА ИЗМЕНЕНИЕ' : 'ОТЛОЖЕНО'}</PortBadge><button className="port-text-button" onClick={() => setDecision('PENDING')}>Вернуть демо</button></>}</div>
    </section>

    <section className="card port-simulator">
      <div className="port-card-head"><div><span className="page-eyebrow">ЧТО ЕСЛИ · ИЗОЛИРОВАННЫЙ СЦЕНАРИЙ</span><h2>Оценка влияния до изменения расписания</h2></div><PortBadge tone="info">не меняет план</PortBadge></div>
      <div className="port-sim-grid"><div className="port-scenario-list">{(Object.keys(scenarios) as ScenarioKey[]).map(key => <button key={key} className={scenario === key ? 'active' : ''} onClick={() => { setScenario(key); setSimulated(false) }}><span>{scenarios[key].label}</span><small>{scenarios[key].description}</small><ChevronRight size={16}/></button>)}</div><div className="port-sim-result">{!simulated ? <div className="port-sim-empty"><BarChart3 size={28}/><strong>Сценарий готов к расчёту</strong><p>{scenarioResult.description}</p><button className="primary-button" onClick={() => setSimulated(true)}>Рассчитать влияние</button></div> : <><div className="port-sim-result-head"><span>Результат сценария</span><strong>{scenarioResult.label}</strong></div><div className="port-sim-kpis"><div><span>Среднее ожидание</span><strong>1 ч 42 мин <ArrowRight size={13}/> {scenarioResult.wait}</strong></div><div><span>Перегрузка</span><strong>{scenarioResult.congestion}</strong></div><div><span>Затронуто</span><strong>{scenarioResult.affected}</strong></div><div><span>Пик</span><strong>{scenarioResult.peak}</strong></div></div><div className="port-sim-queue"><span>Новая расчётная очередь</span>{scenarioResult.queue.map((name, i) => <div key={name}><b>{i + 1}</b>{name}</div>)}</div><p><Info size={14}/>{scenarioResult.explanation}</p></>}</div></div>
    </section>
  </div>
}

export function PortArrivalsPage() {
  const port = aktauPortOperations
  return <div className="content-page port-page port-arrivals-page">
    <button className="port-back" onClick={() => go('/app/port/aktau')}><ArrowLeft size={15}/>Центр управления портом</button>
    <div className="port-page-title"><div><span className="page-eyebrow">АКТАУ · ТАБЛО ПОДХОДОВ</span><h1>Табло подходов</h1><p>Заявленное и прогнозное время, вероятное окно, очередь и операционный приоритет.</p></div><div className="port-title-status"><span/><strong>7 подходов</strong><small>{port.updatedAt}</small></div></div>
    <section className="card port-full-arrivals"><div className="mobile-record-list">{port.arrivals.map(arrival=><button className="mobile-record-card" key={arrival.id} onClick={()=>arrival.portCallId===port.portCall.id&&go(`/app/port-calls/${arrival.portCallId}`)}><span className="mobile-record-icon"><Ship size={18}/></span><span className="mobile-record-main"><strong>{arrival.queuePosition}. {arrival.vesselName}</strong><small>IMO {arrival.imo} · {arrival.cargoMass} {arrival.cargo}</small><span>Окно {arrival.likelyWindow} · причал {arrival.berth}</span></span><PortBadge tone={arrival.risk>=75?'danger':arrival.risk>=25?'warn':'good'}>Риск {arrival.risk}</PortBadge><span className="mobile-record-meta"><span>Заявлено<b>{arrival.reportedEta}</b></span><span>Прогноз<b>{arrival.predictedEta}</b></span><span>Достоверность<b>{arrival.etaConfidence}%</b></span><span>Статус<b>{arrival.status==='ATTENTION'?'Внимание':arrival.status==='WAITING'?'Ожидает':'По плану'}</b></span></span></button>)}</div><div className="port-table-scroll desktop-data-table"><table className="port-table"><thead><tr><th>#</th><th>Судно / груз</th><th>ETA заявл.</th><th>Прогноз ETA</th><th>Вероятное окно</th><th>Достоверность</th><th>Причал</th><th>Риск</th><th>Статус</th><th/></tr></thead><tbody>{port.arrivals.map(arrival => <tr key={arrival.id} className={arrival.risk >= 75 ? 'attention' : ''}><td><b className="port-position">{arrival.queuePosition}</b></td><td><div className="port-vessel-link"><span><Ship size={15}/></span><div><strong>{arrival.vesselName}</strong><small>IMO {arrival.imo} · {arrival.cargoMass} {arrival.cargo}</small></div></div></td><td className="mono">{arrival.reportedEta}</td><td><strong className="mono">{arrival.predictedEta}</strong><small className="port-delay">+{arrival.delayMinutes} мин</small></td><td className="mono">{arrival.likelyWindow}</td><td><div className="port-confidence"><i style={{width: `${arrival.etaConfidence}%`}}/><span>{arrival.etaConfidence}%</span></div></td><td><PortBadge tone="info">{arrival.berth}</PortBadge></td><td><PortBadge tone={arrival.risk >= 75 ? 'danger' : arrival.risk >= 25 ? 'warn' : 'good'}>{arrival.risk}</PortBadge></td><td><PortBadge tone={arrival.status === 'ATTENTION' ? 'danger' : arrival.status === 'WAITING' ? 'warn' : 'good'}>{arrival.status==='ATTENTION'?'ВНИМАНИЕ':arrival.status==='WAITING'?'ОЖИДАЕТ':'ПО ПЛАНУ'}</PortBadge></td><td>{arrival.portCallId === port.portCall.id && <button className="port-row-open" onClick={() => go(`/app/port-calls/${arrival.portCallId}`)}><ChevronRight size={17}/></button>}</td></tr>)}</tbody></table></div></section>
    <p className="port-footnote"><Info size={14}/>ETA является вероятностным прогнозом и обновляется при новых AIS, погодных и операционных данных. Показатель достоверности не означает гарантию времени прибытия.</p>
  </div>
}

export function PreArrivalReportPage() {
  const call = aktauPortOperations.portCall
  const [weatherApplied, setWeatherApplied] = useState(false)
  const serviceTotal = weatherApplied ? '6 ч 20 мин' : call.expectedService.replace('h ', ' ч ').replace('m', ' мин')
  const release = weatherApplied ? '21:25' : call.projectedRelease
  const timeline = useMemo(() => call.timeline, [call.timeline])

  return <div className="content-page port-page prearrival-page">
    <button className="port-back" onClick={() => go('/app/port/aktau')}><ArrowLeft size={15}/>Центр управления портом</button>
    <section className="prearrival-hero"><div className="prearrival-identity"><div className="prearrival-ship"><Ship size={24}/></div><div><span className="port-kicker"><i/>ОТЧЁТ ДО ПРИБЫТИЯ · {call.id}</span><h1>{call.vesselName}</h1><p>IMO {call.imo} · Баку <ArrowRight size={12}/> Актау · Рейс CI-240810</p></div></div><div className="prearrival-status"><span>Операционный статус</span><strong>ПОДХОДИТ</strong><small>Очередь #{call.queuePosition} · причал #5</small></div><div className="prearrival-risk"><span>Приоритет риска</span><strong>{call.risk}<small>/100</small></strong><em>КРИТИЧЕСКИЙ · CI-RISK-2.0</em></div></section>
    <p className="port-caution prearrival-caution"><TriangleAlert size={16}/>Отчёт помогает подготовить портовую операцию. Risk Score и события не доказывают нарушение и не заменяют решение уполномоченного сотрудника.</p>

    <div className="prearrival-top-grid">
      <section className="card eta-card"><div className="port-card-head"><div><span className="page-eyebrow">ОБЪЯСНИМЫЙ ПРОГНОЗ ETA · CI-ETA-1.0</span><h2>Прогноз прибытия</h2></div><PortBadge tone="good">достоверность 87%</PortBadge></div><div className="eta-main"><div><span>Заявлено</span><strong>14:30</strong></div><ArrowRight size={21}/><div className="predicted"><span>Прогноз</span><strong>15:05</strong><small>+35 минут</small></div></div><div className="eta-window"><span>Вероятное окно</span><strong>{call.etaWindow}</strong><small>пересчитывается при новых наблюдениях</small></div><div className="eta-factors"><div><span>Текущая позиция</span><strong>96 км до Актау</strong><em>основа</em></div><div><span>Скорость</span><strong>12,4 уз / обычно 11,8</strong><em>+8 мин</em></div><div><span>Состояние маршрута</span><strong>возвращение в коридор</strong><em>+21 мин</em></div><div><span>Погода</span><strong>12,4 м/с · 0,8 м</strong><em>+6 мин</em></div></div></section>

      <section className="card berth-fit-card"><div className="port-card-head"><div><span className="page-eyebrow">СОВМЕСТИМОСТЬ С ПРИЧАЛОМ</span><h2>Рекомендация: причал #5</h2></div><PortBadge tone="good">СОВМЕСТИМО</PortBadge></div><div className="berth-window"><Anchor size={22}/><div><span>Будет доступен</span><strong>14:45</strong><small>плановое освобождение TURAN CARRIER</small></div></div><div className="compatibility-list">{call.compatibility.map(item => <div key={item.label} className={item.result === 'NOT_COMPATIBLE' ? 'failed' : ''}><span>{item.result === 'COMPATIBLE' ? <Check size={14}/> : <TriangleAlert size={14}/>}</span><strong>{item.label}</strong><small>{item.vessel}</small><em>{item.berth}</em></div>)}</div><p><Info size={14}/>Причал #2 исключён: плановая осадка 5,0 м превышает лимит 4,5 м.</p></section>
    </div>

    <div className="prearrival-middle-grid">
      <section className="card service-card"><div className="port-card-head"><div><span className="page-eyebrow">ВРЕМЯ ОБРАБОТКИ · CI-SERVICE-1.0</span><h2>План обработки</h2></div><PortBadge tone="good">достоверность 82%</PortBadge></div><div className="service-total"><span>Расчётная длительность</span><strong>{serviceTotal}</strong><small>освобождение #5 · {release}</small></div><div className="service-breakdown"><div style={{'--segment': '80%'} as React.CSSProperties}><span>Обработка груза</span><strong>4 ч 00 мин</strong><i/></div><div style={{'--segment': '11.7%'} as React.CSSProperties}><span>Документы</span><strong>35 мин</strong><i/></div><div style={{'--segment': '8.3%'} as React.CSSProperties}><span>Швартовка / прочее</span><strong>25 мин</strong><i/></div>{weatherApplied && <div className="weather-segment" style={{'--segment': '21%'} as React.CSSProperties}><span>Погодная задержка</span><strong>+80 мин</strong><i/></div>}</div><button className={weatherApplied ? 'secondary-button' : 'port-weather-button'} onClick={() => setWeatherApplied(!weatherApplied)}><CloudRain size={15}/>{weatherApplied ? 'Вернуть текущую погоду' : 'Что если ветер 22 м/с?'}</button></section>

      <section className="card action-card"><div className="port-card-head"><div><span className="page-eyebrow">РЕКОМЕНДУЕМЫЕ ДЕЙСТВИЯ</span><h2>Подготовка до прибытия</h2></div><FileCheck2 size={20}/></div><div className="action-list">{call.recommendedActions.map((action, index) => <div key={action}><span>{index + 1}</span><div><strong>{action}</strong><small>{['Окно доступности с 14:45','Сопоставить с ЗАЯВЛЕНО 5 000 т','Зафиксировать независимое ПРОВЕРЕННОЕ наблюдение','7 значимых событий · открыть доказательства'][index]}</small></div>{index === 3 && <button onClick={() => go('/app/events')}>События <ChevronRight size={13}/></button>}</div>)}</div></section>

      <section className="card risk-context-card"><div className="port-card-head"><div><span className="page-eyebrow">КОНТЕКСТ РЕЙСА</span><h2>Почему нужна проверка</h2></div><ShieldAlert size={20}/></div><div className="risk-context-list">{call.riskReasons.map((reason, index) => <div key={reason}><i className={index < 2 ? 'high' : 'medium'}/><span><strong>{reason}</strong><small>{['Наблюдаемая траектория','Покрытие AIS','14 встреч / 11 вне портов','Заявлено и расчёт модели','Оценка с поправкой на погоду'][index]}</small></span></div>)}</div><div className="risk-context-actions"><button className="secondary-button" onClick={() => go('/app/risk')}>Риск-центр</button><button className="secondary-button" onClick={() => go('/app/voyages/voy-001/intelligence')}>Аналитика рейса</button></div></section>
    </div>

    <section className="card port-feedback-card"><div className="port-card-head"><div><span className="page-eyebrow">ФАКТ И ПРОГНОЗ · ДЕМОНСТРАЦИЯ ОБРАТНОЙ СВЯЗИ</span><h2>Как фактические данные улучшают модели</h2></div><PortBadge tone="info">историческая демо-копия</PortBadge></div><p className="port-feedback-intro">Ниже показан уже завершённый учебный цикл того же сценария. Эти факты не подменяют текущий статус «ПОДХОДИТ».</p><div className="feedback-grid"><div><span>ETA</span><strong>15:05 <ArrowRight size={14}/> 15:20</strong><em>ошибка +15 мин</em></div><div><span>Обработка</span><strong>5 ч 00 мин <ArrowRight size={14}/> 4 ч 42 мин</strong><em>ошибка −18 мин</em></div><div><span>Груз</span><strong>5 000 т <ArrowRight size={14}/> 4 920 т</strong><em>ЗАЯВЛЕНО → ПРОВЕРЕНО</em></div><div><span>Осадка</span><strong>4,5 м <ArrowRight size={14}/> 5,1 м</strong><em>ЗАЯВЛЕНО → ПРОВЕРЕНО</em></div></div><div className="port-feedback-note"><Activity size={16}/><span><strong>Обратная связь записана отдельно от исходных данных</strong><small>Модель получает ошибку ETA, ошибку обработки и подтверждённые портом наблюдения; история декларации не перезаписывается.</small></span></div></section>

    <section className="card port-call-timeline-card"><div className="port-card-head"><div><span className="page-eyebrow">ЖИЗНЕННЫЙ ЦИКЛ ЗАХОДА В ПОРТ</span><h2>Операционная хронология</h2></div><PortBadge tone="neutral">Заход в порт ≠ рейс</PortBadge></div><div className="port-call-timeline">{timeline.map(event => <div key={event.id} className={event.status.toLowerCase()}><time>{event.time}</time><span><i/></span><div><strong>{event.title}</strong><small>{event.detail}</small></div><PortBadge tone={event.status === 'ACTUAL' ? 'good' : event.status === 'PREDICTED' ? 'info' : 'neutral'}>{event.status === 'ACTUAL' ? 'ФАКТ' : event.status === 'PREDICTED' ? 'ПРОГНОЗ' : 'ПЛАН'}</PortBadge></div>)}</div></section>
  </div>
}
