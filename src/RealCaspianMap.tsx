import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import {
  AttributionControl,
  Map as MapLibreMap,
  ScaleControl,
  setWorkerUrl,
  type ExpressionSpecification,
  type GeoJSONSource,
  type MapLayerMouseEvent,
  type StyleSpecification,
} from 'maplibre-gl'
import mapLibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import type { Feature, FeatureCollection, LineString, Point, Polygon } from 'geojson'
import 'maplibre-gl/dist/maplibre-gl.css'
import './real-map.css'

setWorkerUrl(mapLibreWorkerUrl)

export type RealMapMode = 'standard' | 'satellite'

export type RealMapPort = {
  id: string
  name: string
  longitude: number
  latitude: number
  status?: string
  detail?: string
  color?: string
}

export type RealMapVessel = {
  id: string
  name: string
  longitude: number
  latitude: number
  course?: number
  status?: string
  speed?: number
  risk?: number
  riskLevel?: string
  color?: string
  detail?: string
  selected?: boolean
}

export type RealMapEvent = {
  id: string
  title: string
  longitude: number
  latitude: number
  severity?: string
  detail?: string
  color?: string
}

export type RealMapLine = {
  id: string
  coordinates: Array<[number, number]>
  color?: string
  kind?: string
  label?: string
  dashed?: boolean
}

export type RealMapArea = {
  id: string
  rings: number[][][]
  kind: 'pollution' | 'origin' | 'risk' | 'coverage-ais' | 'coverage-environment' | 'coverage-port' | 'selection'
  label?: string
}

export type RealMapAnnotation = {
  id: string
  label: string
  longitude: number
  latitude: number
  detail?: string
  color?: string
}

export type RealCaspianMapHandle = {
  zoomIn: () => void
  zoomOut: () => void
  reset: () => void
  resize: () => void
  unprojectPercent: (x: number, y: number) => { longitude: number; latitude: number } | null
}

type RealCaspianMapProps = {
  className?: string
  ariaLabel?: string
  mode?: RealMapMode
  compact?: boolean
  interactive?: boolean
  clusterVessels?: boolean
  ports?: RealMapPort[]
  vessels?: RealMapVessel[]
  events?: RealMapEvent[]
  environmentalEvents?: RealMapEvent[]
  routes?: RealMapLine[]
  tracks?: RealMapLine[]
  areas?: RealMapArea[]
  annotations?: RealMapAnnotation[]
  focusBounds?: [[number, number], [number, number]]
  onPortSelect?: (id: string) => void
  onVesselSelect?: (id: string) => void
  onEventSelect?: (id: string) => void
  onEnvironmentalSelect?: (id: string) => void
  onPointerCoordinate?: (coordinate: { longitude: number; latitude: number }) => void
}

const DEFAULT_STYLE_URL = import.meta.env.VITE_MAP_STYLE_URL || 'https://tiles.openfreemap.org/styles/liberty'
const SATELLITE_STYLE_URL = import.meta.env.VITE_MAP_SATELLITE_STYLE_URL || ''
const DEFAULT_CENTER: [number, number] = [50.55, 41.75]
const DEFAULT_BOUNDS: [[number, number], [number, number]] = [[46.25, 35.55], [55.75, 47.45]]
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: 'offline-background', type: 'background', paint: { 'background-color': '#dfe8e5' } }],
}

export const satelliteMapAvailable = Boolean(SATELLITE_STYLE_URL)

function emptyCollection<G extends Point | LineString | Polygon>(): FeatureCollection<G> {
  return { type: 'FeatureCollection', features: [] }
}

function pointCollection<T extends { id: string; longitude: number; latitude: number }>(
  items: T[],
  properties: (item: T) => Record<string, string | number | boolean | null>,
): FeatureCollection<Point> {
  return {
    type: 'FeatureCollection',
    features: items.filter(item => Number.isFinite(item.longitude) && Number.isFinite(item.latitude)).map(item => ({
      type: 'Feature',
      id: item.id,
      geometry: { type: 'Point', coordinates: [item.longitude, item.latitude] },
      properties: { id: item.id, ...properties(item) },
    })),
  }
}

function lineCollection(items: RealMapLine[]): FeatureCollection<LineString> {
  return {
    type: 'FeatureCollection',
    features: items.filter(item => item.coordinates.length > 1).map(item => ({
      type: 'Feature',
      id: item.id,
      geometry: { type: 'LineString', coordinates: item.coordinates },
      properties: {
        id: item.id,
        color: item.color || '#19776e',
        kind: item.kind || 'route',
        label: item.label || '',
        dashed: Boolean(item.dashed),
      },
    })),
  }
}

function areaCollection(items: RealMapArea[]): FeatureCollection<Polygon> {
  return {
    type: 'FeatureCollection',
    features: items.filter(item => item.rings.length > 0).map(item => ({
      type: 'Feature',
      id: item.id,
      geometry: { type: 'Polygon', coordinates: item.rings },
      properties: { id: item.id, kind: item.kind, label: item.label || '' },
    })),
  }
}

function riskColor(level?: string, fallback?: string) {
  if (fallback) return fallback
  if (level === 'CRITICAL') return '#bd4c36'
  if (level === 'HIGH') return '#d27631'
  if (level === 'MODERATE') return '#b99432'
  if (level === 'LOW') return '#218170'
  return '#187970'
}

function datasetsFrom(props: RealCaspianMapProps) {
  const ports = pointCollection(props.ports || [], port => ({
    name: port.name,
    label: port.name,
    status: port.status || '',
    detail: port.detail || '',
    color: port.color || '#315f59',
  }))
  const vessels = pointCollection(props.vessels || [], vessel => ({
    name: vessel.name,
    label: vessel.risk === undefined ? vessel.name : `${vessel.name} · ${vessel.risk}`,
    course: vessel.course || 0,
    status: vessel.status || '',
    speed: vessel.speed || 0,
    risk: vessel.risk ?? -1,
    riskLevel: vessel.riskLevel || '',
    detail: vessel.detail || '',
    selected: Boolean(vessel.selected),
    color: riskColor(vessel.riskLevel, vessel.color),
  }))
  const events = pointCollection(props.events || [], event => ({
    title: event.title,
    label: event.title,
    severity: event.severity || '',
    detail: event.detail || '',
    color: event.color || (event.severity === 'high' ? '#bd4c36' : event.severity === 'medium' ? '#d27631' : '#72817d'),
  }))
  const environmental = pointCollection(props.environmentalEvents || [], event => ({
    title: event.title,
    label: event.title,
    severity: event.severity || '',
    detail: event.detail || '',
    color: event.color || '#27785f',
  }))
  const annotations = pointCollection(props.annotations || [], item => ({
    title: item.label,
    label: item.label,
    detail: item.detail || '',
    color: item.color || '#1d625b',
  }))
  return {
    ports,
    vessels,
    events,
    environmental,
    routes: lineCollection(props.routes || []),
    tracks: lineCollection(props.tracks || []),
    areas: areaCollection(props.areas || []),
    annotations,
  }
}

type MapDatasets = ReturnType<typeof datasetsFrom>

function addSource(map: MapLibreMap, id: string, data: FeatureCollection<Point | LineString | Polygon>, cluster = false) {
  map.addSource(id, {
    type: 'geojson',
    data,
    ...(cluster ? { cluster: true, clusterMaxZoom: 6, clusterRadius: 34 } : {}),
  })
}

function localizeBasemapLabels(map: MapLibreMap) {
  for (const layer of map.getStyle().layers || []) {
    if (layer.type !== 'symbol' || layer.id.startsWith('ci-')) continue
    const current = map.getLayoutProperty(layer.id, 'text-field')
    if (!Array.isArray(current) || !JSON.stringify(current).includes('name')) continue
    map.setLayoutProperty(layer.id, 'text-field', [
      'coalesce',
      ['get', 'name:ru'],
      ['get', 'name_ru'],
      current,
    ] as ExpressionSpecification)
  }
}

function addOperationalLayers(map: MapLibreMap, data: MapDatasets, compact: boolean, clusterVessels: boolean) {
  addSource(map, 'ci-areas', data.areas)
  map.addLayer({ id: 'ci-areas-fill', type: 'fill', source: 'ci-areas', paint: {
    'fill-color': ['match', ['get', 'kind'],
      'pollution', '#bd5f2d', 'origin', '#d7a044', 'risk', '#c1533d',
      'coverage-ais', '#3d8d82', 'coverage-environment', '#4f8a67',
      'coverage-port', '#5a7892', 'selection', '#08796e', '#6f8b84'],
    'fill-opacity': ['match', ['get', 'kind'],
      'pollution', .28, 'origin', .16, 'risk', .18,
      'coverage-ais', .13, 'coverage-environment', .12, 'coverage-port', .15, .12],
  } })
  map.addLayer({ id: 'ci-areas-outline', type: 'line', source: 'ci-areas', paint: {
    'line-color': ['match', ['get', 'kind'],
      'pollution', '#a95128', 'origin', '#b67a22', 'risk', '#b24735',
      'coverage-ais', '#287a70', 'coverage-environment', '#387858',
      'coverage-port', '#476a86', 'selection', '#08796e', '#5c7c75'],
    'line-width': ['match', ['get', 'kind'], 'pollution', 2.4, 'selection', 2.2, 1.5],
    'line-opacity': .92,
  } })

  addSource(map, 'ci-routes', data.routes)
  map.addLayer({ id: 'ci-routes-line', type: 'line', source: 'ci-routes', paint: {
    'line-color': ['coalesce', ['get', 'color'], '#4c8c83'],
    'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1, 7, 3],
    'line-opacity': .72,
    'line-dasharray': [2, 2],
  } })

  addSource(map, 'ci-tracks', data.tracks)
  map.addLayer({ id: 'ci-tracks-halo', type: 'line', source: 'ci-tracks', paint: {
    'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 4, 9, 8], 'line-opacity': .76,
  } })
  map.addLayer({ id: 'ci-tracks-line', type: 'line', source: 'ci-tracks', paint: {
    'line-color': ['coalesce', ['get', 'color'], '#b96b2f'],
    'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.8, 9, 4],
    'line-opacity': .95,
  } })

  addSource(map, 'ci-ports', data.ports)
  map.addLayer({ id: 'ci-ports-halo', type: 'circle', source: 'ci-ports', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 5, 8, 10],
    'circle-color': '#ffffff', 'circle-opacity': .94,
  } })
  map.addLayer({ id: 'ci-ports-point', type: 'circle', source: 'ci-ports', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 3.2, 8, 6.5],
    'circle-color': ['coalesce', ['get', 'color'], '#315f59'],
    'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1,
  } })
  map.addLayer({ id: 'ci-ports-label', type: 'symbol', source: 'ci-ports', minzoom: compact ? 4.15 : 3.3, layout: {
    'text-field': ['get', 'label'], 'text-size': compact ? 11 : 12,
    'text-offset': [0, 1.25], 'text-anchor': 'top', 'text-allow-overlap': false,
  }, paint: { 'text-color': '#263f3a', 'text-halo-color': 'rgba(255,255,255,.95)', 'text-halo-width': 1.5 } })

  addSource(map, 'ci-events', data.events)
  map.addLayer({ id: 'ci-events-halo', type: 'circle', source: 'ci-events', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 7, 8, 12],
    'circle-color': ['coalesce', ['get', 'color'], '#c86c30'], 'circle-opacity': .16,
  } })
  map.addLayer({ id: 'ci-events-point', type: 'circle', source: 'ci-events', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 4, 8, 7],
    'circle-color': ['coalesce', ['get', 'color'], '#c86c30'],
    'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2,
  } })
  map.addLayer({ id: 'ci-events-label', type: 'symbol', source: 'ci-events', minzoom: 5.1, layout: {
    'text-field': ['get', 'label'], 'text-size': 11, 'text-offset': [0, 1.4], 'text-anchor': 'top',
  }, paint: { 'text-color': '#64452f', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } })

  addSource(map, 'ci-environmental', data.environmental)
  map.addLayer({ id: 'ci-environmental-halo', type: 'circle', source: 'ci-environmental', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 8, 8, 14],
    'circle-color': '#2f8669', 'circle-opacity': .16,
  } })
  map.addLayer({ id: 'ci-environmental-point', type: 'circle', source: 'ci-environmental', paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 4, 8, 7],
    'circle-color': ['coalesce', ['get', 'color'], '#27785f'],
    'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2,
  } })
  map.addLayer({ id: 'ci-environmental-label', type: 'symbol', source: 'ci-environmental', minzoom: 4.6, layout: {
    'text-field': ['get', 'label'], 'text-size': 11, 'text-offset': [0, 1.45], 'text-anchor': 'top',
  }, paint: { 'text-color': '#235f4b', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } })

  addSource(map, 'ci-annotations', data.annotations)
  map.addLayer({ id: 'ci-annotations-point', type: 'circle', source: 'ci-annotations', paint: {
    'circle-radius': 6, 'circle-color': ['coalesce', ['get', 'color'], '#1d625b'],
    'circle-stroke-color': '#fff', 'circle-stroke-width': 2,
  } })
  map.addLayer({ id: 'ci-annotations-label', type: 'symbol', source: 'ci-annotations', layout: {
    'text-field': ['get', 'label'], 'text-size': 11, 'text-offset': [0, 1.5], 'text-anchor': 'top',
  }, paint: { 'text-color': '#23443e', 'text-halo-color': '#fff', 'text-halo-width': 1.5 } })

  addSource(map, 'ci-vessels', data.vessels, clusterVessels)
  if (clusterVessels) {
    map.addLayer({ id: 'ci-vessel-clusters', type: 'circle', source: 'ci-vessels', filter: ['has', 'point_count'], paint: {
      'circle-radius': ['step', ['get', 'point_count'], 16, 20, 21, 60, 27],
      'circle-color': '#176f66', 'circle-stroke-color': 'rgba(255,255,255,.9)', 'circle-stroke-width': 3,
    } })
    map.addLayer({ id: 'ci-vessel-cluster-count', type: 'symbol', source: 'ci-vessels', filter: ['has', 'point_count'], layout: {
    'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12,
    }, paint: { 'text-color': '#fff' } })
  }
  map.addLayer({ id: 'ci-vessels-selected', type: 'circle', source: 'ci-vessels', filter: ['all', ['!', ['has', 'point_count']], ['==', ['get', 'selected'], true]], paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 10, 9, 18],
    'circle-color': ['coalesce', ['get', 'color'], '#187970'], 'circle-opacity': .14,
    'circle-stroke-color': ['coalesce', ['get', 'color'], '#187970'], 'circle-stroke-width': 1.5,
  } })
  map.addLayer({ id: 'ci-vessels-point', type: 'circle', source: 'ci-vessels', filter: ['!', ['has', 'point_count']], paint: {
    'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 4.2, 9, 8],
    'circle-color': ['coalesce', ['get', 'color'], '#187970'],
    'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2,
  } })
  map.addLayer({ id: 'ci-vessels-direction', type: 'symbol', source: 'ci-vessels', filter: ['!', ['has', 'point_count']], layout: {
    'text-field': '▲', 'text-size': ['interpolate', ['linear'], ['zoom'], 3, 7, 9, 12],
    'text-rotate': ['get', 'course'], 'text-rotation-alignment': 'map', 'text-allow-overlap': true,
  }, paint: { 'text-color': '#ffffff' } })
  map.addLayer({ id: 'ci-vessels-label', type: 'symbol', source: 'ci-vessels', minzoom: compact ? 5.15 : 4.55, filter: ['!', ['has', 'point_count']], layout: {
    'text-field': ['get', 'label'], 'text-size': compact ? 11 : 12,
    'text-offset': [0, 1.55], 'text-anchor': 'top', 'text-allow-overlap': false,
  }, paint: { 'text-color': '#203b35', 'text-halo-color': 'rgba(255,255,255,.96)', 'text-halo-width': 1.5 } })
}

function updateSource(map: MapLibreMap, id: string, data: FeatureCollection<Point | LineString | Polygon>) {
  const source = map.getSource(id) as GeoJSONSource | undefined
  if (source) source.setData(data)
}

function featureId(event: MapLayerMouseEvent) {
  return String(event.features?.[0]?.properties?.id || '')
}

export const RealCaspianMap = forwardRef<RealCaspianMapHandle, RealCaspianMapProps>(function RealCaspianMap(props, ref) {
  const {
    className = '', ariaLabel = 'Интерактивная карта Каспийского моря', mode = 'standard', compact = false,
    interactive = true, clusterVessels = false, focusBounds,
  } = props
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'degraded'>('loading')
  const [reloadKey, setReloadKey] = useState(0)
  const data = useMemo(() => datasetsFrom(props), [
    props.ports, props.vessels, props.events, props.environmentalEvents,
    props.routes, props.tracks, props.areas, props.annotations,
  ])
  const dataRef = useRef(data)
  dataRef.current = data
  const handlersRef = useRef(props)
  handlersRef.current = props

  useImperativeHandle(ref, () => ({
    zoomIn: () => mapRef.current?.zoomIn({ duration: 220 }),
    zoomOut: () => mapRef.current?.zoomOut({ duration: 220 }),
    reset: () => mapRef.current?.easeTo({ center: DEFAULT_CENTER, zoom: compact ? 4.05 : 4.55, bearing: 0, pitch: 0, duration: 420 }),
    resize: () => mapRef.current?.resize(),
    unprojectPercent: (x, y) => {
      const map = mapRef.current
      if (!map) return null
      const canvas = map.getCanvas()
      const point = map.unproject([canvas.clientWidth * x / 100, canvas.clientHeight * y / 100])
      return { longitude: point.lng, latitude: point.lat }
    },
  }), [compact])

  useEffect(() => {
    if (!containerRef.current) return
    setStatus('loading')
    const style: string | StyleSpecification = mode === 'satellite' && SATELLITE_STYLE_URL ? SATELLITE_STYLE_URL : DEFAULT_STYLE_URL
    const map = new MapLibreMap({
      container: containerRef.current,
      style,
      center: DEFAULT_CENTER,
      zoom: compact ? 4.05 : 4.55,
      minZoom: 2.8,
      maxZoom: 14,
      maxBounds: DEFAULT_BOUNDS,
      renderWorldCopies: false,
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      interactive,
    })
    mapRef.current = map
    map.touchZoomRotate.disableRotation()
    map.addControl(new AttributionControl({ compact: true, customAttribution: '© OpenStreetMap contributors · OpenFreeMap' }), 'bottom-right')
    map.addControl(new ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left')

    let fallbackActivated = false
    const installLayers = () => {
      if (map.getSource('ci-areas')) return
      addOperationalLayers(map, dataRef.current, compact, clusterVessels)
      if (focusBounds) map.fitBounds(focusBounds, { padding: compact ? 26 : 46, duration: 0, maxZoom: 10.5 })
    }
    const failedTimer = window.setTimeout(() => {
      if (map.isStyleLoaded()) return
      fallbackActivated = true
      map.setStyle(FALLBACK_STYLE)
    }, 9_000)

    map.on('style.load', () => {
      window.clearTimeout(failedTimer)
      localizeBasemapLabels(map)
      installLayers()
      setStatus(fallbackActivated ? 'degraded' : 'ready')
    })

    const clickable: Array<[string, keyof Pick<RealCaspianMapProps, 'onPortSelect' | 'onVesselSelect' | 'onEventSelect' | 'onEnvironmentalSelect'>]> = [
      ['ci-ports-point', 'onPortSelect'], ['ci-ports-label', 'onPortSelect'],
      ['ci-vessels-point', 'onVesselSelect'], ['ci-vessels-label', 'onVesselSelect'],
      ['ci-events-point', 'onEventSelect'], ['ci-events-label', 'onEventSelect'],
      ['ci-environmental-point', 'onEnvironmentalSelect'], ['ci-environmental-label', 'onEnvironmentalSelect'],
    ]
    clickable.forEach(([layer, handler]) => {
      map.on('click', layer, event => {
        const id = featureId(event)
        const callback = handlersRef.current[handler]
        if (id && callback) callback(id)
      })
      map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
      map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
    })
    map.on('mousemove', event => handlersRef.current.onPointerCoordinate?.({ longitude: event.lngLat.lng, latitude: event.lngLat.lat }))
    map.on('click', 'ci-vessel-clusters', event => {
      const feature = event.features?.[0]
      const clusterId = Number(feature?.properties?.cluster_id)
      if (!feature || !Number.isFinite(clusterId) || feature.geometry.type !== 'Point') return
      const source = map.getSource('ci-vessels') as GeoJSONSource
      const center = feature.geometry.coordinates as [number, number]
      void source.getClusterExpansionZoom(clusterId).then(zoom => map.easeTo({ center, zoom }))
    })

    const observer = new ResizeObserver(() => map.resize())
    observer.observe(containerRef.current)
    return () => {
      window.clearTimeout(failedTimer)
      observer.disconnect()
      map.remove()
      if (mapRef.current === map) mapRef.current = null
    }
  }, [mode, compact, interactive, clusterVessels, reloadKey])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.loaded()) return
    updateSource(map, 'ci-areas', data.areas)
    updateSource(map, 'ci-routes', data.routes)
    updateSource(map, 'ci-tracks', data.tracks)
    updateSource(map, 'ci-ports', data.ports)
    updateSource(map, 'ci-events', data.events)
    updateSource(map, 'ci-environmental', data.environmental)
    updateSource(map, 'ci-annotations', data.annotations)
    updateSource(map, 'ci-vessels', data.vessels)
  }, [data])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.loaded() || !focusBounds) return
    map.fitBounds(focusBounds, { padding: compact ? 26 : 46, duration: 350, maxZoom: 10.5 })
  }, [focusBounds, compact])

  const accessibleFeatures = [
    ...(props.ports || []).map(item => ({ id: item.id, label: `Порт ${item.name}`, action: props.onPortSelect })),
    ...(props.vessels || []).map(item => ({ id: item.id, label: `Судно ${item.name}`, action: props.onVesselSelect })),
    ...(props.events || []).map(item => ({ id: item.id, label: `Событие ${item.title}`, action: props.onEventSelect })),
    ...(props.environmentalEvents || []).map(item => ({ id: item.id, label: `Экологическое событие ${item.title}`, action: props.onEnvironmentalSelect })),
  ]

  return <div className={`real-caspian-map ${compact ? 'compact' : ''} ${className}`} aria-label={ariaLabel}>
    <div ref={containerRef} className="real-caspian-map-canvas"/>
    {status === 'loading' && <div className="real-map-status"><span className="real-map-spinner"/><strong>Загрузка географической подложки</strong><small>OpenFreeMap · vector tiles</small></div>}
    {status === 'degraded' && <div className="real-map-degraded"><span><strong>Подложка недоступна</strong><small>Операционные GeoJSON-слои активны</small></span><button onClick={() => setReloadKey(value => value + 1)}>Повторить</button></div>}
    <div className="real-map-accessible-actions">{accessibleFeatures.filter(item => item.action).map(item => <button key={`${item.label}-${item.id}`} onClick={() => item.action?.(item.id)}>{item.label}</button>)}</div>
  </div>
})

export function circleArea(id: string, longitude: number, latitude: number, radiusKm: number, kind: RealMapArea['kind'], label?: string): RealMapArea {
  const points = 48
  const latitudeRadius = radiusKm / 111.32
  const longitudeRadius = radiusKm / (111.32 * Math.cos(latitude * Math.PI / 180))
  const ring = Array.from({ length: points + 1 }, (_, index) => {
    const angle = index / points * Math.PI * 2
    return [longitude + Math.cos(angle) * longitudeRadius, latitude + Math.sin(angle) * latitudeRadius]
  })
  return { id, rings: [ring], kind, label }
}

export function boundsForCoordinates(coordinates: Array<[number, number]>, paddingRatio = .18): [[number, number], [number, number]] | undefined {
  const valid = coordinates.filter(([longitude, latitude]) => Number.isFinite(longitude) && Number.isFinite(latitude))
  if (!valid.length) return undefined
  const longitudes = valid.map(point => point[0])
  const latitudes = valid.map(point => point[1])
  const west = Math.min(...longitudes); const east = Math.max(...longitudes)
  const south = Math.min(...latitudes); const north = Math.max(...latitudes)
  const longitudePadding = Math.max((east - west) * paddingRatio, .08)
  const latitudePadding = Math.max((north - south) * paddingRatio, .06)
  return [[west - longitudePadding, south - latitudePadding], [east + longitudePadding, north + latitudePadding]]
}
