import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Anchor, ArrowRight, Bot, BrainCircuit, Check, ChevronRight, CircleCheck, Clock3,
  Database, ExternalLink, FileSearch, FileText, Link2, LockKeyhole, Map, MapPin,
  MessageSquareText, Network, Plus, Search, Send, Shield, ShieldCheck, Ship, Sparkles,
  Target, TriangleAlert, UserRound, Waves, X
} from 'lucide-react'
import {
  aktauPortOperations, caspianStarBehavior, detectedEvents, investigationNetwork,
  riskAssessments, vessels, voyageIntelligence
} from './data'
import type { DetectionEvent, RiskAssessment } from './types'
import { operationalText, severityLabel, statusLabel } from './i18n'
import './assistant.css'

type ClaimKind = 'FACT' | 'ESTIMATE' | 'INFERENCE'
type AssistantContext = {
  page: string
  label: string
  vesselId?: string
  vesselName?: string
  voyageId?: string
  area?: string
  areaBounds?: { west: number; south: number; east: number; north: number; fromTime: string; toTime: string }
  portId?: string
  environmentalEventId?: string
}
type EvidenceClaim = { kind: ClaimKind; text: string; source?: string; href?: string }
type AssistantAction = {
  id?: string
  type: 'OPEN_NETWORK' | 'CREATE_CASE' | 'ADD_EVIDENCE' | 'OPEN_PORT' | 'OPEN_CASE'
  label: string
  href?: string
  evidenceIds?: string[]
  status?: 'PENDING' | 'DONE'
}
type ToolCall = { name: string; detail: string; records: number }
type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  text?: string
  title?: string
  intro?: string
  claims?: EvidenceClaim[]
  tools?: ToolCall[]
  action?: AssistantAction
  noData?: boolean
  timestamp: string
}
type CaseEvidence = {
  id: string
  type: string
  title: string
  detail: string
  time: string
  kind: ClaimKind
  sourceHref: string
}
type InvestigationCase = {
  id: string
  title: string
  status: 'OPEN' | 'IN REVIEW' | 'CLOSED'
  priority: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  vesselId: string
  vesselName: string
  voyageId: string
  route: string
  assignedTo: string
  evidence: CaseEvidence[]
  notes: string[]
  timeline: Array<{ id: string; occurredAt: string; title: string; detail: string; kind: ClaimKind; sourceId: string; sourceHref: string }>
  caseType: 'maritime' | 'environmental'
  environmentalEventId?: string
  relatedVesselIds: string[]
  disclaimer?: string
  createdAt: string
}

type ApiEvidenceLink = { id: string; label: string; href: string; source_module: string }
type ApiClaim = { kind: 'fact' | 'estimate' | 'inference'; statement: string; evidence: ApiEvidenceLink[] }
type ApiToolTrace = { name: string; arguments: Record<string, unknown>; record_count: number; data_accessed: string[]; status: string }
type ApiAction = {
  id: string
  action_type: string
  label: string
  requires_confirmation: boolean
  status: string
  payload: Record<string, unknown>
  navigation_target?: string
}
type ApiChatResponse = {
  conversation_id: string
  message_id: string
  title: string
  answer: string
  claims: ApiClaim[]
  tools_called: ApiToolTrace[]
  actions: ApiAction[]
  no_data: boolean
  created_at: string
}
type ApiInvestigation = {
  id: string
  title: string
  status: 'open' | 'in_review' | 'closed'
  priority: 'critical' | 'high' | 'medium' | 'low'
  vessel_id: string
  vessel_name: string
  voyage_id?: string
  route?: string
  assigned_to: string
  evidence: Array<{
    source_id: string
    source_type: string
    title: string
    detail: string
    claim_kind: 'fact' | 'estimate' | 'inference'
    source_href: string
    occurred_at?: string
  }>
  notes: Array<{ text: string }>
  timeline?: Array<{
    id: string
    occurred_at: string
    title: string
    detail: string
    claim_kind: 'fact' | 'estimate' | 'inference'
    source_id: string
    source_href: string
  }>
  case_type?: 'maritime' | 'environmental'
  environmental_event_id?: string
  related_vessel_ids?: string[]
  disclaimer?: string
  created_at: string
}

const TOOL_CATALOG = [
  'get_vessel', 'get_current_voyage', 'get_vessel_events', 'get_vessel_risk',
  'get_risk_factors', 'get_behavior_profile', 'get_encounters', 'get_cargo_analysis',
  'get_fuel_analysis', 'get_vessel_network', 'search_vessels', 'search_events',
  'search_area', 'get_port_status', 'get_arrivals', 'get_port_forecast',
] as const

const defaultCase = (): InvestigationCase => ({
  id: 'CI-2026-00421',
  title: 'CASPIAN STAR · Voyage #143',
  status: 'OPEN',
  priority: 'HIGH',
  vesselId: 'caspian-star',
  vesselName: 'CASPIAN STAR',
  voyageId: 'voy-001',
  route: 'Baku → Aktau',
  assignedTo: 'Аян Касымов',
  createdAt: '10 авг 2026 · 18:12',
  evidence: [],
  notes: [],
  timeline: [],
  caseType: 'maritime',
  relatedVesselIds: [],
})

const evidenceById = (id: string): CaseEvidence | undefined => {
  const event = detectedEvents.find(item => item.id === id)
  if (!event) return undefined
  return {
    id: event.id,
    type: event.type,
    title: event.title,
    detail: event.summary,
    time: event.time,
    kind: 'FACT',
    sourceHref: `/app/events?event=${event.id}`,
  }
}

const CASE_KEY = 'ci-stage8-investigation'
const CHAT_KEY = 'ci-stage8-chat'
const CONTEXT_KEY = 'ci-stage8-context'
const CONVERSATION_KEY = 'ci-stage8-conversation'
const API_BASE = import.meta.env.VITE_API_BASE || (
  ['4173', '5173'].includes(window.location.port)
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : '/api/v1'
)

function apiHeaders() {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('ci-access-token') || 'ci-demo-analyst'}`,
  }
}

function contextForApi(context: AssistantContext) {
  const area = context.areaBounds ? {
    west: context.areaBounds.west,
    south: context.areaBounds.south,
    east: context.areaBounds.east,
    north: context.areaBounds.north,
    from_time: context.areaBounds.fromTime,
    to_time: context.areaBounds.toTime,
  } : undefined
  return {
    current_page: context.page,
    vessel_id: context.vesselId,
    voyage_id: context.voyageId,
    port_id: context.portId,
    investigation_id: context.page.startsWith('/app/investigations/') ? context.page.split('/').pop() : undefined,
    environmental_event_id: context.environmentalEventId,
    area,
  }
}

function apiActionType(value: string): AssistantAction['type'] {
  if (value === 'create_investigation') return 'CREATE_CASE'
  if (value === 'add_case_evidence') return 'ADD_EVIDENCE'
  if (value === 'open_network') return 'OPEN_NETWORK'
  if (value === 'open_investigation') return 'OPEN_CASE'
  return 'OPEN_PORT'
}

function chatFromApi(result: ApiChatResponse): ChatMessage {
  const action = result.actions[0]
  return {
    id: result.message_id,
    role: 'assistant',
    title: result.title,
    intro: result.answer,
    timestamp: new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date(result.created_at)),
    noData: result.no_data,
    claims: result.claims.map(claim => ({
      kind: claim.kind.toUpperCase() as ClaimKind,
      text: claim.statement,
      source: claim.evidence[0] ? `${claim.evidence[0].id} · ${claim.evidence[0].source_module}` : undefined,
      href: claim.evidence[0]?.href,
    })),
    tools: result.tools_called.map(tool => ({
      name: tool.name,
      detail: Object.entries(tool.arguments).map(([key, value]) => `${key}: ${String(value)}`).join(' · ') || tool.status,
      records: tool.record_count,
    })),
    action: action ? {
      id: action.id,
      type: apiActionType(action.action_type),
      label: action.label,
      href: action.navigation_target,
      evidenceIds: Array.isArray(action.payload.evidence_ids) ? action.payload.evidence_ids.map(String) : undefined,
      status: action.status === 'pending' ? 'PENDING' : 'DONE',
    } : undefined,
  }
}

function caseFromApi(value: ApiInvestigation): InvestigationCase {
  return {
    id: value.id,
    title: value.title,
    status: value.status === 'in_review' ? 'IN REVIEW' : value.status.toUpperCase() as InvestigationCase['status'],
    priority: value.priority.toUpperCase() as InvestigationCase['priority'],
    vesselId: value.vessel_id,
    vesselName: value.vessel_name,
    voyageId: value.voyage_id || '',
    route: value.route || 'Маршрут не указан',
    assignedTo: value.assigned_to,
    createdAt: new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value.created_at)),
    evidence: value.evidence.map(item => ({
      id: item.source_id,
      type: item.source_type,
      title: item.title,
      detail: item.detail,
      time: item.occurred_at ? item.occurred_at.slice(11, 16) : '—',
      kind: item.claim_kind.toUpperCase() as ClaimKind,
      sourceHref: item.source_href,
    })),
    notes: value.notes.map(item => item.text),
    timeline: (value.timeline || []).map(item => ({
      id: item.id,
      occurredAt: item.occurred_at,
      title: item.title,
      detail: item.detail,
      kind: item.claim_kind.toUpperCase() as ClaimKind,
      sourceId: item.source_id,
      sourceHref: item.source_href,
    })),
    caseType: value.case_type || 'maritime',
    environmentalEventId: value.environmental_event_id,
    relatedVesselIds: value.related_vessel_ids || [],
    disclaimer: value.disclaimer,
  }
}

function loadCase(): InvestigationCase {
  try {
    const stored = localStorage.getItem(CASE_KEY)
    return stored ? { ...defaultCase(), ...JSON.parse(stored) } : defaultCase()
  } catch { return defaultCase() }
}

function saveCase(value: InvestigationCase) {
  localStorage.setItem(CASE_KEY, JSON.stringify(value))
  window.dispatchEvent(new CustomEvent('ci-case-updated'))
}

function pageContext(path: string): AssistantContext {
  if (path.startsWith('/app/environment/events/')) { const eventId = decodeURIComponent(path.split('/').pop() || 'ENV-2026-00142'); return { page: path, label: 'Environmental Event', environmentalEventId: eventId } }
  if (path.startsWith('/app/environment')) return { page: path, label: 'Environmental Center' }
  if (path.startsWith('/app/investigations/')) {
    const caseId = decodeURIComponent(path.split('/').pop() || '')
    if (caseId.startsWith('ENV-')) return { page: path, label: 'Environmental Investigation', environmentalEventId: 'ENV-2026-00142' }
    return { page: path, label: 'Investigation Case', vesselId: 'caspian-star', vesselName: 'CASPIAN STAR', voyageId: 'voy-001' }
  }
  if (path.startsWith('/app/investigations')) return { page: path, label: 'Investigation workspace' }
  if (path.startsWith('/app/vessels/caspian-star')) return { page: path, label: 'Профиль судна', vesselId: 'caspian-star', vesselName: 'CASPIAN STAR', voyageId: 'voy-001' }
  if (path.startsWith('/app/voyages/voy-001')) return { page: path, label: 'Аналитика рейса', vesselId: 'caspian-star', vesselName: 'CASPIAN STAR', voyageId: 'voy-001' }
  if (path.startsWith('/app/port') || path.startsWith('/app/ports')) return { page: path, label: 'Port Aktau', portId: 'aktau', vesselId: path.includes('port-calls') ? 'caspian-star' : undefined, vesselName: path.includes('port-calls') ? 'CASPIAN STAR' : undefined, voyageId: path.includes('port-calls') ? 'voy-001' : undefined }
  if (path.startsWith('/app/risk')) return { page: path, label: 'Risk Center', vesselId: 'caspian-star', vesselName: 'CASPIAN STAR', voyageId: 'voy-001' }
  if (path.startsWith('/app/network')) return { page: path, label: 'Network View', vesselId: 'caspian-star', vesselName: 'CASPIAN STAR', voyageId: 'voy-001' }
  if (path.startsWith('/app/map')) return { page: path, label: 'Карта Каспия' }
  return { page: path, label: 'Общий контекст платформы' }
}

function getStoredContext(): AssistantContext {
  try {
    const raw = sessionStorage.getItem(CONTEXT_KEY)
    return raw ? JSON.parse(raw) : pageContext('/app/assistant')
  } catch { return pageContext('/app/assistant') }
}

function now() {
  return new Intl.DateTimeFormat('ru-RU', { hour: '2-digit', minute: '2-digit' }).format(new Date())
}

function call(name: string, detail: string, records: number): ToolCall {
  return { name, detail, records }
}

function eventSource(event: DetectionEvent) {
  return { source: event.id, href: `/app/events?event=${event.id}` }
}

function factorSource(factor: RiskAssessment['factors'][number]) {
  return factor.sourceEventId
    ? { source: `${factor.id} · ${factor.sourceEventId}`, href: `/app/events?event=${factor.sourceEventId}` }
    : { source: factor.id, href: `/app/risk?factor=${factor.id}` }
}

function vesselFromContext(context: AssistantContext) {
  return context.vesselId || 'caspian-star'
}

function groundedResponse(question: string, context: AssistantContext): Omit<ChatMessage, 'id' | 'role' | 'timestamp'> {
  const q = question.toLocaleLowerCase('ru-RU')
  const vesselId = vesselFromContext(context)
  const risk = riskAssessments.find(item => item.vesselId === vesselId) || riskAssessments[0]

  if ((q.includes('какие') && q.includes('требуют внимания')) || q.includes('top risk') || q.includes('высокий риск')) {
    const top = [...riskAssessments].sort((a, b) => b.score - a.score).slice(0, 3)
    return {
      title: 'Суда, требующие внимания',
      intro: 'Risk Engine возвращает три наивысшие текущие оценки. Это приоритет проверки, а не утверждение о нарушении.',
      claims: top.map(item => ({ kind: 'FACT', text: `${item.vesselName} — ${item.score} / 100 · ${item.level}`, source: `${item.modelVersion} · ${item.updatedAt}`, href: `/app/risk?vessel=${item.vesselId}` })),
      tools: [call('get_vessel_risk', 'sort: score desc · limit: 3', top.length)],
    }
  }

  if ((q.includes('почему') && (q.includes('риск') || q.includes('caspian') || q.includes('вырос'))) && !q.includes('порт') && !q.includes('актау')) {
    const factors = risk.factors
    return {
      title: `Почему риск ${risk.vesselName} — ${risk.score}`,
      intro: `Оценка сформирована Risk Engine ${risk.modelVersion}. Доступно ${factors.length} факторов; каждый показан с исходным Risk Factor или Event.`,
      claims: factors.map(factor => ({ kind: 'FACT', text: `${factor.title}: ${factor.explanation}`, ...factorSource(factor) })),
      tools: [call('get_vessel', `vessel_id: ${risk.vesselId}`, 1), call('get_vessel_risk', `voyage_id: ${risk.voyageId}`, 1), call('get_risk_factors', `assessment: ${risk.modelVersion}`, factors.length)],
    }
  }

  if ((q.includes('ais') && (q.includes('3 час') || q.includes('трех час') || q.includes('трёх час'))) || q.includes('отсутствовал более')) {
    const matches = detectedEvents.filter(event => event.type === 'ais_gap' && event.metrics.some(metric => metric.value.includes('3h 15m')))
    return {
      title: 'AIS отсутствовал более 3 часов',
      intro: `Структурный фильтр: event_type = AIS_GAP, duration > 3h, period = 30d. Найдено: ${matches.length}.`,
      claims: matches.map(event => ({ kind: 'FACT', text: `${event.vesselName}: ${event.summary}. Покрытие района — ${event.metrics.find(metric => metric.label === 'Покрытие района')?.value || 'нет данных'}.`, ...eventSource(event) })),
      tools: [call('search_events', 'type: ais_gap · duration_gt: 3h · period: 30d', matches.length)],
    }
  }

  if ((q.includes('с кем') && q.includes('встреч')) || q === 'с кем оно встречалось?') {
    const encounters = detectedEvents.filter(event => event.vesselId === vesselId && event.type === 'vessel_encounter')
    const event = encounters[0]
    if (!event) return noData('В доступных событиях этого судна нет подтверждённых encounter-записей.', [call('get_encounters', `vessel_id: ${vesselId}`, 0)])
    return {
      title: `Встреча с ${event.relatedVessel}`,
      intro: 'Ответ собран из детектированного события совместного присутствия.',
      claims: [
        { kind: 'FACT', text: `${event.relatedVessel}: минимальная дистанция ${event.metrics[0]?.value}, длительность ${event.metrics[1]?.value}.`, ...eventSource(event) },
        { kind: 'INFERENCE', text: 'Событие описывает совместное присутствие и само по себе не определяет характер взаимодействия.', ...eventSource(event) },
      ],
      tools: [call('get_encounters', `vessel_id: ${vesselId} · voyage_id: ${event.voyageId}`, encounters.length)],
    }
  }

  if (q.includes('раньше') && (q.includes('встреч') || q.includes('они'))) {
    const connection = investigationNetwork.primaryConnection
    return {
      title: 'История совместных наблюдений',
      intro: 'Агрегированная Network View подтверждает повторяемость наблюдений.',
      claims: [
        { kind: 'FACT', text: `${connection.source} и ${connection.target}: ${connection.encounters} встреч за ${connection.period}, ${connection.openSea} — в открытом море.`, source: 'LINK e-encounter', href: '/app/network?connection=e-encounter' },
        { kind: 'FACT', text: `Суммарная длительность ${connection.totalDuration}, средняя дистанция ${connection.averageDistance}.`, source: 'Network aggregation', href: '/app/network?connection=e-encounter' },
        { kind: 'INFERENCE', text: 'Повторяемость повышает приоритет проверки, но не доказывает связь или нарушение.', source: 'CI Network policy', href: '/app/network?connection=e-encounter' },
      ],
      tools: [call('get_vessel_network', `vessel_id: ${vesselId} · period: 6mo`, investigationNetwork.edges.length), call('get_encounters', 'aggregate: true', connection.encounters)],
    }
  }

  if (q.includes('покажи') && q.includes('связ')) {
    return {
      title: 'Связь подготовлена',
      intro: 'Откройте Network View: CASPIAN STAR и TURAN будут показаны вместе с основанием связи и уровнем уверенности.',
      claims: [{ kind: 'FACT', text: 'Связь построена по 14 агрегированным encounter-событиям за 6 месяцев.', source: 'LINK e-encounter', href: '/app/network?connection=e-encounter' }],
      tools: [call('get_vessel_network', `vessel_id: ${vesselId} · focus: TURAN`, investigationNetwork.edges.length)],
      action: { type: 'OPEN_NETWORK', label: 'Открыть Network View', href: '/app/network?connection=e-encounter' },
    }
  }

  if (q.includes('создай') && q.includes('расслед')) {
    return {
      title: 'Требуется подтверждение',
      intro: 'Создание Investigation изменяет систему. Я подготовил Case из текущего контекста, но не создам его без подтверждения.',
      claims: [
        { kind: 'FACT', text: `${risk.vesselName} · ${risk.route} · Risk ${risk.score}.`, source: risk.modelVersion, href: `/app/risk?vessel=${risk.vesselId}` },
        { kind: 'INFERENCE', text: 'Приоритет HIGH предлагается из-за текущей оценки риска; окончательный приоритет задаёт аналитик.', source: 'Assistant proposal' },
      ],
      tools: [call('get_vessel', `vessel_id: ${risk.vesselId}`, 1), call('get_current_voyage', `vessel_id: ${risk.vesselId}`, 1), call('get_vessel_risk', `vessel_id: ${risk.vesselId}`, 1)],
      action: { type: 'CREATE_CASE', label: 'Подтвердить создание CI-2026-00421', status: 'PENDING' },
    }
  }

  if (q.includes('добав') && (q.includes('ais') || q.includes('встреч')) && (q.includes('доказ') || q.includes('case') || q.includes('расслед'))) {
    const ids = [q.includes('ais') ? 'EV-2802' : '', q.includes('встреч') ? 'EV-2803' : ''].filter(Boolean)
    return {
      title: 'Доказательства готовы к добавлению',
      intro: 'Изменение состава Case требует подтверждения. Исходные Events останутся неизменными.',
      claims: ids.map(id => {
        const event = detectedEvents.find(item => item.id === id)!
        return { kind: 'FACT' as const, text: `${event.title}: ${event.summary}`, ...eventSource(event) }
      }),
      tools: [call('search_events', `ids: ${ids.join(', ')}`, ids.length)],
      action: { type: 'ADD_EVIDENCE', label: `Подтвердить добавление (${ids.length})`, evidenceIds: ids, status: 'PENDING' },
    }
  }

  if ((q.includes('когда') && q.includes('прибуд')) || q.includes('eta')) {
    const portCall = aktauPortOperations.portCall
    return {
      title: `ETA ${portCall.vesselName} в Актау`,
      intro: 'Использован актуальный прогноз Port Operations, а не заявленное судном время.',
      claims: [
        { kind: 'FACT', text: `Заявленный ETA — ${portCall.reportedEta}.`, source: 'PortCall pc-aktau-143', href: '/app/port-calls/pc-aktau-143' },
        { kind: 'ESTIMATE', text: `Расчётный ETA — ${portCall.predictedEta}; вероятное окно ${portCall.etaWindow}; confidence ${portCall.etaConfidence}%.`, source: 'CI-ETA-1.0', href: '/app/port-calls/pc-aktau-143' },
      ],
      tools: [call('get_current_voyage', `vessel_id: ${vesselId}`, 1), call('get_arrivals', 'port_id: aktau · vessel_id: caspian-star', 1)],
      action: { type: 'OPEN_PORT', label: 'Открыть Pre-Arrival Report', href: '/app/port-calls/pc-aktau-143' },
    }
  }

  if ((q.includes('что') && q.includes('порт') && q.includes('подготов')) || q.includes('подготовить причал')) {
    const pc = aktauPortOperations.portCall
    return {
      title: 'Что подготовить порту Актау',
      intro: 'Рекомендации собраны из PortCall, berth compatibility и Pre-Arrival risk review.',
      claims: [
        { kind: 'FACT', text: `Причал #5 совместим; доступен с ${aktauPortOperations.berths.find(item => item.id === 'berth-5')?.availableFrom}.`, source: 'Berth berth-5', href: '/app/port-calls/pc-aktau-143' },
        ...pc.recommendedActions.map(action => ({ kind: 'INFERENCE' as const, text: action, source: 'Pre-Arrival recommendation', href: '/app/port-calls/pc-aktau-143' })),
      ],
      tools: [call('get_port_status', 'port_id: aktau', 1), call('get_arrivals', 'port_call_id: pc-aktau-143', 1), call('get_vessel_risk', 'vessel_id: caspian-star', 1)],
      action: { type: 'OPEN_PORT', label: 'Открыть план подготовки', href: '/app/port-calls/pc-aktau-143' },
    }
  }

  if ((q.includes('почему') && (q.includes('перегруж') || q.includes('актау'))) || (q.includes('порт') && q.includes('4 час'))) {
    const forecast = aktauPortOperations.loadForecast
    const four = forecast.find(item => item.offset === '+4 HOURS')!
    const six = forecast.find(item => item.offset === '+6 HOURS')!
    const occupied = aktauPortOperations.berths.filter(item => item.status === 'OCCUPIED').length
    return {
      title: 'Почему нагрузка Актау растёт',
      intro: 'Объяснение объединяет прогноз заходов, очередь, доступность причалов и сервисные окна.',
      claims: [
        { kind: 'ESTIMATE', text: `Через 4 часа модель ожидает загрузку ${four.load}% (${four.level}); через 6 часов — ${six.load}% (${six.level}).`, source: 'Port Load Forecast', href: '/app/port/aktau' },
        { kind: 'FACT', text: `Сейчас в очереди ${aktauPortOperations.queue.length} судна; занято ${occupied} из ${aktauPortOperations.berths.length} учитываемых причалов.`, source: 'Port queue / berth status', href: '/app/port/aktau' },
        { kind: 'INFERENCE', text: 'Пересечение ETA и сервисных окон на причалах #3–#5 создаёт вероятный bottleneck; перенос BAKU EXPRESS на #7 снижает расчётный пик.', source: aktauPortOperations.recommendation.id, href: '/app/port/aktau' },
      ],
      tools: [call('get_port_status', 'port_id: aktau', 1), call('get_arrivals', 'window: 6h', aktauPortOperations.arrivals.length), call('get_port_forecast', 'horizon: 6h', forecast.length)],
      action: { type: 'OPEN_PORT', label: 'Открыть Port Control Center', href: '/app/port/aktau' },
    }
  }

  if ((q.includes('что происходило') && (q.includes('здесь') || q.includes('район'))) || q.includes('последние 24 часа')) {
    const areaEvents = detectedEvents.filter(event => event.x >= 49 && event.x <= 64 && event.y >= 30 && event.y <= 61)
    const vesselNames = [...new Set(areaEvents.map(event => event.vesselName))]
    return {
      title: 'События в выбранной области · 24 часа',
      intro: `${context.area || 'Central Caspian'}: spatial filter вернул ${areaEvents.length} событий и ${vesselNames.length} судна.`,
      claims: areaEvents.map(event => ({ kind: 'FACT', text: `${event.time} · ${event.vesselName} · ${event.title}: ${event.summary}`, ...eventSource(event) })),
      tools: [call('search_area', 'bbox: selected · period: 24h', areaEvents.length), call('search_events', 'spatial_result: current', areaEvents.length)],
    }
  }

  if (q.includes('суммируй') && q.includes('расслед')) {
    const current = loadCase()
    if (!current.evidence.length) return noData('В Case пока нет evidence. Я не могу сформировать содержательное резюме без источников.', [call('get_vessel_events', `case_id: ${current.id} · evidence_only: true`, 0)])
    return {
      title: `Резюме ${current.id}`,
      intro: 'Резюме построено только по Evidence внутри Case. События вне Case не использованы.',
      claims: [
        ...current.evidence.map(item => ({ kind: item.kind, text: `${item.time} · ${item.title}: ${item.detail}`, source: item.id, href: item.sourceHref })),
        { kind: 'INFERENCE', text: 'Сочетание добавленных событий требует проверки аналитиком; оно не является доказательством нарушения.', source: `Case ${current.id}`, href: `/app/investigations/${current.id}` },
      ],
      tools: [call('get_vessel_events', `case_id: ${current.id} · evidence_only: true`, current.evidence.length)],
      action: { type: 'OPEN_CASE', label: 'Открыть расследование', href: `/app/investigations/${current.id}` },
    }
  }

  return noData('В доступных модулях нет данных, достаточных для ответа на этот вопрос. Уточните судно, период, порт или район — я не буду дополнять отсутствующие факты предположениями.', [call('search_vessels', `query: ${question}`, 0), call('search_events', `query: ${question}`, 0)])
}

function noData(text: string, tools: ToolCall[]): Omit<ChatMessage, 'id' | 'role' | 'timestamp'> {
  return { title: 'Недостаточно данных', intro: text, claims: [], tools, noData: true }
}

function readMessages(): ChatMessage[] {
  try {
    const saved = sessionStorage.getItem(CHAT_KEY)
    if (saved) return JSON.parse(saved)
  } catch { /* use greeting */ }
  return [{
    id: 'welcome', role: 'assistant', timestamp: now(), title: 'Чем помочь?',
    intro: 'Я использую данные Vessel, Voyage, Events, Risk, Advanced Analytics и Port Operations. В ответах факты, оценки и выводы разделены, а источники можно открыть.',
    claims: [], tools: [],
  }]
}

function applyAction(action: AssistantAction) {
  if (action.type === 'CREATE_CASE') {
    const next = defaultCase()
    saveCase(next)
    return
  }
  if (action.type === 'ADD_EVIDENCE') {
    const current = loadCase()
    const additions = (action.evidenceIds || []).map(evidenceById).filter((item): item is CaseEvidence => Boolean(item))
    const existing = new Set(current.evidence.map(item => item.id))
    saveCase({ ...current, evidence: [...current.evidence, ...additions.filter(item => !existing.has(item.id))] })
  }
}

function AssistantMessage({ message, onConfirm }: { message: ChatMessage; onConfirm: (id: string) => void }) {
  if (message.role === 'user') return <div className="ai-message user-message"><div className="ai-avatar user"><UserRound size={15}/></div><div><p>{message.text}</p><time>{message.timestamp}</time></div></div>
  return <div className="ai-message assistant-message">
    <div className="ai-avatar"><Shield size={15}/></div>
    <div className="ai-answer">
      {message.title && <h3>{message.title}</h3>}
      {message.intro && <p className="ai-intro">{message.intro}</p>}
      {message.noData && <div className="ai-no-data"><TriangleAlert size={17}/><span>Ответ ограничен доступными данными</span></div>}
      {!!message.claims?.length && <div className="ai-claims">{message.claims.map((claim, index) => <article key={`${claim.text}-${index}`} className={`ai-claim ${claim.kind.toLowerCase()}`}>
        <span className="claim-kind">{claim.kind}</span>
        <p>{claim.text}</p>
        {claim.source && <button onClick={() => claim.href && go(claim.href)}><Link2 size={12}/>{claim.source}<ExternalLink size={11}/></button>}
      </article>)}</div>}
      {!!message.tools?.length && <details className="tool-trace"><summary><Database size={14}/>Проверено через {message.tools.length} tools <ChevronRight size={13}/></summary><div>{message.tools.map(tool => <div key={`${message.id}-${tool.name}`}><CircleCheck size={13}/><span><strong>{tool.name}</strong><small>{tool.detail}</small></span><em>{tool.records} records</em></div>)}</div></details>}
      {message.action && <div className={`assistant-action ${message.action.status === 'DONE' ? 'done' : ''}`}>
        {message.action.status === 'DONE' ? <CircleCheck size={17}/> : <LockKeyhole size={17}/>}<span><strong>{message.action.status === 'DONE' ? 'Действие выполнено' : 'Write action'}</strong><small>{message.action.label}</small></span>
        {message.action.href ? <button onClick={() => go(message.action!.href!)}>Открыть <ArrowRight size={13}/></button> : message.action.status !== 'DONE' ? <button onClick={() => onConfirm(message.id)}>Подтвердить</button> : <button onClick={() => go('/app/investigations/CI-2026-00421')}>Открыть расследование</button>}
      </div>}
      <time>{message.timestamp}</time>
    </div>
  </div>
}

function go(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

const promptGroups = [
  { label: 'Risk', prompts: ['Какие суда сейчас требуют внимания?', 'Почему CASPIAN STAR?', 'С кем оно встречалось?', 'Они встречались раньше?'] },
  { label: 'Operations', prompts: ['Когда судно прибудет в Актау?', 'Что порту нужно подготовить?', 'Почему Актау будет перегружен через 4 часа?'] },
  { label: 'Investigation', prompts: ['Создай расследование по CASPIAN STAR.', 'Добавь AIS gap и встречу в доказательства.', 'Суммируй расследование.'] },
  { label: 'Environment', prompts: ['Что известно про ENV-142?', 'Какие суда могли быть связаны?', 'Почему CASPIAN STAR первый кандидат?'] },
]

export function AssistantPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(readMessages)
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [context, setContext] = useState<AssistantContext>(getStoredContext)
  const [conversationId, setConversationId] = useState<string | undefined>(() => sessionStorage.getItem(CONVERSATION_KEY) || undefined)
  const endRef = useRef<HTMLDivElement>(null)
  const initialHandled = useRef(false)
  const lastTools = [...messages].reverse().find(item => item.tools?.length)?.tools || []

  const ask = async (question: string) => {
    const clean = question.trim()
    if (!clean || thinking) return
    const user: ChatMessage = { id: `u-${Date.now()}`, role: 'user', text: clean, timestamp: now() }
    setMessages(current => [...current, user])
    setInput('')
    setThinking(true)
    try {
      let response = await fetch(`${API_BASE}/assistant/chat`, {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ question: clean, conversation_id: conversationId, context: contextForApi(context) }),
      })
      if (response.status === 404 && conversationId) {
        sessionStorage.removeItem(CONVERSATION_KEY)
        setConversationId(undefined)
        response = await fetch(`${API_BASE}/assistant/chat`, {
          method: 'POST',
          headers: apiHeaders(),
          body: JSON.stringify({ question: clean, context: contextForApi(context) }),
        })
      }
      if (!response.ok) {
        const problem = await response.json().catch(() => ({}))
        throw new Error(problem.detail || `Assistant API: ${response.status}`)
      }
      const result = await response.json() as ApiChatResponse
      setConversationId(result.conversation_id)
      sessionStorage.setItem(CONVERSATION_KEY, result.conversation_id)
      const answer = chatFromApi(result)
      setMessages(current => [...current, answer])
    } catch (error) {
      const answer: ChatMessage = {
        id: `a-error-${Date.now()}`,
        role: 'assistant',
        timestamp: now(),
        title: 'Assistant API недоступен',
        intro: error instanceof Error ? error.message : 'Не удалось получить grounded response.',
        noData: true,
        claims: [],
        tools: [],
      }
      setMessages(current => [...current, answer])
    } finally {
      setThinking(false)
    }
  }

  useEffect(() => { sessionStorage.setItem(CHAT_KEY, JSON.stringify(messages)); endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages, thinking])
  useEffect(() => {
    if (initialHandled.current) return
    initialHandled.current = true
    const params = new URLSearchParams(window.location.search)
    const q = params.get('q')
    if (q) ask(q)
  }, [])

  const confirm = async (id: string) => {
    const message = messages.find(item => item.id === id)
    if (!message?.action?.id) return
    try {
      const response = await fetch(`${API_BASE}/assistant/actions/${message.action.id}/confirm`, {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ confirmed: true }),
      })
      if (!response.ok) {
        const problem = await response.json().catch(() => ({}))
        throw new Error(problem.detail || `Action API: ${response.status}`)
      }
      const result = await response.json() as { investigation?: ApiInvestigation }
      if (result.investigation) saveCase(caseFromApi(result.investigation))
      setMessages(current => current.map(item => item.id === id && item.action
        ? { ...item, action: { ...item.action, status: 'DONE', href: result.investigation ? `/app/investigations/${result.investigation.id}` : item.action.href } }
        : item))
    } catch (error) {
      setMessages(current => [...current, {
        id: `a-action-error-${Date.now()}`,
        role: 'assistant',
        timestamp: now(),
        title: 'Действие не выполнено',
        intro: error instanceof Error ? error.message : 'Подтверждение не принято.',
        noData: true,
      }])
    }
  }

  const clear = () => {
    sessionStorage.removeItem(CHAT_KEY)
    sessionStorage.removeItem(CONVERSATION_KEY)
    setConversationId(undefined)
    setMessages(readMessages())
  }

  return <div className="assistant-page">
    <aside className="assistant-rail">
      <div className="assistant-brand"><span><Shield size={18}/></span><div><strong>ИИ-помощник CI</strong><small>Ответы на основе данных</small></div></div>
      <button className="new-thread" onClick={clear}><Plus size={15}/>Новый диалог</button>
      <div className="thread-block"><span>Текущий диалог</span><button className="active"><MessageSquareText size={15}/><span><strong>Рабочая область расследования</strong><small>{messages.length} сообщений · сейчас</small></span></button></div>
      <div className="assistant-access"><ShieldCheck size={16}/><span><strong>Доступ: аналитик</strong><small>Ответы учитывают текущие права</small></span></div>
    </aside>

    <main className="assistant-chat">
      <header className="assistant-chat-head"><div><span className="page-eyebrow">ИИ-помощник · Этапы 8–9</span><h1>Работа с данными обычным языком</h1></div><button onClick={() => go('/app/investigations')}><Target size={16}/>Расследования</button></header>
      <div className="assistant-context-bar"><MapPin size={15}/><span><small>Контекст страницы</small><strong>{context.label}</strong></span>{context.vesselName && <em>{context.vesselName}</em>}{context.voyageId && <em>{context.voyageId}</em>}{context.environmentalEventId && <em>{context.environmentalEventId}</em>}<button onClick={() => setContext(pageContext('/app/assistant'))}>Сбросить</button></div>
      <div className="chat-scroll">
        {messages.map(message => <AssistantMessage key={message.id} message={message} onConfirm={confirm}/>)}
        {thinking && <div className="ai-message assistant-message"><div className="ai-avatar"><Shield size={15}/></div><div className="assistant-thinking"><i/><i/><i/><span>Проверяю доступные модули</span></div></div>}
        {messages.length <= 1 && <div className="prompt-grid">{promptGroups.map(group => <section key={group.label}><span>{group.label}</span>{group.prompts.map(prompt => <button key={prompt} onClick={() => ask(prompt)}>{prompt}<ChevronRight size={13}/></button>)}</section>)}</div>}
        <div ref={endRef}/>
      </div>
      <form className="assistant-composer" onSubmit={event => { event.preventDefault(); ask(input) }}><div><Shield size={17}/><textarea rows={1} value={input} onChange={event => setInput(event.target.value)} placeholder="Спросите о судне, событии, риске, порте или районе…" onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); ask(input) } }}/><button disabled={!input.trim() || thinking}><Send size={16}/></button></div><span><ShieldCheck size={12}/>Ответы основаны только на доступных данных</span><small>Enter — отправить · Shift + Enter — новая строка</small></form>
    </main>

    <aside className="assistant-inspector">
      <div className="inspector-title"><Database size={16}/><span><strong>Источники ответа</strong><small>Последний ответ</small></span></div>
      <div className="tool-inspector">{lastTools.length ? lastTools.map(tool => <div key={tool.name}><span><Check size={11}/></span><p><strong>{tool.name}</strong><small>{operationalText(tool.detail)}</small></p><em>{tool.records}</em></div>) : <p className="tools-empty">После запроса здесь появятся вызванные инструменты и объём прочитанных данных.</p>}</div>
      <div className="separation-card"><strong>Факт / Оценка / Вывод</strong><span><i className="fact"/>ФАКТ — сохранённое наблюдение</span><span><i className="estimate"/>ОЦЕНКА — результат модели</span><span><i className="inference"/>ВЫВОД — объяснимый результат</span></div>
      <div className="audit-card"><FileText size={15}/><span><strong>Аудит включён</strong><small>пользователь · вопрос · инструменты · данные · ответ · действия</small></span></div>
    </aside>
  </div>
}

export function AssistantLauncher({ path }: { path: string }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const context = pageContext(path)
  if (path.startsWith('/app/assistant')) return null
  const launch = (question?: string) => {
    const storedMapContext = path.startsWith('/app/map') ? getStoredContext() : null
    const launchContext = storedMapContext?.page.startsWith('/app/map') && storedMapContext.areaBounds ? storedMapContext : context
    sessionStorage.setItem(CONTEXT_KEY, JSON.stringify(launchContext))
    const suffix = question ? `?q=${encodeURIComponent(question)}` : ''
    go(`/app/assistant${suffix}`)
    setOpen(false)
  }
  const storedMapContext = path.startsWith('/app/map') ? getStoredContext() : null
  const hasSelectedArea = Boolean(storedMapContext?.page.startsWith('/app/map') && storedMapContext.areaBounds)
  const suggested = context.environmentalEventId ? `Что известно про ${context.environmentalEventId}?` : context.portId ? 'Почему Актау будет перегружен через 4 часа?' : hasSelectedArea ? 'Что происходило здесь за последние 24 часа?' : context.vesselId ? 'Почему риск вырос?' : 'Какие суда сейчас требуют внимания?'
  return <>
    <button className={`assistant-fab ${open ? 'open' : ''}`} onClick={() => setOpen(value => !value)} aria-label="Открыть ИИ-помощника CI">{open ? <X size={21}/> : <><Shield size={20}/><span>ИИ</span></>}</button>
    {open && <aside className="assistant-popover">
      <header><span><Shield size={17}/></span><div><strong>ИИ-помощник CI</strong><small>Работает с данными платформы</small></div><button onClick={() => setOpen(false)}><X size={16}/></button></header>
      <div className="popover-context"><MapPin size={14}/><span><small>Текущий контекст</small><strong>{hasSelectedArea ? 'Выбранная область Каспия' : context.label}</strong></span>{context.vesselName && <em>{context.vesselName}</em>}{hasSelectedArea && <em>24H</em>}</div>
      <button className="context-question" onClick={() => launch(suggested)}><Sparkles size={14}/><span>{suggested}</span><ChevronRight size={14}/></button>
      <form onSubmit={event => { event.preventDefault(); if (input.trim()) launch(input) }}><input value={input} onChange={event => setInput(event.target.value)} placeholder="Задать вопрос…"/><button disabled={!input.trim()}><Send size={15}/></button></form>
      <button className="open-assistant" onClick={() => launch()}><MessageSquareText size={14}/>Открыть полный ИИ-помощник <ArrowRight size={13}/></button>
    </aside>}
  </>
}

function EvidenceCard({ event, added, pending, onAdd, onConfirm, onCancel }: { event: DetectionEvent; added: boolean; pending: boolean; onAdd: () => void; onConfirm: () => void; onCancel: () => void }) {
  return <article className={`case-evidence-card ${added ? 'added' : ''}`}>
    <div className="evidence-icon"><FileSearch size={17}/></div><div><span><strong>{operationalText(event.title)}</strong><em>{event.id}</em></span><p>{operationalText(event.summary)}</p><small>{event.startedAt} · достоверность {event.confidence}%</small></div>
    {added ? <span className="evidence-added"><CircleCheck size={13}/>В РАССЛЕДОВАНИИ</span> : !pending ? <button onClick={onAdd}><Plus size={13}/>Добавить</button> : <div className="evidence-confirm"><span><LockKeyhole size={12}/>Подтвердить изменение?</span><button onClick={onConfirm}>Да</button><button onClick={onCancel}>Нет</button></div>}
  </article>
}

export function InvestigationWorkspacePage() {
  const [caseData, setCaseData] = useState<InvestigationCase>(loadCase)
  const [pending, setPending] = useState<string | null>(null)
  const [note, setNote] = useState('')
  const [caseError, setCaseError] = useState('')
  const investigationId = window.location.pathname.split('/').pop() || 'CI-2026-00421'
  const isEnvironmental = caseData.caseType === 'environmental'
  const candidates = isEnvironmental ? [] : detectedEvents.filter(event => event.vesselId === caseData.vesselId && ['route_deviation', 'ais_gap', 'vessel_encounter', 'draught_change'].includes(event.type))
  const environmentalVessels = [
    { id: 'caspian-star', name: 'CASPIAN STAR', detail: '0,8 км · соответствие 94% · возможный кандидат' },
    { id: 'turan', name: 'TURAN', detail: '2,4 км · соответствие 72% · возможный кандидат' },
    { id: 'baku-express', name: 'BAKU EXPRESS', detail: '7,1 км · низкое соответствие · возможный кандидат' },
  ].filter(item => caseData.relatedVesselIds.includes(item.id))
  const refresh = () => setCaseData(loadCase())
  useEffect(() => {
    addEventListener('ci-case-updated', refresh)
    fetch(`${API_BASE}/investigations/${investigationId}`, { headers: apiHeaders() })
      .then(async response => {
        if (!response.ok) throw new Error(response.status === 404 ? 'Case ещё не создан. Создайте его через Assistant и подтвердите действие.' : `Case API: ${response.status}`)
        return response.json() as Promise<ApiInvestigation>
      })
      .then(value => { const next = caseFromApi(value); setCaseData(next); saveCase(next); setCaseError('') })
      .catch(error => setCaseError(error instanceof Error ? error.message : 'Case недоступен'))
    return () => removeEventListener('ci-case-updated', refresh)
  }, [investigationId])
  const addEvidence = async (id: string) => {
    if (caseData.evidence.some(entry => entry.id === id)) return
    try {
      const response = await fetch(`${API_BASE}/investigations/${caseData.id}/evidence`, {
        method: 'POST', headers: apiHeaders(), body: JSON.stringify({ evidence_ids: [id], confirmed: true }),
      })
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Evidence API: ${response.status}`)
      const next = caseFromApi(await response.json() as ApiInvestigation)
      setCaseData(next); saveCase(next); setPending(null); setCaseError('')
    } catch (error) {
      setCaseError(error instanceof Error ? error.message : 'Evidence не добавлено')
    }
  }
  const addNote = async () => {
    const clean = note.trim(); if (!clean) return
    try {
      const response = await fetch(`${API_BASE}/investigations/${caseData.id}/notes`, {
        method: 'POST', headers: apiHeaders(), body: JSON.stringify({ note: clean, confirmed: true }),
      })
      if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || `Notes API: ${response.status}`)
      const next = caseFromApi(await response.json() as ApiInvestigation)
      setCaseData(next); saveCase(next); setNote(''); setCaseError('')
    } catch (error) {
      setCaseError(error instanceof Error ? error.message : 'Заметка не добавлена')
    }
  }
  const summary = caseData.evidence.length
    ? isEnvironmental
      ? `${caseData.evidence.length} доказательств описывают обнаружение, полигон, погодные данные, реконструкцию, AIS-треки и связи с возможными кандидатами. Они помогают проверить событие, но не устанавливают источник загрязнения.`
      : `${caseData.evidence.length} выбранных доказательств описывают последовательность наблюдений по рейсу #143. Их сочетание требует аналитической проверки, но не устанавливает факт нарушения.`
    : 'Доказательства ещё не добавлены. ИИ не сформирует сводку расследования без выбранных источников.'
  return <div className="investigation-page content-page">
    {caseError && <div className="case-api-warning"><TriangleAlert size={16}/><span>{caseError}</span><button onClick={() => go('/app/assistant?q=' + encodeURIComponent(isEnvironmental || investigationId.startsWith('ENV-') ? 'Создай расследование по ENV-142.' : 'Создай расследование по CASPIAN STAR.'))}>Открыть ИИ-помощник</button></div>}
    <div className="case-page-head"><button className="back-link" onClick={() => go('/app/investigations')}><ArrowRight size={14}/>Все расследования</button><div><span className="page-eyebrow">Рабочая область расследования · проверяемые источники</span><h1>{caseData.id}</h1><p>{caseData.title}</p></div><div className="case-head-actions"><button className="secondary-button" onClick={() => { sessionStorage.setItem(CONTEXT_KEY, JSON.stringify(pageContext(`/app/investigations/${caseData.id}`))); go('/app/assistant?q=' + encodeURIComponent('Суммируй расследование.')) }}><Sparkles size={15}/>Суммировать</button><button className="primary-button"><UserRound size={15}/>Назначено: Аян</button></div></div>
    <div className="case-status-strip">
      <div><span>Статус</span><strong className="open">{statusLabel(caseData.status)}</strong></div>
      <div><span>Приоритет</span><strong className="high">{severityLabel(caseData.priority)}</strong></div>
      {isEnvironmental ? <>
        <div><span>Экологическое событие</span><button onClick={() => go(`/app/environment/events/${caseData.environmentalEventId || 'ENV-2026-00142'}`)}>{caseData.environmentalEventId || 'ENV-2026-00142'}<ExternalLink size={11}/></button></div>
        <div><span>Основной кандидат</span><button onClick={() => go(`/app/vessels/${caseData.vesselId}?tab=environment`)}>{caseData.vesselName}<ExternalLink size={11}/></button></div>
      </> : <>
        <div><span>Судно</span><button onClick={() => go('/app/vessels/caspian-star')}>{caseData.vesselName}<ExternalLink size={11}/></button></div>
        <div><span>Рейс</span><button onClick={() => go('/app/voyages/voy-001/intelligence')}>#143 · {caseData.route}<ExternalLink size={11}/></button></div>
      </>}
      <div><span>Доказательства</span><strong>{caseData.evidence.length}</strong></div>
    </div>
    <div className="case-layout">
      <main className="case-main">
        <section className="card ai-case-summary"><div className="card-head"><div><span className="page-eyebrow">Сводка расследования от ИИ</span><h2>Только по доказательствам этого расследования</h2></div><span className={caseData.evidence.length ? 'ready' : 'empty'}>{caseData.evidence.length ? 'ЕСТЬ ИСТОЧНИКИ' : 'НЕДОСТАТОЧНО ДАННЫХ'}</span></div><p>{summary}</p>{caseData.evidence.map(item => <button key={item.id} onClick={() => go(item.sourceHref)}><span className={`claim-kind ${item.kind.toLowerCase()}`}>{statusLabel(item.kind)}</span>{item.title}<em>{item.id}</em><ExternalLink size={11}/></button>)}<div className="case-caution"><ShieldCheck size={14}/>{isEnvironmental ? (caseData.disclaimer || 'Пространственно-временная ассоциация не доказывает источник загрязнения или нарушение.') : 'Аномалия является признаком для проверки, а не утверждением о нарушении.'}</div></section>
        {isEnvironmental ? <section className="card evidence-library"><div className="card-head"><div><span className="page-eyebrow">Сбор доказательств</span><h2>Экологические доказательства</h2></div><span>{caseData.evidence.length} зафиксировано</span></div>{caseData.evidence.map(item => <article key={item.id} className="case-evidence-card added"><div className="evidence-icon"><FileSearch size={17}/></div><div><span><strong>{item.title}</strong><em>{item.id}</em></span><p>{item.detail}</p><small>{item.time} · {statusLabel(item.kind)} · связанный источник</small></div><button onClick={() => go(item.sourceHref)}>Источник <ExternalLink size={11}/></button></article>)}</section>
          : <section className="card evidence-library"><div className="card-head"><div><span className="page-eyebrow">Сбор доказательств</span><h2>События текущего рейса</h2></div><span>{caseData.evidence.length} / {candidates.length} добавлено</span></div>{candidates.map(event => <EvidenceCard key={event.id} event={event} added={caseData.evidence.some(item => item.id === event.id)} pending={pending === event.id} onAdd={() => setPending(event.id)} onConfirm={() => addEvidence(event.id)} onCancel={() => setPending(null)}/>)}</section>}
        <section className="card case-timeline"><div className="card-head"><div><span className="page-eyebrow">Хронология расследования</span><h2>{isEnvironmental ? caseData.environmentalEventId : 'Рейс #143'}</h2></div><span>Наблюдения и результаты моделей</span></div>{isEnvironmental
          ? caseData.timeline.map((item, index) => <div key={item.id} className="timeline-row evidence"><time>{new Date(item.occurredAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}</time><i/><div><strong>{item.title}</strong><p>{item.detail}</p></div><span className={item.kind.toLowerCase()}>{statusLabel(item.kind)}</span>{index < caseData.timeline.length - 1 && <b/>}</div>)
          : voyageIntelligence.timeline.map((item, index) => <div key={`${item.time}-${item.title}`} className={`timeline-row ${caseData.evidence.some(evidence => item.title.toLowerCase().includes(evidence.title.toLowerCase().split(' ')[0])) ? 'evidence' : ''}`}><time>{item.time}</time><i/><div><strong>{operationalText(item.title)}</strong><p>{operationalText(item.description)}</p></div><span className={item.status?.toLowerCase() || 'fact'}>{statusLabel(item.status || 'FACT')}</span>{index < voyageIntelligence.timeline.length - 1 && <b/>}</div>)}</section>
      </main>
      <aside className="case-side">
        <section className="card case-entities"><span className="page-eyebrow">Связанные сущности</span><h3>Связанные объекты</h3>{isEnvironmental ? <>
          <button onClick={() => go(`/app/environment/events/${caseData.environmentalEventId || 'ENV-2026-00142'}`)}><Target size={15}/><span><strong>{caseData.environmentalEventId || 'ENV-2026-00142'}</strong><small>Экологическое событие · источник проверяется</small></span><ChevronRight size={13}/></button>
          {environmentalVessels.map(item => <button key={item.id} onClick={() => go(`/app/vessels/${item.id}?tab=environment`)}><Ship size={15}/><span><strong>{item.name}</strong><small>{item.detail}</small></span><ChevronRight size={13}/></button>)}
        </> : <><button onClick={() => go('/app/vessels/caspian-star')}><Ship size={15}/><span><strong>CASPIAN STAR</strong><small>Основное судно · риск 91</small></span><ChevronRight size={13}/></button><button onClick={() => go('/app/network?connection=e-encounter')}><Ship size={15}/><span><strong>TURAN</strong><small>14 исторических встреч</small></span><ChevronRight size={13}/></button><button onClick={() => go('/app/network')}><Network size={15}/><span><strong>Caspian Marine Co.</strong><small>Заявленный владелец / оператор</small></span><ChevronRight size={13}/></button></>}</section>
        <section className="card case-notes"><span className="page-eyebrow">Заметки аналитика</span><h3>Заметки</h3>{caseData.notes.length ? caseData.notes.map((item, index) => <p key={index}>{item}<small>Аян · сейчас</small></p>) : <div className="empty-notes">Заметок пока нет.</div>}<textarea rows={3} value={note} onChange={event => setNote(event.target.value)} placeholder="Добавить наблюдение аналитика…"/><button className="secondary-button" disabled={!note.trim()} onClick={addNote}>Добавить заметку</button></section>
        <section className="case-audit card"><FileText size={17}/><div><strong>Журнал аудита расследования</strong><p>Создание, доказательства, заметки и изменения статуса регистрируются с пользователем и временем.</p></div></section>
      </aside>
    </div>
  </div>
}

export function InvestigationListPage() {
  const [cases, setCases] = useState<InvestigationCase[]>([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    fetch(`${API_BASE}/investigations`, { headers: apiHeaders() })
      .then(async response => {
        if (!response.ok) throw new Error(`Investigations API: ${response.status}`)
        return response.json() as Promise<ApiInvestigation[]>
      })
      .then(items => setCases(items.map(caseFromApi)))
      .finally(() => setLoading(false))
  }, [])
  const evidenceCount = cases.reduce((sum, item) => sum + item.evidence.length, 0)
  return <div className="content-page investigation-list-page">
    <div className="page-header"><div><span className="page-eyebrow">Реестр расследований</span><h1>Расследования</h1><p>Рабочие расследования с доказательствами, связанными объектами и контролируемыми действиями ИИ.</p></div><button className="primary-button" onClick={() => go('/app/assistant?q=' + encodeURIComponent('Создай расследование по CASPIAN STAR.'))}><Plus size={16}/>Новое расследование</button></div>
    <div className="case-overview-metrics"><div><Target size={17}/><span><small>Открытые расследования</small><strong>{cases.filter(item => item.status === 'OPEN').length}</strong></span></div><div><TriangleAlert size={17}/><span><small>Высокий приоритет</small><strong>{cases.filter(item => ['HIGH', 'CRITICAL'].includes(item.priority)).length}</strong></span></div><div><FileSearch size={17}/><span><small>Доказательства</small><strong>{evidenceCount}</strong></span></div><div><Clock3 size={17}/><span><small>Обновлено</small><strong>{loading ? 'загрузка' : 'сейчас'}</strong></span></div></div>
    <section className="table-card case-list-card"><div className="table-toolbar"><div className="inline-search"><Search size={15}/><input placeholder="Расследование, судно, IMO или аналитик"/></div><button className="secondary-button"><ShieldCheck size={14}/>ОТКРЫТЫЕ</button><span className="results-count">{cases.length} расследований</span></div>{cases.map(current => <button key={current.id} className="case-list-row" onClick={() => go(`/app/investigations/${current.id}`)}><span className="case-id"><Target size={16}/><span><strong>{current.id}</strong><small>{current.createdAt}</small></span></span><span><small>Объект</small><strong>{current.vesselName}</strong><em>{current.route}</em></span><span><small>Приоритет</small><strong className="high">{severityLabel(current.priority)}</strong></span><span><small>Статус</small><strong className="open">{statusLabel(current.status)}</strong></span><span><small>Доказательства</small><strong>{current.evidence.length}</strong></span><span><small>Назначено</small><strong>{current.assignedTo}</strong></span><ChevronRight size={17}/></button>)}{!loading && !cases.length && <div className="case-empty-state"><Target size={24}/><strong>Расследований пока нет</strong><p>ИИ-помощник подготовит расследование по контексту судна, но создаст его только после вашего подтверждения.</p><button onClick={() => go('/app/assistant?q=' + encodeURIComponent('Создай расследование по CASPIAN STAR.'))}>Создать через ИИ-помощник</button></div>}</section>
    <section className="investigation-policy"><ShieldCheck size={18}/><div><strong>Решение остаётся за человеком</strong><p>ИИ читает разрешённые данные автоматически. Создание и изменение расследования выполняются только после подтверждения и попадают в журнал аудита.</p></div><button onClick={() => go('/app/assistant')}><Sparkles size={14}/>Открыть ИИ-помощник</button></section>
  </div>
}

export { TOOL_CATALOG }
