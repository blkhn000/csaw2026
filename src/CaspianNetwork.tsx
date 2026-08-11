import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  Activity, Anchor, ArrowLeft, ArrowRight, BadgeCheck, BarChart3, Building2,
  CalendarDays, Check, ChevronDown, ChevronRight, CircleCheck, Clock3, Cloud,
  Database, Eye, FileCheck2, FileSearch, FileText, Filter, Gauge,
  GitCompareArrows, Globe2, History, Info, Layers3, Leaf, Link2, LockKeyhole,
  MapPin, Navigation, Network, Package, Radio, RefreshCw, Route, Search,
  Settings2, ShieldAlert, ShieldCheck, Ship, Sparkles, TimerReset,
  TriangleAlert, Users, Waves, Wifi, WifiOff, X, Zap
} from 'lucide-react'
import './caspian-network.css'
import { RealCaspianMap, circleArea, type RealMapLine } from './RealCaspianMap'
import { operationalText } from './i18n'

type Navigate = (path: string) => void
type IntegrationState = 'CONNECTED' | 'PARTIAL' | 'PLANNED'
type HealthState = 'ONLINE' | 'DEGRADED' | 'OFFLINE'
type RiskBand = 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW'

const integrationLabel = (value: IntegrationState) => ({ CONNECTED: 'ПОДКЛЮЧЕНО', PARTIAL: 'ЧАСТИЧНО', PLANNED: 'ЗАПЛАНИРОВАНО' }[value])
const healthLabel = (value: HealthState) => ({ ONLINE: 'В СЕТИ', DEGRADED: 'ОГРАНИЧЕНО', OFFLINE: 'НЕТ СВЯЗИ' }[value])

export type NetworkPort = {
  id: string
  name: string
  country: string
  countryCode: string
  latitude: number
  longitude: number
  x: number
  y: number
  load: number
  vessels: number
  incoming: number
  waiting: string
  service: string
  highRisk: number
  localTime: string
  timezone: string
  portType: string
  berths: number
  freeBerths: number
  capabilities: string[]
  integration: IntegrationState
  quality: number
  updated: string
}

type RiskRow = {
  id: string
  globalId: string
  name: string
  flag: string
  type: string
  route: string
  originCountry: string
  port: string
  score: number
  band: RiskBand
  factors: string[]
  updated: string
}

type RouteRow = {
  id: string
  from: string
  to: string
  countries: string
  voyages: number
  duration: string
  delay: string
  aisGaps: number
  highRisk: number
  cargo: string
  reliability: number
  trend: number[]
}

type DataSource = {
  id: string
  name: string
  type: string
  country: string
  status: HealthState
  quality: number
  coverage: string
  latency: string
  updated: string
}

type SearchKind = 'VESSEL' | 'COMPANY' | 'PORT' | 'VOYAGE' | 'EVENT' | 'CASE' | 'ENVIRONMENT' | 'CARGO'
type SearchItem = {
  id: string
  kind: SearchKind
  title: string
  subtitle: string
  meta: string
  href: string
  status?: string
  aliases?: string[]
}

type CrossPortData = {
  voyage_id: string
  global_vessel_id: string
  vessel_name: string
  origin_port_id: string
  destination_port_id: string
  departure: { port_id:string; observed_at:string; cargo_t:number; draught_m:number; document_ids:string[]; status:string; source_ids:string[] }
  arrival: { port_id:string; observed_at:string; cargo_t:number; draught_m:number; document_ids:string[]; status:string; source_ids:string[] }
  comparisons: Array<{ field_name:string; departure_value:unknown; arrival_value:unknown; difference:number|null; unit:string|null; status:string; explanation:string; evidence_ids:string[] }>
  overall_status: string
  next_voyage_id: string | null
}

type RegionalGraphData = {
  nodes: Array<{ id:string; type:string; label:string; country:string|null; risk_score:number|null }>
  edges: Array<{ id:string; source:string; target:string; relationship:string; weight:number; evidence_ids:string[] }>
  evidence_grounded: boolean
}

type NetworkAccess = {
  user_id: string
  organization: { id:string; name:string }
  role: string
  permissions: string[]
  data_scope: string[]
}

type NetworkAuditRow = {
  timestamp: string
  user: string
  organization: string
  action: string
  resource: string
  outcome: string
}

const API_BASE = import.meta.env.VITE_API_BASE || (
  ['4173', '5173'].includes(window.location.port)
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : '/api/v1'
)

const networkPorts: NetworkPort[] = [
  { id:'aktau',name:'Aktau',country:'Kazakhstan',countryCode:'KZ',latitude:43.65,longitude:51.16,x:72,y:28,load:68,vessels:12,incoming:7,waiting:'1h 42m',service:'5h 12m',highRisk:1,localTime:'15:05',timezone:'UTC+5',portType:'Commercial seaport',berths:8,freeBerths:3,capabilities:['General cargo','Oil','Ro-Ro','Containers'],integration:'CONNECTED',quality:98,updated:'8 sec ago' },
  { id:'kuryk',name:'Kuryk',country:'Kazakhstan',countryCode:'KZ',latitude:43.20,longitude:51.65,x:70,y:37,load:51,vessels:7,incoming:4,waiting:'1h 18m',service:'4h 48m',highRisk:0,localTime:'15:05',timezone:'UTC+5',portType:'Ferry & Ro-Ro',berths:4,freeBerths:2,capabilities:['Ro-Ro','Rail ferry','Passenger'],integration:'PARTIAL',quality:91,updated:'34 sec ago' },
  { id:'baku',name:'Baku',country:'Azerbaijan',countryCode:'AZ',latitude:40.37,longitude:49.89,x:35,y:60,load:74,vessels:24,incoming:9,waiting:'2h 06m',service:'6h 04m',highRisk:2,localTime:'14:05',timezone:'UTC+4',portType:'Commercial seaport',berths:13,freeBerths:3,capabilities:['General cargo','Containers','Ro-Ro','Passenger'],integration:'CONNECTED',quality:94,updated:'12 min ago' },
  { id:'alat',name:'Alat',country:'Azerbaijan',countryCode:'AZ',latitude:39.95,longitude:49.41,x:37,y:68,load:57,vessels:9,incoming:5,waiting:'1h 34m',service:'5h 22m',highRisk:1,localTime:'14:05',timezone:'UTC+4',portType:'Logistics hub',berths:12,freeBerths:5,capabilities:['Containers','Ro-Ro','Bulk','Rail ferry'],integration:'PARTIAL',quality:88,updated:'4 min ago' },
  { id:'turkmenbashi',name:'Turkmenbashi',country:'Turkmenistan',countryCode:'TM',latitude:40.02,longitude:52.97,x:77,y:64,load:42,vessels:11,incoming:6,waiting:'0h 54m',service:'4h 16m',highRisk:1,localTime:'15:05',timezone:'UTC+5',portType:'International seaport',berths:9,freeBerths:5,capabilities:['Ro-Ro','Bulk','Containers','Passenger'],integration:'CONNECTED',quality:93,updated:'22 sec ago' },
  { id:'astrakhan',name:'Astrakhan',country:'Russia',countryCode:'RU',latitude:46.35,longitude:48.04,x:36,y:5,load:63,vessels:18,incoming:8,waiting:'2h 22m',service:'6h 48m',highRisk:2,localTime:'13:05',timezone:'UTC+3',portType:'River-sea port',berths:10,freeBerths:4,capabilities:['Bulk','General cargo','Containers'],integration:'PLANNED',quality:76,updated:'18 min ago' },
  { id:'makhachkala',name:'Makhachkala',country:'Russia',countryCode:'RU',latitude:42.97,longitude:47.50,x:29,y:35,load:59,vessels:15,incoming:5,waiting:'1h 58m',service:'5h 38m',highRisk:1,localTime:'13:05',timezone:'UTC+3',portType:'Commercial seaport',berths:7,freeBerths:3,capabilities:['Oil','Dry cargo','Ferry'],integration:'PARTIAL',quality:83,updated:'7 min ago' },
  { id:'anzali',name:'Anzali',country:'Iran',countryCode:'IR',latitude:37.47,longitude:49.47,x:39,y:92,load:47,vessels:8,incoming:3,waiting:'1h 12m',service:'5h 02m',highRisk:1,localTime:'13:35',timezone:'UTC+3:30',portType:'Free zone port',berths:10,freeBerths:5,capabilities:['Containers','General cargo','Passenger'],integration:'PLANNED',quality:71,updated:'24 min ago' },
  { id:'amirabad',name:'Amirabad',country:'Iran',countryCode:'IR',latitude:36.85,longitude:53.37,x:63,y:94,load:66,vessels:10,incoming:4,waiting:'2h 14m',service:'6h 18m',highRisk:2,localTime:'13:35',timezone:'UTC+3:30',portType:'Special economic port',berths:15,freeBerths:5,capabilities:['Ro-Ro','Rail ferry','Bulk','Oil'],integration:'PLANNED',quality:68,updated:'29 min ago' },
]

const riskRows: RiskRow[] = [
  { id:'caspian-star',globalId:'CI-VESSEL-000184',name:'CASPIAN STAR',flag:'Kazakhstan',type:'Cargo vessel',route:'Baku → Aktau',originCountry:'Azerbaijan',port:'Aktau',score:91,band:'CRITICAL',factors:['AIS gap','Encounter','Route deviation','Cargo context'],updated:'2 min' },
  { id:'turan',globalId:'CI-VESSEL-000241',name:'TURAN',flag:'Turkmenistan',type:'General cargo',route:'Turkmenbashi → Baku',originCountry:'Turkmenistan',port:'Baku',score:84,band:'HIGH',factors:['Repeated encounters','AIS gap','Network context'],updated:'4 min' },
  { id:'volga-marine',globalId:'CI-VESSEL-000093',name:'VOLGA MARINE',flag:'Russia',type:'General cargo',route:'Astrakhan → Aktau',originCountry:'Russia',port:'Aktau',score:78,band:'HIGH',factors:['Route deviation','Late declaration'],updated:'1 min' },
  { id:'khazar-wave',globalId:'CI-VESSEL-000342',name:'KHAZAR WAVE',flag:'Azerbaijan',type:'Oil tanker',route:'Baku → Turkmenbashi',originCountry:'Azerbaijan',port:'Turkmenbashi',score:68,band:'HIGH',factors:['Speed anomaly','Weather context'],updated:'6 min' },
  { id:'baku-express',globalId:'CI-VESSEL-000415',name:'BAKU EXPRESS',flag:'Azerbaijan',type:'Ro-Ro cargo',route:'Alat → Kuryk',originCountry:'Azerbaijan',port:'Kuryk',score:54,band:'MODERATE',factors:['Schedule deviation'],updated:'8 min' },
  { id:'anzali-trader',globalId:'CI-VESSEL-000508',name:'ANZALI TRADER',flag:'Iran',type:'Container ship',route:'Anzali → Baku',originCountry:'Iran',port:'Baku',score:31,band:'MODERATE',factors:['AIS coverage context'],updated:'5 min' },
]

const routeRows: RouteRow[] = [
  { id:'baku-aktau',from:'Baku',to:'Aktau',countries:'AZ ↔ KZ',voyages:284,duration:'29h 14m',delay:'42 min',aisGaps:17,highRisk:8,cargo:'4 860 t',reliability:94,trend:[61,68,65,74,79,72,83,88,81,90,86,94] },
  { id:'aktau-turkmenbashi',from:'Aktau',to:'Turkmenbashi',countries:'KZ ↔ TM',voyages:173,duration:'24h 48m',delay:'31 min',aisGaps:9,highRisk:4,cargo:'3 920 t',reliability:96,trend:[52,57,61,64,63,72,69,76,82,78,85,89] },
  { id:'alat-kuryk',from:'Alat',to:'Kuryk',countries:'AZ ↔ KZ',voyages:148,duration:'27h 36m',delay:'55 min',aisGaps:12,highRisk:5,cargo:'4 240 t',reliability:91,trend:[44,51,49,58,63,61,68,72,70,77,81,84] },
  { id:'astrakhan-aktau',from:'Astrakhan',to:'Aktau',countries:'RU ↔ KZ',voyages:91,duration:'41h 08m',delay:'1h 18m',aisGaps:11,highRisk:6,cargo:'3 480 t',reliability:86,trend:[38,42,39,46,53,49,51,58,56,61,65,68] },
]

const dataSources: DataSource[] = [
  { id:'kz-ais',name:'Kazakhstan AIS',type:'AIS',country:'Kazakhstan',status:'ONLINE',quality:99,coverage:'Northern / Central',latency:'8 sec',updated:'just now' },
  { id:'aktau-port',name:'Aktau Port',type:'PORT',country:'Kazakhstan',status:'ONLINE',quality:98,coverage:'Calls · Berths · Cargo',latency:'11 sec',updated:'8 sec ago' },
  { id:'baku-port',name:'Baku Port',type:'PORT',country:'Azerbaijan',status:'DEGRADED',quality:84,coverage:'Calls · Cargo · Berths partial',latency:'12 min',updated:'12 min ago' },
  { id:'tm-ais',name:'Turkmenistan AIS',type:'AIS',country:'Turkmenistan',status:'ONLINE',quality:93,coverage:'Eastern Caspian',latency:'22 sec',updated:'22 sec ago' },
  { id:'weather',name:'Caspian Weather',type:'WEATHER',country:'Regional',status:'ONLINE',quality:96,coverage:'Full region',latency:'2 min',updated:'1 min ago' },
  { id:'satellite',name:'Satellite Provider A',type:'ENVIRONMENT',country:'Regional',status:'ONLINE',quality:91,coverage:'Central / Southern',latency:'18 min',updated:'17 min ago' },
  { id:'ru-port',name:'Russia Port Adapter',type:'PORT',country:'Russia',status:'DEGRADED',quality:76,coverage:'Calls only',latency:'18 min',updated:'18 min ago' },
  { id:'ir-port',name:'Iran Port Adapter',type:'PORT',country:'Iran',status:'OFFLINE',quality:0,coverage:'Planned integration',latency:'—',updated:'No live feed' },
]

const searchItems: SearchItem[] = [
  { id:'CI-VESSEL-000184',kind:'VESSEL',title:'CASPIAN STAR',subtitle:'IMO 9384721 · MMSI 436000118',meta:'Baku → Aktau · Risk 91',href:'/app/vessels/caspian-star',status:'CRITICAL',aliases:['CASPIAN STAR II','vessel_184','ship_782'] },
  { id:'CI-VESSEL-000241',kind:'VESSEL',title:'TURAN',subtitle:'IMO 9271156 · MMSI 434120774',meta:'Turkmenbashi → Baku · Risk 84',href:'/app/caspian/risk',status:'HIGH' },
  { id:'CI-VESSEL-000093',kind:'VESSEL',title:'VOLGA MARINE',subtitle:'IMO 9142202 · MMSI 273451810',meta:'Astrakhan → Aktau · Risk 78',href:'/app/vessels/volga-marine',status:'HIGH' },
  { id:'CI-COMPANY-00421',kind:'COMPANY',title:'CASPIAN SHIPPING LTD',subtitle:'Resolved from 3 source names',meta:'6 vessels · 5 ports · HIGH confidence',href:'/app/caspian/network',status:'VERIFIED',aliases:['Caspian Shipping Limited','Caspian Shipping Ltd.'] },
  { id:'PORT-AKTAU',kind:'PORT',title:'Aktau',subtitle:'Kazakhstan · UTC+5',meta:'Load 68% · 7 incoming',href:'/app/ports/aktau',status:'CONNECTED' },
  { id:'PORT-BAKU',kind:'PORT',title:'Baku',subtitle:'Azerbaijan · UTC+4',meta:'Load 74% · source degraded',href:'/app/ports/baku',status:'DEGRADED' },
  { id:'PORT-TURKMENBASHI',kind:'PORT',title:'Turkmenbashi',subtitle:'Turkmenistan · UTC+5',meta:'Load 42% · 6 incoming',href:'/app/ports/turkmenbashi',status:'CONNECTED' },
  { id:'VOY-2026-143',kind:'VOYAGE',title:'Voyage #143',subtitle:'CASPIAN STAR · Baku → Aktau',meta:'ETA 15:05 · Risk 91',href:'/app/voyages/voy-001/intelligence',status:'IN PROGRESS' },
  { id:'EV-2802',kind:'EVENT',title:'AIS gap · CASPIAN STAR',subtitle:'3h 15m · Central Caspian',meta:'10 Aug 2026 · resolved',href:'/app/events',status:'HIGH' },
  { id:'CI-2026-00984',kind:'CASE',title:'Regional Investigation',subtitle:'CASPIAN STAR · Baku → Aktau',meta:'13 evidence items · 3 jurisdictions',href:'/app/investigations/CI-2026-00984',status:'OPEN' },
  { id:'ENV-2026-00142',kind:'ENVIRONMENT',title:'Possible oil pollution',subtitle:'Central Caspian · 3.4 km²',meta:'Confidence 87% · under review',href:'/app/environment/events/ENV-2026-00142',status:'UNDER REVIEW' },
  { id:'CARGO-BAK-AKT-143',kind:'CARGO',title:'Steel cargo · 5,000 t',subtitle:'Baku declaration → Aktau verification',meta:'Verified 4,920 t · within tolerance',href:'/app/caspian/verification',status:'VERIFIED' },
]

const crossPortFallback: CrossPortData = {
  voyage_id:'VOY-2026-143',global_vessel_id:'CI-VESSEL-000184',vessel_name:'CASPIAN STAR',origin_port_id:'baku',destination_port_id:'aktau',
  departure:{port_id:'baku',observed_at:'2026-08-10T04:02:00Z',cargo_t:5000,draught_m:5.2,document_ids:['DECL-BAK-143'],status:'REPORTED',source_ids:['source-baku-port']},
  arrival:{port_id:'aktau',observed_at:'2026-08-11T10:18:00Z',cargo_t:4920,draught_m:5.1,document_ids:['VERIFY-AKT-88412'],status:'VERIFIED',source_ids:['source-aktau-port']},
  comparisons:[
    {field_name:'cargo_t',departure_value:5000,arrival_value:4920,difference:-80,unit:'t',status:'WITHIN_TOLERANCE',explanation:'Допустимая разница 1.6%; обе записи сохранены.',evidence_ids:['PROV-CARGO-BAKU-001','PROV-CARGO-AKTAU-001']},
    {field_name:'draught_m',departure_value:5.2,arrival_value:5.1,difference:-.1,unit:'m',status:'WITHIN_TOLERANCE',explanation:'Изменение остаётся в пределах настроенного допуска рейса.',evidence_ids:['PROV-DRAUGHT-BAKU-001','PROV-DRAUGHT-AKTAU-001']},
    {field_name:'documents',departure_value:'DECL-BAK-143',arrival_value:'VERIFY-AKT-88412',difference:null,unit:null,status:'WITHIN_TOLERANCE',explanation:'Shipper, consignee и cargo type совпадают.',evidence_ids:['DECL-BAK-143','VERIFY-AKT-88412']},
  ],overall_status:'WITHIN_TOLERANCE',next_voyage_id:'NET-VOY-002',
}

const graphFallback: RegionalGraphData = {
  evidence_grounded:true,
  nodes:[
    {id:'CI-COMPANY-00421',type:'COMPANY',label:'CASPIAN SHIPPING LTD',country:'Kazakhstan',risk_score:null},
    {id:'CI-VESSEL-000184',type:'VESSEL',label:'CASPIAN STAR',country:'Kazakhstan',risk_score:91},
    {id:'CI-VESSEL-000241',type:'VESSEL',label:'TURAN',country:'Turkmenistan',risk_score:84},
    {id:'baku',type:'PORT',label:'Baku',country:'Azerbaijan',risk_score:null},
    {id:'aktau',type:'PORT',label:'Aktau',country:'Kazakhstan',risk_score:null},
    {id:'turkmenbashi',type:'PORT',label:'Turkmenbashi',country:'Turkmenistan',risk_score:null},
    {id:'route-baku-aktau',type:'ROUTE',label:'Baku ↔ Aktau',country:null,risk_score:null},
  ],
  edges:[
    {id:'NEDGE-001',source:'CI-COMPANY-00421',target:'CI-VESSEL-000184',relationship:'OPERATES',weight:1,evidence_ids:['PROV-IDENTITY-001']},
    {id:'NEDGE-005',source:'CI-VESSEL-000184',target:'CI-VESSEL-000241',relationship:'ENCOUNTERED',weight:14,evidence_ids:['EN-884']},
    {id:'NEDGE-006',source:'CI-VESSEL-000184',target:'route-baku-aktau',relationship:'SAILED_ROUTE',weight:37,evidence_ids:['NET-VOY-001']},
  ],
}

const accessFallback: NetworkAccess = {
  user_id:'analyst_142',organization:{id:'org-regional-ci',name:'Caspian Intelligence Center'},role:'ANALYST',
  permissions:['network:read','identity:resolve','sensitive:read','audit:read'],
  data_scope:['region:caspian','ports:*','investigations:read'],
}

const auditFallback: NetworkAuditRow[] = [
  {timestamp:'2026-08-10T10:32:14Z',user:'analyst_142',organization:'Caspian Intelligence Center',action:'Viewed risk factors',resource:'CI-VESSEL-000184',outcome:'ALLOWED'},
  {timestamp:'2026-08-10T10:29:08Z',user:'dispatcher_aktau',organization:'Aktau Port',action:'Viewed Baku internal queue',resource:'PORT-BAKU',outcome:'DENIED'},
  {timestamp:'2026-08-10T10:24:51Z',user:'analyst_142',organization:'Caspian Intelligence Center',action:'Viewed investigation',resource:'CI-2026-00984',outcome:'ALLOWED'},
  {timestamp:'2026-08-10T10:19:37Z',user:'assistant/tool',organization:'Caspian Intelligence Center',action:'Regional vessel search',resource:'Baku ↔ Aktau',outcome:'ALLOWED'},
]

const kindLabels: Record<SearchKind,string> = {
  VESSEL:'Суда',COMPANY:'Компании',PORT:'Порты',VOYAGE:'Рейсы',EVENT:'События',
  CASE:'Расследования',ENVIRONMENT:'Экология',CARGO:'Грузы'
}

const kindIcons: Record<SearchKind, typeof Ship> = {
  VESSEL:Ship,COMPANY:Building2,PORT:Anchor,VOYAGE:Route,EVENT:Activity,
  CASE:FileSearch,ENVIRONMENT:Leaf,CARGO:Package
}

function authHeaders() {
  const token = localStorage.getItem('ci-access-token') || localStorage.getItem('access_token') || 'ci-demo-analyst'
  return { Authorization:`Bearer ${token}` }
}

function useNetworkResource<T>(endpoint: string, fallback: T, select?: (payload: unknown) => T) {
  const [data,setData] = useState<T>(fallback)
  const [source,setSource] = useState<'LIVE API'|'DEMO SNAPSHOT'>('DEMO SNAPSHOT')
  const [loading,setLoading] = useState(true)
  const reload = () => {
    setLoading(true)
    fetch(`${API_BASE}${endpoint}`,{ headers:authHeaders() })
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`HTTP ${response.status}`)))
      .then(payload => { setData(select ? select(payload) : payload as T); setSource('LIVE API') })
      .catch(() => { setData(fallback); setSource('DEMO SNAPSHOT') })
      .finally(() => setLoading(false))
  }
  useEffect(reload,[endpoint])
  return { data,source,loading,reload }
}

function normalizeRegionalSearch(payload: unknown): SearchItem[] {
  const groups=(payload as {groups?:Record<string,unknown[]>}).groups
  if(!groups)return searchItems
  const record=(value:unknown)=>value as Record<string,unknown>
  const values=(key:string)=>(Array.isArray(groups[key])?groups[key]:[]).map(record)
  const items:SearchItem[]=[]
  values('vessels').forEach(item=>items.push({
    id:String(item.id),kind:'VESSEL',title:String(item.name),
    subtitle:[item.imo&&`IMO ${item.imo}`,item.mmsi&&`MMSI ${item.mmsi}`].filter(Boolean).join(' · '),
    meta:'Global vessel identity',href:String(item.href||`/app/vessels/${item.legacy_vessel_id}`),status:'VERIFIED',
  }))
  values('companies').forEach(item=>items.push({id:String(item.id),kind:'COMPANY',title:String(item.name),subtitle:String(item.country||'Regional company'),meta:'Resolved company identity',href:'/app/caspian/network',status:'VERIFIED'}))
  values('ports').forEach(item=>items.push({id:String(item.id),kind:'PORT',title:String(item.name),subtitle:String(item.country||'Caspian port'),meta:'Port Registry',href:String(item.href||`/app/ports/${item.id}`),status:'REGISTERED'}))
  values('voyages').forEach(item=>items.push({id:String(item.id),kind:'VOYAGE',title:String(item.vessel_name||item.id),subtitle:`${String(item.origin_port_id||'—')} → ${String(item.destination_port_id||'—')}`,meta:String(item.status||'VOYAGE'),href:item.id==='NET-VOY-001'?'/app/caspian/verification':'/app/caspian/routes',status:String(item.status||'TRACKED')}))
  values('events').forEach(item=>items.push({id:String(item.id),kind:'EVENT',title:String(item.type||'Maritime event'),subtitle:String(item.vessel||item.route||''),meta:String(item.route||'Evidence-linked event'),href:'/app/events',status:'REVIEW'}))
  values('investigations').forEach(item=>items.push({id:String(item.id),kind:'CASE',title:String(item.title||item.id),subtitle:Array.isArray(item.ports)?item.ports.join(' → '):'Regional case',meta:'Investigation Case',href:String(item.href||`/app/investigations/${item.id}`),status:'OPEN'}))
  values('environmental_events').forEach(item=>items.push({id:String(item.id),kind:'ENVIRONMENT',title:String(item.type||'Environmental event'),subtitle:'Regional environmental intelligence',meta:'Evidence-linked observation',href:String(item.href||`/app/environment/events/${item.id}`),status:String(item.status||'REVIEW')}))
  values('cargo').forEach(item=>items.push({id:String(item.id),kind:'CARGO',title:`Cargo · ${Number(item.departure_cargo_t||0).toLocaleString('en-US')} t`,subtitle:`Departure ${item.departure_cargo_t} t → arrival ${item.arrival_cargo_t} t`,meta:'Cross-port verification',href:'/app/caspian/verification',status:String(item.status||'REVIEW')}))
  return items
}

function normalizeAudit(payload:unknown):NetworkAuditRow[]{
  const items=(payload as {items?:unknown[]}).items
  if(!Array.isArray(items))return auditFallback
  return items.map(entry=>{const item=entry as Record<string,unknown>;return {
    timestamp:String(item.timestamp||''),user:String(item.user_id||'—'),organization:String(item.organization_id||'—'),
    action:`${String(item.action||'VIEW')} ${String(item.resource_type||'RESOURCE').replaceAll('_',' ').toLowerCase()}`,
    resource:String(item.resource_id||'—'),outcome:String(item.outcome||'ALLOWED'),
  }})
}

function goAssistant(question: string, context: Record<string,unknown> = {}) {
  sessionStorage.setItem('ci-stage8-context',JSON.stringify({
    page:window.location.pathname,label:'Сеть Каспия',...context
  }))
  window.history.pushState({},'',`/app/assistant?q=${encodeURIComponent(question)}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

function SourceBadge({ source, loading }: { source: 'LIVE API'|'DEMO SNAPSHOT'; loading?: boolean }) {
  return <span className={`cn-source-badge ${source==='LIVE API'?'live':''}`}>
    <i/>{loading?'СИНХРОНИЗАЦИЯ':source === 'LIVE API' ? 'API ПОДКЛЮЧЁН' : 'ДЕМО-ДАННЫЕ'}
  </span>
}

function ScopeBadge({ compact=false }: { compact?: boolean }) {
  void compact
  return null
}

export function TopbarScopeIndicator({ navigate }: { navigate: Navigate }) {
  return <button className="cn-topbar-scope" onClick={()=>navigate('/app/caspian/scope')} title="Текущий контур доступа">
    <Globe2 size={15}/><span><small>Доступ</small><strong>Весь Каспий</strong></span><ChevronDown size={13}/>
  </button>
}

export function GlobalIdentityBadge({ vesselId, navigate }: { vesselId:string; navigate:Navigate }) {
  const identity = vesselId==='caspian-star' ? 'CI-VESSEL-000184'
    : vesselId==='volga-marine' ? 'CI-VESSEL-000093'
    : `CI-VESSEL-${String(Math.abs([...vesselId].reduce((sum,char)=>sum+char.charCodeAt(0),0))).padStart(6,'0')}`
  return <button className="cn-global-id" onClick={()=>navigate(`/app/caspian/search?q=${encodeURIComponent(identity)}`)} title="Глобальный идентификатор судна">
    <Globe2 size={12}/>{identity}<BadgeCheck size={12}/>
  </button>
}

function NetworkHeader({ eyebrow, title, description, actions, source, loading }: {
  eyebrow:string; title:string; description:string; actions?:ReactNode;
  source?:'LIVE API'|'DEMO SNAPSHOT'; loading?:boolean
}) {
  return <div className="cn-page-header">
    <div><span className="page-eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>
    <div className="cn-page-actions">{source&&<SourceBadge source={source} loading={loading}/>} {actions}</div>
  </div>
}

const moduleNav = [
  ['/app/caspian','Обзор',Globe2],['/app/ports','Порты',Anchor],['/app/caspian/risk','Риски',ShieldAlert],
  ['/app/caspian/routes','Маршруты',Route],['/app/caspian/verification','Верификация',GitCompareArrows],
  ['/app/caspian/data-health','Качество данных',Database],['/app/caspian/network','Сеть',Network]
] as const

function NetworkModuleNav({ navigate, active }: { navigate:Navigate; active:string }) {
  return <nav className="cn-module-nav">{moduleNav.map(([path,label,Icon])=><button key={path} className={active===path?'active':''} onClick={()=>navigate(path)}><Icon size={15}/>{label}</button>)}</nav>
}

function MetricCard({ label, value, detail, icon, tone='neutral' }: { label:string; value:string; detail:string; icon:ReactNode; tone?:string }) {
  return <article className={`cn-metric-card ${tone}`}><div>{icon}</div><span>{label}</span><strong>{value}</strong><small>{detail}</small></article>
}

function riskBandLabel(value:string) {
  return ({CRITICAL:'КРИТИЧЕСКИЙ',HIGH:'ВЫСОКИЙ',MODERATE:'УМЕРЕННЫЙ',LOW:'НИЗКИЙ'} as Record<string,string>)[value] || value
}

function RegionalMap({ navigate, compact=false, coverage=false }: { navigate:Navigate; compact?:boolean; coverage?:boolean }) {
  const [layer,setLayer] = useState<'TRAFFIC'|'RISK'|'COVERAGE'>(coverage?'COVERAGE':'TRAFFIC')
  const visiblePorts = compact ? networkPorts.filter(port=>['aktau','baku','turkmenbashi','kuryk'].includes(port.id)) : networkPorts
  const routePairs=[['baku','aktau'],['aktau','turkmenbashi'],['alat','kuryk'],['astrakhan','aktau'],['anzali','baku']] as const
  const routes:RealMapLine[]=routePairs.flatMap(([fromId,toId])=>{
    const from=networkPorts.find(port=>port.id===fromId);const to=networkPorts.find(port=>port.id===toId)
    return from&&to?[{id:`${fromId}-${toId}`,coordinates:[[from.longitude,from.latitude],[to.longitude,to.latitude]],label:`${from.name} — ${to.name}`,color:fromId==='baku'&&toId==='aktau'?'#18796e':'#5e928a',dashed:true}]:[]
  })
  const vesselPoints=layer==='COVERAGE'?[]:[
    {id:'caspian-star',name:'CASPIAN STAR',longitude:50.74,latitude:42.31,course:47,risk:91,riskLevel:'CRITICAL',detail:'Baku → Aktau'},
    {id:'turan',name:'TURAN',longitude:50.61,latitude:42.04,course:225,risk:84,riskLevel:'HIGH',detail:'Encounter context'},
    {id:'regional-03',name:'VOLGA MARINE',longitude:48.91,latitude:43.16,course:158,risk:layer==='RISK'?78:undefined,riskLevel:layer==='RISK'?'HIGH':undefined},
    {id:'regional-04',name:'KHAZAR WAVE',longitude:50.21,latitude:40.82,course:344,risk:layer==='RISK'?68:undefined,riskLevel:layer==='RISK'?'HIGH':undefined},
    {id:'regional-05',name:'ANZALI TRADER',longitude:50.51,latitude:38.72,course:352,risk:layer==='RISK'?31:undefined,riskLevel:layer==='RISK'?'MODERATE':undefined},
  ]
  const areas=layer==='COVERAGE'?[circleArea('coverage-ais',50.3,43.4,245,'coverage-ais','AIS coverage'),circleArea('coverage-environment',51.1,40.2,225,'coverage-environment','Environmental coverage')]:layer==='RISK'?[circleArea('risk-central',50.62,42.15,115,'risk','Central risk context'),circleArea('risk-south',50.25,40.6,78,'risk','Southern risk context')]:[]
  return <div className={`cn-regional-map ${compact?'compact':''}`}>
    <div className="cn-map-toolbar">
      <span><Radio size={14}/><strong>{layer==='COVERAGE'?'ПОКРЫТИЕ ДАННЫХ':'РЕГИОН В РЕАЛЬНОМ ВРЕМЕНИ'}</strong></span>
      <div>{(['TRAFFIC','RISK','COVERAGE'] as const).map(item=><button key={item} className={layer===item?'active':''} onClick={()=>setLayer(item)}>{item==='TRAFFIC'?'ДВИЖЕНИЕ':item==='RISK'?'РИСК':'ПОКРЫТИЕ'}</button>)}</div>
    </div>
    <div className="cn-map-stage">
      <RealCaspianMap
        compact
        ariaLabel="Реальная региональная карта Каспия"
        ports={visiblePorts.map(port=>({id:port.id,name:port.name,longitude:port.longitude,latitude:port.latitude,status:port.integration,detail:layer==='COVERAGE'?`${port.quality}% quality`:`Load ${port.load}%`,color:port.integration==='CONNECTED'?'#227a6f':port.integration==='PARTIAL'?'#ca8a35':'#8c9894'}))}
        vessels={vesselPoints}
        routes={routes}
        areas={areas}
        environmentalEvents={layer==='COVERAGE'?[]:[{id:'ENV-2026-00142',title:'ENV-142',longitude:50.57,latitude:42.10,detail:'Environmental event under review'}]}
        onPortSelect={id=>navigate(`/app/ports/${id}`)}
        onVesselSelect={id=>id==='caspian-star'?navigate('/app/vessels/caspian-star'):navigate('/app/caspian/risk')}
        onEnvironmentalSelect={id=>navigate(`/app/environment/events/${id}`)}
      />
      {layer==='COVERAGE'&&<div className="cn-coverage-legend"><span><i className="ais"/>Стабильный AIS</span><span><i className="environmental"/>Экология</span><span><i className="port"/>Интеграция портов</span></div>}
    </div>
  </div>
}

function LegacyRegionalMap({ navigate, compact=false, coverage=false }: { navigate:Navigate; compact?:boolean; coverage?:boolean }) {
  const [layer,setLayer] = useState<'TRAFFIC'|'RISK'|'COVERAGE'>(coverage?'COVERAGE':'TRAFFIC')
  const visiblePorts = compact ? networkPorts.filter(port=>['aktau','baku','turkmenbashi','kuryk'].includes(port.id)) : networkPorts
  return <div className={`cn-regional-map ${compact?'compact':''}`}>
    <div className="cn-map-toolbar">
      <span><Radio size={14}/><strong>{layer==='COVERAGE'?'DATA COVERAGE':'REGIONAL LIVE'}</strong></span>
      <div>{(['TRAFFIC','RISK','COVERAGE'] as const).map(item=><button key={item} className={layer===item?'active':''} onClick={()=>setLayer(item)}>{item}</button>)}</div>
    </div>
    <div className="cn-map-stage">
      <svg className="cn-map-base" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <defs><linearGradient id="cnSea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#dceae7"/><stop offset="1" stopColor="#c9dfdc"/></linearGradient></defs>
        <path className="cn-sea-shape" d="M43,0 C58,2 64,12 61,22 C59,30 54,34 59,43 C66,55 83,62 79,76 C77,85 67,92 59,99 L33,99 C25,94 27,84 22,76 C16,66 15,57 23,48 C31,39 32,31 27,22 C22,13 28,3 43,0 Z" fill="url(#cnSea)"/>
        <g className="cn-map-grid"><path d="M0 20H100M0 40H100M0 60H100M0 80H100M20 0V100M40 0V100M60 0V100M80 0V100"/></g>
        <g className="cn-route-lines">
          <path className="primary" d="M35 60 C44 48,56 37,72 28"/>
          <path d="M72 28 C78 39,81 53,77 64"/>
          <path d="M37 68 C50 59,61 48,70 37"/>
          <path d="M36 5 C40 14,51 21,72 28"/>
          <path d="M39 92 C38 80,36 69,35 60"/>
        </g>
        {layer==='COVERAGE'&&<g className="cn-coverage-zones"><ellipse cx="53" cy="28" rx="25" ry="28" className="ais"/><ellipse cx="54" cy="65" rx="32" ry="30" className="environmental"/><circle cx="72" cy="28" r="11" className="port"/><circle cx="35" cy="60" r="12" className="port"/><circle cx="77" cy="64" r="10" className="port"/></g>}
      </svg>
      <span className="cn-country-label ru">РОССИЯ</span><span className="cn-country-label kz">КАЗАХСТАН</span>
      <span className="cn-country-label az">АЗЕРБАЙДЖАН</span><span className="cn-country-label tm">ТУРКМЕНИСТАН</span><span className="cn-country-label ir">ИРАН</span>
      {visiblePorts.map(port=><button key={port.id} className={`cn-map-port ${port.integration.toLowerCase()}`} style={{left:`${port.x}%`,top:`${port.y}%`}} onClick={()=>navigate(`/app/ports/${port.id}`)}>
        <i/><label><strong>{port.name}</strong><span>{layer==='COVERAGE'?`${port.quality}% quality`:`Load ${port.load}%`}</span></label>
      </button>)}
      {layer!=='COVERAGE'&&<>
        <button className="cn-map-vessel critical" style={{left:'59%',top:'34%'}} onClick={()=>navigate('/app/vessels/caspian-star')}><Navigation size={12} fill="currentColor"/><label>CASPIAN STAR <b>91</b></label></button>
        <button className="cn-map-vessel high" style={{left:'50%',top:'49%'}}><Navigation size={11} fill="currentColor"/><label>TURAN <b>84</b></label></button>
        <i className="cn-vessel-dot d1"/><i className="cn-vessel-dot d2"/><i className="cn-vessel-dot d3"/><i className="cn-vessel-dot d4"/><i className="cn-vessel-dot d5"/>
        {layer==='RISK'&&<><span className="cn-risk-zone rz1"/><span className="cn-risk-zone rz2"/></>}
        <button className="cn-environment-marker" onClick={()=>navigate('/app/environment/events/ENV-2026-00142')}><Leaf size={13}/><span>ENV-142</span></button>
      </>}
      {layer==='COVERAGE'&&<div className="cn-coverage-legend"><span><i className="ais"/>Стабильный AIS</span><span><i className="environmental"/>Экологические данные</span><span><i className="port"/>Интеграция портов</span></div>}
      <div className="cn-map-scale">50 km</div>
    </div>
  </div>
}

const overviewFallback = { vesselsActive:482,voyagesToday:127,portCalls:84,highRisk:11,aisGaps:23,encounters:17,environmentalEvents:2 }

export function CaspianNetworkDashboard({ navigate }: { navigate:Navigate }) {
  const [detailsOpen,setDetailsOpen]=useState(false)
  const {data,source,loading,reload}=useNetworkResource('/network/overview',overviewFallback,(payload)=>{
    const raw=(payload as {data?:unknown}).data||payload as unknown
    const envelope=raw as Partial<typeof overviewFallback>&{metrics?:Record<string,number>}
    const value={...envelope,...(envelope.metrics||{})} as Partial<typeof overviewFallback>&Record<string,number>
    return {
      vesselsActive:value.vesselsActive??(value as {vessels_active?:number}).vessels_active??482,
      voyagesToday:value.voyagesToday??(value as {voyages_today?:number}).voyages_today??127,
      portCalls:value.portCalls??(value as {port_calls?:number}).port_calls??84,
      highRisk:value.highRisk??(value as {high_risk?:number}).high_risk??11,
      aisGaps:value.aisGaps??(value as {ais_gaps?:number}).ais_gaps??23,
      encounters:value.encounters??17,
      environmentalEvents:value.environmentalEvents??(value as {environmental_events?:number}).environmental_events??2,
    }
  })
  return <div className="content-page cn-page">
    <NetworkHeader eyebrow="ЕДИНАЯ СЕТЬ КАСПИЯ · РЕГИОНАЛЬНЫЙ ЦЕНТР" title="Движение по Каспию" description="Единая операционная картина морской активности пяти прибрежных стран." source={source} loading={loading} actions={<button className="secondary-button" onClick={reload}><RefreshCw size={15}/>Обновить</button>}/>
    <NetworkModuleNav navigate={navigate} active="/app/caspian"/>
    <section className="cn-command-strip"><div><span className="cn-live-pulse"/><strong>РЕГИОНАЛЬНЫЙ ПОТОК АКТИВЕН</strong><small>9 портов · 8 источников · 5 стран</small></div><div className="cn-country-pills"><span>KZ <b>142</b></span><span>AZ <b>119</b></span><span>TM <b>74</b></span><span>RU <b>83</b></span><span>IR <b>64</b></span></div></section>
    <div className="cn-metrics-grid cn-primary-metrics">
      <MetricCard label="АКТИВНЫЕ СУДА" value={String(data.vesselsActive)} detail="+18 за 24 часа" icon={<Ship size={18}/>} tone="teal"/>
      <MetricCard label="ЗАХОДЫ В ПОРТ" value={String(data.portCalls)} detail="9 портов в сети" icon={<Anchor size={18}/>}/>
      <MetricCard label="ВЫСОКИЙ РИСК" value={String(data.highRisk)} detail="3 требуют проверки" icon={<ShieldAlert size={18}/>} tone="danger"/>
      <MetricCard label="ЭКОЛОГИЯ" value={String(data.environmentalEvents)} detail="1 на проверке" icon={<Leaf size={18}/>} tone="green"/>
    </div>
    <div className="cn-secondary-metrics" aria-label="Дополнительные показатели"><span><Route size={14}/><b>{data.voyagesToday}</b> рейсов сегодня</span><span><WifiOff size={14}/><b>{data.aisGaps}</b> пропуска AIS</span><span><Users size={14}/><b>{data.encounters}</b> встреч</span></div>
    <div className="cn-dashboard-main">
      <section className="cn-panel cn-map-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">КАРТА ПОРТОВ</span><h2>Региональная обстановка</h2></div><button className="text-button" onClick={()=>navigate('/app/map')}>Открыть основную карту <ArrowRight size={14}/></button></div><RegionalMap navigate={navigate}/></section>
      <aside className="cn-panel cn-watch-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">ОЧЕРЕДЬ ВНИМАНИЯ</span><h2>Требуют внимания</h2></div><button onClick={()=>navigate('/app/caspian/risk')}>Все 11</button></div>
        <div className="cn-watch-list">{riskRows.slice(0,3).map((row,index)=><button key={row.id} onClick={()=>index===0?navigate('/app/vessels/caspian-star?tab=risk'):navigate('/app/caspian/risk')}><em>{index+1}</em><span><strong>{row.name}</strong><small>{operationalText(row.route)}</small><i>{row.factors.slice(0,2).map(operationalText).join(' · ')}</i></span><b className={row.band.toLowerCase()}>{row.score}<small>{riskBandLabel(row.band)}</small></b></button>)}</div>
        <div className="cn-assistant-prompt"><Sparkles size={17}/><span><strong>Региональный помощник</strong><small>Ответ строится по данным модулей и вашей области доступа.</small></span><button onClick={()=>goAssistant('Какие суда требуют наибольшего внимания во всем Каспии?',{label:'Движение по Каспию'})}>Спросить <ArrowRight size={13}/></button></div>
      </aside>
    </div>
    <div className="cn-dashboard-disclosure"><button className="secondary-button" aria-expanded={detailsOpen} onClick={()=>setDetailsOpen(value=>!value)}><BarChart3 size={15}/>{detailsOpen?'Скрыть подробную аналитику':'Показать подробную аналитику'}<ChevronDown size={15}/></button><span>Порты, маршрут, качество данных и дополнительные показатели</span></div>
    {detailsOpen&&<div className="cn-dashboard-details"><section className="cn-port-pulse"><div className="cn-section-title"><div><span className="page-eyebrow">АНАЛИТИКА ПОРТОВ</span><h2>Пульс ключевых портов</h2></div><button className="secondary-button" onClick={()=>navigate('/app/ports')}>Реестр портов <ArrowRight size={14}/></button></div><div className="cn-port-pulse-grid">{networkPorts.filter(port=>['aktau','baku','turkmenbashi','kuryk'].includes(port.id)).map(port=><button key={port.id} onClick={()=>navigate(`/app/ports/${port.id}`)}><div><span className={`cn-flag flag-${port.countryCode.toLowerCase()}`}>{port.countryCode}</span><span><strong>{port.name}</strong><small>{port.localTime} местное · {port.integration==='CONNECTED'?'подключён':port.integration==='PARTIAL'?'частично':'планируется'}</small></span><ChevronRight size={15}/></div><div className="cn-port-load"><span><i style={{width:`${port.load}%`}}/></span><strong>{port.load}%</strong></div><footer><span>{port.vessels} судов</span><span>{port.incoming} прибывают</span><span>{port.freeBerths}/{port.berths} свободно</span></footer></button>)}</div></section>
    <div className="cn-dashboard-lower">
      <section className="cn-panel cn-route-spotlight"><div className="cn-panel-head"><div><span className="page-eyebrow">АНАЛИТИКА МАРШРУТА</span><h2>Баку ↔ Актау</h2></div><span className="cn-reliability"><BadgeCheck size={14}/>достоверность 94%</span></div><div className="cn-route-lineage"><button onClick={()=>navigate('/app/ports/baku')}><i>Б</i><span><strong>Баку</strong><small>UTC+4</small></span></button><div><span/><Navigation size={15}/><em>387 км</em></div><button onClick={()=>navigate('/app/ports/aktau')}><i>А</i><span><strong>Актау</strong><small>UTC+5</small></span></button></div><div className="cn-mini-metrics"><span><small>30 дней</small><strong>284 рейса</strong></span><span><small>Средняя длительность</small><strong>29 ч 14 мин</strong></span><span><small>Средняя задержка</small><strong>42 мин</strong></span><span><small>Пропуски AIS</small><strong>17</strong></span></div><button className="cn-wide-link" onClick={()=>navigate('/app/caspian/routes')}>Открыть аналитику маршрута <ArrowRight size={14}/></button></section>
      <section className="cn-panel cn-health-brief"><div className="cn-panel-head"><div><span className="page-eyebrow">КАЧЕСТВО ДАННЫХ</span><h2>Качество сети</h2></div><button onClick={()=>navigate('/app/caspian/data-health')}>Подробнее</button></div><div className="cn-health-score"><div><strong>92</strong><span>/ 100</span></div><span><b>Работает</b><small>6 подключено · 1 нестабильно · 1 планируется</small></span></div>{dataSources.slice(0,4).map(sourceItem=><div className="cn-health-row" key={sourceItem.id}><i className={sourceItem.status.toLowerCase()}/><span><strong>{sourceItem.name}</strong><small>{sourceItem.coverage}</small></span><em>{sourceItem.latency}</em></div>)}</section>
    </div></div>}
  </div>
}

function normalizePorts(payload: unknown): NetworkPort[] {
  const raw=(payload as {items?:unknown[];ports?:unknown[];data?:{items?:unknown[]}})
  const items=raw.items||raw.ports||raw.data?.items
  if(!Array.isArray(items)||!items.length)return networkPorts
  return items.map((item,index)=>{
    const value=item as Record<string,unknown>
    const fallback=networkPorts.find(port=>port.id===value.id||port.id===value.port_id)||networkPorts[index%networkPorts.length]
    const coordinates=(value.coordinates&&typeof value.coordinates==='object'?value.coordinates:{} as Record<string,unknown>) as Record<string,unknown>
    return {
      ...fallback,
      id:String(value.id||value.port_id||fallback.id),name:String(value.name||fallback.name),country:String(value.country||fallback.country),
      latitude:Number(value.latitude??coordinates.latitude??fallback.latitude),longitude:Number(value.longitude??coordinates.longitude??fallback.longitude),
      load:Number(value.load_percent??value.load??fallback.load),vessels:Number(value.vessels??value.active_vessels??fallback.vessels),
      incoming:Number(value.arrivals??value.incoming??fallback.incoming),integration:(()=>{const integration=value.integration_status;if(typeof integration==='string')return integration.toUpperCase() as IntegrationState;if(integration&&typeof integration==='object'){const states=Object.values(integration as Record<string,unknown>).filter(item=>typeof item==='string');return states.includes('NOT_CONNECTED')?'PLANNED':states.includes('PARTIAL')?'PARTIAL':'CONNECTED'}return fallback.integration})(),
      quality:Number(value.quality??value.data_quality??fallback.quality),updated:String(value.updated_at||fallback.updated),
    }
  })
}

export function CaspianPortRegistryPage({ navigate }: { navigate:Navigate }) {
  const {data,source,loading,reload}=useNetworkResource('/network/ports',networkPorts,normalizePorts)
  const [query,setQuery]=useState('')
  const [country,setCountry]=useState('ALL')
  const [integration,setIntegration]=useState('ALL')
  const countries=['ALL',...new Set(data.map(port=>port.country))]
  const filtered=data.filter(port=>(country==='ALL'||port.country===country)&&(integration==='ALL'||port.integration===integration)&&`${port.name} ${port.country} ${port.capabilities.join(' ')}`.toLowerCase().includes(query.toLowerCase()))
  const grouped=useMemo(()=>countries.slice(1).map(name=>({name,items:filtered.filter(port=>port.country===name)})).filter(group=>group.items.length),[filtered,countries.join('|')])
  return <div className="content-page cn-page">
    <NetworkHeader eyebrow="CASPIAN PORT REGISTRY" title="Порты Каспия" description="Единый конфигурационный реестр портов, возможностей и статуса интеграций." source={source} loading={loading} actions={<button className="secondary-button" onClick={reload}><RefreshCw size={15}/>Синхронизировать</button>}/>
    <NetworkModuleNav navigate={navigate} active="/app/ports"/>
    <div className="cn-registry-summary"><span><strong>{data.length}</strong><small>портов в реестре</small></span><span><strong>5</strong><small>стран</small></span><span><strong>{data.filter(port=>port.integration==='CONNECTED').length}</strong><small>подключено</small></span><span><strong>{data.reduce((sum,port)=>sum+port.berths,0)}</strong><small>причалов</small></span><span><strong>{data.reduce((sum,port)=>sum+port.vessels,0)}</strong><small>судов в акваториях</small></span></div>
    <div className="cn-registry-toolbar"><div className="cn-search-field"><Search size={16}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Порт, страна или возможность"/><kbd>9 ПОРТОВ</kbd></div><label>Страна<select value={country} onChange={event=>setCountry(event.target.value)}>{countries.map(item=><option key={item}>{item}</option>)}</select></label><label>Интеграция<select value={integration} onChange={event=>setIntegration(event.target.value)}><option value="ALL">ВСЕ</option><option value="CONNECTED">ПОДКЛЮЧЕНО</option><option value="PARTIAL">ЧАСТИЧНО</option><option value="PLANNED">ЗАПЛАНИРОВАНО</option></select></label><button className="secondary-button"><Filter size={15}/>Фильтры</button></div>
    <div className="cn-port-registry-layout">
      <section className="cn-panel cn-registry-map"><div className="cn-panel-head"><div><span className="page-eyebrow">РЕГИОНАЛЬНОЕ РАСПРЕДЕЛЕНИЕ</span><h2>9 портовых узлов</h2></div><span className="cn-map-key"><i/>Подключено <i/>Частично <i/>Запланировано</span></div><RegionalMap navigate={navigate} compact/></section>
      <section className="cn-port-groups">{grouped.map(group=><div className="cn-port-country" key={group.name}><header><span className={`cn-flag flag-${group.items[0].countryCode.toLowerCase()}`}>{group.items[0].countryCode}</span><div><strong>{operationalText(group.name)}</strong><small>{group.items.length} {group.items.length===1?'порт':'порта'} · {group.items.reduce((sum,port)=>sum+port.vessels,0)} судов</small></div><span>{group.items.filter(port=>port.integration==='CONNECTED').length}/{group.items.length} подключено</span></header>{group.items.map(port=><button className="cn-port-registry-row" key={port.id} onClick={()=>navigate(`/app/ports/${port.id}`)}><span className="cn-port-anchor"><Anchor size={17}/></span><span><strong>{operationalText(port.name)}</strong><small>{operationalText(port.portType)} · {port.timezone}</small></span><div className="cn-port-row-load"><span><i style={{width:`${port.load}%`}}/></span><b>{port.load}%</b><small>ЗАГРУЗКА</small></div><em className={`cn-integration ${port.integration.toLowerCase()}`}><i/>{integrationLabel(port.integration)}</em><ChevronRight size={15}/></button>)}</div>)}</section>
    </div>
  </div>
}

const portTabs=['overview','arrivals','berths','queue','forecast','configuration','integration'] as const
type PortTab=typeof portTabs[number]
const portTabLabels:Record<PortTab,string>={overview:'Обзор',arrivals:'Прибытия',berths:'Причалы',queue:'Очередь',forecast:'Прогноз',configuration:'Конфигурация',integration:'Интеграция'}

const portArrivals=[
  {id:'PC-AKT-143',vessel:'CASPIAN STAR',globalId:'CI-VESSEL-000184',from:'Baku',eta:'15:05',risk:91,cargo:'Steel · 5,000 t',status:'PRE-ARRIVAL'},
  {id:'PC-AKT-144',vessel:'VOLGA MARINE',globalId:'CI-VESSEL-000093',from:'Astrakhan',eta:'17:40',risk:78,cargo:'Grain · 3,200 t',status:'APPROACHING'},
  {id:'PC-AKT-145',vessel:'KHAZAR WAVE',globalId:'CI-VESSEL-000342',from:'Baku',eta:'20:15',risk:68,cargo:'Oil products · reported',status:'SCHEDULED'},
  {id:'PC-AKT-146',vessel:'BAKU EXPRESS',globalId:'CI-VESSEL-000415',from:'Alat',eta:'23:25',risk:54,cargo:'Ro-Ro · 74 units',status:'SCHEDULED'},
]

function BerthGrid({ port }: { port:NetworkPort }) {
  const occupied=Math.max(1,port.berths-port.freeBerths)
  return <div className="cn-berth-grid">{Array.from({length:port.berths},(_,index)=>{
    const busy=index<occupied
    const alert=index===4&&port.id==='aktau'
    return <article key={index} className={`${busy?'occupied':'available'} ${alert?'attention':''}`}><header><span>BERTH #{index+1}</span><em>{alert?'RESERVED':busy?'OCCUPIED':'AVAILABLE'}</em></header><div><Anchor size={18}/><strong>{alert?'CASPIAN STAR':busy?['KAZSEA 7','VOLGA LINE','AKTAU MERCHANT','TURAN'][index%4]:'Ready for assignment'}</strong><small>{alert?'ETA 15:05 · HIGH attention':busy?'Service in progress':'No restrictions'}</small></div><footer><span>{index%3===0?'General cargo':index%3===1?'Ro-Ro':'Bulk'}</span><span>Max 7.2 m</span></footer></article>})}</div>
}

function PortOverviewTab({ port,navigate }: { port:NetworkPort;navigate:Navigate }) {
  return <>
    <div className="cn-port-detail-grid"><section className="cn-panel cn-port-intel"><div className="cn-panel-head"><div><span className="page-eyebrow">АНАЛИТИКА ПОРТА</span><h2>Операционная картина</h2></div><span className="cn-local-time"><Clock3 size={14}/>{port.localTime} местное</span></div><div className="cn-port-kpis"><span><small>Среднее ожидание</small><strong>{port.waiting}</strong><em>−12 мин за 7 дней</em></span><span><small>Средняя обработка</small><strong>{port.service}</strong><em>стабильно</em></span><span><small>Загрузка порта</small><strong>{port.load}%</strong><em>{port.load>70?'повышенная':'нормальная'}</em></span><span><small>Прибывают</small><strong>{port.incoming}</strong><em>следующие 12 ч</em></span><span><small>Прибытия высокого риска</small><strong>{port.highRisk}</strong><em>нужна проверка</em></span></div><div className="cn-load-forecast"><header><span><strong>Прогноз загрузки · следующие 12 часов</strong><small>ETA + очередь + обработка у причала</small></span><em>Пик 82% · 19:00</em></header><div className="cn-forecast-bars">{[54,58,63,68,72,79,82,78,70,64,59,55].map((value,index)=><span key={index}><i style={{height:`${value}%`}} className={value>=80?'peak':''}/><small>{index%2===0?`${15+index}:00`:''}</small></span>)}</div></div></section><section className="cn-panel cn-port-map-detail"><div className="cn-panel-head"><div><span className="page-eyebrow">РАЙОН ПОДХОДА</span><h2>Акватория {operationalText(port.name)}</h2></div><Layers3 size={16}/></div><div className="cn-harbor-map"><span className="cn-harbor-shore"/><i className="cn-harbor-route r1"/><i className="cn-harbor-route r2"/><span className="cn-harbor-berth b1">#1</span><span className="cn-harbor-berth b2">#2</span><span className="cn-harbor-berth b3">#5</span><button className="cn-harbor-vessel"><Navigation size={13}/><span>CASPIAN STAR<small>ETA 15:05</small></span></button><em>Якорная стоянка A</em></div></section></div>
    <div className="cn-port-overview-lower"><section className="cn-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">БЛИЖАЙШИЕ ПРИБЫТИЯ</span><h2>Ближайшие суда</h2></div><button onClick={()=>navigate(`/app/ports/${port.id}/arrivals`)}>Все {port.incoming}</button></div><div className="cn-compact-arrivals">{portArrivals.slice(0,3).map(item=><button key={item.id} onClick={()=>item.vessel==='CASPIAN STAR'&&navigate('/app/voyages/voy-001/intelligence')}><span className="cn-vessel-icon"><Ship size={16}/></span><span><strong>{item.vessel}</strong><small>{operationalText(item.from)} → {operationalText(port.name)} · {item.globalId}</small></span><time>{item.eta}<small>МЕСТНОЕ ETA</small></time><b className={item.risk>=75?'critical':'high'}>{item.risk}</b><ChevronRight size={14}/></button>)}</div></section><section className="cn-panel cn-port-capabilities"><div className="cn-panel-head"><div><span className="page-eyebrow">КОНФИГУРАЦИЯ ПОРТА</span><h2>Возможности</h2></div><Settings2 size={17}/></div><div>{port.capabilities.map(item=><span key={item}><Check size={12}/>{operationalText(item)}</span>)}</div><footer><span>{port.berths} причалов</span><span>Макс. осадка 7,2 м</span><span>Работа 24/7</span></footer></section><section className="cn-panel cn-port-source"><div className="cn-panel-head"><div><span className="page-eyebrow">СТАТУС ИНТЕГРАЦИИ</span><h2>Доступность данных</h2></div><em className={`cn-integration ${port.integration.toLowerCase()}`}><i/>{integrationLabel(port.integration)}</em></div>{['AIS','Заходы в порт','Причалы','Груз','Документы'].map((item,index)=><div key={item}><span>{item}</span>{index<(port.integration==='CONNECTED'?4:port.integration==='PARTIAL'?3:1)?<CircleCheck size={14}/>:index===4&&port.integration==='CONNECTED'?<TriangleAlert size={14}/>:<X size={14}/>}</div>)}<button className="cn-wide-link" onClick={()=>navigate(`/app/ports/${port.id}/integration`)}>Происхождение данных и адаптер <ArrowRight size={14}/></button></section></div>
  </>
}

function PortArrivalsTab({port,navigate}:{port:NetworkPort;navigate:Navigate}) {
  return <section className="cn-panel cn-port-table"><div className="cn-table-toolbar"><div className="cn-search-field"><Search size={15}/><input placeholder="Судно, IMO или порт отправления"/></div><button className="cn-filter-chip active">Следующие 12 ч <span>{port.incoming}</span></button><button className="cn-filter-chip">Высокий риск <span>{port.highRisk}</span></button><button className="secondary-button"><Filter size={14}/>Фильтры</button></div><div className="table-scroll"><table><thead><tr><th>Заход в порт</th><th>Судно / глобальный ID</th><th>Откуда</th><th>Местное ETA</th><th>Груз</th><th>Риск</th><th>Статус</th><th/></tr></thead><tbody>{portArrivals.map(item=><tr key={item.id} onClick={()=>item.vessel==='CASPIAN STAR'?navigate('/app/port-calls/pc-aktau-143'):undefined}><td className="mono">{item.id}</td><td><div className="cn-identity-cell"><span><Ship size={15}/></span><div><strong>{item.vessel}</strong><small>{item.globalId}</small></div></div></td><td><strong>{operationalText(item.from)}</strong> <ArrowRight size={12}/> {operationalText(port.name)}</td><td><strong className="mono">{item.eta}</strong><small className="cn-cell-note">{port.timezone}</small></td><td>{item.cargo}</td><td><b className={`cn-risk-score ${item.risk>=75?'critical':'high'}`}>{item.risk}</b></td><td><span className="cn-status-tag">{operationalText(item.status)}</span></td><td><ChevronRight size={15}/></td></tr>)}</tbody></table></div></section>
}

function PortQueueTab({port}:{port:NetworkPort}) {
  return <div className="cn-port-queue-layout"><section className="cn-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">ОПЕРАЦИОННАЯ ОЧЕРЕДЬ</span><h2>{operationalText(port.name)} · {port.vessels} судов</h2></div><button className="secondary-button"><Settings2 size={14}/>Правила очереди</button></div><div className="cn-queue-list">{portArrivals.map((item,index)=><article key={item.id}><em>{index+1}</em><span className="cn-vessel-icon"><Ship size={16}/></span><span><strong>{item.vessel}</strong><small>{item.cargo} · ETA {item.eta}</small></span><div><small>ГОТОВНОСТЬ</small><strong>{[92,78,71,64][index]}%</strong></div><b className={item.risk>=75?'critical':'high'}>{item.risk}</b><button>ПОДРОБНЕЕ</button></article>)}</div></section><aside className="cn-panel cn-queue-policy"><span className="page-eyebrow">ОБЪЯСНЕНИЕ ОЧЕРЕДИ</span><h2>Почему такой порядок</h2><p>Приоритет рассчитан по готовности причала, ETA, типу груза, ограничениям осадки и уровню внимания.</p>{['Совместимость с причалом','Подтверждённое ETA','Готовность груза','Ограничение осадки','Проверка риска'].map((item,index)=><div key={item}><span><i style={{width:`${[96,91,84,79,72][index]}%`}}/></span><strong>{item}</strong></div>)}<div className="cn-human-note"><ShieldCheck size={15}/><span>Изменение очереди требует подтверждения диспетчера.</span></div></aside></div>
}

function PortForecastTab({port}:{port:NetworkPort}) {
  return <div className="cn-forecast-layout"><section className="cn-panel cn-large-forecast"><div className="cn-panel-head"><div><span className="page-eyebrow">ПРОГНОЗ ЗАГРУЗКИ ПОРТА</span><h2>Следующие 24 часа</h2></div><span className="cn-model-badge">CI-PORT-FORECAST-1.0 · достоверность 91%</span></div><div className="cn-forecast-chart"><div className="cn-threshold">порог перегрузки 80%</div>{[54,58,63,68,72,79,82,85,81,74,68,64,59,57,62,70,76,73,65,58,52,49,46,44].map((value,index)=><span key={index}><i style={{height:`${value}%`}} className={value>=80?'peak':''}/><small>{index%3===0?`${String((15+index)%24).padStart(2,'0')}:00`:''}</small></span>)}</div><footer><span><i className="normal"/>Норма</span><span><i className="peak"/>Вероятна перегрузка</span><em>Обновлено {port.updated}</em></footer></section><aside className="cn-panel cn-forecast-explain"><span className="page-eyebrow">ПОЧЕМУ 82% В 19:00</span><h2>Факторы прогноза</h2>{[{name:'7 прибывающих судов',value:'+24%'},{name:'Обслуживание причала #3',value:'+11%'},{name:'Средняя обработка 5 ч 12 мин',value:'+8%'},{name:'Ветер 14 уз · норма',value:'+1%'}].map(item=><div key={item.name}><Check size={13}/><span><strong>{item.name}</strong><small>Подтверждённый операционный показатель</small></span><em>{item.value}</em></div>)}<button className="primary-button full" onClick={()=>goAssistant(`Почему ${port.name} будет перегружен через 4 часа?`,{label:`Порт ${operationalText(port.name)}`,portId:port.id})}><Sparkles size={14}/>Спросить ИИ-помощника</button></aside></div>
}

function PortConfigurationTab({port}:{port:NetworkPort}) {
  const groups=[{title:'Berths',items:[`${port.berths} configured`,`${port.freeBerths} currently free`,'Max draught 7.2 m']},{title:'Cargo capabilities',items:port.capabilities},{title:'Operational rules',items:['Queue: readiness weighted','Working hours: 24/7','Pilotage required']},{title:'Weather restrictions',items:['Wind warning ≥ 24 kn','Wave warning ≥ 2.5 m','Visibility minimum 1.0 km']}]
  return <div className="cn-config-grid">{groups.map((group,index)=><section className="cn-panel" key={group.title}><header><span>{index+1}</span><div><small>КОНФИГУРАЦИЯ ПОРТА</small><h2>{group.title}</h2></div><Settings2 size={16}/></header>{group.items.map(item=><div key={item}><Check size={13}/><span>{operationalText(item)}</span><em>АКТИВНО</em></div>)}</section>)}</div>
}

function PortIntegrationTab({port}:{port:NetworkPort}) {
  const entries=[['AIS','fetch_positions()','CONNECTED','8 sec'],['Port calls','fetch_arrivals()','CONNECTED','11 sec'],['Berths','fetch_berths()',port.integration==='PLANNED'?'PLANNED':'CONNECTED','24 sec'],['Cargo','fetch_cargo()',port.integration==='CONNECTED'?'CONNECTED':'PARTIAL','2 min'],['Documents','fetch_documents()',port.id==='aktau'?'PARTIAL':'PLANNED','12 min']]
  return <div className="cn-integration-layout"><section className="cn-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">АДАПТЕР ПОРТА</span><h2>Адаптер интеграции {operationalText(port.name)}</h2></div><em className={`cn-integration ${port.integration.toLowerCase()}`}><i/>{integrationLabel(port.integration)}</em></div><div className="cn-adapter-list">{entries.map(entry=><div key={entry[0]}><span className="cn-source-icon"><Database size={15}/></span><span><strong>{operationalText(entry[0])}</strong><small>{operationalText(entry[1])}</small></span><em className={`cn-integration ${entry[2].toLowerCase()}`}><i/>{integrationLabel(entry[2] as IntegrationState)}</em><time>{entry[3]}</time></div>)}</div></section><aside className="cn-panel cn-provenance-card"><div className="cn-panel-head"><div><span className="page-eyebrow">ПРОИСХОЖДЕНИЕ ДАННЫХ</span><h2>Последняя запись</h2></div><FileCheck2 size={18}/></div><div className="cn-provenance-value"><span>Груз</span><strong>4 920 т</strong><em>ПРОВЕРЕНО</em></div><dl><div><dt>Источник</dt><dd>проверка порта {operationalText(port.name)}</dd></div><div><dt>Получено</dt><dd>10 авг · 15:18 местное</dd></div><div><dt>Качество</dt><dd>{port.quality}%</dd></div><div><dt>ID записи</dt><dd>PRV-AKT-88412</dd></div></dl><p><ShieldCheck size={14}/>Значение не перезаписывает исходную декларацию Баку; обе версии сохраняются.</p></aside></div>
}

export function CaspianPortDetailPage({ navigate, portId, initialTab='overview' }: { navigate:Navigate;portId:string;initialTab?:string }) {
  const fallback=networkPorts.find(item=>item.id===portId)||networkPorts[0]
  const tabValue=portTabs.includes(initialTab as PortTab)?initialTab as PortTab:'overview'
  const [tab,setTab]=useState<PortTab>(tabValue)
  useEffect(()=>setTab(tabValue),[tabValue,portId])
  const {data:port,source,loading,reload}=useNetworkResource(`/ports/${portId}/overview`,fallback,(payload)=>{
    const value=((payload as {data?:unknown}).data||payload) as Record<string,unknown>
    return {...fallback,name:String(value.name||fallback.name),country:String(value.country||fallback.country),load:Number(value.load_percent??value.load??fallback.load),incoming:Number(value.incoming??value.arrivals??fallback.incoming),vessels:Number(value.vessels??fallback.vessels),quality:Number(value.data_quality??value.quality??fallback.quality)}
  })
  const selectTab=(next:PortTab)=>{setTab(next);navigate(`/app/ports/${port.id}/${next}`)}
  return <div className="content-page cn-page cn-port-detail-page">
    <button className="back-link" onClick={()=>navigate('/app/ports')}><ArrowLeft size={15}/>К реестру портов</button>
    <header className="cn-port-hero"><div className="cn-port-hero-icon"><Anchor size={25}/></div><div><span className="page-eyebrow">{port.country} · {port.portType}</span><h1>Port {port.name}</h1><p><span className={`cn-flag flag-${port.countryCode.toLowerCase()}`}>{port.countryCode}</span>{port.timezone} · {port.localTime} local · <b>{port.quality}% data quality</b></p></div><div className="cn-port-hero-status"><SourceBadge source={source} loading={loading}/><em className={`cn-integration ${port.integration.toLowerCase()}`}><i/>{port.integration}</em><button className="icon-button" onClick={reload}><RefreshCw size={16}/></button></div></header>
    <div className="cn-port-tabs">{portTabs.map(item=><button key={item} className={tab===item?'active':''} onClick={()=>selectTab(item)}>{portTabLabels[item]}{item==='arrivals'&&<span>{port.incoming}</span>}{item==='queue'&&<span>{port.vessels}</span>}</button>)}</div>
    {tab==='overview'&&<PortOverviewTab port={port} navigate={navigate}/>} {tab==='arrivals'&&<PortArrivalsTab port={port} navigate={navigate}/>} {tab==='berths'&&<BerthGrid port={port}/>} {tab==='queue'&&<PortQueueTab port={port}/>} {tab==='forecast'&&<PortForecastTab port={port}/>} {tab==='configuration'&&<PortConfigurationTab port={port}/>} {tab==='integration'&&<PortIntegrationTab port={port}/>} 
  </div>
}

function normalizeRiskRows(payload: unknown): RiskRow[] {
  const object=payload as {items?:unknown[];vessels?:unknown[];priority_vessels?:unknown[]}
  const items=object.items||object.vessels||object.priority_vessels
  if(!Array.isArray(items)||!items.length)return riskRows
  return items.map((item,index)=>{
    const value=item as Record<string,unknown>
    const fallback=riskRows[index%riskRows.length]
    const score=Number(value.score??value.risk_score??fallback.score)
    return {...fallback,id:String(value.legacy_vessel_id||value.vessel_id||value.id||fallback.id),globalId:String(value.global_vessel_id||value.caspian_vessel_id||value.global_id||fallback.globalId),name:String(value.vessel_name||value.name||fallback.name),route:String(value.display_name||value.route_id||value.route||fallback.route),port:String(value.destination_port_id||value.port||value.destination||fallback.port),score,band:String(value.level||value.risk_level||value.band||(score>=85?'CRITICAL':score>=65?'HIGH':score>=35?'MODERATE':'LOW')).toUpperCase() as RiskBand}
  })
}

export function RegionalRiskCenterPage({ navigate }: { navigate:Navigate }) {
  const {data,source,loading,reload}=useNetworkResource('/network/risk',riskRows,normalizeRiskRows)
  const [country,setCountry]=useState('ALL');const [port,setPort]=useState('ALL');const [band,setBand]=useState('ALL');const [query,setQuery]=useState('')
  const rows=data.filter(item=>(country==='ALL'||item.flag===country)&&(port==='ALL'||item.port===port)&&(band==='ALL'||item.band===band)&&`${item.name} ${item.globalId} ${item.route}`.toLowerCase().includes(query.toLowerCase()))
  return <div className="content-page cn-page">
    <NetworkHeader eyebrow="CASPIAN RISK CENTER" title="Региональный риск-центр" description="Единая приоритетная очередь судов и рейсов всего Каспия. Оценка объяснима и не является обвинительным выводом." source={source} loading={loading} actions={<button className="secondary-button" onClick={reload}><RefreshCw size={15}/>Обновить</button>}/>
    <NetworkModuleNav navigate={navigate} active="/app/caspian/risk"/>
    <div className="cn-risk-summary"><span><strong>11</strong><small>HIGH / CRITICAL</small></span><span><strong>5</strong><small>стран</small></span><span><strong>7</strong><small>маршрутов</small></span><span><strong>3</strong><small>требуют проверки</small></span><p><ShieldCheck size={15}/>Риск помогает расставить приоритеты. Решение принимает уполномоченный специалист.</p></div>
    <div className="cn-regional-filters"><div className="cn-search-field"><Search size={15}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Судно, глобальный ID или маршрут"/></div><label>Страна<select value={country} onChange={event=>setCountry(event.target.value)}><option value="ALL">ВСЕ</option>{[...new Set(data.map(item=>item.flag))].map(item=><option key={item} value={item}>{operationalText(item)}</option>)}</select></label><label>Порт<select value={port} onChange={event=>setPort(event.target.value)}><option value="ALL">ВСЕ</option>{[...new Set(data.map(item=>item.port))].map(item=><option key={item} value={item}>{operationalText(item)}</option>)}</select></label><label>Риск<select value={band} onChange={event=>setBand(event.target.value)}><option value="ALL">ВСЕ</option><option value="CRITICAL">КРИТИЧЕСКИЙ</option><option value="HIGH">ВЫСОКИЙ</option><option value="MODERATE">УМЕРЕННЫЙ</option><option value="LOW">НИЗКИЙ</option></select></label></div>
    <section className="cn-panel cn-regional-risk-table"><div className="table-scroll"><table><thead><tr><th>#</th><th>Судно / глобальный ID</th><th>Маршрут</th><th>Назначение</th><th>Факторы</th><th>Обновлено</th><th>Риск</th><th/></tr></thead><tbody>{rows.map((item,index)=><tr key={item.globalId} onClick={()=>item.id==='caspian-star'?navigate('/app/vessels/caspian-star?tab=risk'):undefined}><td><em className="cn-rank">{index+1}</em></td><td><div className="cn-identity-cell"><span><Ship size={15}/></span><div><strong>{item.name}</strong><small>{item.globalId} · {operationalText(item.flag)}</small></div></div></td><td><strong>{operationalText(item.route)}</strong><small className="cn-cell-note">{operationalText(item.type)}</small></td><td>{operationalText(item.port)}</td><td><div className="cn-factor-chips">{item.factors.slice(0,3).map(factor=><span key={factor}>{operationalText(factor)}</span>)}</div></td><td>{item.updated}</td><td><b className={`cn-risk-score ${item.band.toLowerCase()}`}>{item.score}<small>{riskBandLabel(item.band)}</small></b></td><td><ChevronRight size={15}/></td></tr>)}</tbody></table></div></section>
  </div>
}

function normalizeRoutes(payload:unknown):RouteRow[]{const object=payload as {items?:unknown[];routes?:unknown[]};const items=object.items||object.routes;if(!Array.isArray(items)||!items.length)return routeRows;return items.map((item,index)=>{const value=item as Record<string,unknown>;const fallback=routeRows[index%routeRows.length];const durationMinutes=Number(value.average_duration_minutes??0),delayMinutes=Number(value.average_delay_minutes??0);return {...fallback,id:String(value.id||value.route_id||fallback.id),from:String(value.origin_port_id||value.origin||value.from_port||value.from||fallback.from).replace(/^./,letter=>letter.toUpperCase()),to:String(value.destination_port_id||value.destination||value.to_port||value.to||fallback.to).replace(/^./,letter=>letter.toUpperCase()),voyages:Number(value.voyages_30d??value.voyages??fallback.voyages),duration:durationMinutes?`${Math.floor(durationMinutes/60)}h ${String(durationMinutes%60).padStart(2,'0')}m`:String(value.average_duration||value.duration||fallback.duration),delay:delayMinutes?`${delayMinutes} min`:String(value.average_delay||value.delay||fallback.delay),aisGaps:Number(value.ais_gaps??fallback.aisGaps),highRisk:Number(value.high_risk_voyages??value.high_risk??fallback.highRisk),cargo:value.average_cargo_t?`${Number(value.average_cargo_t).toLocaleString('en-US')} t`:fallback.cargo,reliability:value.reliability!==undefined?Number(value.reliability):value.confidence!==undefined?Number(value.confidence)*100:fallback.reliability}})}

export function RouteIntelligencePage({ navigate }: { navigate:Navigate }) {
  const {data,source,loading}=useNetworkResource('/network/routes',routeRows,normalizeRoutes);const [selected,setSelected]=useState('baku-aktau');const route=data.find(item=>item.id===selected)||data[0]
  return <div className="content-page cn-page">
    <NetworkHeader eyebrow="REGIONAL ROUTE INTELLIGENCE" title="Маршруты между портами" description="Сравнение потока рейсов, длительности, задержек и качества наблюдения за последние 30 дней." source={source} loading={loading}/><NetworkModuleNav navigate={navigate} active="/app/caspian/routes"/>
    <div className="cn-routes-layout"><section className="cn-panel cn-route-list"><div className="cn-panel-head"><div><span className="page-eyebrow">РЕЕСТР МАРШРУТОВ</span><h2>Ключевые коридоры</h2></div><span>{data.length} маршрута</span></div>{data.map(item=><button key={item.id} className={item.id===route.id?'active':''} onClick={()=>setSelected(item.id)}><span><i>{item.from[0]}</i><strong>{operationalText(item.from)} <ArrowRight size={12}/> {operationalText(item.to)}</strong><small>{item.countries} · {item.voyages} рейсов</small></span><em>{item.reliability}%<small>достоверность</small></em><ChevronRight size={14}/></button>)}</section>
      <section className="cn-panel cn-route-detail"><div className="cn-panel-head"><div><span className="page-eyebrow">МАРШРУТ · ПОСЛЕДНИЕ 30 ДНЕЙ</span><h2>{operationalText(route.from)} ↔ {operationalText(route.to)}</h2></div><span className="cn-reliability"><BadgeCheck size={14}/>достоверность {route.reliability}%</span></div><div className="cn-route-hero"><button onClick={()=>navigate(`/app/ports/${route.from.toLowerCase()}`)}><Anchor size={17}/><span><strong>{operationalText(route.from)}</strong><small>Порт отправления</small></span></button><div><span/><Navigation size={17}/><em>{route.duration}</em></div><button onClick={()=>navigate(`/app/ports/${route.to.toLowerCase()}`)}><Anchor size={17}/><span><strong>{operationalText(route.to)}</strong><small>Порт назначения</small></span></button></div><div className="cn-route-kpis"><span><small>Рейсы</small><strong>{route.voyages}</strong></span><span><small>Средняя длительность</small><strong>{route.duration}</strong></span><span><small>Средняя задержка</small><strong>{route.delay}</strong></span><span><small>Пропуски AIS</small><strong>{route.aisGaps}</strong></span><span><small>Рейсы высокого риска</small><strong>{route.highRisk}</strong></span><span><small>Средний груз</small><strong>{route.cargo}</strong></span></div><div className="cn-route-trend"><header><span><strong>Объём рейсов</strong><small>нормированный тренд за 12 недель</small></span><em>+8,4%</em></header><div>{route.trend.map((value,index)=><span key={index}><i style={{height:`${value}%`}}/><small>{index%2===0?`Н${index+1}`:''}</small></span>)}</div></div><footer><button className="secondary-button" onClick={()=>navigate('/app/caspian/verification')}><GitCompareArrows size={14}/>Межпортовая проверка</button><button className="primary-button" onClick={()=>goAssistant(`Покажи суда с пропуском AIS между ${route.from} и ${route.to}.`,{routeId:route.id,label:`${route.from} — ${route.to}`})}><Sparkles size={14}/>Исследовать с ИИ</button></footer></section></div>
  </div>
}

export function CrossPortVerificationPage({ navigate }: { navigate:Navigate }) {
  const [mode,setMode]=useState<'cargo'|'draught'|'documents'>('cargo')
  const {data,source,loading}=useNetworkResource('/network/voyages/NET-VOY-001/cross-port',crossPortFallback,(payload)=>{const value=payload as CrossPortData;return value?.departure&&value?.arrival&&Array.isArray(value.comparisons)?value:crossPortFallback})
  const field=mode==='cargo'?'cargo_t':mode==='draught'?'draught_m':'documents'
  const selected=data.comparisons.find(item=>item.field_name===field)||crossPortFallback.comparisons.find(item=>item.field_name===field)!
  const unit=selected.unit?` ${selected.unit}`:''
  const formatValue=(value:unknown)=>typeof value==='number'?`${value.toLocaleString('en-US',{maximumFractionDigits:1})}${unit}`:String(value||'—')
  const difference=mode==='documents'?`${data.departure.document_ids.length} / ${data.arrival.document_ids.length} records`:`${Number(selected.difference)<0?'−':'+'}${Math.abs(Number(selected.difference)).toLocaleString('en-US',{maximumFractionDigits:1})}${unit}`
  const comparison={departure:formatValue(selected.departure_value),arrival:formatValue(selected.arrival_value),difference,status:selected.status.replaceAll('_',' '),note:selected.explanation}
  return <div className="content-page cn-page"><NetworkHeader eyebrow="CROSS-PORT INTELLIGENCE" title="Межпортовая верификация" description="Сопоставление независимых записей отправления и прибытия без перезаписи исходных данных." source={source} loading={loading}/><NetworkModuleNav navigate={navigate} active="/app/caspian/verification"/>
    <section className="cn-scenario-banner"><div><span className="page-eyebrow">END-TO-END VOYAGE · {data.voyage_id}</span><h2>{data.vessel_name} <small>{data.global_vessel_id}</small></h2><p>{data.origin_port_id.replace(/^./,c=>c.toUpperCase())} → Caspian Sea → {data.destination_port_id.replace(/^./,c=>c.toUpperCase())} → next: Turkmenbashi</p></div><b>91<small>RISK</small></b><button onClick={()=>navigate('/app/vessels/caspian-star')}>Профиль судна <ArrowRight size={14}/></button></section>
    <div className="cn-verification-tabs">{(['cargo','draught','documents'] as const).map(item=><button key={item} className={mode===item?'active':''} onClick={()=>setMode(item)}>{item==='cargo'?'Груз':item==='draught'?'Осадка':'Документы'}</button>)}</div>
    <section className="cn-panel cn-cross-port-card"><div className="cn-port-record departure"><header><span>DEPARTURE RECORD</span><em>{data.departure.status}</em></header><div><i>B</i><span><strong>Baku Port</strong><small>10 Aug · 08:02 local · UTC+4</small></span></div><b>{comparison.departure}</b><dl><div><dt>Source</dt><dd>{data.departure.source_ids.join(', ')}</dd></div><div><dt>Evidence</dt><dd>{selected.evidence_ids[0]}</dd></div><div><dt>Quality</dt><dd>94%</dd></div></dl></div><div className="cn-compare-engine"><GitCompareArrows size={25}/><strong>CI-CROSSPORT-1.0</strong><span>{comparison.difference}</span><em>{comparison.status}</em><small>{comparison.note}</small></div><div className="cn-port-record arrival"><header><span>ARRIVAL RECORD</span><em>{data.arrival.status}</em></header><div><i>A</i><span><strong>Aktau Port</strong><small>11 Aug · 15:18 local · UTC+5</small></span></div><b>{comparison.arrival}</b><dl><div><dt>Source</dt><dd>{data.arrival.source_ids.join(', ')}</dd></div><div><dt>Evidence</dt><dd>{selected.evidence_ids.at(-1)}</dd></div><div><dt>Quality</dt><dd>98%</dd></div></dl></div></section>
    <div className="cn-verification-lower"><section className="cn-panel cn-voyage-chain"><div className="cn-panel-head"><div><span className="page-eyebrow">UNBROKEN DIGITAL HISTORY</span><h2>Сквозная история рейса</h2></div><BadgeCheck size={18}/></div>{[['08:00','Baku departure','5,000 t · 5.2 m','FACT'],['13:20','Route deviation','38 km from corridor','FACT'],['14:10–17:25','AIS gap','3h 15m','FACT'],['17:28','Encounter TURAN','174 m · 2h 47m','FACT'],['17:40','Draught change','+0.9 m signal','ESTIMATE'],['18:00','Fuel anomaly','61 t vs 38–44 t','ESTIMATE'],['18:05','Risk Engine','91 / 100','INFERENCE'],['15:18 local','Aktau verification','4,920 t · 5.1 m','FACT']].map(item=><div key={item[1]}><time>{item[0]}</time><i/><span><strong>{item[1]}</strong><small>{item[2]}</small></span><em>{item[3]}</em></div>)}</section><aside className="cn-panel cn-next-voyage"><span className="page-eyebrow">NEXT VOYAGE</span><h2>История продолжается</h2><div><span><Anchor size={16}/>Aktau</span><i/><Navigation size={17}/><i/><span><Anchor size={16}/>Turkmenbashi</span></div><p>Тот же глобальный профиль судна продолжает накапливать рейсы, события и проверки независимо от источника.</p><button className="primary-button full" onClick={()=>goAssistant('Суммируй межпортовую проверку CASPIAN STAR.',{vesselId:'CI-VESSEL-000184',voyageId:'VOY-2026-143'})}><Sparkles size={14}/>Суммировать с AI</button></aside></div>
  </div>
}

export function RegionalDataHealthPage({ navigate }: { navigate:Navigate }) {
  const {data,source,loading,reload}=useNetworkResource('/network/data-health',dataSources,(payload)=>{const value=payload as {items?:unknown[];sources?:unknown[]};const items=value.items||value.sources;if(!Array.isArray(items))return dataSources;return items.map((entry,index)=>{const item=entry as Record<string,unknown>,fallback=dataSources[index%dataSources.length];return {...fallback,id:String(item.id||fallback.id),name:String(item.name||fallback.name),type:String(item.source_type||item.type||fallback.type),status:String(item.status||fallback.status) as HealthState,quality:Math.round(Number(item.quality_score??Number(fallback.quality)/100)*100),coverage:String(item.coverage||fallback.coverage),latency:item.latency_seconds!==undefined?`${item.latency_seconds} sec`:String(item.latency||fallback.latency),updated:String(item.last_update_at||item.updated||fallback.updated)}})})
  const online=data.filter(item=>item.status==='ONLINE').length,degraded=data.filter(item=>item.status==='DEGRADED').length
  return <div className="content-page cn-page"><NetworkHeader eyebrow="REGIONAL DATA HEALTH" title="Состояние данных и платформы" description="Покрытие, задержка, качество источников и наблюдаемость регионального контура." source={source} loading={loading} actions={<button className="secondary-button" onClick={reload}><RefreshCw size={15}/>Проверить</button>}/><NetworkModuleNav navigate={navigate} active="/app/caspian/data-health"/>
    <div className="cn-health-metrics"><span><strong>92</strong><small>NETWORK HEALTH</small></span><span><i className="online"/><strong>{online}</strong><small>ONLINE</small></span><span><i className="degraded"/><strong>{degraded}</strong><small>DEGRADED</small></span><span><i className="offline"/><strong>{data.length-online-degraded}</strong><small>OFFLINE / PLANNED</small></span><span><strong>8 sec</strong><small>BEST LATENCY</small></span></div>
    <div className="cn-health-layout"><section className="cn-panel cn-source-table"><div className="cn-panel-head"><div><span className="page-eyebrow">DATA SOURCE REGISTRY</span><h2>Интеграции</h2></div><span>{data.length} sources</span></div>{data.map(item=><article key={item.id}><i className={item.status.toLowerCase()}/><span><strong>{item.name}</strong><small>{item.type} · {item.country}</small></span><div><small>Coverage</small><strong>{item.coverage}</strong></div><div><small>Quality</small><strong>{item.quality}%</strong></div><div><small>Latency</small><strong>{item.latency}</strong></div><em className={item.status.toLowerCase()}>{item.status}</em></article>)}</section><section className="cn-panel cn-coverage-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">DATA COVERAGE</span><h2>Карта покрытия</h2></div><Layers3 size={17}/></div><RegionalMap navigate={navigate} compact coverage/><p><Info size={14}/>AIS gap в зоне нестабильного покрытия получает отдельный coverage context и не трактуется как равнозначный gap в стабильной зоне.</p></section></div>
    <div className="cn-platform-grid"><section className="cn-panel"><span className="page-eyebrow">PLATFORM OBSERVABILITY</span><h2>Контур обработки</h2>{[['API health','99.98%','ONLINE'],['AIS ingestion','1,842 msg/s','NORMAL'],['Event bus lag','280 ms','NORMAL'],['Risk Engine p95','184 ms','NORMAL'],['WebSocket clients','47','NORMAL'],['AI tool errors','0.3%','NORMAL']].map(item=><div className="cn-platform-row" key={item[0]}><span>{item[0]}</span><strong>{item[1]}</strong><em>{item[2]}</em></div>)}</section><section className="cn-panel cn-retention"><span className="page-eyebrow">DATA RETENTION</span><h2>Жизненный цикл данных</h2><div><b>HOT</b><span><strong>0–90 дней</strong><small>Полное разрешение AIS · быстрый PostGIS</small></span></div><div><b>WARM</b><span><strong>90 дней – 2 года</strong><small>Оптимизированные треки и агрегации</small></span></div><div><b>COLD</b><span><strong>Долгосрочный архив</strong><small>Object storage · события и Cases дольше</small></span></div></section><section className="cn-panel cn-event-bus"><span className="page-eyebrow">REGIONAL EVENT BUS</span><h2>Независимые обработчики</h2><div><Database size={17}/><span>INGESTION</span><i/><span>AIS</span><span>BEHAVIOR</span><span>RISK</span><span>ENV</span><span>PORT</span></div><p>Production-ready logical contract; конкретная streaming-технология выбирается при внедрении.</p></section></div>
  </div>
}

export function RegionalNetworkGraphPage({ navigate }: { navigate:Navigate }) {
  const [selected,setSelected]=useState('company')
  const {data,source,loading}=useNetworkResource('/network/graph?vessel_id=CI-VESSEL-000184',graphFallback,(payload)=>{const value=payload as RegionalGraphData;return Array.isArray(value?.nodes)&&Array.isArray(value?.edges)?value:graphFallback})
  const node=(id:string)=>data.nodes.find(item=>item.id===id)
  const edge=(relationship:string)=>data.edges.find(item=>item.relationship===relationship)
  const company=node('CI-COMPANY-00421'),star=node('CI-VESSEL-000184'),turan=node('CI-VESSEL-000241'),route=node('route-baku-aktau'),cargo=node('cargo-steel')
  const details:Record<string,{title:string;type:string;id:string;facts:string[]}>= {
    company:{title:company?.label||'CASPIAN SHIPPING LTD',type:'GLOBAL COMPANY',id:company?.id||'CI-COMPANY-00421',facts:[`OPERATES edge · ${edge('OPERATES')?.evidence_ids.join(', ')||'evidence required'}`,`${data.nodes.filter(item=>item.type==='VESSEL').length} linked vessels`,`${data.nodes.filter(item=>item.type==='PORT').length} observed ports`,'Identity link: VERIFIED']},
    star:{title:star?.label||'CASPIAN STAR',type:'VESSEL',id:star?.id||'CI-VESSEL-000184',facts:[`${data.nodes.filter(item=>item.type==='PORT').map(item=>item.label).join(' → ')}`,`Risk ${star?.risk_score??91}`,'Owner link: VERIFIED',`${edge('ENCOUNTERED')?.weight??14} encounters with TURAN`]},
    turan:{title:turan?.label||'TURAN',type:'VESSEL',id:turan?.id||'CI-VESSEL-000241',facts:[turan?.country||'Turkmenistan',`Risk ${turan?.risk_score??84}`,`${edge('ENCOUNTERED')?.weight??14} previous encounters`,`Evidence: ${edge('ENCOUNTERED')?.evidence_ids.join(', ')||'—'}`]},
    route:{title:route?.label||'Baku ↔ Aktau',type:'ROUTE',id:route?.id||'route-baku-aktau',facts:[`${edge('SAILED_ROUTE')?.weight??37} observed voyages`,'17 AIS gaps','8 high-risk voyages','94% reliability']},
  };const detail=details[selected]
  return <div className="content-page cn-page"><NetworkHeader eyebrow="CASPIAN NETWORK GRAPH" title="Региональная сеть связей" description="Суда, компании, порты, грузы и маршруты объединены доказуемыми связями. Связь не означает нарушение." source={source} loading={loading}/><NetworkModuleNav navigate={navigate} active="/app/caspian/network"/><div className="cn-network-caution"><Info size={15}/><span><strong>Explainable graph.</strong> Каждое ребро хранит тип, источник, время и уверенность; риск автоматически между объектами не переносится.</span></div>
    <div className="cn-regional-network-layout"><section className="cn-panel cn-graph-canvas"><div className="cn-panel-head"><div><span className="page-eyebrow">5 СТРАН · 9 ПОРТОВ</span><h2>Контекст {star?.label||'CASPIAN STAR'}</h2></div><span>{data.edges.length} подтверждённых связей</span></div><div className="cn-graph-stage"><svg viewBox="0 0 760 430" preserveAspectRatio="none"><path d="M380 78L185 178M380 78L380 190M380 78L575 178M185 178L120 330M185 178L285 330M380 190L285 330M380 190L480 330M575 178L480 330M575 178L650 330"/><path className="accent" d="M185 178L380 190"/></svg><button className={`company ${selected==='company'?'active':''}`} onClick={()=>setSelected('company')}><Building2 size={18}/><strong>{company?.label||'CASPIAN SHIPPING LTD'}</strong><small>{company?.id||'CI-COMPANY-00421'}</small></button><button className={`vessel star ${selected==='star'?'active':''}`} onClick={()=>setSelected('star')}><Ship size={18}/><strong>{star?.label||'CASPIAN STAR'}</strong><small>Риск {star?.risk_score??91}</small></button><button className={`vessel turan ${selected==='turan'?'active':''}`} onClick={()=>setSelected('turan')}><Ship size={18}/><strong>{turan?.label||'TURAN'}</strong><small>{edge('ENCOUNTERED')?.weight??14} встреч</small></button><button className="vessel third"><Package size={18}/><strong>{cargo?.label||'СТАЛЬ / 5 000 Т'}</strong><small>Груз со связанными доказательствами</small></button><button className="port baku"><Anchor size={17}/><strong>БАКУ</strong><small>AZ · 74%</small></button><button className="port aktau"><Anchor size={17}/><strong>АКТАУ</strong><small>KZ · 68%</small></button><button className="port tm"><Anchor size={17}/><strong>ТУРКМЕНБАШИ</strong><small>TM · 42%</small></button><button className={`route ${selected==='route'?'active':''}`} onClick={()=>setSelected('route')}><Route size={17}/><strong>{operationalText(route?.label||'BAKU ↔ AKTAU')}</strong><small>{edge('SAILED_ROUTE')?.weight??37} рейсов</small></button></div></section><aside className="cn-panel cn-graph-inspector"><span className="page-eyebrow">ВЫБРАННЫЙ ОБЪЕКТ</span><h2>{detail.title}</h2><p>{operationalText(detail.type)} · <strong>{detail.id}</strong></p>{detail.facts.map(fact=><div key={fact}><BadgeCheck size={14}/><span>{operationalText(fact)}</span></div>)}<section><strong>Основание доказательств</strong><small>{data.edges.flatMap(item=>item.evidence_ids).slice(0,4).join(' · ')}</small><em>{data.evidence_grounded?'ЕСТЬ ДОКАЗАТЕЛЬСТВА':'ТРЕБУЕТСЯ ПРОВЕРКА'}</em></section><button className="secondary-button full" onClick={()=>navigate('/app/caspian/search?q='+encodeURIComponent(detail.id))}>Открыть цифровой профиль <ArrowRight size={14}/></button></aside></div>
  </div>
}

export function RegionalSearchPage({ navigate }: { navigate:Navigate }) {
  const initial=new URLSearchParams(window.location.search).get('q')||'';const [query,setQuery]=useState(initial);const [kind,setKind]=useState<'ALL'|SearchKind>('ALL');const [submitted,setSubmitted]=useState(Boolean(initial))
  const endpointQuery=submitted&&query.trim()?query.trim():'__registry__'
  const {data:apiItems,source,loading}=useNetworkResource(`/network/search?q=${encodeURIComponent(endpointQuery)}`,searchItems,normalizeRegionalSearch)
  const catalog=submitted?apiItems:searchItems
  const results=catalog.filter(item=>(kind==='ALL'||item.kind===kind)&&(source==='LIVE API'||!query||`${item.id} ${item.title} ${item.subtitle} ${item.aliases?.join(' ')||''}`.toLowerCase().includes(query.toLowerCase())))
  return <div className="content-page cn-page"><NetworkHeader eyebrow="SEARCH CASPIAN" title="Глобальный поиск" description="Один результат для одного объекта независимо от страны, порта или исходного идентификатора." source={source} loading={loading} actions={<ScopeBadge/>}/><div className="cn-search-hero"><Search size={21}/><input value={query} onChange={event=>setQuery(event.target.value)} onKeyDown={event=>event.key==='Enter'&&setSubmitted(true)} placeholder="MMSI, IMO, Global ID, судно, компания, порт или событие"/><button className="primary-button" onClick={()=>setSubmitted(true)}>Найти в Каспии</button></div><div className="cn-search-kinds"><button className={kind==='ALL'?'active':''} onClick={()=>setKind('ALL')}>Все <span>{catalog.length}</span></button>{(Object.keys(kindLabels) as SearchKind[]).map(item=><button key={item} className={kind===item?'active':''} onClick={()=>setKind(item)}>{kindLabels[item]}</button>)}</div>
    {!submitted&&!query?<section className="cn-panel cn-search-start"><Globe2 size={28}/><h2>Единый реестр Каспия</h2><p>Попробуйте `436000118`, `CI-VESSEL-000184`, `CASPIAN STAR` или название порта.</p><div>{['CI-VESSEL-000184','CI-COMPANY-00421','Baku','ENV-142'].map(item=><button key={item} onClick={()=>{setQuery(item);setSubmitted(true)}}>{item}</button>)}</div></section>:<div className="cn-search-layout"><section className="cn-panel cn-search-results"><header><span><strong>{results.length} результатов</strong><small>Entity Resolution применён</small></span><em>REGIONAL SCOPE</em></header>{results.map(item=>{const Icon=kindIcons[item.kind];return <button key={item.id} onClick={()=>navigate(item.href)}><span className={`cn-search-kind ${item.kind.toLowerCase()}`}><Icon size={17}/></span><span><small>{item.kind}</small><strong>{item.title}</strong><em>{item.subtitle}</em>{item.aliases&&<i>Aliases: {item.aliases.join(' · ')}</i>}</span><span><b>{item.id}</b><small>{item.meta}</small></span>{item.status&&<em>{item.status}</em>}<ChevronRight size={15}/></button>})}{!results.length&&<div className="cn-no-results"><Search size={25}/><strong>Данные не найдены</strong><span>Система не создаёт объект и не придумывает совпадение.</span></div>}</section>{results[0]?.kind==='VESSEL'&&<aside className="cn-panel cn-identity-history"><span className="page-eyebrow">GLOBAL VESSEL IDENTITY</span><h2>{results[0].id}</h2><p><BadgeCheck size={14}/>Identity confidence 99.4%</p><dl><div><dt>IMO</dt><dd>9384721</dd></div><div><dt>MMSI</dt><dd>436000118</dd></div><div><dt>Call sign</dt><dd>UNCS7</dd></div><div><dt>Sources</dt><dd>KZ AIS · Baku · Aktau</dd></div></dl><h3>Identity history</h3>{[['2024','CASPIAN STAR','Kazakhstan'],['2025','CASPIAN STAR II','Kazakhstan'],['2026','Operator changed','Verified']].map(item=><div className="cn-history-row" key={item[0]}><time>{item[0]}</time><i/><span><strong>{item[1]}</strong><small>{item[2]}</small></span></div>)}</aside>}</div>}
  </div>
}

export function DataScopePage({ navigate }: { navigate:Navigate }) {
  const {data:access,source,loading}=useNetworkResource('/network/access/me',accessFallback,(payload)=>{const value=payload as NetworkAccess;return value?.organization&&Array.isArray(value.permissions)&&Array.isArray(value.data_scope)?value:accessFallback})
  const {data:audit}=useNetworkResource('/network/audit?limit=8',auditFallback,normalizeAudit)
  const permissionLabels:Record<string,[string,string]>= {'network:read':['Regional traffic, ports and routes','Caspian regional'],'identity:resolve':['Global vessel / company identity','Evidence-based resolver'],'sensitive:read':['Risk factors and provenance','Authorized scope'],'audit:read':['Access audit','Organization scope']}
  return <div className="content-page cn-page"><NetworkHeader eyebrow="ORGANIZATION · ROLE · DATA SCOPE" title="Контур доступа" description="Доступ определяется организацией, ролью и разрешённой областью данных; каждое чтение чувствительных данных аудируется." source={source} loading={loading}/><div className="cn-scope-hero"><span><Users size={20}/><small>ORGANIZATION</small><strong>{access.organization.name}</strong></span><i/><span><BadgeCheck size={20}/><small>ROLE</small><strong>{access.role.replaceAll('_',' ')}</strong></span><i/><span><Globe2 size={20}/><small>DATA SCOPE</small><strong>{access.data_scope.join(' · ')}</strong></span></div><div className="cn-scope-layout"><section className="cn-panel"><div className="cn-panel-head"><div><span className="page-eyebrow">EFFECTIVE PERMISSIONS</span><h2>Доступные области</h2></div><ShieldCheck size={18}/></div>{access.permissions.map(permission=>{const label=permissionLabels[permission]||[permission,'Explicit grant'];return <div className="cn-permission-row" key={permission}><CircleCheck size={14}/><span><strong>{label[0]}</strong><small>{label[1]}</small></span><em>{permission.split(':').at(-1)?.toUpperCase()}</em></div>})}</section><section className="cn-panel cn-restricted"><div className="cn-panel-head"><div><span className="page-eyebrow">RESTRICTED BY POLICY</span><h2>Ограниченные данные</h2></div><LockKeyhole size={18}/></div>{[['Other ports internal queue','Organization boundary'],['Restricted customs records','Customs permission required'],['Raw provider payloads','Source-owner restriction'],['Security cases not assigned','Need-to-know policy']].map(item=><div key={item[0]}><LockKeyhole size={14}/><span><strong>{item[0]}</strong><small>{item[1]}</small></span><em>DENIED</em></div>)}<p>AI Assistant использует тот же effective scope и не может обойти Tool Layer.</p></section></div><section className="cn-panel cn-access-audit"><div className="cn-panel-head"><div><span className="page-eyebrow">WHO VIEWED WHAT?</span><h2>Журнал доступа</h2></div><button className="secondary-button"><CalendarDays size={14}/>24 часа</button></div><div className="table-scroll"><table><thead><tr><th>UTC</th><th>User</th><th>Organization</th><th>Action</th><th>Resource</th><th>Outcome</th></tr></thead><tbody>{audit.map(row=>{const values=[new Date(row.timestamp).toISOString().slice(11,19),row.user,row.organization,row.action,row.resource,row.outcome];return <tr key={`${row.timestamp}-${row.action}`}>{values.map((value,index)=><td key={`${index}-${value}`} className={index===0?'mono':''}>{index===5?<span className={`cn-audit-outcome ${value.toLowerCase()}`}>{value}</span>:value}</td>)}</tr>})}</tbody></table></div></section><button className="back-link" onClick={()=>navigate('/app/caspian')}><ArrowLeft size={14}/>Вернуться в Caspian Traffic</button></div>
}
