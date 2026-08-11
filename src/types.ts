export type Role = 'ADMIN' | 'ANALYST' | 'VIEWER'

export type VesselStatus = 'Underway' | 'At anchor' | 'Moored' | 'Stopped' | 'Unknown'

export interface Vessel {
  id: string
  imo: string
  mmsi: string
  name: string
  type: string
  flag: string
  flagCode: string
  length: number
  width: number
  deadweight: number
  owner: string
  operator: string
  latitude: number
  longitude: number
  x: number
  y: number
  speed: number
  course: number
  heading: number
  draught: number
  destination: string
  reportedEta: string
  calculatedEta: string
  navigationStatus: VesselStatus
  lastPositionAt: string
  risk: number
  riskLevel: RiskLevel
  riskUpdatedAt: string
}

export interface Port {
  id: string
  name: string
  country: string
  latitude: number
  longitude: number
  x: number
  y: number
  vessels: number
  status: 'Operational' | 'Busy' | 'Limited'
}

export interface Voyage {
  id: string
  from: string
  to: string
  departed: string
  arrived: string
  distance: number
  status: 'Completed' | 'In progress'
}

export interface MaritimeEvent {
  id: string
  type: 'AIS gap' | 'Route deviation' | 'Port call' | 'Weather'
  vessel: string
  location: string
  time: string
  severity: 'Low' | 'Medium' | 'Info'
}

export interface TrackPoint {
  id: string
  time: string
  label: string
  latitude: number
  longitude: number
  x: number
  y: number
  speed: number
  course: number
  kind?: 'position' | 'departure' | 'stop' | 'course' | 'gap' | 'restored' | 'arrival'
}

export interface TrackingEvent {
  id: string
  time: string
  title: string
  description: string
  kind: 'departure' | 'course' | 'gap' | 'restored' | 'stop' | 'arrival'
}

export type DetectionEventType = 'route_deviation' | 'ais_gap' | 'unusual_stop' | 'unexpected_speed' | 'vessel_encounter' | 'draught_change' | 'cargo_anomaly' | 'cargo_draught_mismatch' | 'fuel_anomaly' | 'economic_anomaly' | 'unusual_connection'
export type DetectionSeverity = 'high' | 'medium' | 'low'
export type DetectionStatus = 'active' | 'resolved' | 'reviewed' | 'dismissed'

export interface DetectionEvent {
  id: string
  type: DetectionEventType
  vesselId: string
  vesselName: string
  relatedVessel?: string
  voyageId: string
  groupId?: string
  startedAt: string
  endedAt?: string
  time: string
  x: number
  y: number
  latitude: number
  longitude: number
  severity: DetectionSeverity
  confidence: number
  status: DetectionStatus
  title: string
  summary: string
  explanation: string
  factors: string[]
  metrics: Array<{ label:string; value:string; baseline?:string }>
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
export type RiskFactorType = DetectionEventType | 'correlation'
export type RiskReviewStatus = 'NEEDS_MORE_DATA' | 'CONFIRMED_RELEVANT' | 'NORMAL_OPERATION' | 'FALSE_POSITIVE'

export interface RiskFactor {
  id: string
  type: RiskFactorType
  title: string
  baseScore: number
  adjustedScore: number
  effectiveScore?: number
  confidence: number
  sourceEventId?: string
  explanation: string
  evidence: string[]
  createdAt: string
  lifecycle: 'ACTIVE' | 'RECENT' | 'HISTORICAL'
  reviewStatus: RiskReviewStatus
}

export interface RiskSnapshot {
  time: string
  score: number
  level: RiskLevel
  reason: string
}

export interface VoyageRiskSummary {
  id: string
  route: string
  date: string
  score: number
  level: RiskLevel
}

export interface RiskAssessment {
  vesselId: string
  vesselName: string
  imo: string
  voyageId: string
  route: string
  score: number
  level: RiskLevel
  previousScore: number
  delta: number
  deltaWindow: string
  updatedAt: string
  modelVersion: string
  voyageScore: number
  vesselScore: number
  factors: RiskFactor[]
  correlationScore: number
  rawFactorScore?: number
  normalizedFactorScore?: number
  baseEventScore?: number
  advancedEffectiveScore?: number
  scenario?: {
    code: string
    label: string
    confidence: number
    explanation: string
  }
  history: RiskSnapshot[]
  recentVoyages: VoyageRiskSummary[]
  x: number
  y: number
}

export type IntelligenceDataStatus = 'REPORTED' | 'ESTIMATED' | 'VERIFIED'
export type IntelligenceConfidence = 'LOW' | 'MEDIUM' | 'HIGH'

export interface IntelligenceEvidence {
  label: string
  value: string
  status: IntelligenceDataStatus
  source: string
  sourceTimestamp: string
  confidence: IntelligenceConfidence
  note?: string
}

export interface IntelligenceTimelineItem {
  time: string
  title: string
  description: string
  kind: 'voyage' | 'route' | 'ais' | 'encounter' | 'draught' | 'cargo' | 'fuel' | 'economics'
  status?: IntelligenceDataStatus
}

export interface VoyageIntelligence {
  id: string
  displayId: string
  vesselId: string
  vesselName: string
  imo: string
  route: { from:string; to:string; distance:string; deviation:string }
  startedAt: string
  eta: string
  riskScore: number
  riskLevel: RiskLevel
  significantFactors: number
  summary: string
  mainFactors: string[]
  cargo: {
    type: IntelligenceEvidence
    mass: IntelligenceEvidence
    value: IntelligenceEvidence
    shipper: IntelligenceEvidence
    consignee: IntelligenceEvidence
    documentReference: string
    origin: string
    destination: string
    history: Array<{ label:string; share:number }>
  }
  draught: {
    departure: IntelligenceEvidence
    observed: IntelligenceEvidence
    expectedRange: IntelligenceEvidence
    expectedChange: string
    observedChange: string
    modelConfidence: number
    operationsAnalyzed: number
    vesselSpecificRange: string
  }
  fuel: {
    expected: IntelligenceEvidence
    reported: IntelligenceEvidence
    weatherCorrection: string
    operationalCorrection: string
    finalDeviation: string
    engine: string
    typicalSpeed: string
  }
  economics: {
    cargoValue: IntelligenceEvidence
    voyageCost: IntelligenceEvidence
    ratio: number
    typicalRatio: string
    costBreakdown: Array<{ label:string; value:number }>
  }
  encounter: {
    vesselId: string
    vesselName: string
    duration: string
    minimumDistance: string
    previousEncounters: number
  }
  timeline: IntelligenceTimelineItem[]
}

export type NetworkNodeType = 'VESSEL' | 'COMPANY' | 'OWNER' | 'OPERATOR' | 'PORT' | 'CARGO' | 'VOYAGE' | 'EVENT' | 'ENCOUNTER'

export interface InvestigationNetworkNode {
  id: string
  label: string
  subtitle: string
  type: NetworkNodeType
  x: number
  y: number
  risk?: number
  details: Array<{ label:string; value:string }>
}

export interface InvestigationNetworkEdge {
  id: string
  source: string
  target: string
  type: 'OWNED_BY' | 'OPERATED_BY' | 'VISITED' | 'CARRIED' | 'ENCOUNTERED' | 'RELATED_TO'
  label: string
  confidence: IntelligenceConfidence
  explanation: string
  priority?: 'LOW' | 'MEDIUM' | 'HIGH'
  observations?: Array<{ label:string; value:string }>
  evidence?: string[]
  sourceLabel?: string
  updatedAt?: string
  dataStatus?: IntelligenceDataStatus
}

export interface InvestigationNetwork {
  nodes: InvestigationNetworkNode[]
  edges: InvestigationNetworkEdge[]
  primaryConnection: {
    source: string
    target: string
    encounters: number
    openSea: number
    averageDistance: string
    totalDuration: string
    period: string
    strength: 'LOW' | 'MEDIUM' | 'HIGH'
    explanation: string
  }
}

export type PortCallStatus = 'APPROACHING' | 'WAITING' | 'BERTH_ASSIGNED' | 'IN_SERVICE' | 'COMPLETED' | 'DEPARTED'
export type BerthOperationalStatus = 'AVAILABLE' | 'OCCUPIED' | 'LIMITED' | 'MAINTENANCE'
export type PortRecommendationStatus = 'PENDING' | 'ACCEPTED' | 'CHANGED' | 'DEFERRED'

export interface PortArrival {
  id: string
  portCallId: string
  vesselId: string
  vesselName: string
  imo: string
  reportedEta: string
  predictedEta: string
  likelyWindow: string
  etaConfidence: number
  delayMinutes: number
  berth: string
  cargo: string
  cargoMass: string
  risk: number
  status: 'ATTENTION' | 'NORMAL' | 'WAITING'
  queuePosition: number
}

export interface PortBerth {
  id: string
  name: string
  length: number
  maxVesselLength: number
  maxDraught: number
  cargoTypes: string[]
  equipment: string[]
  status: BerthOperationalStatus
  currentVessel?: string
  serviceStarted?: string
  expectedCompletion?: string
  nextVessel?: string
  availableFrom: string
  restriction?: string
}

export interface PortQueueItem {
  position: number
  vesselName: string
  eta: string
  berth: string
  cargo: string
  priority: 'HIGH' | 'NORMAL'
  reason: string
}

export interface PortLoadForecastPoint {
  offset: string
  time: string
  load: number
  level: 'NORMAL' | 'ELEVATED' | 'HIGH' | 'CRITICAL'
}

export interface PortRecommendation {
  id: string
  title: string
  vesselName: string
  fromBerth: string
  toBerth: string
  explanation: string
  factors: string[]
  waitingEffect: string
  loadBefore: number
  loadAfter: number
  status: PortRecommendationStatus
}

export interface PortOperationEvent {
  id: string
  time: string
  type: 'VESSEL_APPROACHING' | 'ETA_CHANGED' | 'VESSEL_ARRIVED' | 'VESSEL_WAITING' | 'BERTH_ASSIGNED' | 'BERTH_CHANGED' | 'SERVICE_STARTED' | 'SERVICE_DELAYED' | 'SERVICE_COMPLETED' | 'VESSEL_DEPARTED' | 'PORT_CONGESTION' | 'WEATHER_RESTRICTION'
  title: string
  detail: string
  status: 'PREDICTED' | 'ACTUAL' | 'PLANNED'
}

export interface PortCall {
  id: string
  vesselId: string
  vesselName: string
  imo: string
  voyageId: string
  portId: string
  status: PortCallStatus
  reportedEta: string
  predictedEta: string
  etaWindow: string
  etaConfidence: number
  berthId: string
  queuePosition: number
  cargoType: string
  reportedCargo: string
  verifiedCargo: string
  reportedDraught: string
  verifiedDraught: string
  expectedService: string
  serviceConfidence: number
  projectedRelease: string
  risk: number
  attention: 'HIGH' | 'NORMAL'
  significantEvents: number
  riskReasons: string[]
  recommendedActions: string[]
  compatibility: Array<{ label: string; vessel: string; berth: string; result: 'COMPATIBLE' | 'NOT_COMPATIBLE' }>
  timeline: PortOperationEvent[]
  feedback: {
    predictedEta: string
    actualArrival: string
    etaError: string
    predictedService: string
    actualService: string
    serviceError: string
  }
}

export interface AktauPortOperations {
  updatedAt: string
  operationalLoad: number
  arriving: number
  inPort: number
  waiting: number
  departing: number
  averageWaiting: string
  berthsAvailable: number
  berthsOccupied: number
  highRiskArrivals: number
  arrivals: PortArrival[]
  berths: PortBerth[]
  queue: PortQueueItem[]
  loadForecast: PortLoadForecastPoint[]
  recommendation: PortRecommendation
  portCall: PortCall
}
