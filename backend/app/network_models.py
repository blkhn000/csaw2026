"""Typed contracts for Stage 10 Caspian Network.

The network layer deliberately has its own models.  Existing Stage 1-9
contracts remain stable while regional integrations can evolve independently.
All timestamps emitted by this module are UTC ISO-8601 values.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


NetworkRole = Literal["ADMIN", "ANALYST", "VIEWER", "PORT_DISPATCHER"]
ProvenanceStatus = Literal["REPORTED", "OBSERVED", "VERIFIED", "ESTIMATED", "INFERRED"]


class NetworkOrganization(BaseModel):
    id: str
    name: str
    country: str | None = None
    organization_type: Literal[
        "REGIONAL_PLATFORM", "PORT_AUTHORITY", "PORT", "CUSTOMS",
        "ENVIRONMENTAL_AGENCY", "SHIPPING_COMPANY", "PUBLIC",
    ]
    home_port_ids: list[str] = Field(default_factory=list)
    active: bool = True


class NetworkPrincipal(BaseModel):
    user_id: str
    organization: NetworkOrganization
    role: NetworkRole
    permissions: list[str]
    data_scope: list[str]


class PortCoordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class PortConfiguration(BaseModel):
    berth_count: int = Field(ge=0)
    cargo_capabilities: list[str]
    maximum_draught_m: float = Field(gt=0)
    operational_rules: list[str]
    queue_policy: str
    weather_restrictions: list[str]
    working_hours: str
    service_models: list[str]
    configuration_version: str


class PortIntegrationStatus(BaseModel):
    ais: Literal["CONNECTED", "PARTIAL", "NOT_CONNECTED"]
    port_calls: Literal["CONNECTED", "PARTIAL", "NOT_CONNECTED"]
    berths: Literal["CONNECTED", "PARTIAL", "NOT_CONNECTED"]
    cargo: Literal["CONNECTED", "PARTIAL", "NOT_CONNECTED"]
    documents: Literal["CONNECTED", "PARTIAL", "NOT_CONNECTED"]
    adapter_id: str
    last_sync_at: str


class NetworkPort(BaseModel):
    id: str
    name: str
    country: str
    country_code: str
    coordinates: PortCoordinates
    timezone: str
    utc_offset: str
    port_type: str
    capabilities: list[str]
    anchorage_zones: list[str]
    navigation_zones: list[str]
    data_source_ids: list[str]
    operational_status: Literal["OPERATIONAL", "BUSY", "LIMITED", "DEGRADED"]
    integration_status: PortIntegrationStatus
    configuration: PortConfiguration


class PortStatus(BaseModel):
    port_id: str
    name: str
    country: str
    latitude: float
    longitude: float
    load_percent: int = Field(ge=0, le=100)
    arrivals: int = Field(ge=0)
    departures: int = Field(ge=0)
    vessels: int = Field(ge=0)
    high_risk_arrivals: int = Field(ge=0)
    status: Literal["NORMAL", "BUSY", "DEGRADED", "LIMITED"]
    updated_at: str


class PortBerth(BaseModel):
    id: str
    port_id: str
    name: str
    status: Literal["AVAILABLE", "OCCUPIED", "LIMITED"]
    max_length_m: float
    max_draught_m: float
    cargo_types: list[str]
    current_vessel_id: str | None = None
    available_at: str | None = None


class PortMovement(BaseModel):
    id: str
    port_id: str
    global_vessel_id: str
    vessel_name: str
    voyage_id: str
    movement_type: Literal["ARRIVAL", "DEPARTURE"]
    predicted_at: str
    reported_at: str | None = None
    berth_id: str | None = None
    cargo_type: str | None = None
    cargo_t: float | None = None
    draught_m: float | None = None
    risk_score: int = Field(default=0, ge=0, le=100)
    status: str
    source_ids: list[str]


class VesselSourceAlias(BaseModel):
    source_id: str
    source_vessel_id: str
    name: str
    mmsi: str | None = None
    imo: str | None = None
    first_seen_at: str
    last_seen_at: str
    match_status: Literal["CONFIRMED", "PROBABLE", "REVIEW_REQUIRED"]


class VesselIdentityHistoryItem(BaseModel):
    valid_from: str
    valid_to: str | None = None
    name: str
    mmsi: str
    flag: str
    call_sign: str
    owner_company_id: str
    operator_company_id: str
    change_reason: str
    source_ids: list[str]


class GlobalVesselIdentity(BaseModel):
    caspian_vessel_id: str
    legacy_vessel_id: str
    canonical_name: str
    imo: str
    mmsi: str
    call_sign: str
    flag: str
    vessel_type: str
    length_m: float
    width_m: float
    owner_company_id: str
    operator_company_id: str
    source_aliases: list[VesselSourceAlias]
    identity_history: list[VesselIdentityHistoryItem]
    resolution_confidence: float = Field(ge=0, le=1)
    resolution_status: Literal["CONFIRMED", "PROBABLE", "REVIEW_REQUIRED"]
    updated_at: str


class VesselIdentityResolutionRequest(BaseModel):
    source_id: str
    source_vessel_id: str
    imo: str | None = None
    mmsi: str | None = None
    name: str | None = None
    call_sign: str | None = None
    flag: str | None = None
    length_m: float | None = None
    width_m: float | None = None
    owner: str | None = None
    operator: str | None = None

    @model_validator(mode="after")
    def require_identity_signal(self):
        if not any((self.imo, self.mmsi, self.name, self.call_sign)):
            raise ValueError("At least one strong vessel identity signal is required")
        return self


class IdentityResolutionResult(BaseModel):
    entity_type: Literal["VESSEL", "COMPANY"]
    global_id: str | None
    matched: bool
    confidence: float = Field(ge=0, le=1)
    status: Literal["CONFIRMED", "PROBABLE", "REVIEW_REQUIRED", "NO_MATCH"]
    matched_on: list[str]
    conflicting_fields: list[str]
    candidates: list[dict[str, Any]]
    explanation: str


class GlobalCompanyIdentity(BaseModel):
    caspian_company_id: str
    canonical_name: str
    country: str
    company_type: str
    aliases: list[str]
    registration_numbers: list[str]
    vessel_ids: list[str]
    related_company_ids: list[str]
    resolution_confidence: float = Field(ge=0, le=1)
    updated_at: str


class CompanyIdentityResolutionRequest(BaseModel):
    name: str
    registration_number: str | None = None
    country: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Company name is required")
        return value.strip()


class DataSourceRecord(BaseModel):
    id: str
    name: str
    source_type: Literal["AIS", "PORT", "ENVIRONMENTAL", "WEATHER", "OPERATOR", "PLATFORM"]
    organization_id: str
    status: Literal["ONLINE", "DEGRADED", "OFFLINE"]
    quality_score: float = Field(ge=0, le=1)
    coverage: str
    latency_seconds: int = Field(ge=0)
    last_update_at: str
    authoritative_for: list[str]
    adapter_id: str


class ProvenanceRecord(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    field_name: str
    value: Any
    unit: str | None = None
    source_id: str
    received_at: str
    status: ProvenanceStatus
    quality_score: float = Field(ge=0, le=1)
    supersedes_id: str | None = None


class DataConflictValue(BaseModel):
    provenance_id: str
    source_id: str
    value: Any
    unit: str | None = None
    status: ProvenanceStatus


class DataConflict(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    field_name: str
    values: list[DataConflictValue]
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["OPEN", "RESOLVED", "ACCEPTED_DIFFERENCE"]
    preferred_provenance_id: str | None = None
    explanation: str
    created_at: str
    resolved_at: str | None = None


class RegionalRiskItem(BaseModel):
    global_vessel_id: str
    legacy_vessel_id: str
    vessel_name: str
    score: int = Field(ge=0, le=100)
    level: Literal["LOW", "MODERATE", "HIGH", "CRITICAL"]
    origin_port_id: str
    destination_port_id: str
    route_id: str
    vessel_type: str
    event_types: list[str]
    source_assessment_id: str
    updated_at: str


class RouteIntelligence(BaseModel):
    id: str
    origin_port_id: str
    destination_port_id: str
    display_name: str
    period_days: int
    voyages: int
    average_duration_minutes: int
    average_delay_minutes: int
    ais_gaps: int
    encounters: int
    high_risk_voyages: int
    average_cargo_t: float
    active_vessels: int
    trend_percent: float
    source_ids: list[str]
    generated_at: str


class CrossPortObservation(BaseModel):
    port_id: str
    observed_at: str
    cargo_t: float | None = None
    draught_m: float | None = None
    shipper: str | None = None
    consignee: str | None = None
    document_ids: list[str]
    status: ProvenanceStatus
    source_ids: list[str]


class CrossPortComparison(BaseModel):
    field_name: str
    departure_value: float | str | None
    arrival_value: float | str | None
    difference: float | None = None
    unit: str | None = None
    tolerance: float | None = None
    status: Literal["WITHIN_TOLERANCE", "DATA_MISMATCH", "NOT_COMPARABLE"]
    explanation: str
    evidence_ids: list[str]


class CrossPortReport(BaseModel):
    voyage_id: str
    global_vessel_id: str
    vessel_name: str
    origin_port_id: str
    destination_port_id: str
    departure: CrossPortObservation
    arrival: CrossPortObservation
    comparisons: list[CrossPortComparison]
    overall_status: Literal["WITHIN_TOLERANCE", "REVIEW_REQUIRED", "DATA_MISMATCH"]
    provenance: list[ProvenanceRecord]
    next_voyage_id: str | None = None
    generated_at: str
    disclaimer: str


class RegionalGraphNode(BaseModel):
    id: str
    type: Literal["VESSEL", "COMPANY", "PORT", "ROUTE", "CARGO", "EVENT"]
    label: str
    country: str | None = None
    risk_score: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegionalGraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship: Literal[
        "OWNS", "OPERATES", "VISITED", "SAILED_ROUTE", "ENCOUNTERED",
        "CARRIED", "CONNECTS", "RELATED_TO",
    ]
    weight: float = Field(default=1, ge=0)
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class RegionalAuditEntry(BaseModel):
    id: str
    timestamp: str
    user_id: str
    organization_id: str
    role: NetworkRole
    action: str
    resource_type: str
    resource_id: str | None = None
    data_scope: list[str]
    outcome: Literal["ALLOWED", "DENIED"]
    details: dict[str, Any] = Field(default_factory=dict)


class AdapterStatus(BaseModel):
    id: str
    port_id: str
    adapter_type: str
    version: str
    status: Literal["ONLINE", "DEGRADED", "OFFLINE"]
    capabilities: list[str]
    last_success_at: str
    last_error: str | None = None

