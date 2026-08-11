import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle, ArrowLeft, ArrowRight, Bot, Check, ChevronRight, CircleCheck,
  Clock3, CloudRain, Database, Droplets, ExternalLink, FileSearch, Filter,
  Gauge, History, Info, Layers3, Leaf, Map, Navigation, Pause, Play, Plus,
  RefreshCw, Satellite, Search, ShieldCheck, Ship, Sparkles, Target, Waves,
  Wind, X,
} from 'lucide-react'
import './environmental.css'
import { RealCaspianMap, boundsForCoordinates, type RealMapArea, type RealMapLine } from './RealCaspianMap'

type ProvenanceKind = 'observed' | 'estimated' | 'inferred'
type EnvironmentStatus = 'detected' | 'analyzing' | 'under_review' | 'investigation' | 'resolved' | 'false_positive'

type GeoJSONGeometry = {
  type: 'Polygon' | 'MultiPolygon' | string
  coordinates: unknown
}

type Coordinates = {
  latitude?: number
  longitude?: number
  lat?: number
  lon?: number
}

type EnvironmentalObservation = {
  id?: string
  label?: string
  name?: string
  category?: string
  parameter?: string
  value?: string | number
  unit?: string
  provenance?: ProvenanceKind | string
  kind?: ProvenanceKind | string
  source?: string
  source_id?: string
  source_reference?: string
  direction_degrees?: number
  observed_at?: string
  timestamp?: string
  confidence?: number
}

export type EnvironmentalEvent = {
  id: string
  type: string
  title?: string
  description?: string
  summary?: string
  detected_at: string
  estimated_started_at?: string
  estimated_ended_at?: string
  geometry?: GeoJSONGeometry
  center?: Coordinates
  area_km2: number
  detection_source?: string
  source_reference?: string
  source?: string
  confidence: number
  status: EnvironmentStatus | string
  environmental_data?: EnvironmentalObservation[] | (Record<string, unknown> & {
    observations?: EnvironmentalObservation[]
    weather?: string
    wind?: EnvironmentalVector
    current?: EnvironmentalVector
  })
  observations?: EnvironmentalObservation[]
  risk_context?: EnvironmentalRiskContext
  provenance?: string
  priority?: string
  disclaimer?: string
  created_at?: string
  updated_at?: string
}

type EnvironmentalVector = {
  speed?: number
  speed_mps?: number
  speed_kn?: number
  direction?: number
  direction_degrees?: number
  bearing?: number
  label?: string
  source?: string
  observed_at?: string
  confidence?: number
  provenance?: string
  value?: number | string
  unit?: string
}

type TrackPoint = Coordinates & {
  timestamp?: string
  recorded_at?: string
  time?: string
}

export type EnvironmentalCandidate = {
  id?: string
  rank?: number
  vessel_id: string
  vessel_name: string
  imo?: string
  association_level?: string
  relevance?: string
  priority?: string
  score?: number
  association_score?: number
  distance_km?: number
  closest_distance_km?: number
  overlap_percent?: number
  time_overlap_percent?: number
  temporal_overlap_percent?: number
  ais_gap?: boolean
  has_ais_gap?: boolean
  rationale?: string
  explanation?: string
  factors?: Array<string | { label?: string; name?: string; value?: string | number; observed?: string; interpretation?: string; provenance?: string }>
  evidence_ids?: string[]
  track?: TrackPoint[]
  positions?: TrackPoint[]
  ais_track?: TrackPoint[]
  risk_context?: EnvironmentalRiskContext
}

type EnvironmentalRiskContext = {
  maritime_risk_score?: number
  environmental_adjustment?: number
  environmental_adjustment_raw?: number
  environmental_adjustment_effective?: number
  combined_context_score?: number
  priority_score?: number
  factors?: Array<{
    id: string
    code?: string
    label: string
    observed: string
    contribution: number
    provenance?: string
    interpretation?: string
    source_ids?: string[]
  }>
  model_version?: string
  explanation?: string
  disclaimer?: string
}

export type EnvironmentalReconstruction = {
  id?: string
  event_id?: string
  origin_geometry?: GeoJSONGeometry
  current_geometry?: GeoJSONGeometry
  origin_area?: GeoJSONGeometry
  estimated_origin_geometry?: GeoJSONGeometry
  estimated_started_at?: string
  estimated_ended_at?: string
  estimated_origin_from?: string
  estimated_origin_to?: string
  time_window_start?: string
  time_window_end?: string
  confidence?: number
  method?: string
  model_version?: string
  explanation?: string
  wind?: EnvironmentalObservation & EnvironmentalVector
  current?: EnvironmentalObservation & EnvironmentalVector
  weather?: string | EnvironmentalObservation[] | Record<string, unknown>
  inputs?: EnvironmentalObservation[]
  provenance?: EnvironmentalObservation[]
  steps?: Array<{ timestamp?: string; geometry?: GeoJSONGeometry; area_km2?: number; provenance?: string }>
  limitation?: string
}

type TimelineItem = {
  id?: string
  timestamp?: string
  time?: string
  title?: string
  label?: string
  detail?: string
  description?: string
  type?: string
  provenance?: ProvenanceKind | string
  source_id?: string
  source_ids?: string[]
}

type ReplayFrame = {
  timestamp?: string
  time?: string
  geometry?: GeoJSONGeometry
  pollution_geometry?: GeoJSONGeometry
  origin_geometry?: GeoJSONGeometry
  vessels?: Array<{ vessel_id?: string; vessel_name?: string; latitude?: number; longitude?: number; ais_available?: boolean; provenance?: string }>
}

type EventListResponse = {
  events?: EnvironmentalEvent[]
  total?: number
  stats?: Record<string, number>
  summary?: Record<string, number>
  active_count?: number
  high_priority_count?: number
  in_investigation_count?: number
  resolved_count?: number
}

type CandidateResponse = {
  candidates?: EnvironmentalCandidate[]
  relevant_candidates?: EnvironmentalCandidate[]
  total_candidates?: number
  historical_candidates?: number
  searched_vessels?: number
  searched_candidate_count?: number
  relevant_candidate_count?: number
  disclaimer?: string
}

type ReviewDecision = 'confirmed_pollution' | 'likely_pollution' | 'uncertain' | 'false_positive'

type Navigate = (path: string) => void

const API_BASE = import.meta.env.VITE_API_BASE || (
  ['4173', '5173'].includes(window.location.port)
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : '/api/v1'
)

const DEFAULT_EVENT_ID = 'ENV-2026-00142'

function apiHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('ci-access-token') || 'ci-demo-analyst'}`,
  }
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...apiHeaders(), ...(options?.headers || {}) },
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail || `API ${response.status}`)
  }
  return response.json() as Promise<T>
}

function defaultNavigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function listFrom<T>(value: unknown, keys: string[]): T[] {
  if (Array.isArray(value)) return value as T[]
  if (!value || typeof value !== 'object') return []
  const object = value as Record<string, unknown>
  for (const key of keys) if (Array.isArray(object[key])) return object[key] as T[]
  return []
}

function objectFrom<T>(value: unknown, keys: string[]): T {
  if (value && typeof value === 'object') {
    const object = value as Record<string, unknown>
    for (const key of keys) if (object[key] && typeof object[key] === 'object') return object[key] as T
  }
  return value as T
}

function safeNumber(value: unknown, fallback = 0) {
  const number = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(number) ? number : fallback
}

function confidencePercent(value: number | undefined) {
  const normalized = safeNumber(value)
  return Math.round(normalized <= 1 ? normalized * 100 : normalized)
}

function formatDate(value?: string, withDate = true) {
  if (!value) return 'Нет данных'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ru-RU', withDate
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { hour: '2-digit', minute: '2-digit' },
  ).format(date)
}

function statusKey(status: string) {
  return status.toLowerCase().trim().replaceAll(' ', '_')
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    detected: 'Обнаружено', analyzing: 'Анализируется', under_review: 'На проверке',
    investigation: 'Расследование', resolved: 'Закрыто', false_positive: 'Ложное срабатывание',
  }
  return labels[statusKey(status)] || status.replaceAll('_', ' ')
}

function typeLabel(type: string) {
  const labels: Record<string, string> = {
    oil_pollution: 'Возможное нефтяное загрязнение', oil_spill: 'Возможное нефтяное загрязнение',
    pollution: 'Загрязнение', algal_bloom: 'Цветение воды', debris: 'Плавающие объекты', floating_waste: 'Плавающие объекты',
    unknown_pollution: 'Неустановленное загрязнение',
  }
  return labels[type.toLowerCase()] || type.replaceAll('_', ' ')
}

function levelClass(value?: string) {
  const level = (value || '').toLowerCase().replaceAll(' ', '_')
  if (level.includes('high') || level.includes('critical')) return 'high'
  if (level.includes('medium') || level.includes('moderate')) return 'medium'
  if (level.includes('low')) return 'low'
  return 'neutral'
}

function provenanceKind(value?: string): ProvenanceKind {
  const normalized = (value || '').toLowerCase()
  if (normalized.includes('observ')) return 'observed'
  if (normalized.includes('infer')) return 'inferred'
  return 'estimated'
}

function eventData(event: EnvironmentalEvent) {
  return Array.isArray(event.environmental_data) ? event.environmental_data : event.environmental_data?.observations || []
}

function environmentalRecord(event: EnvironmentalEvent) {
  return !Array.isArray(event.environmental_data) ? event.environmental_data : undefined
}

function ProvenanceBadge({ value }: { value?: string }) {
  const kind = provenanceKind(value)
  const labels = { observed: 'Наблюдение', estimated: 'Оценка', inferred: 'Вывод' }
  return <span className={`env-provenance ${kind}`}>{labels[kind]}</span>
}

function EmptyState({ title, detail, onRetry }: { title: string; detail: string; onRetry?: () => void }) {
  return <div className="env-empty">
    <Database size={26}/>
    <strong>{title}</strong>
    <span>{detail}</span>
    {onRetry && <button className="secondary-button" onClick={onRetry}><RefreshCw size={14}/>Повторить</button>}
  </div>
}

function EnvironmentalPageHeader({ eyebrow, title, description, children }: {
  eyebrow: string
  title: string
  description: string
  children?: ReactNode
}) {
  return <div className="page-header env-page-header">
    <div><span className="page-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
    {children && <div className="header-actions">{children}</div>}
  </div>
}

function EnvironmentalStat({ label, value, tone, note }: { label: string; value: number; tone: string; note: string }) {
  return <div className="env-stat">
    <span><i className={tone}/>{label}</span>
    <strong>{value}</strong>
    <small>{note}</small>
  </div>
}

function EnvironmentalEventRow({ event, onOpen }: { event: EnvironmentalEvent; onOpen: () => void }) {
  return <button className="env-event-row" onClick={onOpen}>
    <span className={`env-event-icon ${levelClass(event.status)}`}><Droplets size={19}/></span>
    <span className="env-event-main">
      <span><strong>{event.id}</strong><em>{typeLabel(event.type)}</em></span>
      <small><Satellite size={12}/>{event.detection_source || event.source || 'Источник не указан'}</small>
    </span>
    <span className="env-event-metric"><small>Площадь</small><strong>{safeNumber(event.area_km2).toLocaleString('ru-RU')} км²</strong></span>
    <span className="env-event-metric"><small>Уверенность</small><strong>{confidencePercent(event.confidence)}%</strong></span>
    <span className={`env-status ${statusKey(event.status)}`}>{statusLabel(event.status)}</span>
    <time>{formatDate(event.detected_at)}</time>
    <ChevronRight size={17}/>
  </button>
}

export function EnvironmentalCenterPage({ navigate = defaultNavigate }: { navigate?: Navigate }) {
  const [response, setResponse] = useState<EventListResponse | EnvironmentalEvent[] | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')

  const load = async () => {
    setLoading(true); setError('')
    try { setResponse(await api<EventListResponse | EnvironmentalEvent[]>('/environment/events')) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось загрузить экологические события') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    void load()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const token = localStorage.getItem('ci-access-token') || 'ci-demo-analyst'
    const socket = new WebSocket(`${protocol}://${window.location.hostname}:8000/ws/environment?token=${encodeURIComponent(token)}`)
    socket.onmessage = message => {
      try {
        const payload = JSON.parse(message.data) as { type?: string }
        if (payload.type?.startsWith('environmental_')) void load()
      } catch { /* Ignore malformed external frames; REST remains authoritative. */ }
    }
    return () => socket.close()
  }, [])

  const events = useMemo(() => listFrom<EnvironmentalEvent>(response, ['events', 'items', 'results']), [response])
  const objectResponse = !Array.isArray(response) && response ? response : null
  const summary = objectResponse ? (objectResponse.summary || objectResponse.stats || {}) : {}
  const active = safeNumber(objectResponse?.active_count ?? summary.active ?? summary.active_events, events.filter(item => !['resolved', 'false_positive'].includes(statusKey(item.status))).length)
  const high = safeNumber(objectResponse?.high_priority_count ?? summary.high ?? summary.high_priority, events.filter(item => confidencePercent(item.confidence) >= 80 && !['resolved', 'false_positive'].includes(statusKey(item.status))).length)
  const investigations = safeNumber(objectResponse?.in_investigation_count ?? summary.investigation ?? summary.investigations, events.filter(item => statusKey(item.status) === 'investigation').length)
  const resolved = safeNumber(objectResponse?.resolved_count ?? summary.resolved, events.filter(item => statusKey(item.status) === 'resolved').length)
  const filtered = events.filter(event => {
    const matchesQuery = `${event.id} ${event.type} ${event.title || ''} ${event.detection_source || event.source || ''}`.toLowerCase().includes(query.toLowerCase())
    return matchesQuery && (status === 'all' || statusKey(event.status) === status)
  })

  return <div className="content-page environmental-center-page">
    <EnvironmentalPageHeader
      eyebrow="Экологический мониторинг"
      title="Экологический центр"
      description="Единый контроль экологических наблюдений, реконструкций и связанных расследований."
    >
      <button className="secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''}/>Обновить</button>
      <button className="primary-button" onClick={() => navigate(`/app/environment/events/${DEFAULT_EVENT_ID}`)}><Map size={15}/>Открыть карту</button>
    </EnvironmentalPageHeader>

    <div className="env-principle"><ShieldCheck size={17}/><span><strong>Система показывает признаки и степень соответствия.</strong> Связь судна с районом не является доказательством источника загрязнения и требует проверки аналитиком.</span></div>

    <section className="env-stat-strip">
      <EnvironmentalStat label="Активные" value={active} tone="teal" note="требуют наблюдения"/>
      <EnvironmentalStat label="Высокий приоритет" value={high} tone="amber" note="по уверенности и контексту"/>
      <EnvironmentalStat label="В расследовании" value={investigations} tone="navy" note="собираются доказательства"/>
      <EnvironmentalStat label="Закрытые" value={resolved} tone="green" note="с решением аналитика"/>
    </section>

    <section className="card env-events-card">
      <div className="env-events-toolbar">
        <div className="inline-search"><Search size={16}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Событие, тип или источник"/></div>
        <label><Filter size={14}/><select value={status} onChange={event => setStatus(event.target.value)}><option value="all">Все статусы</option><option value="detected">Обнаружено</option><option value="analyzing">Анализируется</option><option value="under_review">На проверке</option><option value="investigation">Расследование</option><option value="resolved">Закрыто</option><option value="false_positive">Ложное срабатывание</option></select></label>
        <span>{filtered.length} событий</span>
      </div>
      <div className="env-list-head"><span>Событие</span><span>Площадь</span><span>Уверенность</span><span>Статус</span><span>Обнаружено</span><span/></div>
      {loading && <div className="env-loading-list">{[0, 1, 2].map(item => <span key={item}/>)}</div>}
      {!loading && error && <EmptyState title="API экологического мониторинга недоступен" detail={error} onRetry={() => void load()}/>} 
      {!loading && !error && filtered.map(event => <EnvironmentalEventRow key={event.id} event={event} onOpen={() => navigate(`/app/environment/events/${event.id}`)}/>)}
      {!loading && !error && !filtered.length && <EmptyState title="События не найдены" detail="Измените фильтр или поисковый запрос."/>}
    </section>
  </div>
}

function extractRings(geometry?: GeoJSONGeometry): number[][][] {
  if (!geometry || !Array.isArray(geometry.coordinates)) return []
  const coordinates = geometry.coordinates as unknown[]
  if (geometry.type === 'Polygon') return (coordinates as number[][][]).filter(Array.isArray)
  if (geometry.type === 'MultiPolygon') return (coordinates as number[][][][]).flatMap(polygon => polygon.filter(Array.isArray))
  return []
}

function trackOf(candidate: EnvironmentalCandidate): TrackPoint[] {
  return candidate.track || candidate.positions || candidate.ais_track || []
}

type MapLayers = { pollution: boolean; origin: boolean; tracks: boolean; weather: boolean }

function EnvironmentalMap({ event, reconstruction, candidates, frame, layers, onLayers }: {
  event: EnvironmentalEvent
  reconstruction: EnvironmentalReconstruction | null
  candidates: EnvironmentalCandidate[]
  frame?: ReplayFrame
  layers: MapLayers
  onLayers: (value: MapLayers) => void
}) {
  const currentGeometry = frame?.pollution_geometry || frame?.geometry || event.geometry
  const originGeometry = frame?.origin_geometry || reconstruction?.origin_geometry || reconstruction?.origin_area || reconstruction?.estimated_origin_geometry
  const currentRings = extractRings(currentGeometry)
  const originRings = extractRings(originGeometry)
  const candidateTracks = candidates.map(candidate => ({ candidate, points: trackOf(candidate) })).filter(item => item.points.length)
  const colors = ['#c56a2e', '#137c72', '#6578a4', '#8a6a9f']
  const lines:RealMapLine[]=layers.tracks?candidateTracks.map(({candidate,points},index)=>({
    id:`candidate-${candidate.id||candidate.vessel_id}`,
    coordinates:points.map(point=>[safeNumber(point.longitude??point.lon),safeNumber(point.latitude??point.lat)]),
    color:colors[index%colors.length],kind:'candidate-track',label:candidate.vessel_name,
  })):[]
  const areas:RealMapArea[]=[
    ...(layers.origin?originRings.map((ring,index)=>({id:`origin-${index}`,rings:[ring],kind:'origin' as const,label:'Вероятная область источника'})):[]),
    ...(layers.pollution?currentRings.map((ring,index)=>({id:`pollution-${index}`,rings:[ring],kind:'pollution' as const,label:'Наблюдаемый контур'})):[]),
  ]
  const replayVessels=layers.tracks?(frame?.vessels||[]).map((vessel,index)=>({
    id:vessel.vessel_id||`replay-${index}`,name:vessel.vessel_name||vessel.vessel_id||`Vessel ${index+1}`,
    longitude:safeNumber(vessel.longitude),latitude:safeNumber(vessel.latitude),status:vessel.ais_available===false?'ESTIMATED':'OBSERVED',
    color:colors[index%colors.length],detail:vessel.ais_available===false?'Estimated during AIS gap':'Observed AIS',
  })):[]
  const allCoordinates:Array<[number,number]>=[
    ...currentRings.flat().map(point=>[safeNumber(point[0]),safeNumber(point[1])] as [number,number]),
    ...originRings.flat().map(point=>[safeNumber(point[0]),safeNumber(point[1])] as [number,number]),
    ...lines.flatMap(line=>line.coordinates),
    ...replayVessels.map(vessel=>[vessel.longitude,vessel.latitude] as [number,number]),
  ].filter(point=>point.every(Number.isFinite))
  const record = environmentalRecord(event)
  const wind = reconstruction?.wind || record?.wind
  const current = reconstruction?.current || record?.current
  const anchor=allCoordinates[0]||[event.center?.longitude||50.5,event.center?.latitude||42]
  const annotations=layers.weather?[
    ...(wind?[{id:'wind-vector',label:`Ветер ${Math.round(safeNumber(wind.direction??wind.direction_degrees??wind.bearing))}°`,longitude:anchor[0],latitude:anchor[1],detail:`${safeNumber(wind.speed??wind.speed_mps??wind.speed_kn??wind.value)} ${wind.unit||'м/с'}`,color:'#455f78'}]:[]),
    ...(current?[{id:'current-vector',label:`Течение ${Math.round(safeNumber(current.direction??current.direction_degrees??current.bearing))}°`,longitude:anchor[0]+.06,latitude:anchor[1]-.04,detail:`${safeNumber(current.speed??current.speed_mps??current.speed_kn??current.value)} ${current.unit||'м/с'}`,color:'#167b72'}]:[]),
  ]:[]
  return <div className="env-map">
    <RealCaspianMap
      ariaLabel={`Реальная карта экологического события ${event.id}`}
      ports={[]}
      vessels={replayVessels}
      tracks={lines}
      areas={areas}
      annotations={annotations}
      focusBounds={boundsForCoordinates(allCoordinates)}
    />
    <div className="env-map-title"><span><Map size={14}/>Экологические слои</span><small>{event.id}</small></div>
    <div className="env-map-layers"><strong><Layers3 size={14}/>Слои</strong>
      {([
        ['pollution', 'Контур загрязнения'], ['origin', 'Вероятная область источника'],
        ['tracks', 'Исторические треки'], ['weather', 'Ветер и течение'],
      ] as Array<[keyof MapLayers, string]>).map(([key, label]) => <label key={key}><span>{label}</span><input type="checkbox" checked={layers[key]} onChange={() => onLayers({ ...layers, [key]: !layers[key] })}/><i/></label>)}
    </div>
    <div className="env-map-legend"><span><i className="pollution"/>Наблюдаемый контур</span><span><i className="origin"/>Расчётная область</span>{candidateTracks.slice(0, 3).map(({ candidate }, index) => <span key={candidate.vessel_id}><i className="track" style={{ background: colors[index] }}/>{candidate.vessel_name}</span>)}</div>
    {!allCoordinates.length && <div className="env-map-no-data"><Map size={22}/><span>Геометрия не передана источником</span></div>}
  </div>
}

function LegacyEnvironmentalMap({ event, reconstruction, candidates, frame, layers, onLayers }: {
  event: EnvironmentalEvent
  reconstruction: EnvironmentalReconstruction | null
  candidates: EnvironmentalCandidate[]
  frame?: ReplayFrame
  layers: MapLayers
  onLayers: (value: MapLayers) => void
}) {
  const currentGeometry = frame?.pollution_geometry || frame?.geometry || event.geometry
  const originGeometry = frame?.origin_geometry || reconstruction?.origin_geometry || reconstruction?.origin_area || reconstruction?.estimated_origin_geometry
  const currentRings = extractRings(currentGeometry)
  const originRings = extractRings(originGeometry)
  const candidateTracks = candidates.map(candidate => ({ candidate, points: trackOf(candidate) })).filter(item => item.points.length)
  const allPoints: number[][] = [
    ...currentRings.flat(), ...originRings.flat(),
    ...candidateTracks.flatMap(item => item.points.map(point => [safeNumber(point.longitude ?? point.lon), safeNumber(point.latitude ?? point.lat)])),
    ...(frame?.vessels || []).map(vessel => [safeNumber(vessel.longitude), safeNumber(vessel.latitude)]),
  ].filter(point => point.length >= 2 && point.every(Number.isFinite))
  const xs = allPoints.map(point => point[0]); const ys = allPoints.map(point => point[1])
  const minX = xs.length ? Math.min(...xs) : 0; const maxX = xs.length ? Math.max(...xs) : 1
  const minY = ys.length ? Math.min(...ys) : 0; const maxY = ys.length ? Math.max(...ys) : 1
  const dx = Math.max(maxX - minX, .01); const dy = Math.max(maxY - minY, .01)
  const project = (point: number[]) => `${8 + ((point[0] - minX) / dx) * 84},${92 - ((point[1] - minY) / dy) * 84}`
  const points = (ring: number[][]) => ring.map(project).join(' ')
  const record = environmentalRecord(event)
  const wind = reconstruction?.wind || record?.wind
  const current = reconstruction?.current || record?.current
  const colors = ['#c56a2e', '#137c72', '#6578a4', '#8a6a9f']

  return <div className="env-map">
    <div className="env-map-grid"/>
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Environmental event map">
      <defs>
        <linearGradient id="envSea" x1="0" x2="1"><stop stopColor="#dce9e6"/><stop offset=".52" stopColor="#b9d1cd"/><stop offset="1" stopColor="#dfeae7"/></linearGradient>
        <pattern id="envHatch" width="3" height="3" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><line x1="0" y1="0" x2="0" y2="3" stroke="#a15b2f" strokeOpacity=".36" strokeWidth=".45"/></pattern>
        <marker id="envArrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0 0 L5 2.5 L0 5Z" fill="currentColor"/></marker>
      </defs>
      <rect width="100" height="100" fill="url(#envSea)"/>
      <path className="env-coast" d="M1 0L17 0C14 13 19 23 14 34C9 47 17 62 12 79C10 87 13 95 21 100H0ZM99 0H84C87 15 80 28 87 42C93 55 82 68 88 83C91 91 86 97 82 100H100Z"/>
      {layers.origin && originRings.map((ring, index) => <polygon key={`origin-${index}`} className="env-origin-polygon" points={points(ring)}/>)}
      {layers.tracks && candidateTracks.map(({ candidate, points: track }, index) => <g key={candidate.id || candidate.vessel_id} className="env-vessel-track">
        <polyline points={track.map(item => project([safeNumber(item.longitude ?? item.lon), safeNumber(item.latitude ?? item.lat)])).join(' ')} style={{ stroke: colors[index % colors.length] }}/>
        {track.length > 0 && <circle cx={project([safeNumber(track.at(-1)?.longitude ?? track.at(-1)?.lon), safeNumber(track.at(-1)?.latitude ?? track.at(-1)?.lat)]).split(',')[0]} cy={project([safeNumber(track.at(-1)?.longitude ?? track.at(-1)?.lon), safeNumber(track.at(-1)?.latitude ?? track.at(-1)?.lat)]).split(',')[1]} r="1.5" style={{ fill: colors[index % colors.length] }}/>} 
      </g>)}
      {layers.tracks && (frame?.vessels || []).map((vessel, index) => {
        const [x, y] = project([safeNumber(vessel.longitude), safeNumber(vessel.latitude)]).split(',').map(Number)
        return <g key={vessel.vessel_id || `${vessel.vessel_name}-${index}`} className={`env-replay-vessel ${vessel.ais_available === false ? 'estimated' : ''}`} transform={`translate(${x} ${y})`}>
          <circle className="halo" r="2.65"/><circle r="1.65" style={{ fill: colors[index % colors.length] }}/>
          <text x="3.2" y="-.5">{vessel.vessel_name || vessel.vessel_id}</text>
          <title>{vessel.vessel_name || vessel.vessel_id} · {vessel.ais_available === false ? 'estimated during AIS gap' : 'observed AIS'}</title>
        </g>
      })}
      {layers.pollution && currentRings.map((ring, index) => <g key={`pollution-${index}`}><polygon className="env-pollution-polygon" points={points(ring)}/><polygon fill="url(#envHatch)" points={points(ring)}/></g>)}
      {layers.weather && wind && <g className="env-vector wind" transform={`translate(73 16) rotate(${safeNumber(wind.direction ?? wind.direction_degrees ?? wind.bearing)})`}><line x1="0" y1="0" x2="0" y2="12" markerEnd="url(#envArrow)"/></g>}
      {layers.weather && current && <g className="env-vector current" transform={`translate(80 17) rotate(${safeNumber(current.direction ?? current.direction_degrees ?? current.bearing)})`}><line x1="0" y1="0" x2="0" y2="12" markerEnd="url(#envArrow)"/></g>}
    </svg>
    <div className="env-map-title"><span><Map size={14}/>Экологические слои</span><small>{event.id}</small></div>
    <div className="env-map-layers"><strong><Layers3 size={14}/>Слои</strong>
      {([
        ['pollution', 'Контур загрязнения'], ['origin', 'Вероятная область источника'],
        ['tracks', 'Исторические треки'], ['weather', 'Ветер и течение'],
      ] as Array<[keyof MapLayers, string]>).map(([key, label]) => <label key={key}><span>{label}</span><input type="checkbox" checked={layers[key]} onChange={() => onLayers({ ...layers, [key]: !layers[key] })}/><i/></label>)}
    </div>
    <div className="env-map-legend"><span><i className="pollution"/>Наблюдаемый контур</span><span><i className="origin"/>Расчётная область</span>{candidateTracks.slice(0, 3).map(({ candidate }, index) => <span key={candidate.vessel_id}><i className="track" style={{ background: colors[index] }}/>{candidate.vessel_name}</span>)}</div>
    {!allPoints.length && <div className="env-map-no-data"><Map size={22}/><span>Геометрия не передана источником</span></div>}
  </div>
}

function CandidateCard({ candidate, selected, onSelect }: { candidate: EnvironmentalCandidate; selected: boolean; onSelect: () => void }) {
  const level = candidate.relevance || candidate.association_level || candidate.priority || 'unknown'
  const distance = candidate.closest_distance_km ?? candidate.distance_km
  const overlap = candidate.temporal_overlap_percent ?? candidate.time_overlap_percent ?? candidate.overlap_percent
  const score = candidate.association_score ?? candidate.score
  const rank = candidate.rank ?? ({ HIGH: 1, MEDIUM: 2, LOW: 3 }[level.toUpperCase()] || '—')
  return <button className={`env-candidate ${selected ? 'selected' : ''}`} onClick={onSelect}>
    <span className="env-candidate-rank">{rank}</span>
    <span className="env-candidate-name"><span><Ship size={15}/><strong>{candidate.vessel_name}</strong></span><small>{candidate.imo ? `IMO ${candidate.imo}` : candidate.vessel_id}</small></span>
    <span><small>Мин. дистанция</small><strong>{distance === undefined ? 'Нет данных' : `${safeNumber(distance).toLocaleString('ru-RU')} км`}</strong></span>
    <span><small>Временное пересечение</small><strong>{overlap === undefined ? 'Нет данных' : `${Math.round(safeNumber(overlap))}%`}</strong></span>
    <span className={`env-ais ${candidate.ais_gap ?? candidate.has_ais_gap ? 'gap' : ''}`}><small>Пропуск AIS</small><strong>{candidate.ais_gap ?? candidate.has_ais_gap ? 'Да' : 'Нет'}</strong></span>
    {score !== undefined && <span className="env-candidate-score"><small>Соответствие</small><strong>{confidencePercent(score)}%</strong></span>}
    <em className={`env-association ${levelClass(level)}`}>{level.toUpperCase()}</em>
    <ChevronRight size={16}/>
  </button>
}

function CandidateInspector({ candidate }: { candidate: EnvironmentalCandidate | null }) {
  if (!candidate) return <div className="env-candidate-inspector empty"><Ship size={23}/><span>Выберите судно, чтобы увидеть основания ранжирования.</span></div>
  const factors = candidate.factors || []
  return <aside className="env-candidate-inspector">
    <span className="page-eyebrow">Почему в списке</span>
    <h3>{candidate.vessel_name}</h3>
    <p>{candidate.explanation || candidate.rationale || 'API не передал текстовое объяснение.'}</p>
    <div className="env-factor-list">{factors.map((factor, index) => {
      const item = typeof factor === 'string' ? { label: factor } : factor
      return <div key={`${item.label || item.name}-${index}`}><Check size={13}/><span><strong>{item.label || item.name}</strong>{(item.observed ?? item.value) !== undefined && <small>{String(item.observed ?? item.value)}</small>}{item.interpretation && <small>{item.interpretation}</small>}</span>{typeof factor !== 'string' && <ProvenanceBadge value={factor.provenance}/>}</div>
    })}</div>
    {!!candidate.evidence_ids?.length && <div className="env-source-links">{candidate.evidence_ids.map(id => <span key={id}><Database size={12}/>{id}</span>)}</div>}
    <div className="env-caution"><Info size={14}/><span>Высокая позиция означает пространственно-временное соответствие данным, а не установленную причинность.</span></div>
  </aside>
}

function VectorMetric({ icon, label, vector }: { icon: React.ReactNode; label: string; vector?: EnvironmentalVector }) {
  const speed = vector?.speed ?? vector?.speed_mps ?? vector?.speed_kn ?? vector?.value
  const direction = vector?.direction ?? vector?.direction_degrees ?? vector?.bearing
  return <div className="env-vector-metric">
    <span>{icon}</span><div><small>{label}</small><strong>{speed === undefined ? 'Нет данных' : `${safeNumber(speed)} ${vector?.unit || (vector?.speed_kn !== undefined ? 'kn' : 'м/с')}`}</strong><em>{direction === undefined ? 'Направление не передано' : `${Math.round(safeNumber(direction))}°`}</em></div>
  </div>
}

function TimelineReplay({ items, frames, frame, onFrame, playing, onPlaying }: {
  items: TimelineItem[]
  frames: ReplayFrame[]
  frame: number
  onFrame: (value: number) => void
  playing: boolean
  onPlaying: (value: boolean) => void
}) {
  const current = frames[frame]
  return <section className="card env-timeline-card">
    <div className="card-head"><div><span className="page-eyebrow">Хронология события</span><h2>Реконструкция во времени</h2></div><span className="env-timeline-count">{items.length} точек</span></div>
    {!!frames.length && <div className="env-replay">
      <button onClick={() => onPlaying(!playing)} aria-label={playing ? 'Пауза' : 'Воспроизвести событие'}>{playing ? <Pause size={14} fill="currentColor"/> : <Play size={14} fill="currentColor"/>}<b>{playing ? 'PAUSE' : 'REPLAY EVENT'}</b></button>
      <span><strong>{formatDate(current?.timestamp || current?.time, false)}</strong><small>{formatDate(current?.timestamp || current?.time)}</small></span>
      <input type="range" min="0" max={Math.max(frames.length - 1, 0)} value={frame} onChange={event => onFrame(Number(event.target.value))}/>
      <em>{frame + 1} / {frames.length}</em>
    </div>}
    <div className="env-timeline">{items.map((item, index) => <button key={item.id || `${item.timestamp || item.time}-${index}`} onClick={() => {
      if (!frames.length) return
      const itemTime = new Date(item.timestamp || item.time || 0).getTime()
      const closest = frames.reduce((best, candidate, candidateIndex) => Math.abs(new Date(candidate.timestamp || candidate.time || 0).getTime() - itemTime) < Math.abs(new Date(frames[best]?.timestamp || frames[best]?.time || 0).getTime() - itemTime) ? candidateIndex : best, 0)
      onFrame(closest)
    }}>
      <time>{formatDate(item.timestamp || item.time, false)}</time><i className={provenanceKind(item.provenance)}/><span><small>{item.type?.replaceAll('_', ' ') || 'EVENT'}</small><strong>{item.title || item.label || 'Событие'}</strong><p>{item.detail || item.description}</p></span><ProvenanceBadge value={item.provenance}/>
    </button>)}</div>
    {!items.length && <EmptyState title="Хронология не сформирована" detail="Источник не передал временные точки реконструкции."/>}
  </section>
}

function EvidencePanel({ event, reconstruction, candidate }: { event: EnvironmentalEvent; reconstruction: EnvironmentalReconstruction | null; candidate: EnvironmentalCandidate | null }) {
  const items: EnvironmentalObservation[] = [
    ...(event.observations || []), ...eventData(event),
    ...(reconstruction?.inputs || []), ...(Array.isArray(reconstruction?.weather) ? reconstruction.weather : []),
    ...(reconstruction?.wind ? [reconstruction.wind] : []), ...(reconstruction?.current ? [reconstruction.current] : []),
  ]
  const unique = items.filter((item, index) => items.findIndex(other => (other.id || `${other.label}-${other.source}`) === (item.id || `${item.label}-${item.source}`)) === index)
  return <section className="card env-evidence-card">
    <div className="card-head"><div><span className="page-eyebrow">Доказательства и происхождение</span><h2>Основания анализа</h2></div><Database size={18}/></div>
    <div className="env-evidence-list">{unique.map((item, index) => <div key={item.id || `${item.label}-${index}`}>
      <span className="env-evidence-icon"><Database size={14}/></span>
      <span><strong>{item.parameter || item.label || item.name || item.id || 'Наблюдение'}</strong><small>{item.value !== undefined ? `${item.value}${item.unit ? ` ${item.unit}` : ''}` : item.source || 'Значение не передано'}</small></span>
      <span><ProvenanceBadge value={item.provenance || item.kind}/><small>{item.source_reference || item.source_id || item.source}</small></span>
    </div>)}</div>
    {!unique.length && <div className="env-evidence-empty">Детализированная provenance пока не передана API.</div>}
    {!!candidate?.evidence_ids?.length && <div className="env-linked-evidence"><strong>Связанные записи кандидата</strong>{candidate.evidence_ids.map(id => <span key={id}><ExternalLink size={12}/>{id}</span>)}</div>}
  </section>
}

function EnvironmentalRiskCard({ risk }: { risk?: EnvironmentalRiskContext }) {
  return <section className="card env-risk-card">
    <div className="card-head"><div><span className="page-eyebrow">Контекст риска</span><h2>Экологический контекст</h2></div><Gauge size={18}/></div>
    {risk ? <>
      <div className="env-risk-numbers">
        <span><small>Морской риск</small><strong>{risk.maritime_risk_score ?? '—'}</strong></span>
        <i>+</i><span><small>Экоконтекст</small><strong>{risk.environmental_adjustment_effective ?? risk.environmental_adjustment_raw ?? risk.environmental_adjustment ?? '—'}</strong></span>
        <i>=</i><span className="result"><small>Приоритет проверки</small><strong>{risk.combined_context_score ?? risk.priority_score ?? '—'}</strong></span>
      </div>
      {!!risk.factors?.length && <div className="env-risk-factor-list">{risk.factors.map(factor => <div key={factor.id}><span><strong>{factor.code || factor.label}</strong><small>{factor.observed}</small></span><ProvenanceBadge value={factor.provenance}/><em>+{factor.contribution}</em></div>)}</div>}
      <p>{risk.explanation}</p>
      <div className="env-caution"><Info size={14}/><span>{risk.disclaimer || 'Экологический контекст повышает приоритет проверки, но не устанавливает источник события.'}</span></div>
      {risk.model_version && <small className="env-model-version">{risk.model_version}</small>}
    </> : <EmptyState title="Контекст не рассчитан" detail="Risk Engine не передал экологическую поправку для этого события."/>}
  </section>
}

function ConfirmationDialog({ title, detail, confirmLabel, busy, onConfirm, onClose, children }: {
  title: string
  detail: string
  confirmLabel: string
  busy: boolean
  onConfirm: () => void
  onClose: () => void
  children?: React.ReactNode
}) {
  return <div className="env-modal-backdrop" onMouseDown={onClose}><div className="env-modal" onMouseDown={event => event.stopPropagation()}>
    <button className="env-modal-close" onClick={onClose}><X size={17}/></button>
    <span className="env-modal-icon"><ShieldCheck size={21}/></span>
    <h2>{title}</h2><p>{detail}</p>{children}
    <div className="env-modal-actions"><button className="secondary-button" onClick={onClose}>Отмена</button><button className="primary-button" disabled={busy} onClick={onConfirm}>{busy ? <RefreshCw size={14} className="spin"/> : <Check size={14}/>} {confirmLabel}</button></div>
  </div></div>
}

export function EnvironmentalEventPage({ eventId = DEFAULT_EVENT_ID, navigate = defaultNavigate }: { eventId?: string; navigate?: Navigate }) {
  const [event, setEvent] = useState<EnvironmentalEvent | null>(null)
  const [candidateResponse, setCandidateResponse] = useState<CandidateResponse | EnvironmentalCandidate[] | null>(null)
  const [reconstruction, setReconstruction] = useState<EnvironmentalReconstruction | null>(null)
  const [timeline, setTimeline] = useState<TimelineItem[]>([])
  const [frames, setFrames] = useState<ReplayFrame[]>([])
  const [selectedCandidateId, setSelectedCandidateId] = useState('')
  const [layers, setLayers] = useState<MapLayers>({ pollution: true, origin: true, tracks: true, weather: true })
  const [frame, setFrame] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [dialog, setDialog] = useState<'review' | 'investigation' | null>(null)
  const [decision, setDecision] = useState<ReviewDecision>('uncertain')
  const [sourceClassification, setSourceClassification] = useState<'UNKNOWN' | 'VERIFIED EXTERNAL FINDING'>('UNKNOWN')
  const [note, setNote] = useState('')
  const [writing, setWriting] = useState(false)
  const [actionMessage, setActionMessage] = useState('')

  const load = async () => {
    setLoading(true); setError('')
    const results = await Promise.allSettled([
      api<EnvironmentalEvent | { event: EnvironmentalEvent }>(`/environment/events/${eventId}`),
      api<CandidateResponse | EnvironmentalCandidate[]>(`/environment/events/${eventId}/candidates`),
      api<EnvironmentalReconstruction | { reconstruction: EnvironmentalReconstruction }>(`/environment/events/${eventId}/reconstruction`),
      api<TimelineItem[] | { timeline?: TimelineItem[]; items?: TimelineItem[] }>(`/environment/events/${eventId}/timeline`),
      api<ReplayFrame[] | { frames?: ReplayFrame[]; replay?: ReplayFrame[] }>(`/environment/events/${eventId}/replay`),
    ])
    if (results[0].status === 'rejected') {
      setError(results[0].reason instanceof Error ? results[0].reason.message : 'Событие не найдено')
      setLoading(false); return
    }
    const loadedEvent = objectFrom<EnvironmentalEvent>(results[0].value, ['event'])
    setEvent(loadedEvent)
    if (results[1].status === 'fulfilled') setCandidateResponse(results[1].value)
    if (results[2].status === 'fulfilled') setReconstruction(objectFrom<EnvironmentalReconstruction>(results[2].value, ['reconstruction']))
    if (results[3].status === 'fulfilled') setTimeline(listFrom<TimelineItem>(results[3].value, ['timeline', 'items', 'events']))
    if (results[4].status === 'fulfilled') setFrames(listFrom<ReplayFrame>(results[4].value, ['frames', 'replay', 'items']))
    setLoading(false)
  }

  useEffect(() => {
    void load()
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const token = localStorage.getItem('ci-access-token') || 'ci-demo-analyst'
    const socket = new WebSocket(`${protocol}://${window.location.hostname}:8000/ws/environment?token=${encodeURIComponent(token)}`)
    socket.onmessage = message => {
      try {
        const payload = JSON.parse(message.data) as { type?: string; event?: { id?: string }; event_id?: string }
        const changedEvent = payload.event?.id || payload.event_id
        if (payload.type?.startsWith('environmental_') && (!changedEvent || [eventId, 'ENV-142'].includes(changedEvent))) void load()
      } catch { /* Ignore malformed external frames; REST remains authoritative. */ }
    }
    return () => socket.close()
  }, [eventId])

  const candidates = useMemo(() => listFrom<EnvironmentalCandidate>(candidateResponse, ['relevant_candidates', 'candidates', 'items']), [candidateResponse])
  useEffect(() => { if (!selectedCandidateId && candidates[0]) setSelectedCandidateId(candidates[0].vessel_id) }, [candidates, selectedCandidateId])
  const selectedCandidate = candidates.find(candidate => candidate.vessel_id === selectedCandidateId) || candidates[0] || null
  const candidateMeta = !Array.isArray(candidateResponse) && candidateResponse ? candidateResponse : null

  useEffect(() => {
    if (!playing || frames.length < 2) return
    const timer = window.setInterval(() => setFrame(current => current >= frames.length - 1 ? 0 : current + 1), 1100)
    return () => window.clearInterval(timer)
  }, [playing, frames.length])

  useEffect(() => { if (frame >= frames.length && frames.length) setFrame(frames.length - 1) }, [frames.length, frame])

  const submitReview = async () => {
    if (!event) return
    const cleanNote = note.trim()
    if (cleanNote.length < 2) { setActionMessage('Добавьте основание решения аналитика.'); return }
    setWriting(true); setActionMessage('')
    try {
      const updated = await api<EnvironmentalEvent | { event: EnvironmentalEvent }>(`/environment/events/${event.id}/review`, {
        method: 'POST', body: JSON.stringify({
          outcome: decision.toUpperCase().replaceAll('_', ' '),
          source_classification: sourceClassification,
          note: cleanNote,
        }),
      })
      setEvent(objectFrom<EnvironmentalEvent>(updated, ['event']))
      setActionMessage('Решение аналитика сохранено в журнале события.')
      setDialog(null)
    } catch (reason) { setActionMessage(reason instanceof Error ? reason.message : 'Не удалось сохранить решение') }
    finally { setWriting(false) }
  }

  const createInvestigation = async () => {
    if (!event) return
    setWriting(true); setActionMessage('')
    try {
      const result = await api<Record<string, unknown>>(`/environment/events/${event.id}/investigation`, {
        method: 'POST', body: JSON.stringify({ confirmed: true }),
      })
      const investigation = objectFrom<Record<string, unknown>>(result, ['investigation', 'case'])
      const id = String(investigation.id || result.id || '')
      setActionMessage(id ? `Расследование ${id} создано, evidence собраны автоматически.` : 'Расследование создано.')
      setDialog(null)
      if (id) window.setTimeout(() => navigate(`/app/investigations/${id}`), 600)
    } catch (reason) { setActionMessage(reason instanceof Error ? reason.message : 'Не удалось создать расследование') }
    finally { setWriting(false) }
  }

  if (loading) return <div className="content-page env-detail-loading"><RefreshCw size={24} className="spin"/><strong>Собираем экологическое событие</strong><span>Контур, реконструкция, исторические треки и происхождение данных загружаются из API.</span></div>
  if (error || !event) return <div className="content-page"><EmptyState title="Экологическое событие не открыто" detail={error || 'Нет данных'} onRetry={() => void load()}/></div>

  const record = environmentalRecord(event)
  const started = reconstruction?.estimated_origin_from || reconstruction?.time_window_start || reconstruction?.estimated_started_at || event.estimated_started_at
  const ended = reconstruction?.estimated_origin_to || reconstruction?.time_window_end || reconstruction?.estimated_ended_at || event.estimated_ended_at
  const wind = reconstruction?.wind || record?.wind
  const current = reconstruction?.current || record?.current
  const weather = typeof reconstruction?.weather === 'string'
    ? reconstruction.weather
    : Array.isArray(reconstruction?.weather)
      ? reconstruction.weather.map(item => `${item.parameter || item.label}: ${item.value ?? '—'} ${item.unit || ''}`.trim()).join(' · ')
      : record?.weather || 'Нет данных'

  return <div className="content-page environmental-event-page">
    <button className="back-link" onClick={() => navigate('/app/environment')}><ArrowLeft size={15}/>К экологическому центру</button>
    <header className="env-event-hero">
      <span className="env-hero-icon"><Droplets size={25}/></span>
      <div><span className="page-eyebrow">{event.id} · Экологическое событие</span><h1>{typeLabel(event.type)}</h1><p>{event.description || event.summary || 'Событие обнаружено внешним источником экологических данных.'}</p></div>
      <div className="env-hero-badges"><span className={`env-status ${statusKey(event.status)}`}>{statusLabel(event.status)}</span><span className="env-confidence"><strong>{confidencePercent(event.confidence)}%</strong> достоверность</span></div>
      <div className="env-hero-actions">
        <button className="secondary-button" onClick={() => navigate(`/app/assistant?q=${encodeURIComponent(`Что известно о ${event.id}?`)}`)}><Sparkles size={15}/>Спросить AI</button>
        <button className="secondary-button" onClick={() => setDialog('review')}><CircleCheck size={15}/>Решение</button>
        <button className="primary-button" onClick={() => setDialog('investigation')}><Target size={15}/>Создать расследование</button>
      </div>
    </header>
    {!!actionMessage && <div className={`env-action-message ${actionMessage.includes('не удалось') || actionMessage.includes('Insufficient') ? 'error' : ''}`}><Check size={14}/>{actionMessage}</div>}

    <section className="env-event-metrics-strip">
      <div><span>Обнаружено</span><strong>{formatDate(event.detected_at)}</strong><small><Satellite size={12}/>{event.detection_source || event.source || 'Источник не указан'}</small></div>
      <div><span>Площадь</span><strong>{safeNumber(event.area_km2).toLocaleString('ru-RU')} <em>км²</em></strong><small><ProvenanceBadge value="observed"/></small></div>
      <div><span>Вероятное начало</span><strong>{formatDate(started, false)}–{formatDate(ended, false)}</strong><small><ProvenanceBadge value="estimated"/></small></div>
      <div><span>Кандидаты</span><strong>{candidates.length}</strong><small>из {safeNumber(candidateMeta?.searched_candidate_count ?? candidateMeta?.historical_candidates ?? candidateMeta?.total_candidates ?? candidateMeta?.searched_vessels, candidates.length)} исторических совпадений</small></div>
      <div><span>Центр события</span><strong>{event.center ? `${safeNumber(event.center.latitude ?? event.center.lat).toFixed(3)}°, ${safeNumber(event.center.longitude ?? event.center.lon).toFixed(3)}°` : 'Нет данных'}</strong><small>географическая привязка</small></div>
    </section>

    <section className="env-map-section card">
      <div className="card-head"><div><span className="page-eyebrow">Пространственная реконструкция</span><h2>Контур, вероятный источник и треки судов</h2></div><span className="env-live-source"><i/>Данные API</span></div>
      <EnvironmentalMap event={event} reconstruction={reconstruction} candidates={candidates} frame={frames[frame]} layers={layers} onLayers={setLayers}/>
      <div className="env-map-footer">
        <div><Wind size={15}/><span><strong>Ветер</strong><small>{wind ? `${wind.speed ?? wind.speed_mps ?? wind.speed_kn ?? wind.value ?? '—'} ${wind.unit || ''} · ${wind.direction ?? wind.direction_degrees ?? wind.bearing ?? '—'}°` : 'Нет данных'}</small></span></div>
        <div><Navigation size={15}/><span><strong>Течение</strong><small>{current ? `${current.speed ?? current.speed_mps ?? current.speed_kn ?? current.value ?? '—'} ${current.unit || ''} · ${current.direction ?? current.direction_degrees ?? current.bearing ?? '—'}°` : 'Нет данных'}</small></span></div>
        <div><CloudRain size={15}/><span><strong>Погода</strong><small>{weather || 'Нет данных'}</small></span></div>
        <div className="env-map-method"><Database size={15}/><span><strong>{reconstruction?.method || reconstruction?.model_version || 'Метод не указан'}</strong><small>обратная реконструкция</small></span></div>
      </div>
    </section>

    <section className="env-detail-grid">
      <div className="env-detail-main">
        <section className="card env-candidates-card">
          <div className="card-head"><div><span className="page-eyebrow">Возможные связи</span><h2>Суда в историческом контексте района</h2></div><span className="env-timeline-count">{candidates.length} релевантных</span></div>
          <div className="env-candidates-layout"><div className="env-candidate-list">{candidates.map(candidate => <CandidateCard key={candidate.id || candidate.vessel_id} candidate={candidate} selected={selectedCandidate?.vessel_id === candidate.vessel_id} onSelect={() => setSelectedCandidateId(candidate.vessel_id)}/>)}{!candidates.length && <EmptyState title="Кандидаты не найдены" detail="Исторический пространственный поиск не вернул пересечений."/>}</div><CandidateInspector candidate={selectedCandidate}/></div>
          <div className="env-association-note"><AlertTriangle size={15}/><span><strong>Association ≠ causation.</strong> Ранжирование учитывает дистанцию, время, направление, движение и качество AIS. Оно помогает выбрать порядок проверки.</span></div>
        </section>

        <TimelineReplay items={timeline} frames={frames} frame={frame} onFrame={setFrame} playing={playing} onPlaying={setPlaying}/>
      </div>

      <aside className="env-detail-side">
        <section className="card env-reconstruction-card">
          <div className="card-head"><div><span className="page-eyebrow">Обратная реконструкция</span><h2>Обратный расчёт</h2></div><History size={18}/></div>
          <div className="env-origin-window"><span>Вероятное окно источника</span><strong>{formatDate(started, false)} — {formatDate(ended, false)}</strong><small><ProvenanceBadge value="estimated"/> {confidencePercent(reconstruction?.confidence)}% confidence</small></div>
          <VectorMetric icon={<Wind size={17}/>} label="Ветер" vector={wind}/>
          <VectorMetric icon={<Navigation size={17}/>} label="Поверхностное течение" vector={current}/>
          <p>{reconstruction?.explanation || reconstruction?.limitation || 'Подробное объяснение модели не передано API.'}</p>
          <div className="env-caution"><Info size={14}/><span>Результат — вероятная область и интервал, а не точная координата или установленный момент.</span></div>
        </section>
        <EnvironmentalRiskCard risk={selectedCandidate?.risk_context || event.risk_context}/>
        <EvidencePanel event={event} reconstruction={reconstruction} candidate={selectedCandidate}/>
      </aside>
    </section>

    {dialog === 'review' && <ConfirmationDialog title="Зафиксировать решение аналитика" detail="Это изменит статус проверки и будет записано в журнал аудита. Исходные наблюдения останутся неизменными." confirmLabel="Сохранить решение" busy={writing} onConfirm={() => void submitReview()} onClose={() => setDialog(null)}>
      <div className="env-review-options">{([
        ['confirmed_pollution', 'Подтверждённое загрязнение'], ['likely_pollution', 'Вероятное загрязнение'], ['uncertain', 'Неопределённо'], ['false_positive', 'Ложное срабатывание'],
      ] as Array<[ReviewDecision, string]>).map(([value, label]) => <label key={value} className={decision === value ? 'active' : ''}><input type="radio" name="env-review" value={value} checked={decision === value} onChange={() => setDecision(value)}/><span>{label}</span></label>)}</div>
      <label className="env-review-note">Классификация источника<select value={sourceClassification} onChange={event => setSourceClassification(event.target.value as 'UNKNOWN' | 'VERIFIED EXTERNAL FINDING')}><option value="UNKNOWN">Источник не установлен</option><option value="VERIFIED EXTERNAL FINDING">Подтверждён внешним заключением</option></select></label>
      <label className="env-review-note">Комментарий<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="Основание решения или необходимые дополнительные данные"/></label>
    </ConfirmationDialog>}
    {dialog === 'investigation' && <ConfirmationDialog title="Создать экологическое расследование" detail={`Для ${event.id} будут собраны контур, внешнее наблюдение, погода, течение, реконструкция, исторические AIS-треки и кандидаты. Действие требует подтверждения.`} confirmLabel="Создать Case" busy={writing} onConfirm={() => void createInvestigation()} onClose={() => setDialog(null)}>
      <div className="env-case-evidence-preview"><FileSearch size={16}/><span><strong>Сбор доказательств</strong><small>Только данные этого события и ссылки на их источники</small></span></div>
    </ConfirmationDialog>}
  </div>
}

type VesselEnvironmentHistory = {
  id?: string
  event_id?: string
  environmental_event_id?: string
  detected_at?: string
  occurred_at?: string
  date?: string
  type?: string
  event_type?: string
  association_level?: string
  relevance?: string
  relationship?: string
  distance_km?: number
  status?: string
  conclusion?: string
  title?: string
  detail?: string
  provenance?: string
}

export function VesselEnvironmentTab({ vesselId, navigate = defaultNavigate }: { vesselId: string; navigate?: Navigate }) {
  const [history, setHistory] = useState<VesselEnvironmentHistory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    api<VesselEnvironmentHistory[] | { events?: VesselEnvironmentHistory[]; history?: VesselEnvironmentHistory[] }>(`/vessels/${vesselId}/environment`)
      .then(value => { if (active) setHistory(listFrom(value, ['events', 'history', 'items'])) })
      .catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Не удалось загрузить историю') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [vesselId])
  return <section className="card vessel-environment-tab">
    <div className="card-head"><div><span className="page-eyebrow">История экологических событий</span><h2>Экологический контекст судна</h2></div><Leaf size={18}/></div>
    <div className="env-caution"><Info size={14}/><span>История показывает попадание судна в аналитический контекст экологических событий. Это не является историей нарушений.</span></div>
    {loading && <div className="env-inline-loading"><RefreshCw size={16} className="spin"/>Загрузка истории</div>}
    {!loading && error && <EmptyState title="История недоступна" detail={error}/>} 
    {!loading && !error && <div className="vessel-env-history">{history.map(item => <button key={item.id || item.event_id} onClick={() => navigate(`/app/environment/events/${item.environmental_event_id || item.event_id || item.id}`)}>
      <time>{formatDate(item.occurred_at || item.detected_at || item.date)}</time><span><strong>{item.environmental_event_id || item.event_id || item.id}</strong><small>{typeLabel(item.event_type || item.type || 'pollution')} · {item.title || item.conclusion || statusLabel(item.relationship || item.status || 'under_review')}</small></span><em className={`env-association ${levelClass(item.relevance || item.association_level)}`}>{item.relevance || item.association_level || 'CONTEXT'}</em><ProvenanceBadge value={item.provenance}/><ChevronRight size={15}/>
    </button>)}</div>}
    {!loading && !error && !history.length && <EmptyState title="Экологический контекст не найден" detail="Для судна нет связанных экологических событий."/>}
  </section>
}
