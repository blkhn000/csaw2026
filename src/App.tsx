import { forwardRef, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import {
  Activity, Anchor, ArrowLeft, ArrowRight, BarChart3, Bell, BrainCircuit, Building2, Check,
  ChevronDown, ChevronRight, CircleUserRound, Clock3, Compass, Database,
  CalendarDays, CircleCheck, CircleDollarSign, CloudRain, Crosshair, Droplets, Eye, EyeOff, FileCheck2, FileText, Filter, Fuel, Gauge, GitCompareArrows, Globe2, History, Info, Layers3, Link2, ListFilter, LocateFixed,
  Leaf, LockKeyhole, LogOut, Map, MapPin, Menu, Mountain, Navigation, PanelLeftClose, Plus, Radio,
  Network, Package, Pause, Play, RadioTower, Route, Search, Settings, Shield, ShieldAlert, ShieldCheck, Ship, SlidersHorizontal, Sparkles,
  Target, TimerReset, TriangleAlert, Users, Warehouse, Waves, WifiOff, X, ZoomIn, ZoomOut
} from 'lucide-react'
import { caspianStarBehavior, caspianStarTrack, demoEventGroup, detectedEvents, events, investigationNetwork, ports, riskAssessments, trackingEvents, vessels, voyageIntelligence, voyages } from './data'
import type { DetectionEvent, IntelligenceDataStatus, IntelligenceEvidence, InvestigationNetworkEdge, InvestigationNetworkNode, NetworkNodeType, Port, RiskAssessment, RiskFactor, RiskLevel, RiskReviewStatus, TrackPoint, Vessel } from './types'
import { confidenceLabel, countryLabel, dataStatusLabel, etaLabel, navigationStatusLabel, operationalText, relativeTimeLabel, riskLevelLabel, severityLabel, statusLabel, t, vesselTypeLabel } from './i18n'
import { PortArrivalsPage, PortControlCenterPage, PreArrivalReportPage } from './PortOperations'
import { AssistantLauncher, AssistantPage, InvestigationListPage, InvestigationWorkspacePage } from './Assistant'
import { EnvironmentalCenterPage, EnvironmentalEventPage, VesselEnvironmentTab, type EnvironmentalEvent } from './Environmental'
import {
  CaspianNetworkDashboard, CaspianPortDetailPage, CaspianPortRegistryPage,
  CrossPortVerificationPage, DataScopePage, GlobalIdentityBadge,
  RegionalDataHealthPage, RegionalNetworkGraphPage, RegionalRiskCenterPage,
  RegionalSearchPage, RouteIntelligencePage,
} from './CaspianNetwork'
import {
  RealCaspianMap,
  circleArea,
  satelliteMapAvailable,
  type RealCaspianMapHandle,
  type RealMapAnnotation,
  type RealMapArea,
  type RealMapLine,
} from './RealCaspianMap'
import './risk.css'
import './advanced.css'
import './port.css'
import './readability.css'
import './ux-improvements.css'
import './network-orbit.css'
import './topbar-popovers.css'

const navItems = [
  { path: '/app/caspian', label: 'Сеть Каспия', icon: Globe2 },
  { path: '/app/map', label: 'Карта', icon: Map },
  { path: '/app/vessels', label: 'Суда', icon: Ship },
  { path: '/app/voyages', label: 'Рейсы', icon: Route },
  { path: '/app/history', label: 'История', icon: History },
  { path: '/app/risk', label: 'Риск-центр', icon: ShieldAlert, badge: '4' },
  { path: '/app/events', label: 'События', icon: Activity, badge: '3' },
  { path: '/app/environment', label: 'Экология', icon: Leaf, badge: '4' },
  { path: '/app/assistant', label: 'ИИ-помощник', icon: Shield },
  { path: '/app/investigations', label: 'Расследования', icon: Target },
  { section: 'Аналитика' },
  { path: '/app/voyages/voy-001/intelligence', label: 'Разбор рейса', icon: BrainCircuit, badge: '7' },
  { path: '/app/network', label: 'Сеть связей', icon: Network },
  { section: 'Операции' },
  { path: '/app/ports', label: 'Порты', icon: Anchor },
  { path: '/app/analytics', label: 'Аналитика', icon: BarChart3 },
  { path: '/app/settings', label: 'Настройки', icon: Settings },
]

const headerNotifications = [
  {id:'NT-401',title:'CASPIAN STAR: риск вырос до 91',detail:'Добавлен расширенный контекст рейса · 84 → 91',time:'5 мин назад',route:'/app/risk',tone:'critical' as const},
  {id:'NT-402',title:'Новая встреча требует проверки',detail:'CASPIAN STAR + TURAN · минимальная дистанция 174 м',time:'18 мин назад',route:'/app/network?edge=e-encounter',tone:'warning' as const},
  {id:'NT-403',title:'Экологическое событие обновлено',detail:'ENV-2026-00142 · добавлена реконструкция движения',time:'32 мин назад',route:'/app/environment/events/ENV-2026-00142',tone:'warning' as const},
  {id:'NT-404',title:'Прогноз загрузки порта Актау',detail:'Через 4 часа ожидается повышенная загрузка причалов',time:'1 ч назад',route:'/app/ports/aktau/forecast',tone:'info' as const},
  {id:'NT-405',title:'Данные AIS синхронизированы',detail:'Последний пакет проверен · полнота данных 98.7%',time:'2 ч назад',route:'/app/map',tone:'success' as const},
]

function navigate(path: string) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

const API_BASE = import.meta.env.VITE_API_BASE || (
  ['4173', '5173'].includes(window.location.port)
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : '/api/v1'
)

const WS_BASE = import.meta.env.VITE_WS_BASE || (
  ['4173', '5173'].includes(window.location.port)
    ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8000`
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`
)

function Logo({ compact = false }: { compact?: boolean }) {
  return <div className={`logo ${compact ? 'logo-compact' : ''}`}>
    <div className="logo-mark"><Mountain size={21} strokeWidth={2.1} /></div>
    {!compact && <div><strong>CASPIAN</strong><span>INTELLIGENCE</span></div>}
  </div>
}

function Login() {
  const [visible, setVisible] = useState(false)
  const [loading, setLoading] = useState(false)
  const login = (e: React.FormEvent) => {
    e.preventDefault(); setLoading(true)
    setTimeout(() => { localStorage.setItem('ci-session', 'demo'); navigate('/app/map') }, 550)
  }
  return <main className="login-page">
    <section className="login-showcase">
      <Logo />
      <div className="showcase-content">
        <div className="eyebrow light"><span /> Морская ситуационная осведомлённость</div>
        <h1>Каспийское море.<br />Единая картина.</h1>
        <p>Операционная платформа для мониторинга судов, портов и морских маршрутов в одном рабочем пространстве.</p>
        <div className="showcase-metrics">
          <div><strong>10</strong><span>ключевых портов</span></div>
          <div><strong>24/7</strong><span>мониторинг</span></div>
          <div><strong>5</strong><span>прибрежных стран</span></div>
        </div>
      </div>
      <div className="showcase-map" aria-hidden="true">
        <CaspianOutline />
        <span className="pulse p1" /><span className="pulse p2" /><span className="pulse p3" />
      </div>
      <div className="showcase-foot"><span>Защищённая операционная среда</span><span>v0.1 • DEMO</span></div>
    </section>
    <section className="login-panel">
      <form className="login-card" onSubmit={login}>
        <div className="mobile-logo"><Logo /></div>
        <div className="eyebrow"><span /> Авторизация</div>
        <h2>Добро пожаловать</h2>
        <p className="muted">Войдите в защищённое рабочее пространство Caspian Intelligence.</p>
        <label>Рабочая почта<input type="email" defaultValue="analyst@caspian.int" required /></label>
        <label>Пароль<div className="password-wrap"><input type={visible ? 'text' : 'password'} defaultValue="caspian2026" required /><button type="button" onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18}/> : <Eye size={18}/>}</button></div></label>
        <div className="form-row"><label className="check-label"><input type="checkbox" defaultChecked /><span><Check size={12}/></span>Запомнить меня</label><button type="button" className="text-button">Забыли пароль?</button></div>
        <button className="primary-button login-button" disabled={loading}>{loading ? <span className="loader"/> : <>Войти в систему <ArrowRight size={17}/></>}</button>
        <div className="secure-note"><ShieldCheck size={16}/><span>Демо-доступ: данные уже заполнены</span></div>
      </form>
      <p className="login-legal">Доступ разрешён только авторизованным пользователям.<br/>Все действия регистрируются системой.</p>
    </section>
  </main>
}

function CaspianOutline() {
  return <svg viewBox="0 0 350 600" className="caspian-outline"><path d="M159 14c40 5 79 48 76 92-2 31-24 51-16 87 11 49 79 86 76 153-2 46-31 79-46 116-12 30-17 76-54 101-34 23-85 29-110-8-17-25-1-56-10-87-11-37-38-55-42-96-4-43 24-71 37-108 13-35 10-62 1-99-8-34-4-77 20-109 18-25 39-45 68-42Z" fill="currentColor" /></svg>
}

function AppShell({ path, children }: { path: string; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileNav, setMobileNav] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [notificationsOpen,setNotificationsOpen]=useState(false)
  const [profileOpen,setProfileOpen]=useState(false)
  const [unreadNotifications,setUnreadNotifications]=useState<Set<string>>(()=>new Set(headerNotifications.slice(0,3).map(item=>item.id)))
  useEffect(()=>{setNotificationsOpen(false);setProfileOpen(false)},[path])
  useEffect(()=>{if(!notificationsOpen&&!profileOpen)return;const close=(event:KeyboardEvent)=>{if(event.key==='Escape'){setNotificationsOpen(false);setProfileOpen(false)}};addEventListener('keydown',close);return()=>removeEventListener('keydown',close)},[notificationsOpen,profileOpen])
  const isNavActive=(itemPath:string)=>itemPath==='/app/voyages'?path==='/app/voyages':path.startsWith(itemPath)
  return <div className={`app-shell ${collapsed ? 'nav-collapsed' : ''}`}>
    <header className="topbar">
      <button className="icon-button menu-button" onClick={() => setMobileNav(true)}><Menu size={20}/></button>
      <Logo compact={collapsed}/>
      <button className="global-search" onClick={() => setSearchOpen(true)}><Search size={18}/><span>Поиск судов, портов, IMO, MMSI...</span><kbd>⌘ K</kbd></button>
      <div className="top-actions">
        <div className="live-indicator"><span/> Данные актуальны</div>
        <button className={`icon-button notification ${notificationsOpen?'active':''}`} aria-label="Открыть уведомления" aria-expanded={notificationsOpen} onClick={()=>{setNotificationsOpen(value=>!value);setProfileOpen(false)}}><Bell size={19}/>{unreadNotifications.size>0&&<i/>}</button>
        <button className={`profile-button ${profileOpen?'active':''}`} aria-label="Открыть меню профиля" aria-expanded={profileOpen} onClick={()=>{setProfileOpen(value=>!value);setNotificationsOpen(false)}}><div className="avatar">AK</div><span><strong>Аян Касымов</strong><small>Демо-аккаунт</small></span><ChevronDown size={16}/></button>
        {notificationsOpen&&<NotificationsPopover unread={unreadNotifications} onRead={id=>setUnreadNotifications(current=>{const next=new Set(current);next.delete(id);return next})} onReadAll={()=>setUnreadNotifications(new Set())} onNavigate={route=>{setNotificationsOpen(false);navigate(route)}}/>}
        {profileOpen&&<ProfilePopover onNavigate={route=>{setProfileOpen(false);navigate(route)}} onLogout={()=>{localStorage.removeItem('ci-session');setProfileOpen(false);navigate('/login')}}/>}
      </div>
    </header>
    {(notificationsOpen||profileOpen)&&<button className="topbar-popover-backdrop" aria-label="Закрыть меню" onClick={()=>{setNotificationsOpen(false);setProfileOpen(false)}}/>}
    <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>
      <button className="mobile-close" onClick={() => setMobileNav(false)}><X size={20}/></button>
      <nav>
        {navItems.map((item, i) => item.section
          ? <div className="nav-section" key={i}>{item.section}</div>
          : <button key={item.path} title={collapsed ? item.label : ''} className={`nav-item ${isNavActive(item.path!) ? 'active' : ''}`} onClick={() => {navigate(item.path!); setMobileNav(false)}}>
              {item.icon && <item.icon size={19}/>}<span>{item.label}</span>{item.badge && <em>{item.badge}</em>}
            </button>)}
      </nav>
      <div className="sidebar-footer">
        <button className="collapse-button" onClick={() => setCollapsed(!collapsed)}><PanelLeftClose size={18}/><span>Свернуть меню</span></button>
        <div className="environment"><Database size={16}/><span><strong>Демонстрационная среда</strong><small>Тестовый набор данных AIS</small></span><i/></div>
      </div>
    </aside>
    <div className="page-area">{children}</div>
    <footer className="statusbar"><span><i className="ok"/>Все системы работают</span><span>Поток AIS <strong>Демо</strong></span><span>Последнее обновление <strong>14:42:18</strong></span><span className="status-spacer"/><span>UTC+5</span></footer>
    <AssistantLauncher path={path}/>
    {mobileNav && <div className="backdrop" onClick={() => setMobileNav(false)}/>} 
    {searchOpen && <SearchModal onClose={() => setSearchOpen(false)}/>} 
  </div>
}

function NotificationsPopover({unread,onRead,onReadAll,onNavigate}:{unread:Set<string>;onRead:(id:string)=>void;onReadAll:()=>void;onNavigate:(route:string)=>void}){
  return <section className="topbar-popover notifications-popover" role="dialog" aria-label="Уведомления"><header><div><span className="page-eyebrow">Операционные сигналы</span><h2>Уведомления</h2></div><span className="notification-count">{unread.size} новых</span></header><div className="notification-popover-actions"><button onClick={onReadAll} disabled={!unread.size}><CircleCheck size={14}/>Отметить все прочитанными</button></div><div className="notification-popover-list">{headerNotifications.map(item=><button key={item.id} className={`${item.tone} ${unread.has(item.id)?'unread':''}`} onClick={()=>{onRead(item.id);onNavigate(item.route)}}><span className="notification-type-icon">{item.tone==='critical'?<ShieldAlert size={16}/>:item.tone==='warning'?<TriangleAlert size={16}/>:item.tone==='success'?<ShieldCheck size={16}/>:<Info size={16}/>}</span><span><strong>{item.title}</strong><small>{item.detail}</small><time>{item.time} · {item.id}</time></span>{unread.has(item.id)&&<i/>}<ChevronRight size={15}/></button>)}</div><footer><button onClick={()=>onNavigate('/app/settings')}><Settings size={14}/>Настроить уведомления</button></footer></section>
}

function ProfilePopover({onNavigate,onLogout}:{onNavigate:(route:string)=>void;onLogout:()=>void}){
  return <section className="topbar-popover profile-popover" role="dialog" aria-label="Меню профиля"><div className="profile-popover-account"><div className="avatar large">AK</div><span><strong>Аян Касымов</strong><small>analyst@caspian.int</small><em>Демонстрационный аккаунт</em></span></div><div className="profile-popover-menu"><button onClick={()=>onNavigate('/app/settings')}><CircleUserRound size={16}/><span><strong>Профиль и настройки</strong><small>Данные аккаунта и интерфейс</small></span><ChevronRight size={14}/></button><button onClick={()=>onNavigate('/app/investigations')}><Target size={16}/><span><strong>Мои расследования</strong><small>Открытые рабочие материалы</small></span><ChevronRight size={14}/></button></div><div className="profile-popover-session"><span><i/>Сеанс защищён · демо-среда</span><button onClick={onLogout}><LogOut size={15}/>Сменить аккаунт</button></div></section>
}

function SearchModal({ onClose }: { onClose: () => void }) {
  const [query, setQuery] = useState('')
  useEffect(() => { const fn=(e:KeyboardEvent)=>{if(e.key==='Escape')onClose()}; addEventListener('keydown',fn); return()=>removeEventListener('keydown',fn)},[onClose])
  const vesselResults = vessels.filter(v => [v.name,v.imo,v.mmsi].some(x=>x.toLowerCase().includes(query.toLowerCase())))
  const portResults = ports.filter(p => p.name.toLowerCase().includes(query.toLowerCase()))
  return <div className="modal-backdrop" onMouseDown={onClose}><div className="search-modal" onMouseDown={e=>e.stopPropagation()}>
    <div className="search-input"><Search size={21}/><input autoFocus value={query} onChange={e=>setQuery(e.target.value)} placeholder="Название судна, IMO, MMSI или порт"/><kbd>ESC</kbd></div>
    <div className="search-results">
      {!query && <><div className="search-hint"><Sparkles size={17}/><span><strong>Быстрый поиск по платформе</strong>Начните вводить название судна, порт или идентификатор</span></div><h4>Недавние</h4>{vessels.slice(0,3).map(v=><SearchVessel key={v.id} vessel={v} onClose={onClose}/>)}</>}
      {query && <>
        <h4>Суда <span>{vesselResults.length}</span></h4>{vesselResults.map(v=><SearchVessel key={v.id} vessel={v} onClose={onClose}/>) }
        {portResults.length>0 && <><h4>Порты <span>{portResults.length}</span></h4>{portResults.map(p=><button className="search-result" key={p.id} onClick={()=>{navigate(`/app/ports/${p.id}`);onClose()}}><div className="result-icon port"><Anchor size={18}/></div><span><strong>{p.name}</strong><small>{p.country} • {p.vessels} судов</small></span><ChevronRight size={17}/></button>)}</>}
        <button className="search-result cn-search-caspian-action" onClick={()=>{navigate(`/app/caspian/search${query?`?q=${encodeURIComponent(query)}`:''}`);onClose()}}><div className="result-icon"><Globe2 size={18}/></div><span><strong>Искать во всём Каспии</strong><small>Суда, компании, порты, рейсы, события и расследования</small></span><ChevronRight size={17}/></button>
        {!vesselResults.length && !portResults.length && <div className="empty-search"><Search size={28}/><strong>Ничего не найдено</strong><span>Проверьте запрос или попробуйте IMO / MMSI</span></div>}
      </>}
    </div>
    <div className="search-footer"><span><kbd>↑</kbd><kbd>↓</kbd> навигация</span><span><kbd>↵</kbd> открыть</span></div>
  </div></div>
}

function SearchVessel({ vessel, onClose }: { vessel: Vessel; onClose: () => void }) {
  return <button className="search-result" onClick={()=>{navigate(`/app/vessels/${vessel.id}`);onClose()}}><div className="result-icon"><Ship size={18}/></div><span><strong>{vessel.name}</strong><small>IMO {vessel.imo} • {vessel.destination} • {vessel.speed} уз</small></span><span className={`status-pill ${vessel.navigationStatus==='Underway'?'green':''}`}>{navigationStatusLabel(vessel.navigationStatus)}</span><ChevronRight size={17}/></button>
}

function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <div className="page-header"><div>{eyebrow && <span className="page-eyebrow">{eyebrow}</span>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{actions && <div className="header-actions">{actions}</div>}</div>
}

function MapPage() {
  const mapRef = useRef<RealCaspianMapHandle>(null)
  const [selected, setSelected] = useState<Vessel | null>(null)
  const [selectedEvent, setSelectedEvent] = useState<DetectionEvent | null>(null)
  const [layers, setLayers] = useState({ vessels:true, ports:true, routes:true, events:true, risk:false, environmental:true, pollution:true })
  const [environmentalEvents, setEnvironmentalEvents] = useState<EnvironmentalEvent[]>([])
  const [riskLevels, setRiskLevels] = useState<RiskLevel[]>(['CRITICAL','HIGH','MODERATE','LOW'])
  const [layersOpen, setLayersOpen] = useState(true)
  const [mapType, setMapType] = useState<'Standard'|'Satellite'>('Standard')
  const [pointerCoordinate, setPointerCoordinate] = useState({ latitude:41.8642, longitude:50.3741 })
  const [mode, setMode] = useState<'live'|'historical'>('live')
  const [liveFleet, setLiveFleet] = useState(vessels)
  const [streamConnected, setStreamConnected] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [frame, setFrame] = useState(caspianStarTrack.length - 1)
  const [areaTool, setAreaTool] = useState(false)
  const [areaStart, setAreaStart] = useState<{x:number;y:number}|null>(null)
  const [areaRect, setAreaRect] = useState<{x:number;y:number;w:number;h:number}|null>(null)
  useEffect(()=>{
    let active=true
    const token=localStorage.getItem('ci-access-token')||'ci-demo-analyst'
    const loadEnvironmental=()=>fetch(`${API_BASE}/environment/events`,{headers:{Authorization:`Bearer ${token}`}})
        .then(response=>response.ok?response.json():Promise.reject(new Error(`Environmental API ${response.status}`)))
        .then((payload:{items?:EnvironmentalEvent[];events?:EnvironmentalEvent[]}|EnvironmentalEvent[])=>{
          if(!active)return
          const items=Array.isArray(payload)?payload:payload.items||payload.events||[]
          setEnvironmentalEvents(items.filter(item=>!['RESOLVED','FALSE POSITIVE'].includes(item.status.toUpperCase())).slice(0,4))
        })
        .catch(()=>{if(active)setEnvironmentalEvents([])})
    void loadEnvironmental()
    const socket=new WebSocket(`${WS_BASE}/ws/environment?token=${encodeURIComponent(token)}`)
    socket.onmessage=message=>{try{const payload=JSON.parse(message.data) as {type?:string};if(payload.type?.startsWith('environmental_'))void loadEnvironmental()}catch{/* REST snapshot remains authoritative. */}}
    return()=>{active=false;socket.close()}
  },[])
  useEffect(()=>{
    if(!areaRect||areaRect.w<=3||areaRect.h<=3||areaStart)return
    const northWest=mapRef.current?.unprojectPercent(areaRect.x,areaRect.y)
    const southEast=mapRef.current?.unprojectPercent(areaRect.x+areaRect.w,areaRect.y+areaRect.h)
    if(!northWest||!southEast)return
    const round=(value:number)=>Math.round(value*10_000)/10_000
    const bounds={
      west:round(Math.min(northWest.longitude,southEast.longitude)),
      east:round(Math.max(northWest.longitude,southEast.longitude)),
      north:round(Math.max(northWest.latitude,southEast.latitude)),
      south:round(Math.min(northWest.latitude,southEast.latitude)),
      fromTime:'2026-08-09T18:42:00+05:00',
      toTime:'2026-08-10T18:42:00+05:00',
    }
    sessionStorage.setItem('ci-stage8-context',JSON.stringify({page:'/app/map',label:'Выбранная область Каспия',area:'Выделенный район · последние 24 часа',areaBounds:bounds}))
  },[areaRect,areaStart])
  useEffect(()=>{
    if(mode!=='live'||streamConnected) return
    const id=setInterval(()=>setLiveFleet(current=>current.map((v,i)=>v.navigationStatus==='Underway'?{...v,x:Math.max(20,Math.min(78,v.x+(i%2?-.07:.08))),y:Math.max(5,Math.min(96,v.y-.05)),latitude:v.latitude+.0012,longitude:v.longitude+(i%2?-.0015:.0018),lastPositionAt:'just now'}:v)),1800)
    return()=>clearInterval(id)
  },[mode,streamConnected])
  useEffect(()=>{
    if(mode!=='live') return
    const socket=new WebSocket(`${WS_BASE}/ws/vessels?token=ci-demo-analyst`)
    socket.onopen=()=>setStreamConnected(true)
    socket.onmessage=event=>{const message=JSON.parse(event.data);if(message.type!=='position_update')return;const next=message.vessel;setLiveFleet(current=>current.map(v=>v.id===next.id?{...v,x:Math.max(20,Math.min(78,v.x+(next.lon-v.longitude)*6)),y:Math.max(5,Math.min(96,v.y-(next.lat-v.latitude)*6)),latitude:next.lat,longitude:next.lon,speed:next.speed,course:next.course,heading:next.heading||next.course,lastPositionAt:'just now'}:v))}
    socket.onerror=()=>setStreamConnected(false);socket.onclose=()=>setStreamConnected(false)
    return()=>socket.close()
  },[mode])
  useEffect(()=>{
    if(!playing||mode!=='historical') return
    const id=setInterval(()=>setFrame(value=>value>=caspianStarTrack.length-1?0:value+1),900)
    return()=>clearInterval(id)
  },[playing,mode])
  const historicalVessel={...vessels[0],x:caspianStarTrack[frame].x,y:caspianStarTrack[frame].y,latitude:caspianStarTrack[frame].latitude,longitude:caspianStarTrack[frame].longitude,speed:caspianStarTrack[frame].speed,course:caspianStarTrack[frame].course,lastPositionAt:caspianStarTrack[frame].time}
  const drawPoint=(e:React.PointerEvent<HTMLDivElement>)=>{const b=e.currentTarget.getBoundingClientRect();return{x:(e.clientX-b.left)/b.width*100,y:(e.clientY-b.top)/b.height*100}}
  return <div className="map-page">
    <div className="map-title-row"><div><span className="page-eyebrow">Операционная картина</span><h1>Каспийское море</h1></div><div className="time-mode"><button className={mode==='live'?'active':''} onClick={()=>{setMode('live');setPlaying(false)}}><i/> В РЕАЛЬНОМ ВРЕМЕНИ</button><button className={mode==='historical'?'active':''} onClick={()=>setMode('historical')}><History size={14}/> История</button></div><div className="map-summary"><span className="stream-status"><RadioTower size={12}/>{streamConnected?'WebSocket подключён':'Демонстрационный поток'}</span><span><i className="green-dot"/>36 в движении</span><span>84 судна в регионе</span><span>9 портов</span></div></div>
    <div className="map-canvas">
      <CaspianMap ref={mapRef} selected={selected} onSelect={v=>{setSelected(v);setSelectedEvent(null)}} onEventSelect={event=>{setSelectedEvent(event);setSelected(null)}} layers={layers} riskLevels={riskLevels} mapType={mapType} onPointerCoordinate={setPointerCoordinate} vesselData={mode==='live'?liveFleet:[historicalVessel]} track={mode==='historical'?caspianStarTrack.slice(0,frame+1):undefined} activeTrackPoint={mode==='historical'?caspianStarTrack[frame]:undefined} environmentalEvents={environmentalEvents}/>
      <div className="map-mode"><button className={mapType==='Standard'?'active':''} onClick={()=>setMapType('Standard')}>Карта</button><button className={`${mapType==='Satellite'?'active':''} ${!satelliteMapAvailable?'map-type-unavailable':''}`} disabled={!satelliteMapAvailable} title={satelliteMapAvailable?'Спутниковая подложка':'Укажите VITE_MAP_SATELLITE_STYLE_URL для лицензированного спутникового слоя'} onClick={()=>setMapType('Satellite')}>Спутник</button></div>
      <div className="map-tools"><button aria-label="Приблизить" onClick={()=>mapRef.current?.zoomIn()}><ZoomIn size={18}/></button><button aria-label="Отдалить" onClick={()=>mapRef.current?.zoomOut()}><ZoomOut size={18}/></button><hr/><button aria-label="Показать весь Каспий" onClick={()=>mapRef.current?.reset()}><LocateFixed size={18}/></button><hr/><button className={areaTool?'active':''} title="Поиск по области" onClick={()=>{setAreaTool(!areaTool);setAreaRect(null)}}><Crosshair size={18}/></button></div>
      <div className={`layers-card ${layersOpen?'':'closed'}`}>
        <button className="layers-head" onClick={()=>setLayersOpen(!layersOpen)}><span><Layers3 size={18}/>Слои карты</span><ChevronDown size={17}/></button>
        {layersOpen && <div className="layer-list">
          <LayerToggle icon={<Ship size={16}/>} label="Суда" count="84" checked={layers.vessels} onChange={()=>setLayers({...layers,vessels:!layers.vessels})}/>
          <LayerToggle icon={<Anchor size={16}/>} label="Порты" count="9" checked={layers.ports} onChange={()=>setLayers({...layers,ports:!layers.ports})}/>
          <LayerToggle icon={<Route size={16}/>} label="Маршруты" checked={layers.routes} onChange={()=>setLayers({...layers,routes:!layers.routes})}/>
          <LayerToggle icon={<TriangleAlert size={16}/>} label="События" count="6" checked={layers.events} onChange={()=>setLayers({...layers,events:!layers.events})}/>
          <LayerToggle icon={<ShieldAlert size={16}/>} label="Оценка риска" count="4" checked={layers.risk} onChange={()=>setLayers({...layers,risk:!layers.risk})}/>
          <LayerToggle icon={<Leaf size={16}/>} label={t('map.environmentalEvents')} count={`${environmentalEvents.length||4}`} checked={layers.environmental} onChange={()=>setLayers({...layers,environmental:!layers.environmental})}/>
          <LayerToggle icon={<Droplets size={16}/>} label={t('map.pollutionAreas')} count="1" checked={layers.pollution} onChange={()=>setLayers({...layers,pollution:!layers.pollution})}/>
          <div className="future-layers"><span>Дополнительные слои</span><div><EyeOff size={15}/>Якорные зоны</div><div><EyeOff size={15}/>Разрывы AIS</div></div>
        </div>}
      </div>
      {layers.risk&&<div className="risk-map-filter"><span>Показывать риск</span>{(['CRITICAL','HIGH','MODERATE','LOW'] as RiskLevel[]).map(level=><button key={level} className={`${level.toLowerCase()} ${riskLevels.includes(level)?'active':''}`} onClick={()=>setRiskLevels(current=>current.includes(level)?current.filter(item=>item!==level):[...current,level])}><i/>{riskLevelLabel(level)}</button>)}</div>}
      <div className={`map-legend ${layers.risk?'risk-legend':''}`}>{layers.risk?<><span><i className="risk-dot critical"/>Критический</span><span><i className="risk-dot high"/>Высокий</span><span><i className="risk-dot moderate"/>Умеренный</span><span><i className="risk-dot low"/>Низкий</span></>:<><span><i className="vessel-legend underway"/>В движении</span><span><i className="vessel-legend anchor"/>На якоре</span><span><i className="port-legend"/>Порт</span></>}</div>
      <div className="coordinates">{Math.abs(pointerCoordinate.latitude).toFixed(4)}° {pointerCoordinate.latitude>=0?'N':'S'}&nbsp;&nbsp; {Math.abs(pointerCoordinate.longitude).toFixed(4)}° {pointerCoordinate.longitude>=0?'E':'W'}</div>
      {mode==='historical' && <PlaybackBar frame={frame} setFrame={setFrame} playing={playing} setPlaying={setPlaying}/>} 
      {areaTool && <div className="area-draw-layer" onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);const p=drawPoint(e);setAreaStart(p);setAreaRect({x:p.x,y:p.y,w:0,h:0})}} onPointerMove={e=>{if(!areaStart)return;const p=drawPoint(e);setAreaRect({x:Math.min(areaStart.x,p.x),y:Math.min(areaStart.y,p.y),w:Math.abs(p.x-areaStart.x),h:Math.abs(p.y-areaStart.y)})}} onPointerUp={()=>setAreaStart(null)}>{areaRect&&<div className="search-area" style={{left:`${areaRect.x}%`,top:`${areaRect.y}%`,width:`${areaRect.w}%`,height:`${areaRect.h}%`}}/>}<span className="draw-instruction"><Crosshair size={15}/>Потяните по карте, чтобы выбрать область</span></div>}
      {areaRect && areaRect.w>3 && !areaStart && <div className="area-results"><div className="area-results-head"><span><Crosshair size={16}/>Поиск по области</span><button onClick={()=>{setAreaRect(null);setAreaTool(false);sessionStorage.removeItem('ci-stage8-context')}}><X size={16}/></button></div><label>Период<div><input type="date" defaultValue="2026-08-10"/><input type="time" defaultValue="02:00"/><span>—</span><input type="time" defaultValue="08:00"/></div></label><div className="found-vessels"><strong>12</strong><span>судов находились<br/>в выбранной области</span></div><button className="secondary-button full" onClick={()=>navigate('/app/assistant?q='+encodeURIComponent('Что происходило здесь за последние 24 часа?'))}><Sparkles size={14}/>{t('map.askAssistant')}</button><button className="primary-button full" onClick={()=>navigate('/app/history')}>Показать результаты <ArrowRight size={15}/></button></div>}
      <MapObjectInspector vessel={selected} event={selectedEvent} onClose={()=>{setSelected(null);setSelectedEvent(null)}}/>
    </div>
  </div>
}

function PlaybackBar({frame,setFrame,playing,setPlaying}:{frame:number;setFrame:(n:number)=>void;playing:boolean;setPlaying:(v:boolean)=>void}) {
  const point=caspianStarTrack[frame]
  return <div className="playback-bar"><button className="play-button" onClick={()=>setPlaying(!playing)}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</button><div className="playback-date"><span>Исторический режим</span><strong>10 августа 2026 · {point.time}</strong></div><div className="scrubber"><input type="range" min="0" max={caspianStarTrack.length-1} value={frame} onChange={e=>setFrame(Number(e.target.value))}/><div><span>08:00</span><span>12:00</span><span>16:00</span><span>18:42</span></div></div><select defaultValue="1"><option value="1">1×</option><option value="2">2×</option><option value="4">4×</option></select><button className="close-playback" onClick={()=>setPlaying(false)}><TimerReset size={17}/></button></div>
}

function LayerToggle({ icon,label,count,checked,onChange }:{icon:ReactNode,label:string,count?:string,checked:boolean,onChange:()=>void}) {
  return <label className="layer-toggle"><span className="layer-icon">{icon}</span><span>{label}</span>{count&&<small>{count}</small>}<input type="checkbox" checked={checked} onChange={onChange}/><i/></label>
}

function environmentalMapRings(event: EnvironmentalEvent): number[][][] {
  const geometry=event.geometry
  if(!geometry||!Array.isArray(geometry.coordinates))return []
  if(geometry.type==='Polygon')return geometry.coordinates as number[][][]
  if(geometry.type==='MultiPolygon')return (geometry.coordinates as number[][][][]).flatMap(polygon=>polygon)
  return []
}

function projectEnvironmentalPoint(longitude:number,latitude:number):[number,number]{
  const clamp=(value:number)=>Math.max(2,Math.min(98,value))
  return [clamp((longitude-47)/.07),clamp((46.5-latitude)/.1)]
}

type CaspianMapProps = {
  selected?: Vessel|null
  onSelect?: (v:Vessel)=>void
  onEventSelect?:(event:DetectionEvent)=>void
  onPointerCoordinate?:(coordinate:{latitude:number;longitude:number})=>void
  layers:{vessels:boolean;ports:boolean;routes:boolean;events?:boolean;risk?:boolean;environmental?:boolean;pollution?:boolean}
  riskLevels?:RiskLevel[]
  zoom?:number
  mini?:boolean
  mapType?:'Standard'|'Satellite'
  vesselData?:Vessel[]
  track?:TrackPoint[]
  activeTrackPoint?:TrackPoint
  environmentalEvents?:EnvironmentalEvent[]
  customAreas?:RealMapArea[]
  customAnnotations?:RealMapAnnotation[]
}

const caspianRouteDefinitions: Array<{id:string;from:string;to:string}> = [
  {id:'baku-aktau',from:'baku',to:'aktau'},
  {id:'alat-kuryk',from:'alat',to:'kuryk'},
  {id:'aktau-turkmenbashi',from:'aktau',to:'turkmenbashi'},
  {id:'astrakhan-aktau',from:'astrakhan',to:'aktau'},
  {id:'anzali-turkmenbashi',from:'anzali',to:'turkmenbashi'},
]

const trackAnnotationLabels:Partial<Record<NonNullable<TrackPoint['kind']>,string>>={
  departure:'Отправление',stop:'Остановка',course:'Изменение курса',gap:'Пропуск AIS',restored:'AIS восстановлен',arrival:'Прибытие',position:'Позиция',
}

const CaspianMap=forwardRef<RealCaspianMapHandle,CaspianMapProps>(function CaspianMap({
  selected,onSelect,onEventSelect,onPointerCoordinate,layers,riskLevels,mini=false,mapType='Standard',vesselData=vessels,track,activeTrackPoint,environmentalEvents=[],customAreas=[],customAnnotations=[],
},ref){
  const visibleVessels=layers.risk&&riskLevels?vesselData.filter(v=>riskLevels.includes(v.riskLevel)):vesselData
  const routeLines:RealMapLine[]=layers.routes?caspianRouteDefinitions.flatMap(route=>{
    const from=ports.find(port=>port.id===route.from);const to=ports.find(port=>port.id===route.to)
    if(!from||!to)return []
    return [{id:route.id,coordinates:[[from.longitude,from.latitude],[to.longitude,to.latitude]],label:`${from.name} — ${to.name}`,color:'#4d8a82',dashed:true}]
  }):[]
  const areas:RealMapArea[]=layers.pollution?environmentalEvents.flatMap(event=>environmentalMapRings(event).map((ring,index)=>({
    id:`${event.id}-${index}`,rings:[ring],kind:'pollution' as const,label:event.title||event.type,
  }))):[]
  const environmentalPoints=layers.environmental?environmentalEvents.flatMap(event=>{
    const longitude=event.center?.longitude;const latitude=event.center?.latitude
    if(!Number.isFinite(longitude)||!Number.isFinite(latitude))return []
    return [{id:event.id,title:event.id.replace('ENV-2026-','ENV-'),longitude:Number(longitude),latitude:Number(latitude),detail:`${event.title||event.type} · ${event.area_km2} km²`}]
  }):[]
  const annotations=[
    ...(track||[]).filter(point=>point.kind).map(point=>({id:`track-${point.id}`,label:trackAnnotationLabels[point.kind!]||point.time,longitude:point.longitude,latitude:point.latitude,color:point.kind==='gap'?'#c5652f':'#276f67',detail:`${point.time} · ${point.speed} уз`})),
    ...(activeTrackPoint?[{id:`active-${activeTrackPoint.id}`,label:activeTrackPoint.time,longitude:activeTrackPoint.longitude,latitude:activeTrackPoint.latitude,color:'#183f3a',detail:`${activeTrackPoint.speed} уз · ${activeTrackPoint.course}°`}]:[]),
  ]
  return <RealCaspianMap
    ref={ref}
    compact={mini}
    mode={mapType==='Satellite'?'satellite':'standard'}
    ariaLabel="Реальная интерактивная карта Каспийского моря"
    clusterVessels={!mini&&visibleVessels.length>12}
    ports={layers.ports?ports.map(port=>({id:port.id,name:port.name,longitude:port.longitude,latitude:port.latitude,status:port.status,detail:`${countryLabel(port.country)} · ${port.vessels} судов`})):[]}
    vessels={layers.vessels?visibleVessels.map(vessel=>({id:vessel.id,name:vessel.name,longitude:vessel.longitude,latitude:vessel.latitude,course:vessel.course,status:vessel.navigationStatus,speed:vessel.speed,risk:layers.risk?vessel.risk:undefined,riskLevel:layers.risk?vessel.riskLevel:undefined,detail:`${vessel.speed} уз · ${operationalText(vessel.destination)}`,selected:selected?.id===vessel.id})):[]}
    events={layers.events?detectedEvents.map(event=>({id:event.id,title:event.title,longitude:event.longitude,latitude:event.latitude,severity:event.severity,detail:`${event.vesselName} · ${event.summary}`})):[]}
    environmentalEvents={environmentalPoints}
    routes={routeLines}
    tracks={track&&track.length>1?[{id:'active-voyage-track',coordinates:track.map(point=>[point.longitude,point.latitude]),kind:'track',color:'#a9612b'}]:[]}
    areas={[...areas,...customAreas]}
    annotations={[...annotations,...customAnnotations]}
    onPortSelect={id=>navigate(`/app/ports/${id}`)}
    onVesselSelect={id=>{const vessel=visibleVessels.find(item=>item.id===id);if(vessel)onSelect?.(vessel)}}
    onEventSelect={id=>{const event=detectedEvents.find(item=>item.id===id);if(event)onEventSelect?.(event)}}
    onEnvironmentalSelect={id=>navigate(`/app/environment/events/${id}`)}
    onPointerCoordinate={onPointerCoordinate}
  />
})

function LegacyCaspianMap({ selected, onSelect, onEventSelect, layers, riskLevels, zoom=1, mini=false, vesselData=vessels, track, activeTrackPoint, environmentalEvents=[] }: { selected?: Vessel|null; onSelect?: (v:Vessel)=>void;onEventSelect?:(event:DetectionEvent)=>void;layers:{vessels:boolean;ports:boolean;routes:boolean;events?:boolean;risk?:boolean;environmental?:boolean;pollution?:boolean};riskLevels?:RiskLevel[];zoom?:number;mini?:boolean;vesselData?:Vessel[];track?:TrackPoint[];activeTrackPoint?:TrackPoint;environmentalEvents?:EnvironmentalEvent[] }) {
  const clustered=zoom<.95&&!mini
  const visibleVessels=layers.risk&&riskLevels?vesselData.filter(v=>riskLevels.includes(v.riskLevel)):vesselData
  return <div className={`caspian-map ${mini?'mini-map':''}`}>
    <div className="map-grid" />
    <div className="map-content" style={{transform:`scale(${zoom})`}}>
      <svg className="sea-shape" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Схематическая карта Каспийского моря">
        <path className="sea" d="M38,0 C48,2 60,9 61,19 C62,29 54,34 58,42 C63,52 78,55 78,67 C79,79 68,88 64,97 L34,100 C28,94 34,83 30,76 C25,67 18,61 20,51 C22,40 33,35 31,25 C29,15 28,5 38,0Z"/>
        <path className="coast" d="M38,0 C48,2 60,9 61,19 C62,29 54,34 58,42 C63,52 78,55 78,67 C79,79 68,88 64,97 L34,100 C28,94 34,83 30,76 C25,67 18,61 20,51 C22,40 33,35 31,25 C29,15 28,5 38,0Z"/>
        {layers.routes && <g className="route-lines"><path d="M35,60 Q50,43 72,28"/><path d="M37,67 Q56,70 77,64"/><path d="M29,35 Q48,31 70,37"/><path d="M39,94 Q54,76 63,96"/></g>}
      </svg>
      {layers.pollution&&environmentalEvents.length>0&&<svg className="environmental-map-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Pollution areas">{environmentalEvents.flatMap(event=>environmentalMapRings(event).map((ring,index)=><polygon key={`${event.id}-${index}`} points={ring.map(point=>projectEnvironmentalPoint(point[0],point[1]).join(',')).join(' ')} className={event.id==='ENV-2026-00142'?'primary':''}/>))}</svg>}
      {track && <svg className="track-overlay" viewBox="0 0 100 100" preserveAspectRatio="none"><polyline points={track.map(p=>`${p.x},${p.y}`).join(' ')} />{track.map(p=><circle key={p.id} cx={p.x} cy={p.y} r={p.kind?'.7':'.35'} className={p.kind||''}/>)}</svg>}
      <div className="country-label russia">РОССИЯ</div><div className="country-label kazakhstan">КАЗАХСТАН</div><div className="country-label azerbaijan">АЗЕРБАЙДЖАН</div><div className="country-label turkmenistan">ТУРКМЕНИСТАН</div><div className="country-label iran">ИРАН</div><div className="sea-label">КАСПИЙСКОЕ МОРЕ<span>Каспийское море</span></div>
      {layers.ports && ports.map(p=><button key={p.id} className="port-marker" style={{left:`${p.x}%`,top:`${p.y}%`}} title={`${p.name}, ${p.country}`}><span><Anchor size={11}/></span><label>{p.name}</label></button>)}
      {layers.vessels && clustered && <><button className="vessel-cluster" style={{left:'45%',top:'30%'}} onClick={()=>{}}><strong>34</strong><span>судна</span></button><button className="vessel-cluster" style={{left:'52%',top:'60%'}}><strong>18</strong><span>судов</span></button><button className="vessel-cluster" style={{left:'56%',top:'83%'}}><strong>7</strong><span>судов</span></button></>}
      {layers.vessels && !clustered && visibleVessels.map(v=><button key={v.id} className={`vessel-marker ${selected?.id===v.id?'selected':''} ${v.navigationStatus!=='Underway'?'stationary':''} ${zoom>1.08?'with-label':''} ${layers.risk?`risk-vessel risk-${v.riskLevel.toLowerCase()}`:''}`} style={{left:`${v.x}%`,top:`${v.y}%`,transform:`rotate(${v.course}deg)`}} onClick={()=>onSelect?.(v)} title={layers.risk?`${v.name}: risk ${v.risk}`:v.name}><Navigation size={mini?11:15} fill="currentColor"/><span className="marker-pulse"/>{layers.risk&&<b className="risk-marker-score" style={{transform:`rotate(${-v.course}deg)`}}>{v.risk}</b>}{zoom>1.08&&!mini&&<label style={{transform:`rotate(${-v.course}deg)`}}><strong>{v.name}</strong>{layers.risk?`${v.riskLevel} · ${v.risk}/100`:`${v.speed} kn`}</label>}</button>)}
      {layers.events && detectedEvents.map(event=><button key={event.id} className={`event-map-marker ${event.severity}`} style={{left:`${event.x}%`,top:`${event.y}%`}} onClick={()=>onEventSelect?.(event)} title={`${event.title}: ${event.vesselName}`}><TriangleAlert size={mini?11:14} fill="currentColor"/>{!mini&&zoom>1.08&&<label>{event.title}</label>}</button>)}
      {layers.environmental && environmentalEvents.map(event=>{const point=projectEnvironmentalPoint(event.center?.longitude||0,event.center?.latitude||0);return <button key={event.id} className="environmental-event-marker" style={{left:`${point[0]}%`,top:`${point[1]}%`}} onClick={()=>navigate(`/app/environment/events/${event.id}`)} title={`${event.id}: ${event.title||event.type}`}><Leaf size={mini?11:14} fill="currentColor"/>{!mini&&<label><strong>{event.id.replace('ENV-2026-','ENV-')}</strong><span>{event.area_km2} km² · {Math.round(event.confidence*100)}%</span></label>}</button>})}
      {activeTrackPoint&&<div className="track-tooltip" style={{left:`${activeTrackPoint.x}%`,top:`${activeTrackPoint.y}%`}}><strong>{activeTrackPoint.time}</strong><span>{activeTrackPoint.speed} kn · {String(activeTrackPoint.course).padStart(3,'0')}°</span><small>{activeTrackPoint.latitude.toFixed(3)} / {activeTrackPoint.longitude.toFixed(3)}</small></div>}
    </div>
  </div>
}

function MapObjectInspector({vessel,event,onClose}:{vessel:Vessel|null;event:DetectionEvent|null;onClose:()=>void}) {
  if(vessel)return <VesselDrawer vessel={vessel} onClose={onClose}/>
  if(event)return <EventDrawer event={event} onClose={onClose}/>
  return null
}

function VesselDrawer({ vessel, onClose }: { vessel: Vessel; onClose: () => void }) {
  const [section,setSection]=useState<'overview'|'risk'|'voyage'|'events'>('overview')
  const assessment=riskAssessments.find(item=>item.vesselId===vessel.id)
  const vesselEvents=detectedEvents.filter(item=>item.vesselId===vessel.id).slice(0,3)
  return <aside className="vessel-drawer map-object-inspector">
    <div className="drawer-head"><div className="vessel-avatar"><Ship size={22}/></div><div><span className="page-eyebrow">Выбранное судно</span><h2>{vessel.name}</h2></div><button onClick={onClose}><X size={19}/></button></div>
    <div className="vessel-meta"><span>{vesselTypeLabel(vessel.type)}</span><i/> <span>IMO {vessel.imo}</span></div>
    <div className="flag-row"><span className={`flag flag-${vessel.flagCode.toLowerCase()}`}/>{countryLabel(vessel.flag)}<span className={`status-pill green`}>{navigationStatusLabel(vessel.navigationStatus)}</span></div>
    <nav className="map-inspector-tabs" aria-label="Данные выбранного судна"><button className={section==='overview'?'active':''} onClick={()=>setSection('overview')}>Обзор</button><button className={section==='risk'?'active':''} onClick={()=>setSection('risk')}>Риск</button><button className={section==='voyage'?'active':''} onClick={()=>setSection('voyage')}>Рейс</button><button className={section==='events'?'active':''} onClick={()=>setSection('events')}>События</button></nav>
    {section==='overview'&&<div className="map-inspector-panel"><div className="drawer-section"><h4>Навигационные данные <span><Radio size={13}/>СЕЙЧАС</span></h4><div className="metric-grid"><Metric label="Скорость" value={`${vessel.speed}`} unit="уз" icon={<Waves size={16}/>}/><Metric label="Курс" value={String(vessel.course).padStart(3,'0')} unit="°" icon={<Compass size={16}/>}/><Metric label="Осадка" value={`${vessel.draught}`} unit="м" icon={<Anchor size={16}/>}/><Metric label="Направление" value={`${vessel.heading}`} unit="°" icon={<Navigation size={16}/>}/></div></div><div className="risk-block quality-block"><div className="risk-score"><span>99</span><small>%</small></div><div><span>Качество позиции</span><strong>Проверено</strong><small>Демо AIS · замечаний нет</small></div><ShieldCheck size={22}/></div><div className="position-note"><Clock3 size={15}/>Позиция обновлена {relativeTimeLabel(vessel.lastPositionAt)}</div></div>}
    {section==='risk'&&<div className="map-inspector-panel"><div className="map-inspector-quick-risk"><strong>{assessment?.score??vessel.risk}</strong><span><b>{assessment?riskLevelLabel(assessment.level):riskLevelLabel(vessel.riskLevel)}</b><small>{assessment?.delta?`+${assessment.delta} за ${assessment.deltaWindow}`:'Текущая оценка'}</small></span></div><div className="drawer-section"><h4>Основные причины</h4><div className="factor-evidence">{assessment?.factors.slice(0,3).map(factor=><span key={factor.id}><TriangleAlert size={12}/>{operationalText(factor.title)} · +{factor.effectiveScore??factor.adjustedScore}</span>)??<span>Подробные факторы пока недоступны</span>}</div></div><button className="secondary-button full" onClick={()=>navigate(`/app/vessels/${vessel.id}?tab=risk`)}>Все факторы и доказательства <ArrowRight size={15}/></button></div>}
    {section==='voyage'&&<div className="map-inspector-panel"><div className="voyage-brief"><div><small>Маршрут</small><strong>Баку <ArrowRight size={15}/> {operationalText(vessel.destination)}</strong></div><div><small>Расчётное прибытие</small><strong>{vessel.calculatedEta}</strong></div><div className="progress"><i style={{width:'66%'}}/><span style={{left:'66%'}}/></div><div className="voyage-cities"><span>Баку</span><span>{operationalText(vessel.destination)}</span></div></div><div className="drawer-section"><InfoRow label="Пройдено" value="258 км"/><InfoRow label="Осталось" value="129 км"/><InfoRow label="Средняя скорость" value="11.8 уз"/></div></div>}
    {section==='events'&&<div className="map-inspector-panel"><div className="drawer-section"><h4>Последние события</h4>{vesselEvents.length?vesselEvents.map(item=><button className="map-inspector-event" key={item.id} onClick={()=>navigate(`/app/events?event=${item.id}`)}><span className={`event-type-icon ${item.severity}`}><EventTypeIcon type={item.type} size={14}/></span><span><strong>{item.title}</strong><small>{item.time} · {item.id}</small></span><ChevronRight size={14}/></button>):<p>Событий для текущего судна нет.</p>}</div></div>}
    <button className="primary-button full" onClick={()=>navigate(`/app/vessels/${vessel.id}`)}>Открыть профиль судна <ArrowRight size={17}/></button>
  </aside>
}

const eventLabels:Record<DetectionEvent['type'],string>={route_deviation:'Отклонение маршрута',ais_gap:'Разрыв AIS',unusual_stop:'Нетипичная остановка',unexpected_speed:'Нетипичная скорость',vessel_encounter:'Встреча судов',draught_change:'Изменение осадки',cargo_anomaly:'Несоответствие груза',cargo_draught_mismatch:'Груз / осадка',fuel_anomaly:'Расход топлива',economic_anomaly:'Экономическая согласованность',unusual_connection:'Нетипичная связь'}

function EventTypeIcon({type,size=18}:{type:DetectionEvent['type'];size?:number}){if(type==='ais_gap')return <WifiOff size={size}/>;if(type==='vessel_encounter'||type==='unusual_connection')return <Users size={size}/>;if(type==='draught_change'||type==='cargo_draught_mismatch')return <Droplets size={size}/>;if(type==='fuel_anomaly')return <Fuel size={size}/>;if(type==='economic_anomaly')return <CircleDollarSign size={size}/>;if(type==='cargo_anomaly')return <Package size={size}/>;if(type==='unexpected_speed')return <Gauge size={size}/>;if(type==='route_deviation')return <GitCompareArrows size={size}/>;return <Anchor size={size}/>}

function EventDrawer({event,onClose}:{event:DetectionEvent;onClose:()=>void}){
  const [reviewed,setReviewed]=useState(event.status==='reviewed')
  return <aside className="vessel-drawer event-drawer map-object-inspector"><div className="drawer-head"><div className={`event-type-icon ${event.severity}`}><EventTypeIcon type={event.type} size={20}/></div><div><span className="page-eyebrow">{event.id} · Морское событие</span><h2>{event.title}</h2></div><button onClick={onClose}><X size={19}/></button></div><div className="event-subject"><div><small>Судно</small><strong>{event.vesselName}{event.relatedVessel&&<> <span>+</span> {event.relatedVessel}</>}</strong></div><span className={`severity ${event.severity}`}>{event.severity==='high'?'ВЫСОКАЯ':event.severity==='medium'?'СРЕДНЯЯ':'НИЗКАЯ'}</span></div><div className="event-score-row"><div><span>Значимость</span><strong className={event.severity}>{event.severity==='high'?'Высокая':event.severity==='medium'?'Средняя':'Низкая'}</strong><small>Важность события</small></div><div><span>Достоверность</span><strong>{event.confidence}%</strong><small>Уверенность детектора</small></div><div><span>Статус</span><strong>{reviewed?'ПРОСМОТРЕНО':event.status==='active'?'АКТИВНО':event.status.toUpperCase()}</strong><small>{event.endedAt?'Событие завершено':'Наблюдается сейчас'}</small></div></div><div className="drawer-section"><h4>Наблюдаемые параметры</h4><div className="event-metrics">{event.metrics.map(metric=><div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong>{metric.baseline&&<small>{metric.baseline}</small>}</div>)}</div></div>{event.type==='ais_gap'&&<div className="possible-area-card"><div className="possible-radar"><span/><i/><b/></div><div><span>Возможная область движения</span><strong>Радиус до 72 км</strong><small>Расчёт по последней скорости и длительности отсутствия данных</small></div></div>}<div className="explanation-block"><div><BrainCircuit size={17}/><span>Объяснение детектора</span></div><p>{event.explanation}</p><ul>{event.factors.map(f=><li key={f}><Check size={12}/>{f}</li>)}</ul></div><div className="event-time-block"><div><span>Начало</span><strong>{event.startedAt}</strong></div><div><span>{event.endedAt?'Завершение':'Текущая длительность'}</span><strong>{event.endedAt||'Активно'}</strong></div></div><div className="human-decision"><Info size={15}/><span>Система обнаружила отклонение и собрала факты. Окончательная интерпретация остаётся за аналитиком.</span></div><div className="drawer-actions"><button className="secondary-button" onClick={()=>navigate('/app/vessels/caspian-star?tab=track')}><Play size={15}/>Повтор</button></div><button className={`primary-button full ${reviewed?'reviewed':''}`} onClick={()=>setReviewed(true)}>{reviewed?<><CircleCheck size={17}/>Отмечено как просмотренное</>:<>Отметить как просмотренное <ArrowRight size={16}/></>}</button></aside>
}

function Metric({label,value,unit,icon}:{label:string;value:string;unit:string;icon:ReactNode}) { return <div className="metric"><span>{icon}{label}</span><strong>{value}<small>{unit}</small></strong></div> }

function VesselsPage() {
  const [q,setQ]=useState(''); const [status,setStatus]=useState('Все статусы')
  const filtered=vessels.filter(v=>v.name.includes(q.toUpperCase())&&(status==='Все статусы'||v.navigationStatus===status))
  return <div className="content-page"><PageHeader eyebrow="Реестр флота" title="Суда" description="Текущая операционная обстановка по судам в Каспийском регионе." actions={<button className="secondary-button"><Plus size={17}/>Добавить в список</button>}/>
    <div className="stat-strip"><Stat label="Всего в регионе" value="84" trend="+6 за сутки"/><Stat label="В движении" value="36" dot="green"/><Stat label="В портах" value="31"/><Stat label="На якоре" value="17"/><Stat label="Требуют внимания" value="3" dot="amber"/></div>
    <div className="table-card"><div className="table-toolbar"><div className="inline-search"><Search size={17}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Поиск по названию, IMO или MMSI"/></div><select value={status} onChange={e=>setStatus(e.target.value)}><option>Все статусы</option><option value="Underway">В пути</option><option value="At anchor">На якоре</option><option value="Moored">У причала</option></select><button className="secondary-button"><ListFilter size={16}/>Фильтры</button><span className="results-count">{filtered.length} записей</span></div>
      <div className="mobile-record-list">{filtered.map(v=><button className="mobile-record-card" key={v.id} onClick={()=>navigate(`/app/vessels/${v.id}`)}><span className="mobile-record-icon"><Ship size={18}/></span><span className="mobile-record-main"><strong>{v.name}</strong><small>IMO {v.imo} · {vesselTypeLabel(v.type)}</small><span>{countryLabel(v.flag)} · {v.destination}</span></span><span className={`status-pill ${v.navigationStatus==='Underway'?'green':''}`}>{navigationStatusLabel(v.navigationStatus)}</span><span className="mobile-record-meta"><span>Скорость<b>{v.speed} уз</b></span><span>Курс<b>{String(v.course).padStart(3,'0')}°</b></span><span>ETA<b>{etaLabel(v.reportedEta)}</b></span></span></button>)}</div>
      <div className="table-scroll desktop-data-table"><table><thead><tr><th>Судно</th><th>Тип / флаг</th><th>Статус</th><th>Скорость</th><th>Курс</th><th>Назначение</th><th>ETA</th><th>Обновлено</th><th/></tr></thead><tbody>{filtered.map(v=><tr key={v.id} onClick={()=>navigate(`/app/vessels/${v.id}`)}><td><div className="vessel-cell"><span><Ship size={17}/></span><div><strong>{v.name}</strong><small>IMO {v.imo}</small></div></div></td><td>{vesselTypeLabel(v.type)}<small className="cell-sub">{countryLabel(v.flag)}</small></td><td><span className={`status-pill ${v.navigationStatus==='Underway'?'green':''}`}>{navigationStatusLabel(v.navigationStatus)}</span></td><td className="mono">{v.speed} уз</td><td className="mono">{String(v.course).padStart(3,'0')}°</td><td><strong className="medium">{v.destination}</strong></td><td className="mono">{etaLabel(v.reportedEta)}</td><td>{relativeTimeLabel(v.lastPositionAt)}</td><td><ChevronRight size={17}/></td></tr>)}</tbody></table></div>
    </div>
  </div>
}

function Stat({label,value,trend,dot}:{label:string;value:string;trend?:string;dot?:string}) {return <div className="stat"><span>{dot&&<i className={dot}/>} {label}</span><strong>{value}</strong>{trend&&<small>{trend}</small>}</div>}

function VesselProfile({ vessel }: { vessel: Vessel }) {
  const requestedTab=new URLSearchParams(window.location.search).get('tab')
  const [tab,setTab]=useState(requestedTab==='environment'?'Экология':requestedTab==='risk'?'Риск':requestedTab==='behavior'?'Поведение':requestedTab==='track'?'Трек':requestedTab==='events'?'События':'Обзор')
  const tabs=['Обзор','Текущий рейс','Трек','История','Поведение','События','Риск','Экология','Связи','Аналитика']
  return <div className="content-page profile-page"><button className="back-link" onClick={()=>navigate('/app/vessels')}><ArrowLeft size={16}/>К реестру судов</button>
    <div className="profile-hero"><div className="profile-ship"><Ship size={29}/></div><div><div className="title-line"><h1>{vessel.name}</h1><span className="status-pill green">{navigationStatusLabel(vessel.navigationStatus)}</span><GlobalIdentityBadge vesselId={vessel.id} navigate={navigate}/></div><p>{vesselTypeLabel(vessel.type)} <i/> IMO {vessel.imo} <i/> MMSI {vessel.mmsi}</p><div className="flag-row"><span className={`flag flag-${vessel.flagCode.toLowerCase()}`}/>{countryLabel(vessel.flag)}</div></div><div className="profile-actions"><button className="secondary-button" onClick={()=>navigate('/app/map')}><MapPin size={17}/>Показать на карте</button><button className="icon-button"><Bell size={18}/></button></div></div>
    <div className="tabs">{tabs.map(t=><button key={t} onClick={()=>setTab(t)} className={tab===t?'active':''}>{t}</button>)}</div>
    {tab==='Обзор' && <Overview vessel={vessel} onRisk={()=>setTab('Риск')}/>} {tab==='Текущий рейс' && <VoyageView vessel={vessel}/>} {tab==='Трек' && <TrackHistoryView vessel={vessel}/>} {tab==='История' && <HistoryView/>} {tab==='Поведение' && <BehaviorView vessel={vessel}/>} {tab==='События' && <VesselEventsView vessel={vessel}/>} {tab==='Риск' && <VesselRiskView vessel={vessel}/>} {tab==='Экология' && <VesselEnvironmentTab vesselId={vessel.id} navigate={navigate}/>} {tab==='Связи' && <ConnectionsView/>} {tab==='Аналитика' && <AdvancedProfileView vessel={vessel}/>} 
  </div>
}

function Overview({vessel,onRisk}:{vessel:Vessel;onRisk:()=>void}) {return <div className="profile-grid">
  <div className="profile-main"><section className="card current-voyage"><div className="card-head"><div><span className="page-eyebrow">Текущий рейс</span><h2>Baku <ArrowRight size={20}/> {vessel.destination}</h2></div><span className="status-pill green"><Radio size={12}/> В пути</span></div><div className="voyage-stats"><Metric label="Отправление" value="08:00" unit="10 авг" icon={<Clock3 size={16}/>}/><Metric label="Пройдено" value="258" unit="km" icon={<Route size={16}/>}/><Metric label="Скорость" value={`${vessel.speed}`} unit="kn" icon={<Waves size={16}/>}/><Metric label="ETA" value={vessel.calculatedEta} unit="сегодня" icon={<Navigation size={16}/>}/></div><div className="route-progress"><div><span>Baku</span><small>Отправлено 08:00</small></div><div className="route-line"><i/><span/></div><div><span>Aktau</span><small>ETA {vessel.calculatedEta}</small></div></div></section>
    <section className="card"><div className="card-head"><div><span className="page-eyebrow">Положение</span><h2>Маршрут в реальном времени</h2></div><button className="text-button" onClick={()=>navigate('/app/map')}>Открыть карту <ArrowRight size={15}/></button></div><div className="profile-map"><CaspianMap selected={vessel} layers={{vessels:true,ports:true,routes:true}} mini/></div></section>
  </div>
  <aside className="profile-side"><button className={`profile-risk-card ${vessel.riskLevel.toLowerCase()}`} onClick={onRisk}><span className="profile-risk-score">{vessel.risk}</span><span><small>Текущая оценка риска</small><strong>{vessel.riskLevel}</strong><em>Обновлено {vessel.riskUpdatedAt} · Почему?</em></span><ChevronRight size={18}/></button><section className="card"><div className="card-head"><h3>Основные сведения</h3><button className="icon-button"><FileText size={17}/></button></div><InfoRow label="Тип судна" value={vessel.type}/><InfoRow label="Флаг" value={vessel.flag}/><InfoRow label="Позывной" value="UPCS8"/><InfoRow label="Год постройки" value="2011"/><InfoRow label="Владелец" value={vessel.owner}/><InfoRow label="Оператор" value={vessel.operator}/></section>
    <section className="card dimensions"><h3>Размерения</h3><div><span><small>Длина</small><strong>{vessel.length} m</strong></span><span><small>Ширина</small><strong>{vessel.width} m</strong></span><span><small>Дедвейт</small><strong>{vessel.deadweight.toLocaleString()} t</strong></span><span><small>Осадка</small><strong>{vessel.draught} m</strong></span></div></section>
    <section className="card historical-mini"><div className="card-head"><h3>Исторический профиль</h3><button className="text-button">Поведение <ArrowRight size={14}/></button></div><InfoRow label="Наблюдение" value="18 месяцев"/><InfoRow label="Рейсов изучено" value="143"/><InfoRow label="Основной маршрут" value="Baku ↔ Aktau"/><InfoRow label="Типичная скорость" value="11.2–13.1 kn"/></section>
    <section className="card attention"><ShieldCheck size={22}/><div><span>Качество текущих данных</span><strong>Проверено · 99%</strong><small>Последнее сообщение прошло валидацию</small></div></section>
  </aside>
 </div>}

function InfoRow({label,value}:{label:string;value:string}) {return <div className="info-row"><span>{label}</span><strong>{value}</strong></div>}
function VoyageView({vessel}:{vessel:Vessel}) {return <div className="module-layout"><section className="card"><PageHeader eyebrow="Рейс CI-240810" title={`Баку → ${vessel.destination}`} description="Текущий рейс • отправление сегодня в 08:00"/><div className="large-route-map"><CaspianMap selected={vessel} layers={{vessels:true,ports:true,routes:true}} vesselData={[vessel]} track={caspianStarTrack} activeTrackPoint={caspianStarTrack.at(-1)} mini/></div></section><section className="card voyage-details"><h3>Параметры рейса</h3><InfoRow label="Расстояние" value="387 км"/><InfoRow label="Пройдено" value="258 км"/><InfoRow label="Осталось" value="129 км"/><InfoRow label="Средняя скорость" value="11.8 уз"/><InfoRow label="Расчётное прибытие" value={vessel.calculatedEta}/><div className="neutral-note"><ShieldCheck size={17}/><span><strong>Фактические данные</strong>Без интерпретации поведения</span></div>{vessel.id==='caspian-star'&&<button className="primary-button full voyage-intelligence-link" onClick={()=>navigate('/app/voyages/voy-001/intelligence')}><BrainCircuit size={16}/>Открыть аналитику рейса<ArrowRight size={15}/></button>}</section></div>}

function TrackHistoryView({vessel}:{vessel:Vessel}) {
  const [range,setRange]=useState('24H'); const [frame,setFrame]=useState(caspianStarTrack.length-1); const [playing,setPlaying]=useState(false)
  useEffect(()=>{if(!playing)return;const id=setInterval(()=>setFrame(v=>v>=caspianStarTrack.length-1?0:v+1),800);return()=>clearInterval(id)},[playing])
  const point=caspianStarTrack[frame]; const playbackVessel={...vessel,x:point.x,y:point.y,speed:point.speed,course:point.course,latitude:point.latitude,longitude:point.longitude}
  const voyageEvents=detectedEvents.filter(e=>e.vesselId==='caspian-star'&&e.groupId==='EG-441')
  return <div className="track-history-layout"><section className="card track-workspace"><div className="track-toolbar"><div><span className="page-eyebrow">История движения</span><h2>История трека</h2></div><div className="range-chips">{['6H','24H','7D','30D'].map(r=><button key={r} className={range===r?'active':''} onClick={()=>setRange(r)}>{r.replace('H','Ч').replace('D','Д')}</button>)}<button><CalendarDays size={14}/>Период</button></div></div><div className="track-map"><CaspianMap selected={playbackVessel} vesselData={frame===8?[]:[playbackVessel]} layers={{vessels:true,ports:true,routes:false,events:true}} track={caspianStarTrack.slice(0,frame+1)} activeTrackPoint={point} mini/>{frame===8&&<div className="possible-movement-area" style={{left:'59%',top:'35%'}}><span/><i>Возможная область</i></div>}</div><div className="track-event-ruler"><span>08:00</span><div>{voyageEvents.map((event,i)=><button key={event.id} className={event.severity} style={{left:`${52+i*11}%`}} onClick={()=>setFrame(Math.min(7+i,caspianStarTrack.length-1))}><TriangleAlert size={11}/><small>{event.time}</small></button>)}</div><span>18:42</span></div><div className="profile-playback"><button onClick={()=>setPlaying(!playing)}>{playing?<Pause size={17} fill="currentColor"/>:<Play size={17} fill="currentColor"/>}</button><div><strong>{point.time}</strong><span>10 августа 2026</span></div><input type="range" min="0" max={caspianStarTrack.length-1} value={frame} onChange={e=>setFrame(Number(e.target.value))}/><span>{frame+1} / {caspianStarTrack.length}</span></div><div className="track-summary"><div><span>Точек трека</span><strong>1 284</strong></div><div><span>Расстояние</span><strong>258 км</strong></div><div><span>Средняя скорость</span><strong>11,8 уз</strong></div><div><span>События</span><strong>4</strong></div><div><span>Качество данных</span><strong className="quality-good">98,7%</strong></div></div></section><aside className="card track-events"><div className="card-head"><div><span className="page-eyebrow">Аналитическая хронология</span><h3>События рейса</h3></div><span className="status-pill">{voyageEvents.length} событий</span></div>{voyageEvents.map((event,i)=><button key={event.id} className={`tracking-event analytical ${frame>=7+i?'passed':''}`} onClick={()=>setFrame(Math.min(7+i,caspianStarTrack.length-1))}><i className={event.severity}/><time>{event.time}</time><span><strong>{operationalText(event.title)}</strong><small>{operationalText(event.summary)}</small></span></button>)}<div className="event-timeline-note"><Info size={13}/>Нажмите на событие, чтобы перейти к позиции на треке.</div></aside></div>
}

function BehaviorView({vessel}:{vessel:Vessel}) {
  const b=caspianStarBehavior; const [routeId,setRouteId]=useState(b.routes[0].id); const route=b.routes.find(r=>r.id===routeId)!
  if(vessel.id!=='caspian-star') return <InsufficientBehavior vessel={vessel}/>
  return <div className="behavior-view">
    <section className="behavior-hero card"><div className="behavior-identity"><div className="brain-mark"><BrainCircuit size={25}/></div><div><span className="page-eyebrow">Индивидуальная модель</span><h2>Профиль поведения</h2><p>Исторический baseline судна без интерпретации риска</p></div></div><div className="confidence-block"><div className="confidence-label"><span>Уверенность модели</span><strong>{b.confidence}%</strong></div><div className="confidence-track"><i style={{width:`${b.confidence}%`}}/></div><small><CircleCheck size={12}/>{b.confidenceLevel} · {b.voyagesAnalyzed} рейсов · {b.observationMonths} месяцев</small></div><div className="model-meta"><span>Версия модели</span><strong>Baseline v1.0</strong><small>Пересчитано сегодня, 14:42</small></div></section>

    <section className="card current-baseline"><div className="card-head"><div><span className="page-eyebrow">Текущий рейс и baseline</span><h2>Baku → Aktau</h2></div><div className="consistent-status"><CircleCheck size={18}/><span><strong>Соответствует историческому профилю</strong><small>Сравнение фактов, не оценка риска</small></span></div></div><div className="comparison-table"><div className="comparison-head"><span>Параметр</span><span>Обычно</span><span>Сейчас</span><span>Контекст</span></div>{b.comparison.map(row=><div className="comparison-row" key={row.parameter}><strong>{row.parameter}</strong><span>{row.typical}</span><span>{row.current}</span><em><Check size={12}/>В диапазоне</em></div>)}</div><div className="explain-note"><Info size={15}/><span>Сравнение основано на <strong>82 завершённых рейсах</strong> по маршруту Baku → Aktau за последние 18 месяцев.</span></div></section>

    <section className="card route-intelligence"><div className="card-head"><div><span className="page-eyebrow">Аналитика маршрутов</span><h2>Повторяющиеся маршруты</h2></div><span className="sample-badge">137 из 143 рейсов сгруппированы</span></div><div className="route-layout"><div className="route-list">{b.routes.map(r=><button key={r.id} className={routeId===r.id?'active':''} onClick={()=>setRouteId(r.id)}><i style={{background:r.color}}/><span><strong>{operationalText(r.from)} <ArrowRight size={12}/> {operationalText(r.to)}</strong><small>{r.voyages} рейсов</small></span><em>{r.share}%</em></button>)}</div><div className="corridor-card"><div className="corridor-visual"><svg viewBox="0 0 500 190" preserveAspectRatio="none"><defs><linearGradient id="seaWash" x1="0" x2="1"><stop stopColor="#e8efed"/><stop offset=".5" stopColor="#c5d9d5"/><stop offset="1" stopColor="#e8efed"/></linearGradient></defs><rect width="500" height="190" fill="url(#seaWash)"/><path className="corridor-wide" d="M55 145 C150 115 255 75 445 42"/><path className="corridor-line" d="M55 145 C150 115 255 75 445 42"/><circle cx="55" cy="145" r="6"/><circle cx="445" cy="42" r="6"/></svg><span className="corridor-from">{operationalText(route.from)}</span><span className="corridor-to">{operationalText(route.to)}</span><span className="corridor-caption">Исторический коридор · 80% наблюдений</span></div><div className="route-profile-grid"><BehaviorMetric label="Рейсов" value={`${route.voyages}`} note={`${route.share}% истории`}/><BehaviorMetric label="Дистанция" value={route.distance} note="типичный диапазон"/><BehaviorMetric label="Длительность" value={route.duration} note="типичный диапазон"/><BehaviorMetric label="Скорость" value={route.speed} note="открытое море"/><BehaviorMetric label="Остановки" value={route.stops} note="за рейс"/><BehaviorMetric label="Выход" value={route.departure} note="типичное окно"/></div></div></div><div className="explain-note"><Info size={15}/><span>Нормальный маршрут представлен <strong>коридором</strong>, а не одной линией. Границы построены по историческим траекториям судна.</span></div></section>

    <div className="behavior-two-col"><section className="card speed-profile"><div className="card-head"><div><span className="page-eyebrow">Открытое море</span><h2>Профиль скорости</h2></div><button className="context-select">Фаза: Открытое море <ChevronDown size={14}/></button></div><div className="speed-summary"><BehaviorMetric label="Средняя" value={`${b.speed.average} уз`}/><BehaviorMetric label="Медиана" value={`${b.speed.median} уз`}/><BehaviorMetric label="P95" value={`${b.speed.p95} уз`}/><BehaviorMetric label="Норма" value={`${b.speed.min}–${b.speed.max} уз`}/></div><div className="speed-distribution">{b.speed.distribution.map((h,i)=><div key={i}><span className={i>=10&&i<=12?'typical':''} style={{height:`${h}%`}}/><small>{i}</small></div>)}<div className="normal-band"/></div><div className="chart-foot"><span><i/>Типичный диапазон {b.speed.min}–{b.speed.max} уз</span><small>На основе {b.speed.samples.toLocaleString()} AIS-позиций</small></div></section>
      <section className="card duration-profile"><div className="card-head"><div><span className="page-eyebrow">Baku → Aktau</span><h2>Длительность рейса</h2></div><span className="sample-badge">82 рейса</span></div><div className="duration-main"><span>Типичный диапазон</span><strong>{b.duration.typical}</strong><div><i/><em style={{left:'34%'}}/><em style={{left:'68%'}}/></div><small><span>24h</span><span>29h</span><span>36h</span></small></div><div className="duration-grid"><BehaviorMetric label="Среднее" value={b.duration.average}/><BehaviorMetric label="Медиана" value={b.duration.median}/><BehaviorMetric label="Самый быстрый" value={b.duration.fastest}/><BehaviorMetric label="Самый долгий" value={b.duration.longest}/></div></section></div>

    <div className="behavior-two-col"><section className="card port-behavior"><div className="card-head"><div><span className="page-eyebrow">Поведение в портах</span><h2>Посещения портов</h2></div><span className="sample-badge">143 захода</span></div><div className="port-behavior-list">{b.ports.map(p=><div key={p.name}><div className="port-rank"><Anchor size={15}/><span><strong>{operationalText(p.name)}</strong><small>{p.visits} посещений · медиана стоянки {p.median}</small></span>{p.usual&&<em>Обычный порт</em>}</div><div className="port-share"><i style={{width:`${p.share}%`}}/><strong>{p.share}%</strong></div></div>)}</div></section>
      <section className="card temporal-profile"><div className="card-head"><div><span className="page-eyebrow">Временной профиль</span><h2>Временные паттерны</h2></div></div><h4>Время отправления</h4><div className="departure-bars">{b.departurePattern.map((v,i)=><div key={i}><span><i style={{width:`${v}%`}}/></span><strong>{v}%</strong><small>{['00–06','06–12','12–18','18–24'][i]}</small></div>)}</div><h4>Рейсы по дням недели</h4><div className="weekday-bars">{b.weekdays.map((v,i)=><div key={i}><span style={{height:`${v/25*100}%`}}/><small>{['ПН','ВТ','СР','ЧТ','ПТ','СБ','ВС'][i]}</small></div>)}</div><div className="chart-foot"><small>На основе времени выхода из портовых геозон</small></div></section></div>

    <div className="behavior-two-col"><section className="card stop-profile"><div className="card-head"><div><span className="page-eyebrow">Профиль остановок</span><h2>Обычные зоны остановок</h2></div><span className="sample-badge">27 остановок</span></div><div className="behavior-map"><CaspianMap layers={{vessels:false,ports:true,routes:false}} mini/>{b.stops.map(s=><button key={s.id} className="stop-bubble" style={{left:`${s.x}%`,top:`${s.y}%`,width:s.radius,height:s.radius}}><strong>{s.count}</strong><span>{s.duration}</span></button>)}</div><div className="stop-stats"><BehaviorMetric label="Средняя остановка" value="24 мин"/><BehaviorMetric label="Медиана" value="17 мин"/><BehaviorMetric label="Общих зон" value="3"/></div></section>
      <section className="card activity-profile"><div className="card-head"><div><span className="page-eyebrow">Пространственное поведение</span><h2>Зоны активности</h2></div><button className="context-select">12 месяцев <ChevronDown size={14}/></button></div><div className="behavior-map activity-map"><CaspianMap layers={{vessels:false,ports:true,routes:false}} mini/><i className="heat h1"/><i className="heat h2"/><i className="heat h3"/><i className="heat h4"/></div><div className="heat-legend"><span>Низкая активность</span><div/><span>Высокая активность</span></div></section></div>

    <section className="card draught-profile"><div className="card-head"><div><span className="page-eyebrow">История осадки</span><h2>История осадки</h2></div><div className="typical-draught"><span>Типичный диапазон</span><strong>4,5–5,1 м</strong></div></div><div className="draught-table"><div className="draught-head"><span>Рейс</span><span>Маршрут</span><span>При выходе</span><span>При прибытии</span><span>Изменение</span><span>Исторический контекст</span></div>{b.draught.map(d=><div className="draught-row" key={d.voyage}><strong>Рейс #{d.voyage}</strong><span>{operationalText(d.route)}</span><span className="mono">{d.start.toFixed(1)} м</span><span className="mono">{d.end.toFixed(1)} м</span><em className="mono">{d.end-d.start>0?'+':''}{(d.end-d.start).toFixed(1)} м</em><span><i className={(d.start<4.5||d.start>5.1||d.end<4.5||d.end>5.1)?'context-observed':'context-typical'}/>{(d.start<4.5||d.start>5.1||d.end<4.5||d.end>5.1)?'Наблюдавшийся диапазон':'Типичный диапазон'}</span></div>)}</div><div className="explain-note"><Info size={15}/><span>История осадки отображает фактические изменения. На этом этапе система <strong>не классифицирует их как аномалии</strong>.</span></div></section>
  </div>
}

function InsufficientBehavior({vessel}:{vessel:Vessel}){return <div className="behavior-view"><section className="behavior-hero card"><div className="behavior-identity"><div className="brain-mark"><BrainCircuit size={25}/></div><div><span className="page-eyebrow">Индивидуальная модель</span><h2>Профиль поведения</h2><p>Исторический baseline судна</p></div></div><div className="confidence-block"><div className="confidence-label"><span>Уверенность модели</span><strong>24%</strong></div><div className="confidence-track low"><i style={{width:'24%'}}/></div><small><Info size={12}/>INSUFFICIENT DATA · 8 рейсов · 3 месяца</small></div><div className="model-meta"><span>Статус</span><strong>Сбор истории</strong><small>Baseline ещё формируется</small></div></section><section className="insufficient-card card"><div className="insufficient-visual"><Gauge size={28}/><span/></div><h2>Недостаточно индивидуальной истории</h2><p>Для {vessel.name} наблюдается только 8 завершённых рейсов. Система продолжает собирать маршруты, скорость, стоянки и портовые посещения, но пока не делает уверенных сравнений.</p><div className="confidence-requirements"><div className="done"><Check size={14}/><span><strong>Текущие позиции</strong><small>Доступны</small></span></div><div className="done"><Check size={14}/><span><strong>История рейсов</strong><small>8 рейсов</small></span></div><div><Clock3 size={14}/><span><strong>Устойчивый baseline</strong><small>Рекомендуется от 20 рейсов</small></span></div></div><div className="explain-note"><Info size={15}/><span>Низкая уверенность модели не означает риск. Она означает, что системе <strong>пока недостаточно данных</strong> о конкретном судне.</span></div></section></div>}

function BehaviorMetric({label,value,note}:{label:string;value:string;note?:string}){return <div className="behavior-metric"><span>{label}</span><strong>{value}</strong>{note&&<small>{note}</small>}</div>}
function HistoryView(){
  const durations=['В процессе','28 ч 35 мин','29 ч 12 мин','26 ч 48 мин','11 ч 34 мин','26 ч 33 мин','34 ч 22 мин','9 ч 51 мин','10 ч 42 мин','9 ч 48 мин','18 ч 44 мин','28 ч 51 мин','40 ч 38 мин','9 ч 44 мин']
  const averageSpeeds=['12.4','11.8','12.1','10.4','11.2','10.6','9.1','11.7','11.3','10.9','9.8','10.7','9.4','11.5']
  const coverage=[99,98.7,97.9,99.2,98.4,96.8,94.9,98.1,97.6,96.3,93.8,97.2,92.6,98.5]
  return <div className="vessel-history"><section className="card history-summary"><div className="card-head"><div><span className="page-eyebrow">Цифровая история</span><h2>18 месяцев наблюдений</h2></div><div className="range-chips"><button>30 дней</button><button>6 месяцев</button><button>1 год</button><button className="active">Всё время</button></div></div><div className="history-metrics"><BehaviorMetric label="Рейсов" value="143"/><BehaviorMetric label="Дистанция" value="31 420 км"/><BehaviorMetric label="Портов посещено" value="9"/><BehaviorMetric label="В движении" value="3 810 ч"/><BehaviorMetric label="В портах" value="1 280 ч"/><BehaviorMetric label="Остановки в море" value="27"/><BehaviorMetric label="Разрывы данных" value="8" note="историческая статистика"/></div></section><section className="card history-card"><div className="card-head"><div><span className="page-eyebrow">История рейсов</span><h2>Последние рейсы</h2></div><button className="secondary-button"><Filter size={16}/>Фильтры</button></div><table><thead><tr><th>Рейс</th><th>Маршрут</th><th>Отправление</th><th>Прибытие</th><th>Длительность</th><th>Дистанция</th><th>Средняя скорость</th><th>Покрытие AIS</th><th/></tr></thead><tbody>{voyages.map((v,i)=><tr key={v.id}><td className="mono">#{143-i}</td><td><strong>{operationalText(v.from)}</strong> <ArrowRight size={14}/> <strong>{operationalText(v.to)}</strong></td><td>{v.departed}</td><td>{v.arrived}</td><td>{durations[i]}</td><td>{v.distance} км</td><td className="mono">{averageSpeeds[i]} уз</td><td><span className="coverage"><i style={{width:`${coverage[i]}%`}}/>{coverage[i]}%</span></td><td><button className="replay-link"><Play size={12}/>Повтор</button></td></tr>)}</tbody></table></section></div>
}

function ConnectionsView(){const connections=[{name:'TURAN',type:'Грузовое судно',count:18,ports:'Актау · Баку',last:'7 авг 2026'},{name:'CASPIAN WIND',type:'Нефтяной танкер',count:11,ports:'Центральный Каспий',last:'2 авг 2026'},{name:'BAKU STAR',type:'Ролкер',count:9,ports:'Баку · Алят',last:'28 июл 2026'}];return <div className="connections-layout"><section className="card connection-network"><div className="card-head"><div><span className="page-eyebrow">Исторические связи</span><h2>Регулярно наблюдались рядом</h2></div><button className="secondary-button" onClick={()=>navigate('/app/network')}><Network size={15}/>Сеть расследования</button></div><div className="network-visual"><div className="network-center"><Ship size={22}/><strong>CASPIAN STAR</strong></div>{connections.map((c,i)=><div key={c.name} className={`network-node n${i+1}`}><Ship size={16}/><span><strong>{c.name}</strong><small>{c.count} наблюдений</small></span></div>)}<svg viewBox="0 0 600 300" preserveAspectRatio="none"><line x1="300" y1="150" x2="90" y2="60"/><line x1="300" y1="150" x2="505" y2="72"/><line x1="300" y1="150" x2="470" y2="246"/></svg></div><div className="explain-note"><Info size={15}/><span>Связь означает регулярное совместное присутствие в одном районе или порту. Это <strong>не классификация встречи</strong>.</span></div></section><section className="card connection-list"><h3>Основные связи</h3>{connections.map(c=><div key={c.name}><div className="connection-icon"><Ship size={17}/></div><span><strong>{c.name}</strong><small>{c.type} · {c.ports}</small></span><em>{c.count}<small>наблюдений</small></em><time>{c.last}</time></div>)}</section></div>}
function EmptyModule({tab}:{tab:string}) {return <div className="empty-module"><div><Sparkles size={26}/></div><h2>{tab}</h2><p>Раздел подготовлен для подключения данных на следующих этапах развития платформы.</p><span>Модуль расширения</span></div>}

function PortsPage(){return <div className="content-page"><PageHeader eyebrow="Портовая инфраструктура" title="Порты Каспийского моря" description="Статусы, загрузка и операционная информация по основным портам региона."/><div className="ports-layout"><div className="card port-map"><CaspianMap layers={{vessels:false,ports:true,routes:true}} mini/></div><div className="ports-list">{ports.map(p=><PortCard key={p.id} port={p}/>)}</div></div></div>}
function PortCard({port}:{port:Port}) {return <button className="port-card"><div className="port-icon"><Anchor size={20}/></div><div><span className="page-eyebrow">{port.country}</span><h3>{port.name}</h3><p><Ship size={14}/>{port.vessels} судов в акватории</p></div><span className={`port-status ${port.status==='Busy'?'busy':''}`}>{port.status}</span><ChevronRight size={18}/></button>}

function VoyagesPage(){
  const origins=['Baku','Aktau','Astrakhan','Turkmenbashi','Anzali','Aktau','Baku','Alat','Turkmenbashi','Makhachkala','Baku','Amirabad']
  const departureTimes=['08:00','08:42','09:15','10:02','11:30','12:05','12:48','13:20','14:05','14:42','15:10','15:34']
  const progress=[67,42,81,24,53,16,74,36,58,89,31,47]
  return <div className="content-page"><PageHeader eyebrow="Мониторинг рейсов" title="Рейсы" description="Текущие и завершённые перемещения судов между портами Каспия." actions={<button className="secondary-button"><CalendarDays size={16}/>10 августа 2026</button>}/><div className="stat-strip voyage-strip"><Stat label="Активные рейсы" value="36" dot="green"/><Stat label="Завершено сегодня" value="18"/><Stat label="Средняя длительность" value="11.4 ч"/><Stat label="Пройдено за сутки" value="7 840 км"/><Stat label="Данные поступают" value="98.7%" dot="green"/></div><div className="table-card"><div className="table-toolbar"><div className="inline-search"><Search size={17}/><input placeholder="Судно, порт или номер рейса"/></div><button className="filter-chip active">Активные <span>36</span></button><button className="filter-chip">Завершённые</button><span className="results-count">Показано 12 демонстрационных рейсов</span></div><div className="mobile-record-list">{vessels.slice(0,12).map((v,i)=><button className="mobile-record-card" key={v.id} onClick={()=>i===0?navigate('/app/voyages/voy-001/intelligence'):navigate(`/app/vessels/${v.id}`)}><span className="mobile-record-icon"><Route size={18}/></span><span className="mobile-record-main"><strong>{v.name}</strong><small>Рейс CI-{240810+i} · IMO {v.imo}</small><span>{operationalText(origins[i])} → {operationalText(v.destination)}</span></span><span className={`status-pill ${v.navigationStatus==='Underway'?'green':''}`}>{navigationStatusLabel(v.navigationStatus)}</span><span className="mobile-record-meta"><span>Отправление<b>{departureTimes[i]}</b></span><span>Скорость<b>{v.speed} уз</b></span><span>ETA<b>{etaLabel(v.reportedEta)}</b></span><span>Прогресс<b>{progress[i]}%</b></span></span></button>)}</div><div className="table-scroll desktop-data-table"><table><thead><tr><th>Рейс</th><th>Судно</th><th>Маршрут</th><th>Отправление</th><th>Прогресс</th><th>Скорость</th><th>ETA</th><th>Статус</th><th/></tr></thead><tbody>{vessels.slice(0,12).map((v,i)=><tr key={v.id} onClick={()=>i===0?navigate('/app/voyages/voy-001/intelligence'):navigate(`/app/vessels/${v.id}`)}><td className="mono">CI-{240810+i}</td><td><div className="vessel-cell"><span><Ship size={17}/></span><div><strong>{v.name}</strong><small>IMO {v.imo}</small></div></div></td><td><strong>{operationalText(origins[i])}</strong> <ArrowRight size={13}/> <strong>{operationalText(v.destination)}</strong></td><td>{departureTimes[i]}</td><td><div className="table-progress"><i style={{width:`${progress[i]}%`}}/></div></td><td className="mono">{v.speed} уз</td><td className="mono">{etaLabel(v.reportedEta)}</td><td><span className={`status-pill ${v.navigationStatus==='Underway'?'green':''}`}>{navigationStatusLabel(v.navigationStatus)}</span></td><td>{i===0?<span className="voyage-intelligence-table-link"><BrainCircuit size={14}/>АНАЛИТИКА</span>:<ChevronRight size={16}/>}</td></tr>)}</tbody></table></div></div></div>
}

function HistoryPage(){
  const [frame,setFrame]=useState(7);const [playing,setPlaying]=useState(false);const point=caspianStarTrack[frame]
  useEffect(()=>{if(!playing)return;const id=setInterval(()=>setFrame(v=>v>=caspianStarTrack.length-1?0:v+1),850);return()=>clearInterval(id)},[playing])
  const vessel={...vessels[0],x:point.x,y:point.y,speed:point.speed,course:point.course}
  const playbackEvent=frame>=10?detectedEvents[3]:frame===9?detectedEvents[2]:frame===8?detectedEvents[1]:frame===7?detectedEvents[0]:undefined
  return <div className="content-page history-page"><PageHeader eyebrow="Морской видеорегистратор" title="История движения" description="Воспроизведение фактических позиций судов и автоматически обнаруженных событий." actions={<><button className="secondary-button"><CalendarDays size={16}/>10 августа 2026</button><button className="secondary-button"><Crosshair size={16}/>Выбрать область</button></>}/><div className="history-workspace"><aside className="history-panel"><div className="history-status"><History size={18}/><span><small>Режим</small><strong>ИСТОРИЧЕСКИЙ</strong></span></div><label>Период<select><option>10 августа 2026</option></select></label><div className="time-inputs"><label>От<input type="time" defaultValue="08:00"/></label><label>До<input type="time" defaultValue="18:42"/></label></div><div className="history-vessels"><span>Суда в выборке <strong>12</strong></span>{vessels.slice(0,4).map((v,i)=><button className={i===0?'active':''} key={v.id}><i style={{background:['#08796e','#7b8c87','#5b817a','#9a7e5a'][i]}}/><span><strong>{v.name}</strong><small>{vesselTypeLabel(v.type)}</small></span><Eye size={15}/></button>)}</div><div className="history-events-filter"><span>События рейса <strong>4</strong></span>{detectedEvents.slice(0,4).map((event,i)=><button key={event.id} className={frame>=7+i?'visible':''} onClick={()=>setFrame(7+i)}><i className={event.severity}/><span>{event.time} · {operationalText(event.title)}</span></button>)}</div><div className="data-quality"><ShieldCheck size={18}/><span><strong>98,7% данных</strong><small>прошли валидацию</small></span></div></aside><section className="history-map"><CaspianMap selected={vessel} vesselData={frame===8?vessels.slice(1,4):[vessel,...vessels.slice(1,4)]} layers={{vessels:true,ports:true,routes:false,events:true}} track={caspianStarTrack.slice(0,frame+1)} activeTrackPoint={point}/>{frame===8&&<div className="possible-movement-area large" style={{left:'59%',top:'35%'}}><span/><i>Возможная область движения · 72 км</i></div>}{playbackEvent&&<div className={`playback-event-toast ${playbackEvent.severity}`}><div className="event-type-icon"><EventTypeIcon type={playbackEvent.type}/></div><span><small>СОБЫТИЕ ОБНАРУЖЕНО · {playbackEvent.time}</small><strong>{operationalText(playbackEvent.title)}</strong><em>{operationalText(playbackEvent.summary)}</em></span><button onClick={()=>navigate('/app/events')}><ChevronRight size={16}/></button></div>}<div className="history-playback"><button onClick={()=>setPlaying(!playing)}>{playing?<Pause size={18} fill="currentColor"/>:<Play size={18} fill="currentColor"/>}</button><div className="history-clock"><strong>{point.time}</strong><span>10 АВГ 2026</span></div><input type="range" min="0" max={caspianStarTrack.length-1} value={frame} onChange={e=>setFrame(Number(e.target.value))}/><div className="speed-controls"><button className="active">1×</button><button>2×</button><button>4×</button></div></div></section></div></div>
}

function EventsPage(){
  const [type,setType]=useState('all');const [severity,setSeverity]=useState('all');const [activeOnly,setActiveOnly]=useState(false);const [selected,setSelected]=useState<DetectionEvent>(detectedEvents[1]);const [groupOpen,setGroupOpen]=useState(false)
  const filtered=detectedEvents.filter(e=>(type==='all'||e.type===type)&&(severity==='all'||e.severity===severity)&&(!activeOnly||e.status==='active'))
  return <div className="content-page event-center-page"><PageHeader eyebrow="Центр обнаружения событий" title="Морские события" description="Автоматически обнаруженные факты и отличия от исторического поведения." actions={<><div className="detector-health"><i/>6 детекторов работают</div><button className="secondary-button"><SlidersHorizontal size={16}/>Правила детекторов</button></>}/><div className="event-kpis"><div><span className="event-kpi-icon high"><TriangleAlert size={18}/></span><p><small>Высокая значимость</small><strong>1</strong></p><em>1 завершено</em></div><div><span className="event-kpi-icon medium"><Activity size={18}/></span><p><small>Средняя значимость</small><strong>4</strong></p><em>3 активных</em></div><div><span className="event-kpi-icon low"><Info size={18}/></span><p><small>Низкая значимость</small><strong>1</strong></p><em>1 завершено</em></div><div><span className="event-kpi-icon"><GitCompareArrows size={18}/></span><p><small>Связанные группы</small><strong>1</strong></p><em>4 события</em></div></div><div className="event-filterbar"><div className="inline-search"><Search size={17}/><input placeholder="Судно, событие или рейс"/></div><select><option>Последние 24 часа</option><option>Последний час</option><option>7 дней</option><option>30 дней</option></select><select value={type} onChange={e=>setType(e.target.value)}><option value="all">Все типы</option><option value="route_deviation">Отклонение маршрута</option><option value="ais_gap">Пропуск AIS</option><option value="unusual_stop">Нетипичная остановка</option><option value="unexpected_speed">Нетипичная скорость</option><option value="vessel_encounter">Встреча судов</option><option value="draught_change">Изменение осадки</option></select><div className="severity-filters"><button className={severity==='all'?'active':''} onClick={()=>setSeverity('all')}>Все</button>{(['high','medium','low'] as const).map(s=><button key={s} className={`${s} ${severity===s?'active':''}`} onClick={()=>setSeverity(s)}><i/>{severityLabel(s)}</button>)}</div><label className="active-switch"><input type="checkbox" checked={activeOnly} onChange={e=>setActiveOnly(e.target.checked)}/><i/><span>Только активные</span></label><em>{filtered.length} событий</em></div>{groupOpen&&<EventGroupPanel onClose={()=>setGroupOpen(false)} onSelect={event=>{setSelected(event);setGroupOpen(false)}}/>}<div className="event-center-layout"><section className="event-feed"><div className="feed-heading"><span>Обнаруженные события</span><button><ListFilter size={14}/>Сначала значимые</button></div>{filtered.map(event=><button key={event.id} className={`detected-event-row ${selected.id===event.id?'selected':''}`} onClick={()=>setSelected(event)}><div className={`event-type-icon ${event.severity}`}><EventTypeIcon type={event.type}/></div><div className="event-row-main"><span><strong>{operationalText(event.title)}</strong><em className={`severity ${event.severity}`}>{severityLabel(event.severity)}</em></span><h3>{event.vesselName}{event.relatedVessel&&<> <small>+</small> {event.relatedVessel}</>}</h3><p>{operationalText(event.summary)}</p><div><time>{event.time}</time><span>{statusLabel(event.status)}</span>{event.groupId&&<em><GitCompareArrows size={11}/>{event.groupId}</em>}</div></div><div className="confidence-mini"><span>{event.confidence}%</span><small>достоверность</small></div><ChevronRight size={17}/></button>) }{!filtered.length&&<div className="empty-event-feed"><Filter size={23}/><strong>Нет событий по фильтру</strong><span>Измените тип, значимость или статус</span></div>}</section><EventDetailPanel event={selected} onGroup={()=>setGroupOpen(true)}/></div></div>
}

function EventDetailPanel({event,onGroup}:{event:DetectionEvent;onGroup:()=>void}){const [reviewed,setReviewed]=useState(false);useEffect(()=>setReviewed(event.status==='reviewed'),[event]);return <aside className="event-detail card"><div className="event-detail-head"><div className={`event-type-icon ${event.severity}`}><EventTypeIcon type={event.type} size={20}/></div><div><span>{event.id} · {eventLabels[event.type]}</span><h2>{event.vesselName}{event.relatedVessel&&<> + {event.relatedVessel}</>}</h2></div><span className={`severity ${event.severity}`}>{severityLabel(event.severity)}</span></div><div className="severity-confidence"><div><span>Значимость</span><strong className={event.severity}>{severityLabel(event.severity)}</strong><small>Значимость факта</small></div><div><span>Достоверность</span><strong>{event.confidence}%</strong><small>Уверенность классификации</small></div><div><span>Статус</span><strong>{reviewed?'ПРОСМОТРЕНО':statusLabel(event.status)}</strong><small>{event.endedAt?'Завершено':'Наблюдается'}</small></div></div><div className="detail-section"><h4>Наблюдаемые параметры</h4><div className="detail-metrics">{event.metrics.map(m=><div key={m.label}><span>{operationalText(m.label)}</span><strong>{operationalText(m.value)}</strong>{m.baseline&&<small>{operationalText(m.baseline)}</small>}</div>)}</div></div>{event.type==='ais_gap'&&<div className="possible-area-wide"><div className="possible-radar"><span/><i/><b/></div><div><span>Возможная область движения</span><strong>До 72 км от последней позиции</strong><small>Теоретическая область, не фактический маршрут</small></div></div>}<div className="detail-section explanation-section"><h4><BrainCircuit size={14}/>Почему создано событие</h4><p>{operationalText(event.explanation)}</p><ul>{event.factors.map(f=><li key={f}><Check size={12}/>{operationalText(f)}</li>)}</ul></div>{event.groupId&&<button className="event-group-link" onClick={onGroup}><GitCompareArrows size={17}/><span><strong>Связано с 3 другими событиями</strong><small>{event.groupId} · Рейс #143</small></span><ChevronRight size={16}/></button>}<div className="human-review-note"><ShieldCheck size={16}/><span><strong>Требуется решение аналитика</strong><small>Система описывает наблюдаемые факты и не утверждает наличие нарушения.</small></span></div><div className="event-detail-actions"><button className="secondary-button" onClick={()=>navigate('/app/map')}><MapPin size={15}/>На карте</button><button className="secondary-button" onClick={()=>navigate('/app/history')}><Play size={14}/>Повтор</button></div><button className={`primary-button full ${reviewed?'reviewed':''}`} onClick={()=>setReviewed(true)}>{reviewed?<><CircleCheck size={16}/>Просмотрено аналитиком</>:<>Отметить как просмотренное <ArrowRight size={15}/></>}</button></aside>}

function EventGroupPanel({onClose,onSelect}:{onClose:()=>void;onSelect:(event:DetectionEvent)=>void}){const groupEvents=detectedEvents.filter(e=>demoEventGroup.eventIds.includes(e.id));return <section className="event-group-panel"><div className="group-head"><div className="group-icon"><GitCompareArrows size={20}/></div><div><span className="page-eyebrow">Event group · {demoEventGroup.id}</span><h2>{demoEventGroup.vessel} · {demoEventGroup.voyage}</h2><p>{demoEventGroup.startedAt}–{demoEventGroup.endedAt} · {groupEvents.length} связанных события</p></div><button onClick={onClose}><X size={18}/></button></div><div className="group-timeline">{groupEvents.map((event,i)=><button key={event.id} onClick={()=>onSelect(event)}><i className={event.severity}/><time>{event.time}</time><span><strong>{event.title}</strong><small>{event.summary}</small></span>{i<groupEvents.length-1&&<em/>}</button>)}</div><div className="group-explanation"><Info size={15}/>{demoEventGroup.explanation}</div></section>}

function VesselEventsView({vessel}:{vessel:Vessel}){const items=detectedEvents.filter(e=>e.vesselId===vessel.id);const [selected,setSelected]=useState(items[0]||detectedEvents[0]);if(!items.length)return <EmptyModule tab="События"/>;return <div className="vessel-events-view"><section className="card vessel-event-summary"><div className="card-head"><div><span className="page-eyebrow">События текущего рейса</span><h2>{items.length} событий в текущем рейсе</h2></div><button className="secondary-button" onClick={()=>navigate('/app/events')}>Открыть центр событий <ArrowRight size={15}/></button></div><div className="analytic-timeline"><span className="timeline-start"><i/>08:00<small>Отправление</small></span><div className="timeline-line"/>{items.map((event,i)=><button key={event.id} className={event.severity} style={{left:`${32+i*15}%`}} onClick={()=>setSelected(event)}><TriangleAlert size={13}/><span>{event.time}</span><small>{operationalText(event.title)}</small></button>)}<span className="timeline-end"><i/>00:25<small>Прибытие</small></span></div><div className="event-group-summary"><GitCompareArrows size={17}/><span><strong>{demoEventGroup.id} · Связанный контекст</strong><small>Отклонение маршрута + пропуск AIS + встреча судов + изменение осадки</small></span><em>4 события</em></div></section><div className="vessel-events-grid"><section className="card compact-event-list">{items.map(event=><button key={event.id} className={selected.id===event.id?'active':''} onClick={()=>setSelected(event)}><div className={`event-type-icon ${event.severity}`}><EventTypeIcon type={event.type}/></div><span><strong>{operationalText(event.title)}</strong><small>{event.time} · {operationalText(event.summary)}</small></span><em className={`severity ${event.severity}`}>{severityLabel(event.severity)}</em><ChevronRight size={15}/></button>)}</section><EventDetailPanel event={selected} onGroup={()=>navigate('/app/events')}/></div></div>}

const reviewLabels:Record<RiskReviewStatus,string>={NEEDS_MORE_DATA:'Нужно больше данных',CONFIRMED_RELEVANT:'Фактор подтверждён',NORMAL_OPERATION:'Штатная операция',FALSE_POSITIVE:'Ложное срабатывание'}

function RiskBadge({level}:{level:RiskLevel}){return <span className={`risk-level-badge ${level.toLowerCase()}`}><i/>{riskLevelLabel(level)}</span>}

function RiskScore({assessment,compact=false}:{assessment:RiskAssessment;compact?:boolean}){
  const color={CRITICAL:'#a54539',HIGH:'#bd702d',MODERATE:'#9a7b35',LOW:'#297a69'}[assessment.level]
  return <div className={`risk-score-ring ${assessment.level.toLowerCase()} ${compact?'compact':''}`} style={{background:`conic-gradient(${color} ${assessment.score*3.6}deg,#e9eeec 0deg)`}}><div><strong>{assessment.score}</strong>{!compact&&<small>/100</small>}</div></div>
}

function RiskCenterPage(){
  const [selectedId,setSelectedId]=useState(riskAssessments[0].vesselId)
  const [query,setQuery]=useState('')
  const [listLevel,setListLevel]=useState<'ALL'|RiskLevel>('ALL')
  const [mapLevels,setMapLevels]=useState<RiskLevel[]>(['CRITICAL','HIGH','MODERATE','LOW'])
  const selected=riskAssessments.find(item=>item.vesselId===selectedId)||riskAssessments[0]
  const visible=riskAssessments.filter(item=>(listLevel==='ALL'||item.level===listLevel)&&item.vesselName.includes(query.toUpperCase()))
  const riskCoordinates:Record<string,[number,number]>={
    'caspian-star':[50.74,42.31],turan:[50.61,42.04],'baku-express':[50.18,40.92],'caspian-wind':[52.18,41.35],
  }
  return <div className="content-page risk-center-page">
    <PageHeader eyebrow="Морской риск-центр" title="Центр оценки риска" description="Единая объяснимая приоритизация судов на основе связанных событий и контекста." actions={<><div className="risk-model-status"><ShieldCheck size={16}/><span><small>Модель</small><strong>{riskAssessments[0].modelVersion}</strong></span><i/></div><button className="secondary-button"><SlidersHorizontal size={16}/>Правила оценки</button></>}/>
    <div className="risk-principle"><Info size={17}/><span><strong>Оценка помогает расставить приоритеты и не является выводом о нарушении.</strong> Все факторы доступны для проверки и решения аналитика.</span><em>Поддержка решения</em></div>
    <div className="risk-kpis"><div><span className="risk-kpi-dot critical"/><p><small>Критический</small><strong>1</strong></p><em>требует внимания</em></div><div><span className="risk-kpi-dot high"/><p><small>Высокий</small><strong>3</strong></p><em>в активном рейсе</em></div><div><TrendingIndicator value="+30"/><p><small>Макс. изменение</small><strong>+30</strong></p><em>за последние 4 часа</em></div><div><Bell size={19}/><p><small>Важные переходы</small><strong>2</strong></p><em>Высокий → критический</em></div></div>
    <div className="risk-center-layout">
      <aside className="risk-priority card">
        <div className="risk-list-head"><div><span className="page-eyebrow">Очередь внимания</span><h2>Приоритетные суда</h2></div><span>4</span></div>
        <div className="risk-list-search"><Search size={15}/><input value={query} onChange={e=>setQuery(e.target.value)} placeholder="Название или IMO"/></div>
        <div className="risk-list-levels">{(['ALL','CRITICAL','HIGH'] as const).map(level=><button key={level} className={listLevel===level?'active':''} onClick={()=>setListLevel(level)}>{level==='ALL'?'Все':riskLevelLabel(level)}</button>)}</div>
        <div className="risk-vessel-list">{visible.map((item,index)=><button key={item.vesselId} className={selected.vesselId===item.vesselId?'selected':''} onClick={()=>setSelectedId(item.vesselId)}><span className="risk-rank">{String(index+1).padStart(2,'0')}</span><RiskScore assessment={item} compact/><span className="risk-vessel-copy"><strong>{item.vesselName}</strong><small>IMO {item.imo} · {item.route}</small><em className={item.delta>0?'up':''}>{item.delta>0?`+${item.delta}`:'стабильно'} · {item.deltaWindow}</em></span><RiskBadge level={item.level}/><ChevronRight size={15}/></button>)}</div>
        {!visible.length&&<div className="risk-list-empty"><ShieldCheck size={22}/><strong>Нет судов по фильтру</strong></div>}
        <div className="risk-list-note"><Clock3 size={14}/>Очередь обновлена сейчас</div>
      </aside>
      <main className="risk-main">
        <section className="card risk-map-overview"><div className="risk-map-head"><div><span className="page-eyebrow">Карта риска</span><h2>Распределение приоритетов</h2></div><div className="risk-map-levels">{(['CRITICAL','HIGH','MODERATE','LOW'] as RiskLevel[]).map(level=><button key={level} className={`${level.toLowerCase()} ${mapLevels.includes(level)?'active':''}`} onClick={()=>setMapLevels(current=>current.includes(level)?current.filter(item=>item!==level):[...current,level])}><i/>{riskLevelLabel(level)}</button>)}</div></div><div className="risk-mini-map"><RealCaspianMap compact ariaLabel="Реальная карта распределения риска" ports={ports.map(port=>({id:port.id,name:port.name,longitude:port.longitude,latitude:port.latitude}))} vessels={riskAssessments.filter(item=>mapLevels.includes(item.level)).map(item=>({id:item.vesselId,name:item.vesselName,longitude:riskCoordinates[item.vesselId][0],latitude:riskCoordinates[item.vesselId][1],risk:item.score,riskLevel:item.level,selected:item.vesselId===selected.vesselId,detail:item.route}))} onVesselSelect={setSelectedId}/></div></section>
        <RiskAssessmentPanel assessment={selected}/>
      </main>
    </div>
  </div>
}

function TrendingIndicator({value}:{value:string}){return <span className="trend-indicator"><ArrowRight size={17}/><small>{value}</small></span>}

function RiskAssessmentPanel({assessment,profile=false}:{assessment:RiskAssessment;profile?:boolean}){
  const [detailsOpen,setDetailsOpen]=useState(false)
  const factorTotal=assessment.factors.reduce((sum,factor)=>sum+factor.adjustedScore,0)
  const advancedFactors=assessment.factors.filter(factor=>factor.effectiveScore!==undefined)
  const hasAdvanced=advancedFactors.length>0
  return <div className={`risk-assessment ${profile?'profile-risk-assessment':''}`}>
    <section className="card risk-summary-card">
      <div className="risk-summary-main"><RiskScore assessment={assessment}/><div><span className="page-eyebrow">Текущая оценка · обновлено {assessment.updatedAt}</span><h2>{assessment.vesselName}</h2><p>{assessment.voyageId} · {assessment.route}</p><div className="risk-summary-tags"><RiskBadge level={assessment.level}/><span className="risk-change">↑ {assessment.delta} за {assessment.deltaWindow}</span><span>{assessment.modelVersion}</span></div></div></div>
      <div className="risk-scale"><span>0</span><div><i className="low"/><i className="moderate"/><i className="high"/><i className="critical"/><b style={{left:`${assessment.score}%`}}/></div><span>100</span></div>
      <div className="risk-summary-actions"><button className="secondary-button" onClick={()=>navigate('/app/map')}><MapPin size={15}/>На карте</button><button className="secondary-button" onClick={()=>navigate('/app/history')}><Play size={14}/>Повтор риска</button>{assessment.vesselId==='caspian-star'&&<button className="primary-button" onClick={()=>navigate('/app/voyages/voy-001/intelligence')}><BrainCircuit size={15}/>Аналитика рейса</button>}</div>
    </section>
    {assessment.scenario&&<section className="risk-scenario"><ShieldAlert size={20}/><span><small>{assessment.scenario.code}</small><strong>{assessment.scenario.label}</strong><p>{assessment.scenario.explanation}</p></span><em>{assessment.scenario.confidence}%<small>достоверность</small></em></section>}
    {assessment.vesselId==='caspian-star'&&<section className="environmental-risk-context-banner"><Leaf size={20}/><div><span className="page-eyebrow">Экологический контекст · на проверке</span><strong>ENV-2026-00142: пространственно-временная ассоциация</strong><p>Контекстный сигнал <b>+8</b> повышает приоритет проверки до <b>99</b>, но не изменяет каноническую морскую оценку CI-RISK-2.0: <b>91</b>. Ассоциация не доказывает источник загрязнения.</p></div><button onClick={()=>navigate('/app/environment/events/ENV-2026-00142')}>Открыть доказательства <ArrowRight size={14}/></button></section>}
    <section className="risk-explanation-digest">
      <div><span className="page-eyebrow">Краткое объяснение</span><h3>Почему риск {assessment.score}?</h3><p>{assessment.factors.length} факторов сформировали приоритет проверки. Ни один фактор сам по себе не является доказательством нарушения.</p></div>
      <div className="risk-digest-factors">{assessment.factors.slice(0,3).map(factor=><span key={factor.id}>{operationalText(factor.title)} <b>+{factor.effectiveScore??factor.adjustedScore}</b></span>)}</div>
      <button className="secondary-button risk-details-toggle" aria-expanded={detailsOpen} onClick={()=>setDetailsOpen(value=>!value)}>{detailsOpen?'Скрыть подробности':t('risk.allFactors')} <ChevronDown size={14}/></button>
    </section>
    <section className={`card risk-why-card ${detailsOpen?'':'ux-collapsed'}`}>
      <div className="risk-section-head"><div><span className="page-eyebrow">Объяснение оценки</span><h2>Почему оценка {assessment.score}?</h2></div>{hasAdvanced?<span className="factor-equation advanced-equation"><b>{assessment.baseEventScore}</b> события <i>+</i> <b>{assessment.advancedEffectiveScore}</b> расширенный контекст <i>=</i> <strong>{assessment.score}</strong></span>:<span className="factor-equation"><b>{factorTotal}</b> факторы <i>+</i> <b>{assessment.correlationScore}</b> связь <i>=</i> <strong>{assessment.score}</strong></span>}</div>
      <div className="risk-factor-list">{assessment.factors.map(factor=><RiskFactorRow key={factor.id} factor={factor}/>)}</div>
      <div className="correlation-factor"><span className="factor-icon"><GitCompareArrows size={18}/></span><span><strong>Корреляция последовательности</strong><small>Маршрут → AIS gap → встреча → осадка</small><p>Бонус ограничен 15 баллами: связанные события учитываются как одна последовательность без повторного сложения контекста.</p></span><em>+{assessment.correlationScore}</em></div>
      {hasAdvanced?<><div className="advanced-risk-normalization"><Info size={15}/><span><strong>Исходная сила: {advancedFactors.reduce((sum,factor)=>sum+factor.adjustedScore,0)} → эффективный вклад +{assessment.advancedEffectiveScore}</strong>Достоверность, корреляция и защита от двойного учёта ограничивают вклад новых признаков. Это не простая сумма строк.</span></div><div className="factor-total"><span>События этапа 5 + эффективный расширенный контекст</span><strong>{assessment.baseEventScore} + {assessment.advancedEffectiveScore} = {assessment.score}</strong></div></>:<div className="factor-total"><span>Итоговая оценка текущего рейса</span><strong>{factorTotal} + {assessment.correlationScore} = {assessment.score}</strong></div>}
    </section>
    <RiskTimeline assessment={assessment}/>
    <section className="risk-compare-grid">
      <div className="card risk-scope-card"><div className="risk-section-head"><div><span className="page-eyebrow">Область риска</span><h2>Рейс и профиль судна</h2></div></div><div className="risk-scope-values"><div className={assessment.level.toLowerCase()}><span>Риск текущего рейса</span><strong>{assessment.voyageScore}</strong><RiskBadge level={assessment.level}/><small>Активные и недавние факторы V-143</small></div><div><span>Исторический риск судна</span><strong>{assessment.vesselScore}</strong><RiskBadge level={assessment.vesselScore>=50?'HIGH':assessment.vesselScore>=25?'MODERATE':'LOW'}/><small>Взвешено по 10 последним рейсам</small></div></div><div className="decay-note"><History size={15}/><span><strong>Снижение влияния со временем</strong>АКТИВНО → НЕДАВНО → ИСТОРИЯ. Завершённые факторы постепенно перестают влиять на текущую оценку.</span></div></div>
      <div className="card risk-notifications"><div className="risk-section-head"><div><span className="page-eyebrow">Значимые уведомления</span><h2>Важные переходы</h2></div><Bell size={18}/></div>{hasAdvanced&&<div><i className="critical"/><span><strong>ДОБАВЛЕН РАСШИРЕННЫЙ КОНТЕКСТ</strong><small>17:46 · груз, топливо, экономика, связь</small></span><em>84 → 91</em></div>}<div><i className="critical"/><span><strong>ВЫСОКИЙ → КРИТИЧЕСКИЙ</strong><small>17:40 · изменение осадки и корреляция</small></span><em>54 → 84</em></div><p><Info size={13}/>Мелкие изменения не создают уведомления.</p></div>
    </section>
    {assessment.recentVoyages.length>0&&<section className="card recent-risk-voyages"><div className="risk-section-head"><div><span className="page-eyebrow">История риска</span><h2>Последние 10 рейсов</h2></div><span>Среднее: {Math.round(assessment.recentVoyages.reduce((sum,voyage)=>sum+voyage.score,0)/assessment.recentVoyages.length)} / 100</span></div><div className="recent-risk-table"><div className="recent-risk-head"><span>Рейс</span><span>Маршрут</span><span>Дата</span><span>Оценка</span><span>Уровень</span></div>{assessment.recentVoyages.map(voyage=><div className="recent-risk-row" key={voyage.id}><strong>{voyage.id}</strong><span>{voyage.route}</span><span>{voyage.date}</span><span className="voyage-score"><i style={{width:`${voyage.score}%`}}/><b>{voyage.score}</b></span><RiskBadge level={voyage.level}/></div>)}</div></section>}
  </div>
}

function RiskFactorRow({factor}:{factor:RiskFactor}){
  const [review,setReview]=useState<RiskReviewStatus>(factor.reviewStatus)
  return <article className={`risk-factor-row ${factor.effectiveScore!==undefined?'advanced-factor':''}`}><span className={`factor-icon ${factor.type}`}><EventTypeIcon type={factor.type==='correlation'?'route_deviation':factor.type}/></span><div className="factor-copy"><div><span>{factor.id} · {factor.lifecycle}{factor.effectiveScore!==undefined?' · РАСШИРЕННЫЙ':''}</span><strong>{operationalText(factor.title)}</strong></div><p>{operationalText(factor.explanation)}</p><div className="factor-evidence">{factor.evidence.map(item=><span key={item}><Check size={11}/>{operationalText(item)}</span>)}</div><div className="factor-controls">{factor.sourceEventId?<button onClick={()=>navigate('/app/events')}><Eye size={13}/>Открыть {factor.sourceEventId}</button>:factor.effectiveScore!==undefined?<button onClick={()=>navigate('/app/voyages/voy-001/intelligence')}><Eye size={13}/>Открыть расчёт</button>:<span/>}<label>Решение аналитика<select value={review} onChange={e=>setReview(e.target.value as RiskReviewStatus)}>{(Object.keys(reviewLabels) as RiskReviewStatus[]).map(status=><option key={status} value={status}>{reviewLabels[status]}</option>)}</select></label></div></div><div className="factor-score"><strong>+{factor.adjustedScore}</strong><span>{factor.effectiveScore!==undefined?`вклад +${factor.effectiveScore}`:`база ${factor.baseScore}`}</span><small>достоверность {factor.confidence}%</small></div></article>
}

function RiskTimeline({assessment}:{assessment:RiskAssessment}){return <section className="card risk-timeline-card"><div className="risk-section-head"><div><span className="page-eyebrow">Хронология риска</span><h2>Как менялась оценка</h2></div><span>{assessment.history[0]?.score} → {assessment.score}</span></div><div className="risk-timeline-chart" style={{gridTemplateColumns:`repeat(${assessment.history.length},1fr)`}}>{assessment.history.map((point,index)=><div key={`${point.time}-${point.score}`}><span className="risk-bar-space"><i className={point.level.toLowerCase()} style={{height:`${Math.max(point.score,8)}%`}}/><b style={{bottom:`calc(${Math.max(point.score,8)}% + 4px)`}}>{point.score}</b></span><time>{point.time}</time><small>{operationalText(point.reason)}</small>{index<assessment.history.length-1&&<em/>}</div>)}</div><div className="timeline-level-scale"><span>0–24 НИЗКИЙ</span><span>25–49 УМЕРЕННЫЙ</span><span>50–74 ВЫСОКИЙ</span><span>75–100 КРИТИЧЕСКИЙ</span></div></section>}

function VesselRiskView({vessel}:{vessel:Vessel}){const assessment=riskAssessments.find(item=>item.vesselId===vessel.id);if(!assessment)return <EmptyModule tab="Риск"/>;return <div className="vessel-risk-view"><div className="vessel-risk-toolbar"><div><span className="page-eyebrow">Модуль оценки риска</span><h2>Объяснимая оценка риска</h2><p>Текущий рейс, факторы и исторический контекст судна.</p></div><button className="secondary-button" onClick={()=>navigate('/app/risk')}>Открыть риск-центр <ArrowRight size={15}/></button></div><RiskAssessmentPanel assessment={assessment} profile/></div>}

function DataStatusBadge({status}:{status:IntelligenceDataStatus}){return <span className={`data-status ${status.toLowerCase()}`}>{status==='REPORTED'?<FileText size={11}/>:status==='ESTIMATED'?<Sparkles size={11}/>:<FileCheck2 size={11}/>} {dataStatusLabel(status)}</span>}

function EvidenceCard({item,accent=false}:{item:IntelligenceEvidence;accent?:boolean}){return <div className={`evidence-card ${accent?'accent':''}`}><div className="evidence-card-head"><span>{item.label}</span><DataStatusBadge status={item.status}/></div><strong>{item.value}</strong>{item.note&&<p>{item.note}</p>}<div className="evidence-source"><span><Database size={12}/>{item.source}</span><span className={`confidence-label ${item.confidence.toLowerCase()}`}>ДОСТОВЕРНОСТЬ: {confidenceLabel(item.confidence)}</span></div><time>{item.sourceTimestamp}</time></div>}

function IntelligenceSectionTitle({icon,title,eyebrow,action}:{icon:ReactNode;title:string;eyebrow:string;action?:ReactNode}){return <div className="intelligence-section-title"><span className="intelligence-title-icon">{icon}</span><div><span className="page-eyebrow">{eyebrow}</span><h2>{title}</h2></div>{action&&<div className="intelligence-title-action">{action}</div>}</div>}

function VoyageIntelligencePage(){
  const intel=voyageIntelligence
  const signals=[
    {label:'Маршрут',value:'отклонение 38 км',status:'VERIFIED' as const,icon:<Route size={17}/>,tone:'warning'},
    {label:'AIS',value:'пропуск 3 ч 15 мин',status:'VERIFIED' as const,icon:<WifiOff size={17}/>,tone:'critical'},
    {label:'Встреча',value:'TURAN · 2 ч 47 мин',status:'VERIFIED' as const,icon:<Users size={17}/>,tone:'warning'},
    {label:'Груз',value:'сталь · 5 000 т',status:'REPORTED' as const,icon:<Package size={17}/>,tone:'neutral'},
    {label:'Осадка',value:'ожидалось 5,25–5,50 м',status:'ESTIMATED' as const,icon:<Droplets size={17}/>,tone:'warning'},
    {label:'Топливо',value:'38–44 т против 61 т',status:'ESTIMATED' as const,icon:<Fuel size={17}/>,tone:'warning'},
    {label:'Экономика',value:'отношение 0,78',status:'ESTIMATED' as const,icon:<CircleDollarSign size={17}/>,tone:'warning'},
  ]
  return <div className="content-page advanced-page voyage-intelligence-page">
    <button className="back-link" onClick={()=>navigate('/app/voyages')}><ArrowLeft size={16}/>К списку рейсов</button>
    <section className="intelligence-hero">
      <div className="intelligence-identity"><span className="hero-mark"><BrainCircuit size={24}/></span><div><span className="page-eyebrow">Аналитика рейса · {intel.displayId}</span><h1>{intel.vesselName}</h1><p>IMO {intel.imo} · Грузовое судно · Казахстан</p></div></div>
      <div className="intelligence-route"><span>{intel.route.from}</span><div><i/><Ship size={17}/></div><span>{intel.route.to}</span><small>{intel.route.distance} · отправление {intel.startedAt}</small></div>
      <div className="intelligence-risk"><span>Риск</span><strong>{intel.riskScore}</strong><small>/ 100 · {riskLevelLabel(intel.riskLevel)}</small><button onClick={()=>navigate('/app/risk')}>Почему 91? <ArrowRight size={13}/></button></div>
    </section>

    <div className="decision-support-note"><ShieldCheck size={17}/><span><strong>Аналитическая поддержка решения</strong>Несоответствия ниже являются признаками для проверки. Система не делает вывода о нарушении и явно разделяет заявленные, расчётные и проверенные данные.</span><div><DataStatusBadge status="REPORTED"/><DataStatusBadge status="ESTIMATED"/><DataStatusBadge status="VERIFIED"/></div></div>

    <section className="intelligence-summary card">
      <div className="summary-count"><strong>{intel.significantFactors}</strong><span>значимых<br/>факторов</span></div>
      <div className="summary-copy"><span className="page-eyebrow">Структурированная сводка по правилам</span><h2>Рейс требует приоритетной проверки</h2><p>{operationalText(intel.summary)}</p></div>
      <ul>{intel.mainFactors.map(factor=><li key={factor}><Check size={12}/>{factor}</li>)}</ul>
    </section>

    <section className="signal-strip">{signals.map(signal=><article key={signal.label} className={`signal-card ${signal.tone}`}><div><span>{signal.icon}</span><small>{signal.label}</small></div><strong>{signal.value}</strong><DataStatusBadge status={signal.status}/></article>)}</section>

    <section className="card route-intelligence-card">
      <IntelligenceSectionTitle icon={<Route size={19}/>} eyebrow="Маршрут · AIS · встречи" title="Хронология движения и наблюдений" action={<button className="secondary-button" onClick={()=>navigate('/app/network')}><Network size={15}/>Связи рейса</button>}/>
      <div className="route-intelligence-layout">
        <div className="intelligence-route-map">
          <RealCaspianMap compact ariaLabel="Реальная карта маршрута Baku — Aktau"
            focusBounds={[[49.55,40.05],[51.45,43.85]]}
            ports={ports.filter(port=>['baku','aktau'].includes(port.id)).map(port=>({id:port.id,name:port.name,longitude:port.longitude,latitude:port.latitude,detail:port.id==='baku'?'Departure 08:00':'ETA 15:12'}))}
            routes={[
              {id:'expected-route',coordinates:[[49.89,40.37],[51.16,43.65]],color:'#75a49c',kind:'expected',dashed:true,label:'Исторический коридор'},
              {id:'ais-gap-link',coordinates:[[50.52,41.89],[50.61,42.04]],color:'#c57b34',kind:'gap',dashed:true,label:'Нет позиционных данных'},
            ]}
            tracks={[{id:'observed-route',coordinates:caspianStarTrack.map(point=>[point.longitude,point.latitude]),color:'#9d672e',kind:'observed',label:'Наблюдаемый трек'}]}
            events={[
              {id:'EV-2801',title:'Отклонение 38 км',longitude:50.44,latitude:41.74,severity:'medium',detail:'Отклонение маршрута · 13:20'},
              {id:'EV-2802',title:'Пропуск AIS 3 ч 15 мин',longitude:50.52,latitude:41.89,severity:'high',detail:'14:10–17:25'},
              {id:'EV-2803',title:'TURAN · 174 м',longitude:50.61,latitude:42.04,severity:'medium',detail:'2 ч 47 мин · ранее 14'},
            ]}
            onEventSelect={id=>navigate(id==='EV-2803'?'/app/network':'/app/events')}
          />
          <div className="route-legend"><span><i/>Исторический коридор</span><span><i/>Наблюдаемый трек</span><span><i/>Нет позиционных данных</span></div>
        </div>
        <div className="movement-facts"><div><span>Маршрут</span><strong>38 км</strong><small>отклонение · обычно 0–8 км</small></div><div><span>Покрытие AIS</span><strong>ВЫСОКАЯ</strong><small>разрыв не объясняется известной зоной покрытия</small></div><div><span>Встреча</span><strong>{intel.encounter.duration}</strong><small>{intel.encounter.vesselName} · минимум {intel.encounter.minimumDistance}</small></div><p><Info size={14}/>Линия внутри пропуска AIS показывает только возможное соединение между последней и новой позициями, а не восстановленный маршрут.</p></div>
      </div>
    </section>

    <section className="card cargo-intelligence-card">
      <IntelligenceSectionTitle icon={<Package size={19}/>} eyebrow="Аналитика груза" title="Груз и происхождение данных" action={<span className="document-reference"><FileText size={14}/>{intel.cargo.documentReference}</span>}/>
      <div className="cargo-evidence-grid"><EvidenceCard item={intel.cargo.type}/><EvidenceCard item={intel.cargo.mass} accent/><EvidenceCard item={intel.cargo.value}/><EvidenceCard item={intel.cargo.shipper}/><EvidenceCard item={intel.cargo.consignee}/></div>
      <div className="cargo-context"><div><span className="page-eyebrow">Маршрут декларации</span><strong>{operationalText(intel.cargo.origin)} <ArrowRight size={14}/> {operationalText(intel.cargo.destination)}</strong><small>Документ связан с рейсом #143</small></div><div className="cargo-profile"><span>Профиль груза · 143 рейса</span>{intel.cargo.history.map(item=><div key={item.label}><small>{operationalText(item.label)}</small><i><b style={{width:`${item.share}%`}}/></i><em>{item.share}%</em></div>)}</div><div className="cautious-result warning"><TriangleAlert size={18}/><span><strong>ЭКОНОМИЧЕСКАЯ СОГЛАСОВАННОСТЬ · НИЗКАЯ</strong><small>Заявленная стоимость выглядит нетипично для этого рейса. Требуется проверка стоимости и условий сделки.</small></span></div></div>
    </section>

    <section className="advanced-analysis-grid">
      <article className="card draught-analysis-card">
        <IntelligenceSectionTitle icon={<Droplets size={18}/>} eyebrow="Модель конкретного судна" title="Груз ↔ Осадка" action={<span className="model-confidence">87% <small>достоверность</small></span>}/>
        <div className="draught-comparison"><div><span>При отправлении</span><strong>4.2 м</strong><DataStatusBadge status="REPORTED"/></div><ArrowRight size={17}/><div className="expected"><span>Ожидалось</span><strong>5.25–5.50 м</strong><DataStatusBadge status="ESTIMATED"/></div><div className="observed"><span>Наблюдается</span><strong>4.5 м</strong><DataStatusBadge status="REPORTED"/></div></div>
        <div className="draught-scale"><span className="scale-range"/><i className="observed-marker"/><div><small>4.0</small><small>4.5</small><small>5.0</small><small>5.5 m</small></div></div>
        <div className="model-basis"><Database size={14}/><span><strong>{intel.draught.vesselSpecificRange}</strong>Собственная модель CASPIAN STAR · {intel.draught.operationsAnalyzed} исторических грузовых операций</span></div>
        <div className="anomaly-result"><TriangleAlert size={17}/><span><strong>НЕСООТВЕТСТВИЕ ГРУЗА И ОСАДКИ</strong><small>Ожидалось {intel.draught.expectedChange}; наблюдается {intel.draught.observedChange}. Данные не полностью согласуются и требуют верификации.</small></span></div>
      </article>

      <article className="card fuel-analysis-card">
        <IntelligenceSectionTitle icon={<Fuel size={18}/>} eyebrow="Модель топлива" title="Расход топлива" action={<span className="model-confidence">82% <small>достоверность</small></span>}/>
        <div className="fuel-values"><div><span>Ожидалось</span><strong>38–44 <small>т</small></strong><DataStatusBadge status="ESTIMATED"/></div><div><span>Заявлено</span><strong>61 <small>т</small></strong><DataStatusBadge status="REPORTED"/></div><em>{intel.fuel.finalDeviation}</em></div>
        <div className="fuel-corrections"><div><CloudRain size={15}/><span><strong>Поправка на погоду</strong><small>{operationalText(intel.fuel.weatherCorrection)}</small></span></div><div><TimerReset size={15}/><span><strong>Операционная поправка</strong><small>{operationalText(intel.fuel.operationalCorrection)}</small></span></div></div>
        <div className="fuel-model-meta"><span>Двигатель <strong>{intel.fuel.engine}</strong></span><span>Типичная скорость <strong>{intel.fuel.typicalSpeed}</strong></span></div>
        <div className="anomaly-result"><TriangleAlert size={17}/><span><strong>АНОМАЛИЯ РАСХОДА ТОПЛИВА</strong><small>Даже после погодной и операционной поправки заявленное значение выше ожидаемого диапазона.</small></span></div>
      </article>

      <article className="card economics-analysis-card">
        <IntelligenceSectionTitle icon={<CircleDollarSign size={18}/>} eyebrow="Экономика рейса" title="Экономическая согласованность" action={<span className="model-confidence medium">68% <small>достоверность</small></span>}/>
        <div className="economics-main"><EvidenceCard item={intel.economics.cargoValue}/><div className="economics-ratio"><span>Стоимость / затраты</span><strong>{intel.economics.ratio.toFixed(2)}</strong><small>Типично {intel.economics.typicalRatio}</small></div><EvidenceCard item={intel.economics.voyageCost}/></div>
        <div className="cost-breakdown"><span>Расчёт стоимости рейса</span>{intel.economics.costBreakdown.map(item=><div key={item.label}><small>{item.label}</small><i style={{width:`${item.value/1000/3.2}%`}}/><strong>${item.value/1000}k</strong></div>)}</div>
        <div className="anomaly-result"><TriangleAlert size={17}/><span><strong>ЭКОНОМИЧЕСКАЯ АНОМАЛИЯ</strong><small>Соотношение нетипично для исторически сопоставимых рейсов. Это индикатор качества или полноты данных, а не доказательство нарушения.</small></span></div>
      </article>
    </section>

    <section className="card intelligence-timeline-card">
      <IntelligenceSectionTitle icon={<History size={18}/>} eyebrow="Единая хронология" title="Цепочка рейса и аналитики" action={<span className="timeline-range">10 авг · 07:42–17:46</span>}/>
      <div className="intelligence-timeline">{intel.timeline.map((item,index)=><div key={`${item.time}-${item.title}`} className={`timeline-item ${item.kind}`}><time>{item.time}</time><span className="timeline-dot">{index+1}</span><div><span>{item.kind.toUpperCase()}{item.status&&<DataStatusBadge status={item.status}/>}</span><strong>{item.title}</strong><p>{item.description}</p></div></div>)}</div>
    </section>
  </div>
}

function AdvancedProfileView({vessel}:{vessel:Vessel}){if(vessel.id!=='caspian-star')return <div className="empty-module"><div><BrainCircuit size={26}/></div><h2>Расширенная аналитика</h2><p>Для этого судна пока недостаточно связанных грузовых, топливных и экономических данных.</p><span>НЕДОСТАТОЧНО ДАННЫХ</span></div>;return <div className="advanced-profile-view"><section className="card advanced-profile-summary"><div><span className="page-eyebrow">Расширенная аналитика · текущий рейс</span><h2>Данные рейса требуют проверки согласованности</h2><p>Груз, модель осадки конкретного судна, скорректированный расход топлива и экономика собраны в единую объяснимую цепочку.</p></div><span className="profile-advanced-risk"><small>Риск</small><strong>91</strong><em>84 + 7 контекст</em></span></section><div className="advanced-profile-signals"><div><Package size={18}/><span><small>Груз</small><strong>5 000 т стали</strong><em>ЗАЯВЛЕНО</em></span></div><div><Droplets size={18}/><span><small>Расхождение осадки</small><strong>+0.30 м против +1.05–1.30 м</strong><em>достоверность 87%</em></span></div><div><Fuel size={18}/><span><small>Аномалия топлива</small><strong>61 т против 38–44 т</strong><em>с поправкой на погоду и операции</em></span></div><div><CircleDollarSign size={18}/><span><small>Экономика</small><strong>Коэффициент 0.78</strong><em>обычно 2.4–4.8</em></span></div></div><div className="advanced-profile-actions"><button className="primary-button" onClick={()=>navigate('/app/voyages/voy-001/intelligence')}><BrainCircuit size={16}/>Открыть аналитику рейса</button><button className="secondary-button" onClick={()=>navigate('/app/network')}><Network size={16}/>Исследовать связи</button></div></div>}

const networkTypeLabels:Record<NetworkNodeType,string>={VESSEL:'Суда',COMPANY:'Компании',OWNER:'Владельцы',OPERATOR:'Операторы',PORT:'Порты',CARGO:'Грузы',VOYAGE:'Рейсы',EVENT:'События',ENCOUNTER:'Встречи'}
const networkEdgeLabels:Record<InvestigationNetworkEdge['type'],string>={OWNED_BY:'Владение',OPERATED_BY:'Управление',VISITED:'Посещение порта',CARRIED:'Связь с грузом',ENCOUNTERED:'Совместное присутствие',RELATED_TO:'Связанный контекст'}
const connectionPriorityLabels={LOW:'Обычный контекст',MEDIUM:'Требует внимания',HIGH:'Высокий приоритет проверки'} as const

function NetworkEntityIcon({type,size=17}:{type:NetworkNodeType;size?:number}){if(type==='VESSEL')return <Ship size={size}/>;if(type==='COMPANY')return <Building2 size={size}/>;if(type==='OWNER')return <CircleUserRound size={size}/>;if(type==='OPERATOR')return <Warehouse size={size}/>;if(type==='PORT')return <Anchor size={size}/>;if(type==='CARGO')return <Package size={size}/>;if(type==='EVENT')return <Activity size={size}/>;if(type==='ENCOUNTER')return <Users size={size}/>;return <Route size={size}/>}

function InvestigationNetworkPage(){
  const requestedEdgeId=new URLSearchParams(window.location.search).get('edge')
  const initialEdgeId=requestedEdgeId&&investigationNetwork.edges.some(edge=>edge.id===requestedEdgeId)?requestedEdgeId:null
  const [activeType,setActiveType]=useState<'ALL'|NetworkNodeType>('ALL')
  const [centerVesselId,setCenterVesselId]=useState('caspian-star')
  const [selectedNodeId,setSelectedNodeId]=useState('caspian-star')
  const [selectedEdgeId,setSelectedEdgeId]=useState<string|null>(initialEdgeId)
  const [inspectorOpen,setInspectorOpen]=useState(Boolean(initialEdgeId))
  const [graphMode,setGraphMode]=useState<'2D'|'3D'>('3D')
  const [camera,setCamera]=useState({yaw:-0.32,pitch:0.18,zoom:1})
  const [rotating,setRotating]=useState(false)
  const graphDrag=useRef<{pointerId:number;x:number;y:number;yaw:number;pitch:number}|null>(null)
  const [query,setQuery]=useState('')
  const centerVessel=investigationNetwork.nodes.find(node=>node.id===centerVesselId)||investigationNetwork.nodes[0]
  const spatialPositions=useMemo(()=>{
    const positions=new globalThis.Map<string,{x:number;y:number;z:number}>()
    positions.set(centerVesselId,{x:0,y:0,z:0})
    const distribute=(items:InvestigationNetworkNode[],radiusX:number,radiusY:number,depth:number,offset:number)=>items.forEach((node,index)=>{const angle=offset+(Math.PI*2*index/Math.max(items.length,1));positions.set(node.id,{x:Math.cos(angle)*radiusX,y:Math.sin(angle)*radiusY,z:Math.sin(angle*1.7+offset)*depth})})
    const remaining=investigationNetwork.nodes.filter(node=>node.id!==centerVesselId)
    distribute(remaining.filter(node=>node.type==='EVENT'||node.type==='ENCOUNTER'),.52,.58,.34,-Math.PI/2)
    distribute(remaining.filter(node=>node.type==='VESSEL'||node.type==='VOYAGE'),.74,.76,.48,-Math.PI/3)
    distribute(remaining.filter(node=>node.type==='COMPANY'||node.type==='OWNER'||node.type==='OPERATOR'),.88,.89,.64,-Math.PI/2)
    distribute(remaining.filter(node=>node.type==='PORT'||node.type==='CARGO'),1,1,.78,-Math.PI/6)
    return positions
  },[centerVesselId])
  const nodePositions=useMemo(()=>{
    const positions=new globalThis.Map<string,{x:number;y:number;scale:number;depth:number;opacity:number}>()
    const cosYaw=Math.cos(camera.yaw),sinYaw=Math.sin(camera.yaw),cosPitch=Math.cos(camera.pitch),sinPitch=Math.sin(camera.pitch)
    spatialPositions.forEach((point,id)=>{
      if(graphMode==='2D'){positions.set(id,{x:50+point.x*41*camera.zoom,y:48+point.y*45*camera.zoom,scale:1,depth:0,opacity:1});return}
      const rotatedX=point.x*cosYaw-point.z*sinYaw
      const yawDepth=point.x*sinYaw+point.z*cosYaw
      const rotatedY=point.y*cosPitch-yawDepth*sinPitch
      const depth=point.y*sinPitch+yawDepth*cosPitch
      const perspective=Math.max(.68,Math.min(1.38,2.7/(2.7+depth)))
      positions.set(id,{x:50+rotatedX*40*perspective*camera.zoom,y:48+rotatedY*43*perspective*camera.zoom,scale:Math.max(.74,Math.min(1.2,perspective)),depth,opacity:Math.max(.62,Math.min(1,1-depth*.18))})
    })
    return positions
  },[camera,graphMode,spatialPositions])
  const positionOf=(node:InvestigationNetworkNode)=>nodePositions.get(node.id)||{x:node.x,y:node.y,scale:1,depth:0,opacity:1}
  const resetGraphView=()=>setCamera({yaw:-0.32,pitch:0.18,zoom:1})
  const changeZoom=(amount:number)=>setCamera(value=>({...value,zoom:Math.max(.65,Math.min(1.55,value.zoom+amount))}))
  const startGraphRotation=(event:React.PointerEvent<HTMLDivElement>)=>{if(graphMode!=='3D'||(event.target as Element).closest('button,.graph-edge-hit'))return;graphDrag.current={pointerId:event.pointerId,x:event.clientX,y:event.clientY,yaw:camera.yaw,pitch:camera.pitch};event.currentTarget.setPointerCapture(event.pointerId);setRotating(true)}
  const moveGraphRotation=(event:React.PointerEvent<HTMLDivElement>)=>{const drag=graphDrag.current;if(!drag||drag.pointerId!==event.pointerId)return;setCamera(value=>({...value,yaw:drag.yaw+(event.clientX-drag.x)*.008,pitch:Math.max(-1.05,Math.min(1.05,drag.pitch-(event.clientY-drag.y)*.007))}))}
  const stopGraphRotation=(event:React.PointerEvent<HTMLDivElement>)=>{if(graphDrag.current?.pointerId===event.pointerId)graphDrag.current=null;setRotating(false)}
  const nodes=investigationNetwork.nodes.filter(node=>node.id===centerVesselId||((activeType==='ALL'||node.type===activeType)&&node.label.toLowerCase().includes(query.toLowerCase())))
  const visibleNodeIds=new Set(nodes.map(node=>node.id))
  const visibleEdges=investigationNetwork.edges.filter(edge=>visibleNodeIds.has(edge.source)&&visibleNodeIds.has(edge.target))
  const selectedNode=investigationNetwork.nodes.find(node=>node.id===selectedNodeId)||investigationNetwork.nodes[0]
  const selectedEdge=investigationNetwork.edges.find(edge=>edge.id===selectedEdgeId)
  const connectedEdges=investigationNetwork.edges.filter(edge=>edge.source===selectedNode.id||edge.target===selectedNode.id)
  const selectNode=(node:InvestigationNetworkNode)=>{if(node.type==='VESSEL'){setCenterVesselId(node.id);resetGraphView()}setSelectedNodeId(node.id);setSelectedEdgeId(null);setInspectorOpen(true)}
  const selectEdge=(edge:InvestigationNetworkEdge)=>{setSelectedEdgeId(edge.id);setSelectedNodeId(edge.source);setInspectorOpen(true)}
  const nodeById=(id:string)=>investigationNetwork.nodes.find(node=>node.id===id)!
  return <div className="content-page advanced-page network-page">
    <PageHeader eyebrow="Аналитика связей" title="Сеть расследования" description="Объяснимая сеть судов, компаний, владельцев, операторов, портов, грузов и рейсов." actions={<button className="secondary-button" onClick={()=>navigate('/app/voyages/voy-001/intelligence')}><BrainCircuit size={16}/>Аналитика рейса</button>}/>
    <div className="network-caution"><Info size={16}/><span><strong>Связь не означает нарушение и не переносит риск между объектами.</strong> Толщина показывает приоритет проверки, а панель справа — факты, источник и доказательства.</span><em>{investigationNetwork.nodes.length} объектов · {investigationNetwork.edges.length} связей</em></div>
    <div className="network-toolbar"><div className="inline-search"><Search size={16}/><input value={query} onChange={event=>setQuery(event.target.value)} placeholder="Объект, компания или рейс"/></div><div className="network-type-filters"><button className={activeType==='ALL'?'active':''} onClick={()=>setActiveType('ALL')}>Все <span>{investigationNetwork.nodes.length}</span></button>{(Object.keys(networkTypeLabels) as NetworkNodeType[]).map(type=><button key={type} className={activeType===type?'active':''} onClick={()=>setActiveType(type)}>{networkTypeLabels[type]}</button>)}</div></div>
    <div className="network-workspace">
      <main className="card investigation-graph-card">
        <div className="graph-head"><div><span className="page-eyebrow">Интерактивная орбита · центр можно изменить</span><h2>{centerVessel.label} · {investigationNetwork.nodes.length} объектов и {investigationNetwork.edges.length} связей</h2></div><div className="graph-head-actions"><div className="graph-view-controls"><span><button className={graphMode==='3D'?'active':''} onClick={()=>setGraphMode('3D')}>3D</button><button className={graphMode==='2D'?'active':''} onClick={()=>setGraphMode('2D')}>2D</button></span><button aria-label="Отдалить сеть" onClick={()=>changeZoom(-.12)}><ZoomOut size={14}/></button><button aria-label="Приблизить сеть" onClick={()=>changeZoom(.12)}><ZoomIn size={14}/></button><button onClick={resetGraphView}><Target size={14}/>Сбросить</button></div><div className="graph-legend"><span><i className="priority-high"/>Высокий приоритет</span><span><i className="priority-medium"/>Требует внимания</span><span><i className="priority-low"/>Обычный контекст</span></div></div></div>
        <div className={`investigation-graph-canvas graph-mode-${graphMode.toLowerCase()} ${rotating?'is-rotating':''}`} onPointerDown={startGraphRotation} onPointerMove={moveGraphRotation} onPointerUp={stopGraphRotation} onPointerCancel={stopGraphRotation} onWheel={event=>{if(graphMode==='3D'){event.preventDefault();changeZoom(event.deltaY>0?-.08:.08)}}}>
          <div className="orbit-ring orbit-ring-events"/><div className="orbit-ring orbit-ring-vessels"/><div className="orbit-ring orbit-ring-organizations"/><div className="orbit-ring orbit-ring-context"/>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Интерактивные связи объектов">{visibleEdges.map(edge=>{const source=nodeById(edge.source),target=nodeById(edge.target);const sourcePosition=positionOf(source),targetPosition=positionOf(target);const priority=edge.priority||'LOW';const opacity=Math.min(sourcePosition.opacity,targetPosition.opacity);return <g key={edge.id} style={{opacity}} className={`graph-edge-group priority-${priority.toLowerCase()} ${selectedEdgeId===edge.id?'selected':''}`}><line className="graph-edge-visible" x1={sourcePosition.x} y1={sourcePosition.y} x2={targetPosition.x} y2={targetPosition.y}/><line className="graph-edge-hit" x1={sourcePosition.x} y1={sourcePosition.y} x2={targetPosition.x} y2={targetPosition.y} role="button" tabIndex={0} aria-label={`${source.label} — ${target.label}: ${edge.label}`} onClick={()=>selectEdge(edge)} onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selectEdge(edge)}}}/></g>})}</svg>
          <div className="mobile-edge-list">{visibleEdges.map(edge=>{const source=nodeById(edge.source),target=nodeById(edge.target);const priority=edge.priority||'LOW';return <button key={`mobile-${edge.id}`} className={`${priority.toLowerCase()} ${selectedEdgeId===edge.id?'selected':''}`} onClick={()=>selectEdge(edge)}><i/><span><strong>{source.label} → {target.label}</strong><small>{networkEdgeLabels[edge.type]} · {edge.label}</small></span><em>{connectionPriorityLabels[priority]}</em></button>})}</div>
          {nodes.map(node=>{const position=positionOf(node);return <button key={node.id} style={{left:`${position.x}%`,top:`${position.y}%`,zIndex:Math.round(20-position.depth*10),'--node-scale':position.scale,'--node-opacity':position.opacity} as CSSProperties} className={`graph-node ${node.type.toLowerCase()} ${node.id===centerVesselId?'orbit-center':''} ${selectedNode.id===node.id?'selected':''}`} onClick={()=>selectNode(node)}><span><NetworkEntityIcon type={node.type}/></span><div><small>{networkTypeLabels[node.type]}</small><strong>{node.label}</strong><em>{node.subtitle}</em></div>{node.risk!==undefined&&<b className={node.risk>=75?'critical':'high'}>{node.risk}</b>}</button>})}
          {visibleEdges.filter(edge=>edge.id==='e-encounter'||edge.id===selectedEdgeId).map(edge=>{const source=nodeById(edge.source),target=nodeById(edge.target);const sourcePosition=positionOf(source),targetPosition=positionOf(target);return <button key={`label-${edge.id}`} style={{left:`${(sourcePosition.x+targetPosition.x)/2}%`,top:`${(sourcePosition.y+targetPosition.y)/2}%`}} className={`primary-edge-label ${selectedEdgeId===edge.id?'selected':''}`} onClick={()=>selectEdge(edge)}><Link2 size={13}/><span>{edge.label}<small>{connectionPriorityLabels[edge.priority||'LOW']}</small></span></button>})}
          {graphMode==='3D'&&<div className="graph-navigation-hint"><Compass size={14}/><span><strong>Вращение:</strong> тяните свободную область · <strong>масштаб:</strong> колесо</span></div>}
          {!nodes.length&&<div className="graph-empty"><Search size={22}/><strong>Объекты не найдены</strong><span>Измените запрос или тип сущности</span></div>}
        </div>
      </main>
      {inspectorOpen&&<button className="network-inspector-backdrop" aria-label="Закрыть панель связи" onClick={()=>setInspectorOpen(false)}/>}
      <aside className={`network-inspector card ${inspectorOpen?'mobile-open':''}`}>
        <button className="network-inspector-close" aria-label="Закрыть информационную панель" onClick={()=>setInspectorOpen(false)}><X size={17}/></button>
        {selectedEdge?<EdgeInspector edge={selectedEdge} onNode={id=>selectNode(nodeById(id))}/>:<NodeInspector node={selectedNode} edges={connectedEdges} onNode={id=>selectNode(nodeById(id))} onEdge={id=>setSelectedEdgeId(id)}/>} 
      </aside>
    </div>
    <section className="connection-proof card"><div className="connection-proof-head"><span className="connection-pair"><Ship size={18}/><strong>{investigationNetwork.primaryConnection.source}</strong><Link2 size={17}/><strong>{investigationNetwork.primaryConnection.target}</strong></span><span className="connection-strength">{operationalText(investigationNetwork.primaryConnection.strength)} СВЯЗЬ</span></div><div className="connection-proof-metrics"><div><strong>{investigationNetwork.primaryConnection.encounters}</strong><span>встреч</span></div><div><strong>{investigationNetwork.primaryConnection.openSea}</strong><span>в открытом море</span></div><div><strong>{investigationNetwork.primaryConnection.averageDistance}</strong><span>средняя дистанция</span></div><div><strong>{investigationNetwork.primaryConnection.totalDuration}</strong><span>суммарно рядом</span></div><div><strong>{investigationNetwork.primaryConnection.period}</strong><span>период анализа</span></div></div><p><Info size={15}/>{operationalText(investigationNetwork.primaryConnection.explanation)}</p></section>
  </div>
}

function EdgeInspector({edge,onNode}:{edge:InvestigationNetworkEdge;onNode:(id:string)=>void}){const source=investigationNetwork.nodes.find(node=>node.id===edge.source)!;const target=investigationNetwork.nodes.find(node=>node.id===edge.target)!;const priority=edge.priority||'LOW';return <><div className="inspector-heading edge-inspector-heading"><span className={`inspector-icon priority-${priority.toLowerCase()}`}><Link2 size={18}/></span><div><span className="page-eyebrow">Выбранная связь · {edge.id}</span><h2>{networkEdgeLabels[edge.type]}</h2><p>{operationalText(edge.label)}</p></div><span className={`confidence-label ${edge.confidence.toLowerCase()}`}>{confidenceLabel(edge.confidence)}</span></div><div className={`connection-priority-banner ${priority.toLowerCase()}`}><ShieldAlert size={16}/><span><small>Приоритет связи</small><strong>{connectionPriorityLabels[priority]}</strong></span></div><div className="inspector-pair"><button onClick={()=>onNode(source.id)}><NetworkEntityIcon type={source.type}/><span><strong>{source.label}</strong><small>{operationalText(source.subtitle)}</small></span></button><ArrowRight size={16}/><button onClick={()=>onNode(target.id)}><NetworkEntityIcon type={target.type}/><span><strong>{target.label}</strong><small>{operationalText(target.subtitle)}</small></span></button></div><div className="edge-explanation"><h3>Почему объекты связаны</h3><p>{operationalText(edge.explanation)}</p></div>{edge.observations&&<div className="edge-evidence">{edge.observations.map(item=><InfoRow key={item.label} label={operationalText(item.label)} value={operationalText(item.value)}/>)}</div>}{edge.evidence&&<div className="connection-evidence-list"><h3>Связанные доказательства</h3>{edge.evidence.map(item=><button key={item} onClick={()=>navigate('/app/events')}><FileCheck2 size={13}/><span>{operationalText(item)}</span><ChevronRight size={13}/></button>)}</div>}<div className="inspector-source"><Database size={14}/><span><strong>Источник связи</strong><small>{operationalText(edge.sourceLabel||'Объяснимый граф')}{edge.updatedAt&&` · обновлено ${edge.updatedAt}`}</small></span><DataStatusBadge status={edge.dataStatus||'ESTIMATED'}/></div><div className="connection-human-note"><Info size={14}/><span>Приоритет помогает выбрать связь для проверки и не является выводом о нарушении или характере отношений.</span></div></>}

function NodeInspector({node,edges,onNode,onEdge}:{node:InvestigationNetworkNode;edges:typeof investigationNetwork.edges;onNode:(id:string)=>void;onEdge:(id:string)=>void}){return <><div className="inspector-heading"><span className={`inspector-icon ${node.type.toLowerCase()}`}><NetworkEntityIcon type={node.type}/></span><div><span className="page-eyebrow">{networkTypeLabels[node.type]}</span><h2>{node.label}</h2><p>{operationalText(node.subtitle)}</p></div>{node.risk!==undefined&&<b className="inspector-risk">{node.risk}<small>риск</small></b>}</div><div className="node-details">{node.details.map(item=><InfoRow key={item.label} label={operationalText(item.label)} value={operationalText(item.value)}/>)}</div><div className="connected-objects"><h3>Связанные объекты <span>{edges.length}</span></h3>{edges.map(edge=>{const otherId=edge.source===node.id?edge.target:edge.source;const other=investigationNetwork.nodes.find(item=>item.id===otherId)!;const priority=edge.priority||'LOW';return <button key={edge.id} className={`priority-${priority.toLowerCase()}`} onClick={()=>onEdge(edge.id)} onDoubleClick={()=>onNode(other.id)}><span className={`connected-icon ${other.type.toLowerCase()}`}><NetworkEntityIcon type={other.type} size={14}/></span><span><strong>{other.label}</strong><small>{networkEdgeLabels[edge.type]} · {operationalText(edge.label)}</small></span><em>{connectionPriorityLabels[priority]}</em><ChevronRight size={14}/></button>})}</div><div className="inspector-source"><ShieldCheck size={14}/><span><strong>Объяснимые связи</strong><small>Нажмите на строку, чтобы увидеть основание, факты и источник связи.</small></span></div></>}

function AnalyticsPage(){const bars=[48,62,54,77,69,83,74,91,78,67,81,88];return <div className="content-page"><PageHeader eyebrow="Операционная аналитика" title="Обзор региона" description="Сводные показатели движения флота и портовой активности." actions={<button className="secondary-button"><Clock3 size={16}/>Последние 24 часа <ChevronDown size={15}/></button>}/><div className="analytics-stats"><div className="metric-card"><span>Судов в регионе</span><strong>84</strong><small className="positive">↑ 7.7% к вчера</small><Ship size={22}/></div><div className="metric-card"><span>Активных рейсов</span><strong>36</strong><small>43% флота</small><Route size={22}/></div><div className="metric-card"><span>Заходов в порты</span><strong>18</strong><small className="positive">↑ 3 за сутки</small><Anchor size={22}/></div><div className="metric-card"><span>Средняя скорость</span><strong>9.8 <em>kn</em></strong><small>По судам в движении</small><Waves size={22}/></div></div><div className="analytics-grid"><section className="card chart-card"><div className="card-head"><div><span className="page-eyebrow">Плотность трафика</span><h2>Движение судов по часам</h2></div><span className="chart-legend"><i/>Суда в движении</span></div><div className="bar-chart">{bars.map((b,i)=><div key={i}><span style={{height:`${b}%`}}/><small>{String(i*2).padStart(2,'0')}:00</small></div>)}</div></section><section className="card"><div className="card-head"><div><span className="page-eyebrow">Порты</span><h2>Текущая загрузка</h2></div></div><div className="port-load">{ports.slice(0,5).map((p,i)=><div key={p.id}><span><strong>{p.name}</strong><small>{p.vessels} судов</small></span><div><i style={{width:`${[72,88,54,63,47][i]}%`}}/></div><em>{[72,88,54,63,47][i]}%</em></div>)}</div></section></div></div>}

function InvestigationPage(){return <div className="content-page"><PageHeader eyebrow="Рабочая область" title="Расследования" description="Формируйте подборки судов, событий и географических областей." actions={<button className="primary-button"><Plus size={17}/>Новое расследование</button>}/><div className="investigation-empty"><div className="investigation-visual"><Target size={34}/><span/><span/></div><h2>Рабочая область подготовлена</h2><p>На первом этапе вы можете создавать структуры расследований. Интеллектуальные правила и автоматические связи появятся в следующих модулях.</p><button className="secondary-button"><Plus size={17}/>Создать первое расследование</button><div className="capability-row"><span><Ship size={18}/>Подборки судов</span><span><MapPin size={18}/>Области на карте</span><span><History size={18}/>Хронология событий</span></div></div></div>}

function SettingsPage(){return <div className="content-page settings-page"><PageHeader eyebrow="Конфигурация" title="Настройки платформы" description="Профиль, уведомления и параметры рабочего пространства."/><div className="settings-layout"><aside className="settings-nav"><button className="active"><CircleUserRound size={18}/>Профиль</button><button><Bell size={18}/>Уведомления</button><button><Layers3 size={18}/>Карта и слои</button><button><Users size={18}/>Пользователи и роли</button><button><ShieldCheck size={18}/>Безопасность</button></aside><section className="card settings-form"><div className="settings-title"><h2>Профиль пользователя</h2><p>Основная информация о вашей учётной записи.</p></div><div className="profile-edit"><div className="avatar large">АК</div><div><strong>Аян Касымов</strong><span>АНАЛИТИК</span></div><button className="secondary-button">Изменить фото</button></div><div className="form-grid"><label>Имя<input defaultValue="Аян"/></label><label>Фамилия<input defaultValue="Касымов"/></label><label>Рабочая почта<input defaultValue="analyst@caspian.int"/></label><label>Роль<input defaultValue="Аналитик" disabled/></label><label>Организация<input defaultValue="Центр Каспийской аналитики"/></label><label>Часовой пояс<select defaultValue="utc5"><option value="utc5">UTC+5 — Актау</option></select></label></div><div className="form-actions"><button className="secondary-button">Отменить</button><button className="primary-button">Сохранить изменения</button></div></section></div></div>}

function NotFound(){return <div className="empty-module fullpage"><div><MapPin size={28}/></div><h2>Страница не найдена</h2><button className="primary-button" onClick={()=>navigate('/app/map')}>Вернуться на карту</button></div>}

export default function App() {
  const [path,setPath]=useState(window.location.pathname)
  useEffect(()=>{const fn=()=>setPath(window.location.pathname); addEventListener('popstate',fn); return()=>removeEventListener('popstate',fn)},[])
  useEffect(()=>{if(path==='/' ) navigate(localStorage.getItem('ci-session')?'/app/map':'/login')},[path])
  useEffect(()=>{const fn=(e:KeyboardEvent)=>{if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault(); document.querySelector<HTMLButtonElement>('.global-search')?.click()}};addEventListener('keydown',fn);return()=>removeEventListener('keydown',fn)},[])
  const page=useMemo(()=>{
    if(path==='/app/caspian') return <CaspianNetworkDashboard navigate={navigate}/>
    if(path==='/app/caspian/risk') return <RegionalRiskCenterPage navigate={navigate}/>
    if(path==='/app/caspian/routes') return <RouteIntelligencePage navigate={navigate}/>
    if(path==='/app/caspian/verification') return <CrossPortVerificationPage navigate={navigate}/>
    if(path==='/app/caspian/data-health') return <RegionalDataHealthPage navigate={navigate}/>
    if(path==='/app/caspian/network') return <RegionalNetworkGraphPage navigate={navigate}/>
    if(path==='/app/caspian/search') return <RegionalSearchPage navigate={navigate}/>
    if(path==='/app/caspian/scope') return <DataScopePage navigate={navigate}/>
    if(path==='/app/map') return <MapPage/>
    if(path==='/app/vessels') return <VesselsPage/>
    if(path.startsWith('/app/vessels/')) {const v=vessels.find(x=>x.id===path.split('/').pop())||vessels[0];return <VesselProfile vessel={v}/>} 
    if(path==='/app/voyages') return <VoyagesPage/>
    if(path==='/app/voyages/voy-001/intelligence') return <VoyageIntelligencePage/>
    if(path==='/app/history') return <HistoryPage/>
    if(path==='/app/risk') return <RiskCenterPage/>
    if(path==='/app/events') return <EventsPage/>
    if(path.startsWith('/app/environment/events/')) return <EnvironmentalEventPage eventId={decodeURIComponent(path.split('/').pop() || 'ENV-2026-00142')} navigate={navigate}/>
    if(path==='/app/environment') return <EnvironmentalCenterPage navigate={navigate}/>
    if(path==='/app/assistant') return <AssistantPage/>
    if(path==='/app/investigation'||path==='/app/investigations') return <InvestigationListPage/>
    if(path.startsWith('/app/investigations/')) return <InvestigationWorkspacePage/>
    if(path==='/app/network') return <InvestigationNetworkPage/>
    if(path==='/app/ports') return <CaspianPortRegistryPage navigate={navigate}/>
    if(path.startsWith('/app/ports/')) {const parts=path.split('/').filter(Boolean);return <CaspianPortDetailPage navigate={navigate} portId={parts[2]||'aktau'} initialTab={parts[3]||'overview'}/>} 
    if(path==='/app/port'||path==='/app/port/aktau') return <PortControlCenterPage/>
    if(path==='/app/port/aktau/arrivals') return <PortArrivalsPage/>
    if(path==='/app/port-calls/pc-aktau-143') return <PreArrivalReportPage/>
    if(path==='/app/analytics') return <AnalyticsPage/>
    if(path==='/app/settings') return <SettingsPage/>
    return <NotFound/>
  },[path])
  if(path==='/login') return <Login/>
  return <AppShell path={path}>{page}</AppShell>
}
