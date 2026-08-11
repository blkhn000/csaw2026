import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .advanced_analytics import advanced_analytics
from .assistant import assistant_service
from .ais_gateway import gateway, haversine_km
from .behavior_engine import behavior_engine
from .caspian_network import network_service
from .demo_data import PORTS, POSITIONS, VESSELS, VOYAGES
from .event_engine import event_engine
from .environmental import environmental_service
from .models import (
    AISIngestRequest, AssistantActionDecisionRequest, AssistantChatRequest, AssistantChatResponse,
    AssistantConversation, AssistantAuditEntry, BerthAssignmentDecisionRequest, EventStatusUpdate,
    EnvironmentalEvent, EnvironmentalEventList, EnvironmentalInvestigationRequest,
    EnvironmentalRawData, EnvironmentalRawIngestRequest,
    EnvironmentalReviewRequest, EnvironmentalReviewResult,
    Investigation, InvestigationCreateRequest, InvestigationEvidenceRequest, InvestigationNoteRequest,
    InvestigationUpdateRequest, LoginRequest, MapVessel,
    Port, PortActualsInput, PortSimulationRequest, Position, SpatialSearchRequest,
    RiskFactorReviewRequest, TokenResponse, TrackResponse, Vessel, Voyage,
)
from .network_models import (
    CompanyIdentityResolutionRequest, NetworkPrincipal,
    VesselIdentityResolutionRequest,
)
from .port_operations import port_operations
from .realtime import manager
from .risk_engine import risk_engine


ingestion_queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue(maxsize=10_000)


RISK_NOTIFICATIONS: list[dict] = [
    {
        "id": "RN-503",
        "vessel_id": "caspian-star",
        "vessel_name": "CASPIAN STAR",
        "previous_score": 84,
        "current_score": 91,
        "level": "critical",
        "reason": "Advanced context: несоответствие груза и осадки, топлива и экономики рейса",
        "created_at": "2026-08-10T17:46:00+05:00",
        "acknowledged": False,
    },
    {
        "id": "RN-502",
        "vessel_id": "caspian-star",
        "vessel_name": "CASPIAN STAR",
        "previous_score": 54,
        "current_score": 84,
        "level": "critical",
        "reason": "HIGH → CRITICAL: изменение осадки и корреляция последовательности событий",
        "created_at": "2026-08-10T17:40:00+05:00",
        "acknowledged": False,
    },
    {
        "id": "RN-501",
        "vessel_id": "caspian-star",
        "vessel_name": "CASPIAN STAR",
        "previous_score": 35,
        "current_score": 54,
        "level": "high",
        "reason": "MODERATE → HIGH: AIS восстановлен после продолжительного разрыва",
        "created_at": "2026-08-10T17:25:00+05:00",
        "acknowledged": False,
    },
]


def _risk_level_index(level: str) -> int:
    return {"low": 0, "moderate": 1, "high": 2, "critical": 3}.get(level, 0)


def _all_detected_events():
    """Expose operational and advanced signals through one event contract."""
    return list(event_engine.events.values()) + advanced_analytics.list_events()


def _hydrate_current_risk() -> None:
    """Keep the vessel current-state contract aligned with Risk Engine output."""
    for vessel in VESSELS:
        try:
            assessment = risk_engine.get_vessel_risk(vessel.id)
        except HTTPException:
            continue
        vessel.risk_score = assessment.risk_score
        vessel.risk_level = assessment.risk_level
        vessel.risk_updated_at = assessment.risk_updated_at


async def _publish_risk_change(previous_score: int, previous_level: str, assessment, reason: str) -> None:
    if assessment.risk_score == previous_score and assessment.risk_level == previous_level:
        return
    payload = {
        "type": "risk_updated",
        "vessel_id": assessment.vessel_id,
        "voyage_id": assessment.voyage_id,
        "previous_score": previous_score,
        "current_score": assessment.risk_score,
        "level": assessment.risk_level,
        "reason": reason,
        "model_version": assessment.model_version,
        "risk_updated_at": assessment.risk_updated_at,
    }
    await manager.broadcast(payload)

    crossed_attention_level = (
        _risk_level_index(previous_level) < _risk_level_index("high")
        <= _risk_level_index(assessment.risk_level)
        or previous_level == "high" and assessment.risk_level == "critical"
    )
    rapid_increase = assessment.risk_score - previous_score >= 20 or assessment.change_1h >= 20
    critical_factor = assessment.risk_score > previous_score and any(
        factor.effective_score >= 20 for factor in assessment.factors
    )
    if not (crossed_attention_level or rapid_increase or critical_factor):
        return
    vessel = next((item for item in VESSELS if item.id == assessment.vessel_id), None)
    notification = {
        "id": f"RN-{500 + len(RISK_NOTIFICATIONS) + 1}",
        "vessel_id": assessment.vessel_id,
        "vessel_name": vessel.name if vessel else assessment.vessel_name,
        "previous_score": previous_score,
        "current_score": assessment.risk_score,
        "level": assessment.risk_level,
        "reason": reason,
        "created_at": assessment.risk_updated_at,
        "acknowledged": False,
    }
    RISK_NOTIFICATIONS.insert(0, notification)
    await manager.broadcast({"type": "risk_notification", "notification": notification})


async def _recalculate_and_publish_risk(vessel_id: str, reason: str) -> None:
    try:
        before = risk_engine.get_vessel_risk(vessel_id)
    except HTTPException:
        return
    previous_score, previous_level = before.risk_score, before.risk_level
    assessment = risk_engine.recalculate(vessel_id, reason=reason)
    _hydrate_current_risk()
    await _publish_risk_change(previous_score, previous_level, assessment, reason)


async def process_messages() -> None:
    while True:
        provider, payload = await ingestion_queue.get()
        try:
            normalized = gateway.normalize(provider, payload)
            position = gateway.persist(normalized)
            await manager.broadcast({
                "type": "position_update",
                "timestamp": normalized.timestamp.isoformat(),
                "vessel": {
                    "id": position.vessel_id, "mmsi": position.mmsi,
                    "lat": position.latitude, "lon": position.longitude,
                    "speed": position.speed, "course": position.course,
                    "heading": position.heading, "status": position.navigation_status,
                    "quality_status": position.quality_status,
                },
            })
            if position.quality_status == "valid":
                vessel = next((item for item in VESSELS if item.id == position.vessel_id), None)
                if vessel:
                    risk_reasons: list[str] = []
                    restored = event_engine.resolve_active_gap(vessel, datetime.fromisoformat(position.recorded_at.replace("Z", "+00:00")))
                    if restored:
                        await manager.broadcast({"type": "event_resolved", "event": restored.model_dump()})
                        risk_reasons.append(f"AIS gap resolved ({restored.id})")
                    vessel.latitude = position.latitude
                    vessel.longitude = position.longitude
                    vessel.speed = position.speed
                    vessel.course = position.course
                    vessel.heading = position.heading or position.course
                    vessel.navigation_status = position.navigation_status
                    vessel.last_position_at = position.recorded_at
                    for detected in event_engine.process_position(position, vessel):
                        await manager.broadcast({"type": "event_created", "event": detected.model_dump()})
                        risk_reasons.append(f"{detected.type} detected ({detected.id})")
                    for detected in event_engine.process_encounters(vessel, VESSELS, datetime.fromisoformat(position.recorded_at.replace("Z", "+00:00"))):
                        await manager.broadcast({"type": "event_created", "event": detected.model_dump()})
                        risk_reasons.append(f"{detected.type} detected ({detected.id})")
                    if risk_reasons:
                        await _recalculate_and_publish_risk(vessel.id, "; ".join(risk_reasons))
        except Exception as exc:
            detail = getattr(exc, "detail", str(exc))
            await manager.broadcast({"type": "data_quality_warning", "source": provider, "detail": detail})
        finally:
            ingestion_queue.task_done()


async def demo_ais_provider() -> None:
    step = 0
    while True:
        await asyncio.sleep(3)
        step += 1
        for index, vessel in enumerate(VESSELS):
            if vessel.navigation_status != "underway":
                continue
            phase = 1 if index % 2 == 0 else -1
            await ingestion_queue.put(("demo-ais", {
                "mmsi": vessel.mmsi,
                "timestamp": datetime.now().astimezone().isoformat(),
                "lat": vessel.latitude + .0012 * phase,
                "lon": vessel.longitude + .0018 * phase,
                "sog": round(max(0, vessel.speed + (step % 3 - 1) * .1), 1),
                "cog": (vessel.course + (step % 3 - 1) * .3) % 360,
                "heading": vessel.heading,
                "navigation_status": vessel.navigation_status,
                "destination": vessel.destination,
                "draught": vessel.draught,
            }))


async def monitor_ais_gaps() -> None:
    while True:
        await asyncio.sleep(10)
        now = datetime.now().astimezone()
        for vessel in VESSELS:
            event = event_engine.start_ais_gap(vessel, now, "unknown")
            if event:
                await manager.broadcast({"type": "event_created", "event": event.model_dump()})
                await _recalculate_and_publish_risk(vessel.id, f"AIS gap detected ({event.id})")


async def monitor_risk_decay() -> None:
    while True:
        await asyncio.sleep(60)
        previous = {
            item.vessel_id: (item.risk_score, item.risk_level)
            for item in risk_engine.list_assessments()
        }
        for assessment in risk_engine.apply_decay():
            score, level = previous.get(assessment.vessel_id, (0, "low"))
            await _publish_risk_change(score, level, assessment, "Risk lifecycle decay")
        _hydrate_current_risk()


@asynccontextmanager
async def lifespan(_: FastAPI):
    _hydrate_current_risk()
    workers = [
        asyncio.create_task(process_messages()),
        asyncio.create_task(demo_ais_provider()),
        asyncio.create_task(monitor_ais_gaps()),
        asyncio.create_task(monitor_risk_decay()),
    ]
    yield
    for worker in workers:
        worker.cancel()
    for worker in workers:
        with suppress(asyncio.CancelledError):
            await worker


app = FastAPI(
    title="Caspian Intelligence API",
    description=(
        "Stages 1–10 regional Caspian maritime intelligence API with tracking, behavior, "
        "event detection, explainable risk, advanced analytics, Smart Port Aktau, a grounded "
        "Investigation Assistant, human-reviewed environmental monitoring and a multi-port network."
    ),
    version="0.10.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEMO_TOKENS = {
    "ci-demo-admin": "ADMIN",
    "ci-demo-analyst": "ANALYST",
    "ci-demo-viewer": "VIEWER",
    "ci-demo-port-dispatcher": "PORT_DISPATCHER",
}


def current_role(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    role = DEMO_TOKENS.get(authorization.removeprefix("Bearer "))
    if not role:
        raise HTTPException(status_code=401, detail="Invalid access token")
    return role


def current_network_principal(role: str = Depends(current_role)) -> NetworkPrincipal:
    """Resolve the authenticated demo user to organization, role and data scope."""
    return network_service.principal_for_role(role)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "dataset": "demo", "platform_version": "0.10.0"}


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    if not payload.email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    role = (
        "ADMIN" if payload.email.startswith("admin")
        else "VIEWER" if payload.email.startswith("viewer")
        else "PORT_DISPATCHER" if payload.email.startswith(("port", "dispatcher"))
        else "ANALYST"
    )
    return TokenResponse(access_token=f"ci-demo-{role.lower().replace('_', '-')}", role=role)


@app.get("/api/v1/users/me")
def me(role: str = Depends(current_role)) -> dict[str, str]:
    return {"id": "usr-demo", "name": "Ayan Kassymov", "email": "analyst@caspian.int", "role": role}


def _assistant_actor(role: str) -> str:
    return {
        "ADMIN": "demo-admin",
        "ANALYST": "demo-analyst",
        "VIEWER": "demo-viewer",
        "PORT_DISPATCHER": "demo-port-dispatcher",
    }[role]


@app.get("/api/v1/vessels", response_model=list[Vessel])
def list_vessels(_: str = Depends(current_role)) -> list[Vessel]:
    _hydrate_current_risk()
    return VESSELS


@app.get("/api/v1/vessels/live", response_model=list[Vessel])
def live_vessels(_: str = Depends(current_role)) -> list[Vessel]:
    _hydrate_current_risk()
    return VESSELS


@app.get("/api/v1/vessels/{vessel_id}", response_model=Vessel)
def get_vessel(vessel_id: str, _: str = Depends(current_role)) -> Vessel:
    vessel = next((item for item in VESSELS if item.id == vessel_id), None)
    if not vessel:
        raise HTTPException(status_code=404, detail="Vessel not found")
    return vessel


@app.get("/api/v1/vessels/{vessel_id}/positions", response_model=list[Position])
def vessel_positions(
    vessel_id: str,
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    limit: int = Query(default=5000, ge=1, le=50_000),
    _: str = Depends(current_role),
) -> list[Position]:
    points = [item for item in POSITIONS if item.vessel_id == vessel_id]
    if from_time:
        points = [item for item in points if item.recorded_at >= from_time]
    if to_time:
        points = [item for item in points if item.recorded_at <= to_time]
    return points[-limit:]


@app.get("/api/v1/vessels/{vessel_id}/track", response_model=TrackResponse)
def vessel_track(
    vessel_id: str,
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    _: str = Depends(current_role),
) -> TrackResponse:
    points = vessel_positions(vessel_id, from_time, to_time, 50_000, _)
    distance = sum(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) for a, b in zip(points, points[1:]))
    return TrackResponse(vessel_id=vessel_id, from_time=from_time, to_time=to_time, point_count=len(points), distance_km=round(distance, 2), positions=points)


@app.get("/api/v1/vessels/{vessel_id}/voyages", response_model=list[Voyage])
def vessel_voyages(vessel_id: str, _: str = Depends(current_role)) -> list[Voyage]:
    return [item for item in VOYAGES if item.vessel_id == vessel_id]


@app.get("/api/v1/vessels/{vessel_id}/behavior")
def vessel_behavior(vessel_id: str, _: str = Depends(current_role)):
    return behavior_engine.get(vessel_id)


@app.get("/api/v1/vessels/{vessel_id}/behavior/routes")
def vessel_behavior_routes(vessel_id: str, _: str = Depends(current_role)):
    return behavior_engine.get(vessel_id).routes


@app.get("/api/v1/vessels/{vessel_id}/behavior/speed")
def vessel_behavior_speed(vessel_id: str, _: str = Depends(current_role)):
    return behavior_engine.get(vessel_id).speed_profiles


@app.get("/api/v1/vessels/{vessel_id}/behavior/ports")
def vessel_behavior_ports(vessel_id: str, _: str = Depends(current_role)):
    return behavior_engine.get(vessel_id).ports


@app.get("/api/v1/vessels/{vessel_id}/behavior/stops")
def vessel_behavior_stops(vessel_id: str, _: str = Depends(current_role)):
    profile = behavior_engine.get(vessel_id)
    return {"total": profile.stops_at_sea, "average_duration_minutes": profile.average_stop_minutes, "areas": profile.stop_areas}


@app.get("/api/v1/vessels/{vessel_id}/behavior/draught")
def vessel_behavior_draught(vessel_id: str, _: str = Depends(current_role)):
    profile = behavior_engine.get(vessel_id)
    return {"typical": profile.draught_typical, "history": profile.draught_history}


@app.get("/api/v1/vessels/{vessel_id}/behavior/activity")
def vessel_behavior_activity(vessel_id: str, _: str = Depends(current_role)):
    profile = behavior_engine.get(vessel_id)
    return {"activity_cells": profile.activity_cells, "departure_pattern": profile.departure_pattern, "voyages_by_day": profile.voyages_by_day}


@app.get("/api/v1/vessels/{vessel_id}/connections")
def vessel_connections(vessel_id: str, _: str = Depends(current_role)):
    try:
        connections = advanced_analytics.get_connections(vessel_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        # Preserve the Stage 3 contract for known vessels that do not yet have
        # enough encounter history for the Stage 6 aggregation model.
        get_vessel(vessel_id, _)
        connections = []
    return {
        "observation_months": max((item.observation_months for item in connections), default=0),
        "connections": connections,
    }


@app.get("/api/v1/vessels/{vessel_id}/network")
def vessel_network(vessel_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_network(vessel_id)


@app.post("/api/v1/vessels/{vessel_id}/behavior/recalculate")
def recalculate_behavior(vessel_id: str, role: str = Depends(current_role)):
    if role not in {"ADMIN", "ANALYST"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return {"status": "recalculated", "profile": behavior_engine.recalculate(vessel_id)}


@app.get("/api/v1/voyages/{voyage_id}", response_model=Voyage)
def get_voyage(voyage_id: str, _: str = Depends(current_role)) -> Voyage:
    voyage = next((item for item in VOYAGES if item.id == voyage_id), None)
    if not voyage:
        raise HTTPException(status_code=404, detail="Voyage not found")
    return voyage


@app.get("/api/v1/voyages/{voyage_id}/cargo")
def voyage_cargo(voyage_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_cargo(voyage_id)


@app.get("/api/v1/voyages/{voyage_id}/fuel")
def voyage_fuel(voyage_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_fuel(voyage_id)


@app.get("/api/v1/voyages/{voyage_id}/economics")
def voyage_economics(voyage_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_economics(voyage_id)


@app.get("/api/v1/voyages/{voyage_id}/intelligence")
def voyage_intelligence(voyage_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_intelligence(voyage_id)


@app.get("/api/v1/companies/{company_id}/vessels")
def company_vessels(company_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_company_vessels(company_id)


@app.get("/api/v1/companies/{company_id}")
def company_intelligence(company_id: str, _: str = Depends(current_role)):
    return advanced_analytics.get_company(company_id)


@app.get("/api/v1/ports", response_model=list[Port])
def list_ports(_: str = Depends(current_role)) -> list[Port]:
    return PORTS


@app.get("/api/v1/ports/{port_id}/vessels", response_model=list[Vessel])
def port_vessels(
    port_id: str,
    radius_km: float = 35,
    principal: NetworkPrincipal = Depends(current_network_principal),
) -> list[Vessel]:
    network_service.require_port_access(principal, port_id)
    port = next((item for item in PORTS if item.id == port_id), None)
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")
    return [vessel for vessel in VESSELS if haversine_km(port.latitude, port.longitude, vessel.latitude, vessel.longitude) <= radius_km]


@app.get("/api/v1/ports/{port_id}/overview")
def port_operations_overview(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    if port_id == "aktau":
        return port_operations.get_overview(port_id)
    return network_service.get_port_overview(port_id, principal)


@app.get("/api/v1/ports/{port_id}/arrivals")
def port_arrivals(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    if port_id == "aktau":
        return port_operations.get_arrivals(port_id)
    return network_service.get_port_arrivals(port_id, principal)


@app.get("/api/v1/ports/{port_id}/high-risk-arrivals")
def port_high_risk_arrivals(
    port_id: str,
    minimum_score: int = Query(default=75, ge=0, le=100),
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    if port_id == "aktau":
        return port_operations.get_high_risk_arrivals(port_id, minimum_score)
    return [item for item in network_service.get_port_arrivals(port_id, principal) if item.risk_score >= minimum_score]


@app.get("/api/v1/ports/{port_id}/berths")
def port_berths(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    if port_id == "aktau":
        return port_operations.get_berths(port_id)
    return network_service.get_port_berths(port_id, principal)


@app.get("/api/v1/ports/{port_id}/berths/{berth_id}/compatibility")
def port_berth_compatibility(
    port_id: str,
    berth_id: str,
    port_call_id: str = Query(default="pc-aktau-143"),
    _: str = Depends(current_role),
):
    port_operations.get_overview(port_id)
    return port_operations.check_berth_compatibility(port_call_id, berth_id)


@app.get("/api/v1/ports/{port_id}/queue")
def port_queue(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    if port_id == "aktau":
        return port_operations.get_queue(port_id)
    return network_service.get_port_queue(port_id, principal)


@app.get("/api/v1/ports/{port_id}/load-forecast")
def port_load_forecast(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    if port_id == "aktau":
        return port_operations.get_load_forecast(port_id)
    return network_service.get_port_forecast(port_id, principal)


@app.get("/api/v1/ports/{port_id}/departures")
def port_departures(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_port_departures(port_id, principal)


@app.get("/api/v1/ports/{port_id}/forecast")
def regional_port_forecast(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    """Stage 10 generic forecast alias; Stage 7 load-forecast remains compatible."""
    return network_service.get_port_forecast(port_id, principal)


@app.get("/api/v1/ports/{port_id}/configuration")
def regional_port_configuration(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_port_configuration(port_id, principal)


@app.get("/api/v1/ports/{port_id}/integration-status")
def regional_port_integration(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_port_integration(port_id, principal)


@app.get("/api/v1/ports/{port_id}/intelligence")
def regional_port_intelligence(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_port_intelligence(port_id, principal)


@app.get("/api/v1/ports/{port_id}/recommendations")
def port_recommendations(port_id: str, _: str = Depends(current_role)):
    return port_operations.get_recommendations(port_id)


@app.get("/api/v1/ports/{port_id}/weather")
def port_weather(port_id: str, _: str = Depends(current_role)):
    return port_operations.get_weather(port_id)


@app.post("/api/v1/ports/{port_id}/weather/recalculate")
async def port_weather_recalculation(
    port_id: str,
    berth_id: str = Query(default="berth-5"),
    wind_mps: float = Query(default=22, ge=0, le=80),
    role: str = Depends(current_role),
):
    if role not in {"ADMIN", "ANALYST", "PORT_DISPATCHER"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = port_operations.recalculate_for_weather(port_id, berth_id=berth_id, wind_mps=wind_mps)
    await manager.broadcast({"type": "port_weather_recalculated", "port_id": port_id, "result": result.model_dump()})
    return result


@app.get("/api/v1/ports/{port_id}/events")
def port_operational_events(port_id: str, _: str = Depends(current_role)):
    return port_operations.list_events(port_id=port_id)


@app.get("/api/v1/port-calls/{port_call_id}")
def port_call(port_call_id: str, _: str = Depends(current_role)):
    return port_operations.get_port_call(port_call_id)


@app.get("/api/v1/port-calls/{port_call_id}/pre-arrival")
def port_call_pre_arrival(port_call_id: str, _: str = Depends(current_role)):
    return port_operations.get_pre_arrival(port_call_id)


@app.get("/api/v1/port-calls/{port_call_id}/berth-recommendation")
def port_call_berth_recommendation(port_call_id: str, _: str = Depends(current_role)):
    return port_operations.get_berth_recommendation(port_call_id)


@app.get("/api/v1/port-calls/{port_call_id}/events")
def port_call_events(port_call_id: str, _: str = Depends(current_role)):
    return port_operations.list_events(port_call_id=port_call_id)


@app.get("/api/v1/port-calls/{port_call_id}/feedback")
def port_call_feedback(port_call_id: str, _: str = Depends(current_role)):
    return port_operations.get_feedback(port_call_id)


@app.post("/api/v1/port-calls/{port_call_id}/actuals")
async def record_port_call_actuals(
    port_call_id: str,
    payload: PortActualsInput,
    role: str = Depends(current_role),
):
    if role not in {"ADMIN", "ANALYST", "PORT_DISPATCHER"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    feedback = port_operations.record_actuals(port_call_id, payload)
    cargo = advanced_analytics.apply_port_feedback(
        feedback.voyage_id,
        verified_cargo_t=feedback.verified_cargo.value or 0,
        verified_draught_m=feedback.verified_draught.value or 0,
        observed_at=feedback.recorded_at,
        source=feedback.verified_cargo.source,
    )
    await manager.broadcast({
        "type": "port_feedback_recorded",
        "port_call_id": port_call_id,
        "vessel_id": feedback.vessel_id,
        "feedback": feedback.model_dump(),
    })
    return {"feedback": feedback, "cargo_intelligence": cargo}


@app.get("/api/v1/vessels/{vessel_id}/eta")
def vessel_eta(vessel_id: str, _: str = Depends(current_role)):
    return port_operations.get_eta(vessel_id)


@app.post("/api/v1/berth-assignments")
async def decide_berth_assignment(
    payload: BerthAssignmentDecisionRequest,
    role: str = Depends(current_role),
):
    if role not in {"ADMIN", "ANALYST", "PORT_DISPATCHER"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    decision = port_operations.decide_berth(payload)
    await manager.broadcast({
        "type": "berth_assignment_updated",
        "port_call_id": decision.port_call_id,
        "decision": decision.model_dump(),
    })
    return decision


@app.post("/api/v1/simulations")
async def run_port_simulation(
    payload: PortSimulationRequest,
    role: str = Depends(current_role),
):
    if role not in {"ADMIN", "ANALYST", "PORT_DISPATCHER"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = port_operations.run_simulation(payload)
    await manager.broadcast({"type": "port_simulation_completed", "simulation": result.model_dump()})
    return result


@app.get("/api/v1/map/vessels")
def map_vessels(_: str = Depends(current_role)) -> dict[str, list[MapVessel]]:
    _hydrate_current_risk()
    return {"vessels": [MapVessel(
        id=v.id, name=v.name, lat=v.latitude, lon=v.longitude, speed=v.speed,
        course=v.course, status=v.navigation_status, risk_score=v.risk_score,
        risk_level=v.risk_level, risk_updated_at=v.risk_updated_at,
    ) for v in VESSELS]}


@app.post("/api/v1/ais/ingest", status_code=202)
async def ingest_ais(request: AISIngestRequest, role: str = Depends(current_role)) -> dict[str, str | int]:
    if role not in {"ADMIN", "ANALYST"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    await ingestion_queue.put((request.provider, request.payload))
    return {"status": "accepted", "queue_depth": ingestion_queue.qsize()}


@app.get("/api/v1/data-quality")
def data_quality(_: str = Depends(current_role)) -> dict[str, int]:
    suspicious = sum(item.quality_status == "suspicious" for item in POSITIONS)
    cargo = advanced_analytics.get_cargo("voy-001")
    fuel = advanced_analytics.get_fuel("voy-001")
    economics = advanced_analytics.get_economics("voy-001")
    provenance = [
        *cargo.source_quality,
        fuel.weather_correction,
        fuel.reported,
        fuel.estimated,
        fuel.verified,
        economics.cargo_value,
    ]
    source_counts = {
        status: sum(item.verification_status == status for item in provenance)
        for status in ("reported", "estimated", "verified", "not_available")
    }
    return {
        "raw_messages": len(gateway.raw_messages),
        "normalized_positions": len(POSITIONS),
        "suspicious": suspicious,
        "queue_depth": ingestion_queue.qsize(),
        "advanced_source_records": len(provenance),
        "advanced_reported": source_counts["reported"],
        "advanced_estimated": source_counts["estimated"],
        "advanced_verified": source_counts["verified"],
        "advanced_not_available": source_counts["not_available"],
    }


@app.get("/api/v1/risk/vessels")
def risk_vessels(
    level: list[str] | None = Query(default=None),
    _: str = Depends(current_role),
):
    allowed = {"low", "moderate", "high", "critical"}
    normalized = [item.lower() for item in level] if level else None
    invalid = sorted(set(normalized or []) - allowed)
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown risk level: {', '.join(invalid)}")
    return risk_engine.list_assessments(normalized)


@app.get("/api/v1/risk/high-priority")
def high_priority_risk(
    limit: int = Query(default=10, ge=1, le=100),
    minimum_score: int = Query(default=50, ge=0, le=100),
    _: str = Depends(current_role),
):
    return risk_engine.high_priority(limit=limit, minimum_score=minimum_score)


@app.get("/api/v1/risk/notifications")
def risk_notifications(
    unacknowledged_only: bool = True,
    limit: int = Query(default=50, ge=1, le=500),
    _: str = Depends(current_role),
):
    items = [item for item in RISK_NOTIFICATIONS if not unacknowledged_only or not item["acknowledged"]]
    return {"total": len(items), "notifications": items[:limit]}


@app.get("/api/v1/risk/rules")
def risk_rules(_: str = Depends(current_role)):
    return risk_engine.get_configuration()


@app.get("/api/v1/vessels/{vessel_id}/risk")
def vessel_risk(vessel_id: str, _: str = Depends(current_role)):
    return risk_engine.get_vessel_risk(vessel_id)


@app.get("/api/v1/vessels/{vessel_id}/risk/history")
def vessel_risk_history(vessel_id: str, _: str = Depends(current_role)):
    return risk_engine.get_history(vessel_id)


@app.get("/api/v1/vessels/{vessel_id}/risk/voyages")
def vessel_voyage_risk_history(
    vessel_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    _: str = Depends(current_role),
):
    return risk_engine.voyage_history(vessel_id, limit=limit)


@app.get("/api/v1/voyages/{voyage_id}/risk")
def voyage_risk(voyage_id: str, _: str = Depends(current_role)):
    return risk_engine.get_voyage_risk(voyage_id)


@app.get("/api/v1/voyages/{voyage_id}/risk/factors")
def voyage_risk_factors(voyage_id: str, _: str = Depends(current_role)):
    return risk_engine.get_voyage_factors(voyage_id)


@app.patch("/api/v1/risk/factors/{factor_id}/review")
async def review_risk_factor(
    factor_id: str,
    update: RiskFactorReviewRequest,
    role: str = Depends(current_role),
):
    if role not in {"ADMIN", "ANALYST"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    owner = next(
        (
            assessment
            for assessment in risk_engine.list_assessments()
            if any(factor.id == factor_id for factor in assessment.factors)
        ),
        None,
    )
    if owner is None:
        raise HTTPException(status_code=404, detail="Risk factor not found")
    previous_score, previous_level = owner.risk_score, owner.risk_level
    factor = risk_engine.review_factor(factor_id, update, reviewer=update.reviewed_by or "demo-analyst")
    assessment = risk_engine.get_vessel_risk(owner.vessel_id)
    _hydrate_current_risk()
    await _publish_risk_change(
        previous_score,
        previous_level,
        assessment,
        f"Analyst review: {update.status} ({factor_id})",
    )
    return {"factor": factor, "assessment": assessment}


@app.get("/api/v1/events")
def list_events(
    event_type: str | None = Query(default=None, alias="type"),
    severity: str | None = None,
    status: str | None = None,
    vessel_id: str | None = None,
    from_time: str | None = Query(default=None, alias="from"),
    to_time: str | None = Query(default=None, alias="to"),
    _: str = Depends(current_role),
):
    items = _all_detected_events()
    if event_type:
        items = [item for item in items if item.type == event_type]
    if severity:
        items = [item for item in items if item.severity == severity]
    if status:
        items = [item for item in items if item.status == status]
    if vessel_id:
        items = [item for item in items if item.vessel_id == vessel_id]
    if from_time:
        items = [item for item in items if item.started_at >= from_time]
    if to_time:
        items = [item for item in items if item.started_at <= to_time]
    return {"total": len(items), "events": sorted(items, key=lambda item: item.started_at, reverse=True)}


@app.get("/api/v1/events/{event_id}")
def get_event(event_id: str, _: str = Depends(current_role)):
    event = event_engine.events.get(event_id)
    return event if event is not None else advanced_analytics.get_event(event_id)


@app.patch("/api/v1/events/{event_id}/status")
async def update_event_status(event_id: str, update: EventStatusUpdate, role: str = Depends(current_role)):
    if role not in {"ADMIN", "ANALYST"}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if event_id in event_engine.events:
        event = event_engine.update_status(event_id, update, "demo-analyst")
    else:
        event = advanced_analytics.update_event_status(event_id, update, "demo-analyst")
    await manager.broadcast({"type": "event_updated", "event": event.model_dump()})
    await _recalculate_and_publish_risk(event.vessel_id, f"Event {event.id} marked {event.status}")
    return event


@app.get("/api/v1/vessels/{vessel_id}/events")
def vessel_events(vessel_id: str, _: str = Depends(current_role)):
    return [item for item in _all_detected_events() if item.vessel_id == vessel_id or item.related_vessel_id == vessel_id]


@app.get("/api/v1/voyages/{voyage_id}/events")
def voyage_events(voyage_id: str, _: str = Depends(current_role)):
    return [item for item in _all_detected_events() if item.voyage_id == voyage_id]


@app.get("/api/v1/encounters")
def encounters(_: str = Depends(current_role)):
    return [item for item in _all_detected_events() if item.type == "vessel_encounter"]


@app.get("/api/v1/event-groups")
def event_groups(_: str = Depends(current_role)):
    return sorted(event_engine.groups.values(), key=lambda group: group.started_at, reverse=True)


@app.get("/api/v1/event-groups/{group_id}")
def event_group(group_id: str, _: str = Depends(current_role)):
    group = event_engine.groups.get(group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Event group not found")
    return {"group": group, "events": [event_engine.events[event_id] for event_id in group.event_ids]}


@app.post("/api/v1/spatial-search")
def spatial_search(request: SpatialSearchRequest, _: str = Depends(current_role)) -> dict:
    matches = [
        item for item in POSITIONS
        if request.west <= item.longitude <= request.east
        and request.south <= item.latitude <= request.north
        and (not request.from_time or item.recorded_at >= request.from_time)
        and (not request.to_time or item.recorded_at <= request.to_time)
    ]
    vessel_ids = sorted({item.vessel_id for item in matches})
    return {"vessel_count": len(vessel_ids), "position_count": len(matches), "vessel_ids": vessel_ids}


@app.get("/api/v1/search")
def search(q: str = Query(min_length=2), _: str = Depends(current_role)) -> dict[str, list[dict[str, str]]]:
    query = q.casefold()
    vessel_hits = [{"id": v.id, "type": "vessel", "name": v.name, "subtitle": f"IMO {v.imo} · {v.destination}"} for v in VESSELS if query in v.name.casefold() or query in v.imo or query in v.mmsi]
    port_hits = [{"id": p.id, "type": "port", "name": p.name, "subtitle": p.country} for p in PORTS if query in p.name.casefold()]
    return {"results": vessel_hits + port_hits}


# Stage 10: Caspian Network / regional multi-port platform

@app.get("/api/v1/network/overview")
def network_overview(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.overview(principal)


@app.get("/api/v1/network/map")
def network_map(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.regional_map(principal)


@app.get("/api/v1/network/risk")
def network_risk(
    country: str | None = None,
    port_id: str | None = None,
    route_id: str | None = None,
    vessel_type: str | None = None,
    minimum_score: int = Query(default=0, ge=0, le=100),
    event_type: str | None = None,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.list_risk(
        principal, country=country, port_id=port_id, route_id=route_id,
        vessel_type=vessel_type, minimum_score=minimum_score, event_type=event_type,
    )


@app.get("/api/v1/network/routes")
def network_routes(principal: NetworkPrincipal = Depends(current_network_principal)):
    return {"items": network_service.list_routes(principal)}


@app.get("/api/v1/network/routes/{route_id}")
def network_route(route_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_route(route_id, principal)


@app.get("/api/v1/network/ports")
def network_ports(principal: NetworkPrincipal = Depends(current_network_principal)):
    return {"items": network_service.list_ports(principal)}


@app.get("/api/v1/network/ports/compare")
def network_compare_ports(
    port_id: list[str] = Query(default=["aktau", "baku", "turkmenbashi"]),
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.compare_ports(port_id, principal)


@app.get("/api/v1/network/ports/{port_id}")
def network_port(port_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_port(port_id, principal)


@app.get("/api/v1/network/vessels/{vessel_id}/identity")
def network_vessel_identity(vessel_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_vessel_identity(vessel_id, principal)


@app.get("/api/v1/network/vessels/{vessel_id}/identity/history")
def network_vessel_identity_history(vessel_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_vessel_identity_history(vessel_id, principal)


@app.get("/api/v1/network/vessels/{vessel_id}/voyages")
def network_vessel_voyages(vessel_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_vessel_voyages(vessel_id, principal)


@app.post("/api/v1/network/identity/vessels/resolve")
def network_resolve_vessel(
    request: VesselIdentityResolutionRequest,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.resolve_vessel_identity(request, principal)


@app.get("/api/v1/network/companies/{company_id}")
def network_company(company_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_company(company_id, principal)


@app.post("/api/v1/network/identity/companies/resolve")
def network_resolve_company(
    request: CompanyIdentityResolutionRequest,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.resolve_company_identity(request, principal)


@app.get("/api/v1/network/voyages/{voyage_id}/cross-port")
def network_cross_port(voyage_id: str, principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_cross_port_report(voyage_id, principal)


@app.get("/api/v1/network/graph")
def network_graph(
    vessel_id: str | None = None,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.graph(principal, vessel_id=vessel_id)


@app.get("/api/v1/network/search")
def network_search(
    q: str = Query(min_length=1),
    entity_type: list[str] | None = Query(default=None),
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return network_service.search(q, principal, entity_types=entity_type)


@app.get("/api/v1/network/data-sources")
def network_data_sources(principal: NetworkPrincipal = Depends(current_network_principal)):
    return {"items": network_service.list_sources(principal)}


@app.get("/api/v1/network/provenance/{entity_type}/{entity_id}")
def network_provenance(
    entity_type: str,
    entity_id: str,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return {"items": network_service.list_provenance(entity_type, entity_id, principal)}


@app.get("/api/v1/network/conflicts")
def network_conflicts(
    status: str | None = None,
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return {"items": network_service.list_conflicts(principal, status=status)}


@app.get("/api/v1/network/data-health")
def network_data_health(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.data_health(principal)


@app.get("/api/v1/network/coverage")
def network_coverage(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.coverage(principal)


@app.get("/api/v1/network/adapters")
def network_adapters(principal: NetworkPrincipal = Depends(current_network_principal)):
    return {"items": network_service.list_adapters(principal)}


@app.get("/api/v1/network/observability")
def network_observability(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.observability(principal)


@app.get("/api/v1/network/audit")
def network_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    principal: NetworkPrincipal = Depends(current_network_principal),
):
    return {"items": network_service.list_audit(principal, limit=limit)}


@app.get("/api/v1/network/access/me")
def network_access(principal: NetworkPrincipal = Depends(current_network_principal)):
    return network_service.get_access(principal)


# Stage 9: Environmental Intelligence

def _require_environment_intelligence(role: str) -> None:
    if role not in {"ADMIN", "ANALYST"}:
        raise HTTPException(status_code=403, detail="Environmental intelligence access denied")


@app.get("/api/v1/environment/events", response_model=EnvironmentalEventList)
def environmental_events(
    status: str | None = None,
    _: str = Depends(current_role),
) -> EnvironmentalEventList:
    normalized = status.upper().replace("_", " ") if status else None
    return environmental_service.list_events(status=normalized)


@app.post("/api/v1/environment/events", response_model=EnvironmentalEvent, status_code=201)
async def create_environmental_event(
    request: EnvironmentalRawIngestRequest,
    role: str = Depends(current_role),
) -> EnvironmentalEvent:
    _require_environment_intelligence(role)
    event = environmental_service.create_event(request, created_by=_assistant_actor(role))
    await manager.broadcast({"type": "environmental_event_detected", "event": event.model_dump(mode="json")})
    return event


@app.get("/api/v1/environment/events/{event_id}", response_model=EnvironmentalEvent)
def environmental_event(event_id: str, _: str = Depends(current_role)) -> EnvironmentalEvent:
    return environmental_service.get_event(event_id)


@app.get("/api/v1/environment/events/{event_id}/candidates")
def environmental_candidates(
    event_id: str,
    include_extended: bool = False,
    role: str = Depends(current_role),
):
    _require_environment_intelligence(role)
    return environmental_service.get_candidates(event_id, include_extended=include_extended)


@app.get("/api/v1/environment/events/{event_id}/reconstruction")
def environmental_reconstruction(event_id: str, role: str = Depends(current_role)):
    _require_environment_intelligence(role)
    return environmental_service.get_reconstruction(event_id)


@app.get("/api/v1/environment/events/{event_id}/timeline")
def environmental_timeline(event_id: str, role: str = Depends(current_role)):
    _require_environment_intelligence(role)
    return environmental_service.get_timeline(event_id)


@app.get("/api/v1/environment/events/{event_id}/replay")
def environmental_replay(event_id: str, role: str = Depends(current_role)):
    _require_environment_intelligence(role)
    return environmental_service.get_replay(event_id)


@app.get("/api/v1/environment/events/{event_id}/raw", response_model=EnvironmentalRawData)
def environmental_raw(event_id: str, role: str = Depends(current_role)) -> EnvironmentalRawData:
    _require_environment_intelligence(role)
    return environmental_service.get_raw_for_event(event_id)


@app.get("/api/v1/environment/events/{event_id}/risk-context/{vessel_id}")
def environmental_risk_context(
    event_id: str,
    vessel_id: str,
    role: str = Depends(current_role),
):
    _require_environment_intelligence(role)
    context = environmental_service.get_risk_context(event_id, vessel_id)
    maritime = risk_engine.get_vessel_risk(vessel_id)
    return context.model_copy(update={
        "maritime_risk_score": maritime.risk_score,
        "combined_context_score": min(100, maritime.risk_score + context.environmental_adjustment_raw),
    })


@app.get("/api/v1/vessels/{vessel_id}/environment")
def vessel_environment(vessel_id: str, role: str = Depends(current_role)):
    _require_environment_intelligence(role)
    return environmental_service.get_vessel_environment(vessel_id)


@app.get("/api/v1/environment/events/{event_id}/reviews")
def environmental_reviews(event_id: str, role: str = Depends(current_role)):
    _require_environment_intelligence(role)
    return environmental_service.list_reviews(event_id)


@app.post("/api/v1/environment/events/{event_id}/review", response_model=EnvironmentalReviewResult)
async def review_environmental_event(
    event_id: str,
    request: EnvironmentalReviewRequest,
    role: str = Depends(current_role),
) -> EnvironmentalReviewResult:
    _require_environment_intelligence(role)
    result = environmental_service.review_event(
        event_id, request, reviewer=_assistant_actor(role),
    )
    await manager.broadcast({
        "type": "environmental_event_updated",
        "event": result.event.model_dump(mode="json"),
        "review": result.review.model_dump(mode="json"),
    })
    return result


@app.post("/api/v1/environment/events/{event_id}/investigation", response_model=Investigation)
async def create_environmental_investigation(
    event_id: str,
    request: EnvironmentalInvestigationRequest,
    role: str = Depends(current_role),
) -> Investigation:
    _require_environment_intelligence(role)
    case = assistant_service.create_environmental_investigation(
        event_id,
        confirmed=request.confirmed,
        user_id=_assistant_actor(role),
        role=role,
        assigned_to=request.assigned_to,
    )
    event = environmental_service.get_event(event_id)
    await manager.broadcast({
        "type": "environmental_event_updated",
        "event": event.model_dump(mode="json"),
        "investigation_id": case.id,
    })
    return case


# Stage 8: Grounded Assistant & Investigation

@app.get("/api/v1/assistant/tools")
def assistant_tools(role: str = Depends(current_role)):
    """Return the RBAC-filtered read/write tool catalogue."""
    return {"tools": assistant_service.list_tools(role)}


@app.post("/api/v1/assistant/chat", response_model=AssistantChatResponse)
def assistant_chat(
    request: AssistantChatRequest,
    role: str = Depends(current_role),
) -> AssistantChatResponse:
    return assistant_service.chat(request, user_id=_assistant_actor(role), role=role)


@app.get("/api/v1/assistant/conversations", response_model=list[AssistantConversation])
def assistant_conversations(role: str = Depends(current_role)) -> list[AssistantConversation]:
    return assistant_service.list_conversations(user_id=_assistant_actor(role), role=role)


@app.get("/api/v1/assistant/conversations/{conversation_id}", response_model=AssistantConversation)
def assistant_conversation(conversation_id: str, role: str = Depends(current_role)) -> AssistantConversation:
    return assistant_service.get_conversation(conversation_id, user_id=_assistant_actor(role), role=role)


@app.get("/api/v1/assistant/audit", response_model=list[AssistantAuditEntry])
def assistant_audit(
    limit: int = Query(default=100, ge=1, le=1000),
    role: str = Depends(current_role),
) -> list[AssistantAuditEntry]:
    return assistant_service.list_audit(role=role, limit=limit)


@app.get("/api/v1/investigations", response_model=list[Investigation])
def investigations(role: str = Depends(current_role)) -> list[Investigation]:
    return assistant_service.list_investigations(role=role)


@app.post("/api/v1/investigations", response_model=Investigation)
def create_investigation(
    request: InvestigationCreateRequest,
    role: str = Depends(current_role),
) -> Investigation:
    return assistant_service.create_investigation(request, user_id=_assistant_actor(role), role=role)


@app.get("/api/v1/investigations/{investigation_id}", response_model=Investigation)
def investigation(investigation_id: str, role: str = Depends(current_role)) -> Investigation:
    return assistant_service.get_investigation(investigation_id, role=role)


@app.patch("/api/v1/investigations/{investigation_id}", response_model=Investigation)
def update_investigation(
    investigation_id: str,
    request: InvestigationUpdateRequest,
    role: str = Depends(current_role),
) -> Investigation:
    return assistant_service.update_investigation(
        investigation_id, request, user_id=_assistant_actor(role), role=role,
    )


@app.post("/api/v1/investigations/{investigation_id}/evidence", response_model=Investigation)
def add_investigation_evidence(
    investigation_id: str,
    request: InvestigationEvidenceRequest,
    role: str = Depends(current_role),
) -> Investigation:
    return assistant_service.add_evidence(
        investigation_id, request, user_id=_assistant_actor(role), role=role,
    )


@app.post("/api/v1/investigations/{investigation_id}/notes", response_model=Investigation)
def add_investigation_note(
    investigation_id: str,
    request: InvestigationNoteRequest,
    role: str = Depends(current_role),
) -> Investigation:
    return assistant_service.add_note(
        investigation_id, request, user_id=_assistant_actor(role), role=role,
    )


@app.post("/api/v1/investigations/{investigation_id}/summarize", response_model=AssistantChatResponse)
def summarize_investigation(
    investigation_id: str,
    role: str = Depends(current_role),
) -> AssistantChatResponse:
    return assistant_service.summarize_investigation(
        investigation_id, user_id=_assistant_actor(role), role=role,
    )


@app.post("/api/v1/assistant/actions/{action_id}/confirm")
def confirm_assistant_action(
    action_id: str,
    request: AssistantActionDecisionRequest,
    role: str = Depends(current_role),
):
    if not request.confirmed:
        raise HTTPException(status_code=400, detail="The confirm endpoint requires confirmed=true")
    return assistant_service.decide_action(
        action_id,
        confirmed=True,
        user_id=_assistant_actor(role),
        role=role,
        note=request.note,
    )


@app.post("/api/v1/assistant/actions/{action_id}/reject")
def reject_assistant_action(
    action_id: str,
    request: AssistantActionDecisionRequest,
    role: str = Depends(current_role),
):
    if request.confirmed:
        raise HTTPException(status_code=400, detail="The reject endpoint requires confirmed=false")
    return assistant_service.decide_action(
        action_id,
        confirmed=False,
        user_id=_assistant_actor(role),
        role=role,
        note=request.note,
    )


@app.websocket("/ws/vessels")
async def vessel_updates(websocket: WebSocket, token: str = Query(default="")) -> None:
    if token not in DEMO_TOKENS:
        await websocket.close(code=1008, reason="Invalid token")
        return
    await manager.connect(websocket)
    await websocket.send_json({"type": "connected", "channel": "vessels", "vessel_count": len(VESSELS)})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/ports/{port_id}")
async def port_updates(websocket: WebSocket, port_id: str, token: str = Query(default="")) -> None:
    if token not in DEMO_TOKENS:
        await websocket.close(code=1008, reason="Invalid token")
        return
    try:
        overview = port_operations.get_overview(port_id)
    except HTTPException:
        await websocket.close(code=1008, reason="Unknown port")
        return
    await manager.connect(websocket)
    await websocket.send_json({
        "type": "connected",
        "channel": f"port:{port_id}",
        "port_load_percent": overview.port_load_percent,
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/environment")
async def environmental_updates(websocket: WebSocket, token: str = Query(default="")) -> None:
    if token not in DEMO_TOKENS:
        await websocket.close(code=1008, reason="Invalid token")
        return
    if DEMO_TOKENS[token] not in {"ADMIN", "ANALYST"}:
        await websocket.close(code=1008, reason="Environmental intelligence access denied")
        return
    await manager.connect(websocket)
    summary = environmental_service.list_events()
    await websocket.send_json({
        "type": "connected",
        "channel": "environment",
        "active_count": summary.active_count,
        "high_priority_count": summary.high_priority_count,
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.websocket("/ws/network")
async def regional_network_updates(websocket: WebSocket, token: str = Query(default="")) -> None:
    if token not in DEMO_TOKENS:
        await websocket.close(code=1008, reason="Invalid token")
        return
    role = DEMO_TOKENS[token]
    principal = network_service.principal_for_role(role)
    await manager.connect(websocket)
    overview = network_service.overview(principal)
    await websocket.send_json({
        "type": "connected",
        "channel": "network",
        "region": overview["region"],
        "metrics": overview["metrics"],
        "model_version": overview["model_version"],
        "data_scope": principal.data_scope,
    })
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
