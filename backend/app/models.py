from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Coordinates(BaseModel):
    latitude: float
    longitude: float


class Vessel(BaseModel):
    id: str
    imo: str
    mmsi: str
    name: str
    type: str
    flag: str
    length: float
    width: float
    deadweight: float
    owner: str
    operator: str
    latitude: float
    longitude: float
    speed: float
    course: float
    heading: float
    draught: float
    destination: str
    reported_eta: str
    calculated_eta: str
    navigation_status: Literal["underway", "at_anchor", "moored", "stopped", "unknown"]
    last_position_at: str
    risk_score: int = Field(default=0, ge=0, le=100)
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    risk_updated_at: str | None = None


class MapVessel(BaseModel):
    id: str
    name: str
    lat: float
    lon: float
    speed: float
    course: float
    status: str
    risk_score: int = Field(default=0, ge=0, le=100)
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    risk_updated_at: str | None = None


class Port(BaseModel):
    id: str
    name: str
    country: str
    latitude: float
    longitude: float
    status: str


class Position(BaseModel):
    id: str | None = None
    vessel_id: str
    mmsi: str | None = None
    latitude: float
    longitude: float
    speed: float
    course: float
    heading: float | None = None
    navigation_status: str = "unknown"
    source: str = "demo"
    quality_status: Literal["valid", "suspicious", "rejected"] = "valid"
    recorded_at: str
    received_at: str | None = None


class Voyage(BaseModel):
    id: str
    vessel_id: str
    origin: str
    destination: str
    departed_at: str
    arrived_at: str | None = None
    distance_km: float
    status: Literal["completed", "in_progress"]


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Literal["ADMIN", "ANALYST", "VIEWER", "PORT_DISPATCHER"]


class NormalizedAISMessage(BaseModel):
    mmsi: str
    timestamp: datetime
    latitude: float
    longitude: float
    speed: float = 0
    course: float = 0
    heading: float | None = None
    navigation_status: str = "unknown"
    destination: str | None = None
    eta: str | None = None
    draught: float | None = None
    source: str
    quality_status: Literal["valid", "suspicious"] = "valid"
    quality_notes: list[str] = Field(default_factory=list)


class AISIngestRequest(BaseModel):
    provider: str = "generic"
    payload: dict[str, Any]


class TrackResponse(BaseModel):
    vessel_id: str
    from_time: str | None
    to_time: str | None
    point_count: int
    distance_km: float
    positions: list[Position]


class SpatialSearchRequest(BaseModel):
    west: float
    south: float
    east: float
    north: float
    from_time: str | None = None
    to_time: str | None = None


class BehaviorRange(BaseModel):
    minimum: float
    maximum: float
    unit: str


class RouteBehaviorProfile(BaseModel):
    id: str
    origin: str
    destination: str
    voyage_count: int
    share: float
    typical_distance: BehaviorRange
    typical_duration: BehaviorRange
    typical_speed: BehaviorRange
    typical_stops: BehaviorRange
    typical_departure: str
    typical_arrival: str
    corridor: list[list[float]]


class SpeedBehaviorProfile(BaseModel):
    phase: str
    average: float
    median: float
    p95: float
    typical_range: BehaviorRange
    sample_count: int
    distribution: list[int]


class PortBehaviorProfile(BaseModel):
    port_id: str
    port_name: str
    visits: int
    share: float
    median_stay_hours: float
    typical_stay: BehaviorRange
    usual: bool


class StopAreaProfile(BaseModel):
    id: str
    latitude: float
    longitude: float
    stops: int
    average_duration_minutes: float
    radius_km: float


class DraughtHistoryItem(BaseModel):
    voyage_id: str
    origin: str
    destination: str
    departure_draught: float
    arrival_draught: float


class CurrentComparison(BaseModel):
    parameter: str
    typical: str
    current: str
    status: Literal["consistent", "insufficient"] = "consistent"


class BehaviorProfile(BaseModel):
    vessel_id: str
    generated_at: str
    confidence: float
    confidence_level: Literal["insufficient", "developing", "high"]
    voyages_analyzed: int
    observation_months: int
    distance_tracked_km: float
    total_sailing_hours: float
    total_port_hours: float
    stops_at_sea: int
    historical_ais_gaps: int
    main_route_id: str
    routes: list[RouteBehaviorProfile]
    speed_profiles: list[SpeedBehaviorProfile]
    ports: list[PortBehaviorProfile]
    stop_areas: list[StopAreaProfile]
    average_stop_minutes: float
    draught_typical: BehaviorRange
    draught_history: list[DraughtHistoryItem]
    departure_pattern: list[int]
    voyages_by_day: list[int]
    activity_cells: list[list[float]]
    current_comparison: list[CurrentComparison]


EventType = Literal[
    "route_deviation",
    "ais_gap",
    "unusual_stop",
    "unexpected_speed",
    "vessel_encounter",
    "draught_change",
    "cargo_anomaly",
    "cargo_draught_mismatch",
    "fuel_anomaly",
    "economic_anomaly",
    "unusual_connection",
    "unexplained_load_change",
]
EventSeverity = Literal["low", "medium", "high"]
EventStatus = Literal["active", "resolved", "reviewed", "dismissed"]


class DetectedEvent(BaseModel):
    id: str
    type: EventType
    vessel_id: str
    vessel_name: str
    related_vessel_id: str | None = None
    related_vessel_name: str | None = None
    voyage_id: str | None = None
    group_id: str | None = None
    started_at: str
    ended_at: str | None = None
    latitude: float
    longitude: float
    severity: EventSeverity
    confidence: float
    status: EventStatus
    data: dict[str, Any] = Field(default_factory=dict)
    explanation: str
    factors: list[str] = Field(default_factory=list)
    created_at: str
    reviewed_by: str | None = None
    review_note: str | None = None


class EventGroup(BaseModel):
    id: str
    vessel_id: str
    vessel_name: str
    voyage_id: str
    started_at: str
    ended_at: str | None = None
    event_ids: list[str]
    event_types: list[EventType]
    status: EventStatus = "active"
    explanation: str


class EventStatusUpdate(BaseModel):
    status: Literal["reviewed", "dismissed"]
    note: str | None = None


RiskLevel = Literal["low", "moderate", "high", "critical"]
RiskLifecycle = Literal["active", "recent", "historical"]
FactorReviewStatus = Literal[
    "confirmed_relevant",
    "normal_operation",
    "false_positive",
    "needs_more_data",
]


class RiskFactor(BaseModel):
    """One explainable contribution to a risk assessment.

    ``adjusted_score`` is the context-aware contribution before lifecycle decay
    and analyst review. ``effective_score`` is the value actually used in the
    current assessment, which makes every score change auditable.
    """

    id: str
    vessel_id: str
    voyage_id: str | None = None
    type: EventType
    label: str = ""
    base_score: int = Field(ge=0, le=100)
    adjusted_score: int = Field(ge=0, le=100)
    effective_score: int = Field(default=0, ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    source_event_id: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)
    lifecycle: RiskLifecycle = "active"
    created_at: str
    review_status: FactorReviewStatus | None = None
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_comment: str | None = None
    stage: Literal[5, 6] = 5
    confidence_weighted_score: int | None = Field(default=None, ge=0, le=100)
    deduplication_group: str | None = None
    deduplicated: bool = False


class RiskScenario(BaseModel):
    id: str
    vessel_id: str
    voyage_id: str | None = None
    type: str
    title: str
    status: Literal["requires_review", "reviewed", "dismissed"] = "requires_review"
    confidence: float = Field(ge=0, le=1)
    score_adjustment: int = Field(default=0, ge=0, le=100)
    source_event_ids: list[str] = Field(default_factory=list)
    explanation: str
    created_at: str


class RiskSnapshot(BaseModel):
    id: str
    vessel_id: str
    voyage_id: str | None = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    recorded_at: str
    reason: str
    source_event_id: str | None = None
    model_version: str


class VoyageRiskSummary(BaseModel):
    id: str
    vessel_id: str
    voyage_id: str
    origin: str
    destination: str
    completed_at: str
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    model_version: str


class RiskCorrelationAdjustment(BaseModel):
    id: str
    event_types: list[EventType]
    raw_score: int = Field(ge=0)
    applied_score: int = Field(ge=0)
    explanation: str
    capped: bool = False


class RiskAssessment(BaseModel):
    id: str
    scope: Literal["vessel", "voyage"] = "voyage"
    vessel_id: str
    vessel_name: str
    voyage_id: str | None = None
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    previous_score: int = Field(default=0, ge=0, le=100)
    change_1h: int = 0
    change_4h: int = 0
    trend: Literal["rising", "stable", "falling"] = "stable"
    factor_score: int = Field(default=0, ge=0)
    correlation_adjustment: int = Field(default=0, ge=0)
    factors: list[RiskFactor] = Field(default_factory=list)
    correlations: list[RiskCorrelationAdjustment] = Field(default_factory=list)
    scenarios: list[RiskScenario] = Field(default_factory=list)
    explanation: str
    disclaimer: str
    risk_updated_at: str
    model_version: str
    priority_rank: int | None = None
    base_risk_score: int | None = Field(default=None, ge=0, le=100)
    advanced_adjustment: int = Field(default=0, ge=0, le=100)
    advanced_adjustment_cap: int = Field(default=0, ge=0, le=100)


class RiskFactorReviewRequest(BaseModel):
    status: FactorReviewStatus
    comment: str | None = Field(default=None, max_length=1000)
    reviewed_by: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower().replace(" ", "_")
        return value


class RiskRule(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool = True
    category: Literal["factor", "correlation", "lifecycle"]
    parameters: dict[str, Any] = Field(default_factory=dict)


class RiskModelConfiguration(BaseModel):
    model_version: str
    updated_at: str
    level_thresholds: dict[RiskLevel, list[int]]
    correlation_cap: int = Field(ge=0, le=100)
    decay_hours: dict[RiskLifecycle, int | None]
    review_multipliers: dict[str, float]
    rules: list[RiskRule]
    disclaimer: str
    advanced_contribution_cap: int = Field(default=0, ge=0, le=100)


VerificationStatus = Literal["reported", "estimated", "verified", "not_available"]
ConfidenceLevel = Literal["low", "medium", "high", "insufficient"]


class SourceMetadata(BaseModel):
    """Provenance attached to every non-AIS intelligence value."""

    source: str
    source_timestamp: str
    confidence: float = Field(ge=0, le=1)
    verification_status: VerificationStatus


class QuantityObservation(BaseModel):
    value: float | None = None
    unit: str
    source: str
    source_timestamp: str
    confidence: float = Field(ge=0, le=1)
    verification_status: VerificationStatus


class NumericRange(BaseModel):
    minimum: float
    maximum: float
    unit: str


class CargoDeclaration(BaseModel):
    id: str
    vessel_id: str
    voyage_id: str
    cargo_type: str
    cargo_name: str
    declared_mass: float
    mass_unit: str = "t"
    declared_volume: float | None = None
    volume_unit: str | None = None
    origin_port: str
    destination_port: str
    shipper: str | None = None
    consignee: str | None = None
    declared_value: float | None = None
    currency: str = "USD"
    document_reference: str | None = None
    loaded_at: str | None = None
    unloaded_at: str | None = None
    source: str
    source_timestamp: str
    confidence: float = Field(ge=0, le=1)
    verification_status: VerificationStatus


class CargoProfileItem(BaseModel):
    cargo_type: str
    voyage_share: float = Field(ge=0, le=1)
    voyage_count: int = Field(ge=0)


class CargoProfile(BaseModel):
    vessel_id: str
    generated_at: str
    voyage_count: int = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    items: list[CargoProfileItem]
    route_typical_cargo: list[str]
    current_cargo_historical_share: float = Field(ge=0, le=1)
    interpretation: str


class CargoTimelineItem(BaseModel):
    id: str
    timestamp: str
    type: str
    title: str
    detail: str
    source_reference: str | None = None
    confidence: float = Field(ge=0, le=1)


class DraughtModel(BaseModel):
    vessel_id: str
    model_version: str
    tonnes_reference: float = 1000
    expected_change_per_reference: NumericRange
    confidence: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    sample_count: int = Field(ge=0)
    generated_at: str
    limitation: str


class CargoConsistencyCheck(BaseModel):
    type: Literal["cargo_vessel", "cargo_route", "cargo_draught"]
    status: Literal["consistent", "context", "requires_review", "insufficient_data"]
    confidence: float = Field(ge=0, le=1)
    expected: str
    observed: str
    explanation: str


class CargoDraughtAssessment(BaseModel):
    vessel_id: str
    voyage_id: str
    departure_draught_m: float
    observed_draught_m: float
    observed_change_m: float
    expected_change_m: NumericRange
    expected_arrival_draught_m: NumericRange
    mismatch: bool
    anomaly_type: Literal[
        "consistent",
        "cargo_draught_mismatch",
        "unexplained_load_change",
        "insufficient_data",
    ] = "consistent"
    deviation_from_expected_m: float
    model: DraughtModel
    explanation: str
    disclaimer: str


class DraughtConsistencyResult(BaseModel):
    declared_mass_change_t: float
    observed_change_m: float
    expected_change_m: NumericRange
    status: Literal[
        "consistent",
        "cargo_draught_mismatch",
        "unexplained_load_change",
        "insufficient_data",
    ]
    confidence: float = Field(ge=0, le=1)
    explanation: str
    disclaimer: str


class CargoIntelligence(BaseModel):
    vessel_id: str
    voyage_id: str
    declaration: CargoDeclaration
    profile: CargoProfile
    timeline: list[CargoTimelineItem]
    consistency_checks: list[CargoConsistencyCheck]
    draught_assessment: CargoDraughtAssessment
    source_quality: list[SourceMetadata]
    port_verified_cargo: QuantityObservation | None = None
    port_verified_draught: QuantityObservation | None = None
    port_feedback_at: str | None = None
    generated_at: str
    summary: str
    disclaimer: str


class FuelProfile(BaseModel):
    vessel_id: str
    engine: str
    route: str
    typical_consumption: NumericRange
    typical_cruising_speed: NumericRange
    confidence: float = Field(ge=0, le=1)
    sample_count: int = Field(ge=0)
    model_version: str


class WeatherCorrection(BaseModel):
    wind_kn: float
    waves_m: float
    current_kn: float
    multiplier: float = Field(gt=0)
    source: str
    source_timestamp: str
    confidence: float = Field(ge=0, le=1)
    verification_status: VerificationStatus


class OperationalCorrection(BaseModel):
    waiting_hours: float
    maneuvering_hours: float
    average_speed_kn: float
    multiplier: float = Field(gt=0)
    explanation: str


class FuelAnalysis(BaseModel):
    vessel_id: str
    voyage_id: str
    profile: FuelProfile
    baseline_expected: NumericRange
    weather_correction: WeatherCorrection
    operational_correction: OperationalCorrection
    corrected_expected: NumericRange
    reported: QuantityObservation
    estimated: QuantityObservation
    verified: QuantityObservation
    deviation_from_upper_percent: float
    anomaly: bool
    confidence: float = Field(ge=0, le=1)
    explanation: str
    disclaimer: str


class VoyageCostBreakdown(BaseModel):
    fuel: float = Field(ge=0)
    port_fees: float = Field(ge=0)
    crew: float = Field(ge=0)
    handling: float = Field(ge=0)
    operating_cost: float = Field(ge=0)
    currency: str = "USD"


class VoyageEconomics(BaseModel):
    vessel_id: str
    voyage_id: str
    cargo_value: QuantityObservation
    cost_breakdown: VoyageCostBreakdown
    estimated_voyage_cost: float = Field(ge=0)
    value_cost_ratio: float = Field(ge=0)
    typical_ratio: NumericRange
    anomaly: bool
    confidence: float = Field(ge=0, le=1)
    explanation: str
    disclaimer: str


GraphNodeType = Literal["vessel", "company", "owner", "operator", "port", "cargo", "voyage"]
GraphEdgeType = Literal["owned_by", "operated_by", "visited", "carried", "encountered", "related_to"]


class GraphNode(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    risk_score: int | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    source_id: str
    target_id: str
    type: GraphEdgeType
    strength: Literal["low", "medium", "high"] | None = None
    confidence: float = Field(ge=0, le=1)
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class VesselConnection(BaseModel):
    id: str
    vessel_id: str
    related_vessel_id: str
    related_vessel_name: str
    encounters_total: int = Field(ge=0)
    encounters_last_six_months: int = Field(ge=0)
    average_duration_minutes: float = Field(ge=0)
    average_distance_m: float = Field(ge=0)
    open_sea_encounters: int = Field(ge=0)
    port_encounters: int = Field(ge=0)
    total_duration_minutes: float = Field(ge=0)
    observation_months: int = Field(ge=0)
    strength: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    explanation: str
    disclaimer: str


class InvestigationNetwork(BaseModel):
    root_id: str
    generated_at: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    disclaimer: str


class CompanyVoyageSummary(BaseModel):
    voyage_id: str
    vessel_id: str
    vessel_name: str
    route: str
    status: Literal["in_progress", "completed"]
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel


class CompanyRiskHistoryPoint(BaseModel):
    recorded_at: str
    average_risk_score: float = Field(ge=0, le=100)
    high_priority_vessels: int = Field(ge=0)
    model_version: str


class CompanyIntelligence(BaseModel):
    id: str
    name: str
    country: str
    role: Literal["owner", "operator", "owner_operator"]
    vessel_ids: list[str]
    voyage_count: int = Field(ge=0)
    ports: list[str]
    cargo_types: list[str]
    event_count: int = Field(ge=0)
    event_type_counts: dict[str, int] = Field(default_factory=dict)
    average_risk_score: float = Field(ge=0, le=100)
    recent_voyages: list[CompanyVoyageSummary] = Field(default_factory=list)
    risk_history: list[CompanyRiskHistoryPoint] = Field(default_factory=list)
    connection_ids: list[str]
    source: str
    source_timestamp: str
    confidence: float = Field(ge=0, le=1)
    verification_status: VerificationStatus
    disclaimer: str


class CompanyVesselSummary(BaseModel):
    id: str
    name: str
    vessel_type: str
    flag: str
    relationship: Literal["owned", "operated", "owned_operated"]
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    voyage_count: int = Field(ge=0)
    event_count: int = Field(ge=0)


class IntelligenceSummaryFactor(BaseModel):
    type: EventType
    title: str
    severity: EventSeverity
    confidence: float = Field(ge=0, le=1)
    source_event_id: str
    explanation: str


class VoyageIntelligenceSummary(BaseModel):
    vessel_id: str
    vessel_name: str
    voyage_id: str
    origin: str
    destination: str
    route_deviation_km: float
    ais_gap_minutes: int
    encounter_vessel_name: str
    encounter_duration_minutes: int
    cargo: CargoIntelligence
    fuel: FuelAnalysis
    economics: VoyageEconomics
    connections: list[VesselConnection]
    factors: list[IntelligenceSummaryFactor]
    significant_factor_count: int = Field(ge=0)
    base_risk_score: int = Field(ge=0, le=100)
    advanced_adjustment: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    summary: str
    main_factor_titles: list[str]
    generated_at: str
    disclaimer: str


class AdvancedRiskSignal(BaseModel):
    id: str
    event_id: str
    vessel_id: str
    voyage_id: str
    type: EventType
    label: str
    base_score: int = Field(ge=0, le=100)
    adjusted_score: int = Field(ge=0, le=100)
    confidence_weighted_score: int = Field(ge=0, le=100)
    effective_score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    deduplication_group: str
    deduplicated: bool = False
    source_timestamp: str
    explanation: str
    evidence: list[str] = Field(default_factory=list)


# Stage 7: Port Aktau / Smart Port

PortCallStatus = Literal[
    "approaching",
    "waiting",
    "arrived",
    "berth_assigned",
    "in_service",
    "service_completed",
    "departed",
]
PortEventType = Literal[
    "vessel_approaching",
    "eta_changed",
    "vessel_arrived",
    "vessel_waiting",
    "berth_assigned",
    "berth_changed",
    "service_started",
    "service_delayed",
    "service_completed",
    "vessel_departed",
    "port_congestion",
    "weather_restriction",
]
BerthDecisionAction = Literal["accept", "change_berth", "defer"]
SimulationScenario = Literal[
    "vessel_delay",
    "berth_unavailable",
    "service_extension",
    "new_vessel_arrival",
]


class ETAPredictionFactor(BaseModel):
    name: str
    value: str
    effect_minutes: int
    explanation: str
    source: SourceMetadata


class ETAPrediction(BaseModel):
    id: str
    port_call_id: str
    vessel_id: str
    reported_eta: str
    predicted_eta: str
    expected_delay_minutes: int
    confidence: float = Field(ge=0, le=1)
    likely_window_start: str
    likely_window_end: str
    calculated_at: str
    previous_prediction: str | None = None
    change_minutes: int = 0
    factors: list[ETAPredictionFactor]
    model_version: str
    explanation: str
    disclaimer: str


class BerthCompatibilityCheck(BaseModel):
    parameter: Literal["length", "draught", "cargo", "status", "availability", "restriction"]
    required: str
    capability: str
    compatible: bool
    explanation: str


class BerthCompatibility(BaseModel):
    vessel_id: str
    berth_id: str
    compatible: bool
    confidence: float = Field(ge=0, le=1)
    checks: list[BerthCompatibilityCheck]
    blocking_reasons: list[str] = Field(default_factory=list)
    explanation: str


class Berth(BaseModel):
    id: str
    port_id: str
    number: int = Field(gt=0)
    name: str
    length_m: float = Field(gt=0)
    max_vessel_length_m: float = Field(gt=0)
    max_draught_m: float = Field(gt=0)
    cargo_types: list[str]
    equipment: list[str]
    operational_status: Literal["available", "occupied", "limited", "closed", "maintenance"]
    current_vessel_id: str | None = None
    current_vessel_name: str | None = None
    service_started_at: str | None = None
    expected_completion_at: str | None = None
    next_vessel_id: str | None = None
    next_vessel_name: str | None = None
    available_from: str
    restrictions: list[str] = Field(default_factory=list)


class ServiceTimePrediction(BaseModel):
    id: str
    port_call_id: str
    vessel_id: str
    berth_id: str
    cargo_type: str
    cargo_mass_t: float = Field(ge=0)
    historical_rate_tph: float = Field(gt=0)
    cargo_handling_minutes: int = Field(ge=0)
    documentation_minutes: int = Field(ge=0)
    other_operations_minutes: int = Field(ge=0)
    weather_delay_minutes: int = Field(default=0, ge=0)
    total_minutes: int = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    berth_available_from: str
    projected_service_start: str
    projected_release_at: str
    model_version: str
    explanation: str


class BerthAssignmentRecommendation(BaseModel):
    id: str
    port_call_id: str
    vessel_id: str
    recommended_berth_id: str
    recommended_berth_number: int = Field(gt=0)
    state: Literal["recommended", "accepted", "changed", "deferred"] = "recommended"
    compatibility: BerthCompatibility
    alternative_berth_ids: list[str] = Field(default_factory=list)
    queue_position: int = Field(gt=0)
    berth_available_from: str
    service_prediction: ServiceTimePrediction
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    expected_effect: str
    human_decision_required: bool = True
    generated_at: str
    decided_by: str | None = None
    decided_at: str | None = None
    decision_note: str | None = None
    assigned_berth_id: str | None = None
    disclaimer: str


class BerthAssignmentDecisionRequest(BaseModel):
    port_call_id: str
    action: BerthDecisionAction
    operator: str = Field(min_length=2, max_length=120)
    berth_id: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class BerthAssignmentDecision(BaseModel):
    recommendation_id: str
    port_call_id: str
    action: BerthDecisionAction
    state: Literal["accepted", "changed", "deferred"]
    recommended_berth_id: str
    selected_berth_id: str | None = None
    operator: str
    decided_at: str
    note: str | None = None
    automated: bool = False
    explanation: str


class PortQueueItem(BaseModel):
    position: int = Field(gt=0)
    port_call_id: str
    vessel_id: str
    vessel_name: str
    eta: str
    berth_id: str | None = None
    berth_number: int | None = Field(default=None, gt=0)
    cargo_type: str
    risk_score: int = Field(ge=0, le=100)
    operational_priority: int = Field(ge=0, le=100)
    expected_service_minutes: int = Field(gt=0)
    expected_wait_minutes: int = Field(ge=0)
    status: Literal["scheduled", "attention", "waiting", "deferred"]
    factors: list[str]


class PortQueueSnapshot(BaseModel):
    port_id: str
    generated_at: str
    average_wait_minutes: int = Field(ge=0)
    dynamic: bool = True
    items: list[PortQueueItem]
    recalculation_reason: str
    disclaimer: str


class PortWeather(BaseModel):
    observed_at: str
    wind_mps: float = Field(ge=0)
    waves_m: float = Field(ge=0)
    visibility_km: float = Field(ge=0)
    temperature_c: float
    storm: bool
    source: str
    confidence: float = Field(ge=0, le=1)


class WeatherRestriction(BaseModel):
    id: str
    berth_id: str
    active: bool
    operation_status: Literal["normal", "limited", "suspended"]
    reason: str
    processing_delay_minutes: int = Field(ge=0)
    started_at: str
    expected_end_at: str | None = None
    source: SourceMetadata


class WeatherRecalculationResult(BaseModel):
    port_id: str
    restriction: WeatherRestriction
    previous_service_minutes: int = Field(gt=0)
    recalculated_service: ServiceTimePrediction
    previous_average_wait_minutes: int = Field(ge=0)
    recalculated_queue: PortQueueSnapshot
    recalculated_load_forecast: "PortLoadForecast"
    affected_port_call_ids: list[str]
    explanation: str


class PortLoadForecastPoint(BaseModel):
    horizon_hours: int = Field(ge=0)
    forecast_at: str
    handling_pressure_percent: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    primary_driver: str


class PortBottleneck(BaseModel):
    id: str
    severity: Literal["watch", "warning", "critical"]
    window_start: str
    window_end: str
    berth_ids: list[str]
    expected_load_percent: int = Field(ge=0, le=100)
    primary_reason: str
    affected_vessel_ids: list[str]
    confidence: float = Field(ge=0, le=1)


class PortOperationalRecommendation(BaseModel):
    id: str
    action: str
    vessel_id: str
    from_berth_id: str | None = None
    to_berth_id: str | None = None
    average_wait_change_minutes: int
    load_before_percent: int = Field(ge=0, le=100)
    load_after_percent: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reasons: list[str]
    human_decision_required: bool = True
    disclaimer: str


class PortLoadForecast(BaseModel):
    port_id: str
    generated_at: str
    metric_label: str
    current_operational_utilization_percent: int = Field(ge=0, le=100)
    points: list[PortLoadForecastPoint]
    bottlenecks: list[PortBottleneck]
    recommendations: list[PortOperationalRecommendation]
    weather_restriction: WeatherRestriction | None = None
    model_version: str
    explanation: str


class ArrivalBoardEntry(BaseModel):
    port_call_id: str
    vessel_id: str
    vessel_name: str
    predicted_eta: str
    eta_confidence: float = Field(ge=0, le=1)
    berth_id: str | None = None
    berth_number: int | None = Field(default=None, gt=0)
    berth_assignment_status: Literal["recommended", "confirmed", "waiting", "deferred"]
    cargo_type: str
    cargo_mass_t: float | None = Field(default=None, ge=0)
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    attention_status: Literal["normal", "attention", "high"]
    port_call_status: PortCallStatus


class PortOperationsOverview(BaseModel):
    port_id: str
    port_name: str
    generated_at: str
    port_load_percent: int = Field(ge=0, le=100)
    load_metric_label: str
    arriving_vessels: int = Field(ge=0)
    in_port: int = Field(ge=0)
    waiting: int = Field(ge=0)
    departing: int = Field(ge=0)
    average_wait_minutes: int = Field(ge=0)
    berths_available: int = Field(ge=0)
    berths_occupied: int = Field(ge=0)
    high_risk_arrivals: int = Field(ge=0)
    weather: PortWeather
    active_weather_restrictions: int = Field(ge=0)
    next_bottleneck: PortBottleneck | None = None
    operational_recommendations: list[PortOperationalRecommendation]
    disclaimer: str


class PortTimelineEntry(BaseModel):
    id: str
    event_type: PortEventType
    planned_at: str | None = None
    actual_at: str | None = None
    berth_id: str | None = None
    title: str
    detail: str
    source: str
    verification_status: VerificationStatus


class PortCall(BaseModel):
    id: str
    vessel_id: str
    vessel_name: str
    voyage_id: str
    port_id: str
    reported_eta: str
    predicted_eta: str
    actual_arrival: str | None = None
    berth_id: str | None = None
    berth_assignment_status: Literal["recommended", "confirmed", "deferred"]
    queue_position: int | None = Field(default=None, gt=0)
    queue_entered_at: str | None = None
    berth_started_at: str | None = None
    service_started_at: str | None = None
    service_completed_at: str | None = None
    actual_departure: str | None = None
    status: PortCallStatus
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    significant_event_count: int = Field(ge=0)
    cargo_type: str
    reported_cargo_t: float = Field(ge=0)
    verified_cargo_t: float | None = Field(default=None, ge=0)
    reported_draught_m: float = Field(ge=0)
    verified_draught_m: float | None = Field(default=None, ge=0)
    documents_verified: bool | None = None
    timeline: list[PortTimelineEntry]
    created_at: str
    updated_at: str


class PreArrivalReport(BaseModel):
    id: str
    port_call_id: str
    vessel_id: str
    vessel_name: str
    eta: ETAPrediction
    berth_recommendation: BerthAssignmentRecommendation
    cargo_summary: str
    service_prediction: ServiceTimePrediction
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    attention_level: Literal["normal", "elevated", "high"]
    significant_event_count: int = Field(ge=0)
    significant_events: list[str]
    recommended_actions: list[str]
    generated_at: str
    disclaimer: str


class PortOperationalEvent(BaseModel):
    id: str
    type: PortEventType
    port_id: str
    port_call_id: str | None = None
    vessel_id: str | None = None
    berth_id: str | None = None
    occurred_at: str
    status: Literal["active", "completed", "cancelled"] = "active"
    severity: Literal["info", "warning", "critical"] = "info"
    source: str
    confidence: float = Field(ge=0, le=1)
    data: dict[str, Any] = Field(default_factory=dict)
    explanation: str
    created_by: str
    automated: bool


class PortActualsInput(BaseModel):
    actual_arrival: str
    berth_started_at: str
    service_started_at: str
    service_completed_at: str
    actual_departure: str
    verified_cargo_t: float = Field(ge=0)
    verified_draught_m: float = Field(ge=0)
    documents_verified: bool
    recorded_by: str = Field(min_length=2, max_length=120)
    source: str = "Aktau port operations"


class ActualVsPredictedMetric(BaseModel):
    metric: Literal["arrival", "service_duration", "cargo", "draught"]
    predicted: float | str
    actual: float | str
    error: float
    unit: str
    interpretation: str


class PortFeedbackRecord(BaseModel):
    id: str
    port_call_id: str
    vessel_id: str
    voyage_id: str
    recorded_at: str
    recorded_by: str
    reported_cargo: QuantityObservation
    verified_cargo: QuantityObservation
    reported_draught: QuantityObservation
    verified_draught: QuantityObservation
    comparisons: list[ActualVsPredictedMetric]
    intelligence_update_targets: list[str]
    emitted_event_ids: list[str]
    closed_loop_complete: bool
    explanation: str
    disclaimer: str


class PortSimulationRequest(BaseModel):
    scenario: SimulationScenario
    vessel_id: str | None = None
    delay_minutes: int = Field(default=0, ge=0, le=1440)
    berth_id: str | None = None
    service_extension_minutes: int = Field(default=0, ge=0, le=1440)
    new_vessel_name: str | None = None
    new_vessel_eta: str | None = None


class PortSimulationResult(BaseModel):
    id: str
    scenario: SimulationScenario
    generated_at: str
    baseline_average_wait_minutes: int = Field(ge=0)
    simulated_average_wait_minutes: int = Field(ge=0)
    waiting_time_change_minutes: int
    baseline_peak_load_percent: int = Field(ge=0, le=100)
    simulated_peak_load_percent: int = Field(ge=0, le=100)
    berth_congestion_change_percent: int
    affected_vessel_ids: list[str]
    simulated_queue: PortQueueSnapshot
    impacts: list[str]
    recommendations: list[str]
    state_changed: bool = False
    human_decision_required: bool = True
    disclaimer: str


# Stage 8: grounded AI Assistant & Investigation

AssistantRole = Literal["ADMIN", "ANALYST", "VIEWER", "PORT_DISPATCHER"]
AssistantClaimKind = Literal["fact", "estimate", "inference"]
AssistantActionStatus = Literal["pending", "confirmed", "rejected", "failed"]
InvestigationStatus = Literal["open", "in_review", "closed"]
InvestigationPriority = Literal["low", "medium", "high", "critical"]


class AssistantAreaContext(BaseModel):
    west: float = Field(ge=-180, le=180)
    south: float = Field(ge=-90, le=90)
    east: float = Field(ge=-180, le=180)
    north: float = Field(ge=-90, le=90)
    from_time: str | None = None
    to_time: str | None = None

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.east <= self.west or self.north <= self.south:
            raise ValueError("Area bounds must describe a non-empty rectangle")
        return self


class AssistantContext(BaseModel):
    current_page: str = "/app/assistant"
    vessel_id: str | None = None
    voyage_id: str | None = None
    port_id: str | None = None
    investigation_id: str | None = None
    environmental_event_id: str | None = None
    area: AssistantAreaContext | None = None


class AssistantChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    conversation_id: str | None = None
    context: AssistantContext = Field(default_factory=AssistantContext)


class AssistantEvidenceLink(BaseModel):
    id: str
    source_type: Literal[
        "vessel", "voyage", "event", "risk_assessment", "risk_factor",
        "behavior", "cargo", "fuel", "network", "eta", "port",
        "port_call", "investigation", "policy", "environmental_event",
        "environmental_candidate", "environmental_reconstruction", "environmental_observation",
    ]
    label: str
    href: str
    source_module: str


class AssistantClaim(BaseModel):
    kind: AssistantClaimKind
    statement: str
    evidence: list[AssistantEvidenceLink] = Field(default_factory=list)


class AssistantToolTrace(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    record_count: int = Field(ge=0)
    data_accessed: list[str] = Field(default_factory=list)
    status: Literal["success", "denied", "not_found", "error"] = "success"


class AssistantAction(BaseModel):
    id: str
    action_type: Literal[
        "create_investigation", "add_case_evidence", "update_investigation",
        "add_case_note", "assign_berth", "change_port_queue", "close_event",
        "open_network", "open_port", "open_investigation", "open_environment",
        "open_regional_risk", "open_global_identity", "open_cross_port",
        "open_regional_network", "open_data_health",
    ]
    label: str
    requires_confirmation: bool
    status: AssistantActionStatus = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)
    navigation_target: str | None = None
    created_at: str
    requested_by: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None


class AssistantChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    title: str
    answer: str
    claims: list[AssistantClaim] = Field(default_factory=list)
    tools_called: list[AssistantToolTrace] = Field(default_factory=list)
    actions: list[AssistantAction] = Field(default_factory=list)
    grounded: bool = True
    no_data: bool = False
    created_at: str
    disclaimer: str


class AssistantConversationMessage(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str
    response: AssistantChatResponse | None = None


class AssistantConversation(BaseModel):
    id: str
    user_id: str
    role: AssistantRole
    title: str
    context: AssistantContext
    messages: list[AssistantConversationMessage] = Field(default_factory=list)
    last_vessel_id: str | None = None
    last_voyage_id: str | None = None
    last_related_vessel_id: str | None = None
    last_investigation_id: str | None = None
    last_environmental_event_id: str | None = None
    created_at: str
    updated_at: str


class AssistantAuditEntry(BaseModel):
    id: str
    user_id: str
    role: AssistantRole
    question: str
    conversation_id: str | None = None
    timestamp: str
    tools_called: list[str] = Field(default_factory=list)
    data_accessed: list[str] = Field(default_factory=list)
    answer: str
    actions: list[str] = Field(default_factory=list)
    outcome: Literal["answered", "insufficient_data", "denied", "confirmed", "rejected", "failed"]


class InvestigationEvidence(BaseModel):
    id: str
    source_id: str
    source_type: Literal[
        "event", "risk_factor", "voyage", "port_event", "document",
        "environmental_event", "environmental_observation", "environmental_geometry",
        "environmental_reconstruction", "environmental_candidate", "ais_track",
    ]
    title: str
    detail: str
    claim_kind: AssistantClaimKind
    source_href: str
    source_module: str
    occurred_at: str | None = None
    added_by: str
    added_at: str


class InvestigationTimelineItem(BaseModel):
    id: str
    occurred_at: str
    title: str
    detail: str
    claim_kind: AssistantClaimKind
    source_id: str
    source_href: str


class InvestigationNote(BaseModel):
    id: str
    text: str
    author: str
    created_at: str


class Investigation(BaseModel):
    id: str
    title: str
    status: InvestigationStatus
    priority: InvestigationPriority
    vessel_id: str
    vessel_name: str
    voyage_id: str | None = None
    route: str | None = None
    assigned_to: str
    event_ids: list[str] = Field(default_factory=list)
    evidence: list[InvestigationEvidence] = Field(default_factory=list)
    related_vessel_ids: list[str] = Field(default_factory=list)
    related_company_ids: list[str] = Field(default_factory=list)
    notes: list[InvestigationNote] = Field(default_factory=list)
    timeline: list[InvestigationTimelineItem] = Field(default_factory=list)
    summary: str | None = None
    summary_claims: list[AssistantClaim] = Field(default_factory=list)
    conclusion: str | None = None
    case_type: Literal["maritime", "environmental"] = "maritime"
    environmental_event_id: str | None = None
    disclaimer: str | None = None
    created_by: str
    created_at: str
    updated_at: str


class InvestigationCreateRequest(BaseModel):
    vessel_id: str
    voyage_id: str | None = None
    title: str | None = Field(default=None, max_length=300)
    priority: InvestigationPriority | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    confirmed: bool = False


class InvestigationEvidenceRequest(BaseModel):
    evidence_ids: list[str] = Field(min_length=1, max_length=100)
    confirmed: bool = False


class InvestigationNoteRequest(BaseModel):
    note: str = Field(min_length=1, max_length=4000)
    confirmed: bool = False


class InvestigationUpdateRequest(BaseModel):
    status: InvestigationStatus | None = None
    priority: InvestigationPriority | None = None
    assigned_to: str | None = Field(default=None, max_length=120)
    conclusion: str | None = Field(default=None, max_length=8000)
    confirmed: bool = False


class AssistantActionDecisionRequest(BaseModel):
    confirmed: bool
    note: str | None = Field(default=None, max_length=1000)


# Stage 9: Environmental Intelligence

EnvironmentalProvenance = Literal["OBSERVED", "ESTIMATED", "INFERRED"]
EnvironmentalStatus = Literal[
    "DETECTED", "ANALYZING", "UNDER REVIEW", "INVESTIGATION", "RESOLVED", "FALSE POSITIVE",
]
EnvironmentalReviewOutcome = Literal[
    "CONFIRMED POLLUTION", "LIKELY POLLUTION", "UNCERTAIN", "FALSE POSITIVE",
]
EnvironmentalSourceClassification = Literal["UNKNOWN", "VERIFIED EXTERNAL FINDING"]
EnvironmentalPriority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
EnvironmentalRiskFactorCode = Literal[
    "ENVIRONMENTAL_PROXIMITY",
    "ENVIRONMENTAL_TIME_OVERLAP",
    "ENVIRONMENTAL_ROUTE_MATCH",
    "ENVIRONMENTAL_ASSOCIATION",
]
EnvironmentalInputType = Literal[
    "EXTERNAL_API", "PREPROCESSED_SATELLITE", "MANUAL", "DEMO",
]


class EnvironmentalGeometry(BaseModel):
    """GeoJSON-compatible polygon used by the spatial API and PostGIS layer."""

    type: Literal["Polygon", "MultiPolygon"]
    coordinates: list[Any]

    @model_validator(mode="after")
    def validate_polygon(self):
        if not self.coordinates:
            raise ValueError("Environmental geometry cannot be empty")
        if self.type == "Polygon":
            rings = self.coordinates
        else:
            if any(not isinstance(polygon, list) or not polygon for polygon in self.coordinates):
                raise ValueError("Each MultiPolygon member must contain polygon rings")
            rings = [ring for polygon in self.coordinates for ring in polygon]
        if not rings:
            raise ValueError("Environmental geometry must contain at least one ring")
        for ring in rings:
            if not isinstance(ring, list) or len(ring) < 4:
                raise ValueError("Each polygon ring must contain at least four positions")
            if ring[0] != ring[-1]:
                raise ValueError("Each polygon ring must be closed")
            for point in ring:
                if not isinstance(point, list) or len(point) < 2:
                    raise ValueError("Polygon positions must be [longitude, latitude] pairs")
                longitude, latitude = point[0], point[1]
                if (
                    isinstance(longitude, bool) or isinstance(latitude, bool)
                    or not isinstance(longitude, (int, float))
                    or not isinstance(latitude, (int, float))
                ):
                    raise ValueError("Polygon longitude and latitude must be numeric")
                if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                    raise ValueError("Polygon longitude or latitude is outside WGS84 bounds")
        return self


class EnvironmentalObservation(BaseModel):
    id: str
    category: Literal["wind", "current", "weather", "water", "detection"]
    parameter: str
    value: float | str
    unit: str | None = None
    direction_degrees: float | None = Field(default=None, ge=0, le=360)
    observed_at: str
    source: str
    source_reference: str | None = None
    confidence: float = Field(ge=0, le=1)
    provenance: EnvironmentalProvenance


class EnvironmentalRawData(BaseModel):
    id: str
    event_id: str | None = None
    provider: str
    input_type: EnvironmentalInputType
    received_at: str
    observed_at: str
    source_reference: str
    payload: dict[str, Any]
    checksum: str
    created_by: str


class EnvironmentalEvent(BaseModel):
    id: str
    alias: str | None = None
    type: Literal[
        "OIL_POLLUTION", "CHEMICAL_POLLUTION", "ALGAE_BLOOM",
        "FLOATING_WASTE", "UNKNOWN_POLLUTION",
    ]
    title: str
    detected_at: str
    estimated_started_at: str | None = None
    estimated_ended_at: str | None = None
    geometry: EnvironmentalGeometry
    center: Coordinates
    area_km2: float = Field(gt=0)
    detection_source: str
    source_reference: str
    raw_data_id: str
    confidence: float = Field(ge=0, le=1)
    status: EnvironmentalStatus
    priority: EnvironmentalPriority
    environmental_data: list[EnvironmentalObservation] = Field(default_factory=list)
    investigation_id: str | None = None
    provenance: EnvironmentalProvenance = "OBSERVED"
    summary: str
    disclaimer: str
    created_at: str
    updated_at: str


class EnvironmentalRawIngestRequest(BaseModel):
    """Provider-neutral envelope; provider-specific data stays in ``payload``."""

    provider: str = Field(min_length=1, max_length=120)
    input_type: EnvironmentalInputType
    observed_at: str
    source_reference: str = Field(min_length=1, max_length=500)
    payload: dict[str, Any]
    confidence: float = Field(default=.5, ge=0, le=1)


class EnvironmentalEventList(BaseModel):
    items: list[EnvironmentalEvent]
    total: int = Field(ge=0)
    active_count: int = Field(ge=0)
    high_priority_count: int = Field(ge=0)
    in_investigation_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)


class EnvironmentalTrackPoint(BaseModel):
    timestamp: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    speed_kn: float = Field(ge=0)
    course_degrees: float = Field(ge=0, le=360)
    source_reference: str
    provenance: EnvironmentalProvenance = "OBSERVED"


class EnvironmentalAssociationFactor(BaseModel):
    id: str
    code: EnvironmentalRiskFactorCode | None = None
    label: str
    observed: str
    contribution: int = Field(ge=0, le=100)
    provenance: EnvironmentalProvenance
    source_ids: list[str] = Field(default_factory=list)
    interpretation: str


class EnvironmentalRiskContext(BaseModel):
    id: str
    event_id: str
    vessel_id: str
    maritime_risk_score: int = Field(ge=0, le=100)
    environmental_adjustment_raw: int = Field(ge=0, le=100)
    environmental_adjustment_effective: int = Field(ge=0, le=100)
    combined_context_score: int = Field(ge=0, le=100)
    status: Literal["UNDER REVIEW", "REVIEWED", "DISMISSED"] = "UNDER REVIEW"
    provenance: Literal["INFERRED"] = "INFERRED"
    factors: list[EnvironmentalAssociationFactor]
    source_ids: list[str]
    model_version: str
    explanation: str
    disclaimer: str


class EnvironmentalCandidate(BaseModel):
    id: str
    event_id: str
    vessel_id: str
    vessel_name: str
    distance_km: float = Field(ge=0)
    temporal_overlap_percent: float = Field(ge=0, le=100)
    ais_gap: bool
    relevance: Literal["HIGH", "MEDIUM", "LOW", "EXCLUDED"]
    association_score: int = Field(ge=0, le=100)
    factors: list[EnvironmentalAssociationFactor]
    track: list[EnvironmentalTrackPoint]
    evidence_ids: list[str]
    risk_context: EnvironmentalRiskContext | None = None
    provenance: Literal["INFERRED"] = "INFERRED"
    explanation: str
    disclaimer: str


class EnvironmentalCandidateSearchResult(BaseModel):
    event_id: str
    search_started_at: str
    search_ended_at: str
    searched_candidate_count: int = Field(ge=0)
    relevant_candidate_count: int = Field(ge=0)
    candidates: list[EnvironmentalCandidate]
    extended_candidates: list[EnvironmentalCandidate] = Field(default_factory=list)
    method: str
    disclaimer: str


class EnvironmentalReconstructionStep(BaseModel):
    timestamp: str
    geometry: EnvironmentalGeometry
    center: Coordinates
    area_km2: float = Field(gt=0)
    provenance: Literal["ESTIMATED"] = "ESTIMATED"


class EnvironmentalReconstruction(BaseModel):
    id: str
    event_id: str
    current_geometry: EnvironmentalGeometry
    origin_geometry: EnvironmentalGeometry
    estimated_origin_from: str
    estimated_origin_to: str
    wind: EnvironmentalObservation
    current: EnvironmentalObservation
    weather: list[EnvironmentalObservation]
    steps: list[EnvironmentalReconstructionStep]
    confidence: float = Field(ge=0, le=1)
    provenance: Literal["ESTIMATED"] = "ESTIMATED"
    model_version: str
    method: str
    limitation: str
    disclaimer: str


class EnvironmentalTimelineItem(BaseModel):
    id: str
    timestamp: str
    type: Literal[
        "ORIGIN_WINDOW", "VESSEL_POSITION", "AIS_GAP", "WEATHER",
        "DETECTION", "ANALYSIS", "REVIEW",
    ]
    title: str
    detail: str
    vessel_id: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    provenance: EnvironmentalProvenance


class EnvironmentalTimeline(BaseModel):
    event_id: str
    items: list[EnvironmentalTimelineItem]


class EnvironmentalReplayVessel(BaseModel):
    vessel_id: str
    vessel_name: str
    latitude: float
    longitude: float
    speed_kn: float = Field(ge=0)
    course_degrees: float = Field(ge=0, le=360)
    ais_available: bool = True
    provenance: EnvironmentalProvenance = "OBSERVED"


class EnvironmentalReplayFrame(BaseModel):
    timestamp: str
    pollution_geometry: EnvironmentalGeometry
    vessels: list[EnvironmentalReplayVessel]
    wind_direction_degrees: float = Field(ge=0, le=360)
    current_direction_degrees: float = Field(ge=0, le=360)
    provenance: EnvironmentalProvenance


class EnvironmentalReplay(BaseModel):
    event_id: str
    started_at: str
    ended_at: str
    step_minutes: int = Field(gt=0)
    frames: list[EnvironmentalReplayFrame]
    disclaimer: str


class VesselEnvironmentalHistoryItem(BaseModel):
    id: str
    environmental_event_id: str
    occurred_at: str
    event_type: str
    relationship: Literal["CANDIDATE", "NEARBY", "CLEARED", "REVIEWED"]
    relevance: Literal["HIGH", "MEDIUM", "LOW", "NONE"]
    distance_km: float = Field(ge=0)
    title: str
    detail: str
    provenance: EnvironmentalProvenance
    source_ids: list[str]


class VesselEnvironmentProfile(BaseModel):
    vessel_id: str
    vessel_name: str
    candidate_event_count: int = Field(ge=0)
    reviewed_event_count: int = Field(ge=0)
    history: list[VesselEnvironmentalHistoryItem]
    generated_at: str
    disclaimer: str


class EnvironmentalReviewRequest(BaseModel):
    outcome: EnvironmentalReviewOutcome
    source_classification: EnvironmentalSourceClassification = "UNKNOWN"
    note: str = Field(min_length=2, max_length=4000)


class EnvironmentalReview(BaseModel):
    id: str
    event_id: str
    outcome: EnvironmentalReviewOutcome
    source_classification: EnvironmentalSourceClassification
    note: str
    reviewer: str
    reviewed_at: str
    provenance: Literal["OBSERVED"] = "OBSERVED"


class EnvironmentalReviewResult(BaseModel):
    event: EnvironmentalEvent
    review: EnvironmentalReview


class EnvironmentalInvestigationRequest(BaseModel):
    confirmed: bool = False
    priority: InvestigationPriority = "high"
    assigned_to: str | None = Field(default=None, max_length=120)
