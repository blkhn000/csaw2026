from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException

from .models import (
    ActualVsPredictedMetric,
    ArrivalBoardEntry,
    Berth,
    BerthAssignmentDecision,
    BerthAssignmentDecisionRequest,
    BerthAssignmentRecommendation,
    BerthCompatibility,
    BerthCompatibilityCheck,
    ETAPrediction,
    ETAPredictionFactor,
    PortActualsInput,
    PortBottleneck,
    PortCall,
    PortFeedbackRecord,
    PortLoadForecast,
    PortLoadForecastPoint,
    PortOperationalEvent,
    PortOperationalRecommendation,
    PortOperationsOverview,
    PortQueueItem,
    PortQueueSnapshot,
    PortSimulationRequest,
    PortSimulationResult,
    PortTimelineEntry,
    PortWeather,
    PreArrivalReport,
    QuantityObservation,
    ServiceTimePrediction,
    SourceMetadata,
    WeatherRecalculationResult,
    WeatherRestriction,
)


PORT_MODEL_VERSION = "CI-PORT-1.0"
ETA_MODEL_VERSION = "CI-ETA-1.0"
SERVICE_MODEL_VERSION = "CI-SERVICE-1.0"
PORT_DISCLAIMER = (
    "Smart Port calculations are operational decision support. Berth assignments, queue changes, "
    "restrictions and service actions require an authorized dispatcher decision."
)
SIMULATION_DISCLAIMER = (
    "A WHAT IF result is an isolated planning scenario. It does not change the operational schedule "
    "or issue instructions to port personnel."
)


def _parse(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result


def _minutes(start: str, end: str) -> int:
    return round((_parse(end) - _parse(start)).total_seconds() / 60)


def _source(
    source: str,
    timestamp: str,
    confidence: float,
    verification_status: str = "estimated",
) -> SourceMetadata:
    return SourceMetadata(
        source=source,
        source_timestamp=timestamp,
        confidence=confidence,
        verification_status=verification_status,
    )


class PortOperationsService:
    """Explainable in-memory prototype for Stage 7 Port Aktau operations."""

    model_version = PORT_MODEL_VERSION
    port_id = "aktau"

    def __init__(self) -> None:
        self._generated_at = "2026-08-10T14:10:00+05:00"
        self._berths: dict[str, Berth] = {}
        self._arrivals: list[ArrivalBoardEntry] = []
        self._port_calls: dict[str, PortCall] = {}
        self._eta: dict[str, ETAPrediction] = {}
        self._recommendations: dict[str, BerthAssignmentRecommendation] = {}
        self._decisions: list[BerthAssignmentDecision] = []
        self._events: dict[str, PortOperationalEvent] = {}
        self._feedback: dict[str, PortFeedbackRecord] = {}
        self._simulations: dict[str, PortSimulationResult] = {}
        self._seed_demo()

    def get_overview(self, port_id: str = "aktau") -> PortOperationsOverview:
        self._require_port(port_id)
        return self._overview.model_copy(deep=True)

    def get_arrivals(self, port_id: str = "aktau") -> list[ArrivalBoardEntry]:
        self._require_port(port_id)
        return [item.model_copy(deep=True) for item in self._arrivals]

    def get_high_risk_arrivals(
        self,
        port_id: str = "aktau",
        minimum_score: int = 75,
    ) -> list[ArrivalBoardEntry]:
        self._require_port(port_id)
        return [
            item.model_copy(deep=True)
            for item in self._arrivals
            if item.risk_score >= minimum_score
        ]

    def get_berths(self, port_id: str = "aktau") -> list[Berth]:
        self._require_port(port_id)
        return [item.model_copy(deep=True) for item in self._berths.values()]

    def get_queue(self, port_id: str = "aktau") -> PortQueueSnapshot:
        self._require_port(port_id)
        return self._queue.model_copy(deep=True)

    def get_load_forecast(self, port_id: str = "aktau") -> PortLoadForecast:
        self._require_port(port_id)
        return self._forecast.model_copy(deep=True)

    def get_recommendations(self, port_id: str = "aktau") -> list[PortOperationalRecommendation]:
        self._require_port(port_id)
        return [item.model_copy(deep=True) for item in self._forecast.recommendations]

    def get_weather(self, port_id: str = "aktau") -> PortWeather:
        self._require_port(port_id)
        return self._weather.model_copy(deep=True)

    def get_port_call(self, port_call_id: str) -> PortCall:
        item = self._port_calls.get(port_call_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Port call not found")
        return item.model_copy(deep=True)

    def get_eta(self, vessel_id: str) -> ETAPrediction:
        item = self._eta.get(vessel_id)
        if item is None:
            raise HTTPException(status_code=404, detail="ETA prediction not found")
        return item.model_copy(deep=True)

    def get_pre_arrival(self, port_call_id: str) -> PreArrivalReport:
        call = self.get_port_call(port_call_id)
        recommendation = self.get_berth_recommendation(port_call_id)
        eta = self.get_eta(call.vessel_id)
        significant_events = [
            "Route deviation: 38 km",
            "AIS gap: 3 h 15 min",
            "Offshore encounter with TURAN",
            "Cargo / draught mismatch",
            "Fuel consumption anomaly",
            "Voyage economics outside historical range",
            "Repeated vessel connection context",
        ]
        return PreArrivalReport(
            id=f"PAR-{port_call_id}",
            port_call_id=port_call_id,
            vessel_id=call.vessel_id,
            vessel_name=call.vessel_name,
            eta=eta,
            berth_recommendation=recommendation,
            cargo_summary=f"{call.reported_cargo_t:,.0f} t {call.cargo_type.lower()} (reported)",
            service_prediction=recommendation.service_prediction,
            risk_score=call.risk_score,
            risk_level=call.risk_level,
            attention_level="high" if call.risk_score >= 75 else "elevated" if call.risk_score >= 50 else "normal",
            significant_event_count=call.significant_event_count,
            significant_events=significant_events[: call.significant_event_count],
            recommended_actions=[
                "Prepare berth #5, subject to dispatcher acceptance",
                "Verify cargo documents against the declaration",
                "Verify arrival draught with a port observation",
                "Review the current voyage events before service",
            ],
            generated_at=self._generated_at,
            disclaimer=(
                "Pre-arrival attention is based on explainable risk and operational facts. "
                "It does not establish a violation and does not authorize enforcement action."
            ),
        )

    def get_berth_recommendation(self, port_call_id: str) -> BerthAssignmentRecommendation:
        item = next(
            (value for value in self._recommendations.values() if value.port_call_id == port_call_id),
            None,
        )
        if item is None:
            raise HTTPException(status_code=404, detail="Berth recommendation not found")
        return item.model_copy(deep=True)

    def check_berth_compatibility(self, port_call_id: str, berth_id: str) -> BerthCompatibility:
        call = self.get_port_call(port_call_id)
        berth = self._berths.get(berth_id)
        if berth is None:
            raise HTTPException(status_code=404, detail="Berth not found")
        vessel_length = 142.0 if call.vessel_id == "caspian-star" else 135.0
        planning_draught = 5.0 if call.vessel_id == "caspian-star" else call.reported_draught_m
        checks = [
            BerthCompatibilityCheck(
                parameter="length",
                required=f"{vessel_length:g} m",
                capability=f"maximum {berth.max_vessel_length_m:g} m",
                compatible=vessel_length <= berth.max_vessel_length_m,
                explanation="Vessel length is checked against the berth operating limit.",
            ),
            BerthCompatibilityCheck(
                parameter="draught",
                required=f"{planning_draught:g} m conservative planning draught",
                capability=f"maximum {berth.max_draught_m:g} m",
                compatible=planning_draught <= berth.max_draught_m,
                explanation="The conservative arrival draught is used until the port observation is verified.",
            ),
            BerthCompatibilityCheck(
                parameter="cargo",
                required=call.cargo_type,
                capability=" / ".join(berth.cargo_types),
                compatible=call.cargo_type.casefold() in {item.casefold() for item in berth.cargo_types},
                explanation="Declared cargo is compared with supported berth cargo capabilities.",
            ),
            BerthCompatibilityCheck(
                parameter="status",
                required="Operational at the service window",
                capability=berth.operational_status,
                compatible=berth.operational_status not in {"closed", "maintenance"},
                explanation="Occupied is allowed only when the berth is forecast to be available before service.",
            ),
            BerthCompatibilityCheck(
                parameter="availability",
                required=f"available by {call.predicted_eta}",
                capability=berth.available_from,
                compatible=_parse(berth.available_from) <= _parse(call.predicted_eta),
                explanation="Forecast availability is compared with the CI ETA, not only the reported ETA.",
            ),
            BerthCompatibilityCheck(
                parameter="restriction",
                required="No blocking restriction",
                capability="; ".join(berth.restrictions) or "none",
                compatible=not any("closed" in item.casefold() for item in berth.restrictions),
                explanation="Restrictions remain visible and can block an otherwise compatible berth.",
            ),
        ]
        blocking = [item.explanation for item in checks if not item.compatible]
        compatible = not blocking
        return BerthCompatibility(
            vessel_id=call.vessel_id,
            berth_id=berth_id,
            compatible=compatible,
            confidence=.93,
            checks=checks,
            blocking_reasons=blocking,
            explanation=(
                f"Berth #{berth.number} is compatible with {call.vessel_name}."
                if compatible
                else f"Berth #{berth.number} has {len(blocking)} blocking compatibility condition(s)."
            ),
        )

    def decide_berth(self, request: BerthAssignmentDecisionRequest | dict[str, Any]) -> BerthAssignmentDecision:
        if not isinstance(request, BerthAssignmentDecisionRequest):
            request = BerthAssignmentDecisionRequest.model_validate(request)
        recommendation = self.get_berth_recommendation(request.port_call_id)
        selected: str | None
        if request.action == "accept":
            selected = recommendation.recommended_berth_id
            state = "accepted"
        elif request.action == "change_berth":
            if request.berth_id is None:
                raise HTTPException(status_code=400, detail="berth_id is required when changing berth")
            compatibility = self.check_berth_compatibility(request.port_call_id, request.berth_id)
            if not compatibility.compatible:
                raise HTTPException(status_code=409, detail="Selected berth is not compatible")
            selected = request.berth_id
            state = "changed"
        else:
            selected = None
            state = "deferred"
        decided_at = self._generated_at
        decision = BerthAssignmentDecision(
            recommendation_id=recommendation.id,
            port_call_id=request.port_call_id,
            action=request.action,
            state=state,
            recommended_berth_id=recommendation.recommended_berth_id,
            selected_berth_id=selected,
            operator=request.operator,
            decided_at=decided_at,
            note=request.note,
            automated=False,
            explanation=(
                "The dispatcher accepted the explainable berth recommendation."
                if state == "accepted"
                else "The dispatcher selected a compatible alternative berth."
                if state == "changed"
                else "The dispatcher deferred assignment; no berth was confirmed."
            ),
        )
        stored = self._recommendations[recommendation.id]
        stored.state = state
        stored.decided_by = request.operator
        stored.decided_at = decided_at
        stored.decision_note = request.note
        stored.assigned_berth_id = selected
        call = self._port_calls[request.port_call_id]
        call.berth_assignment_status = "deferred" if state == "deferred" else "confirmed"
        call.berth_id = selected
        call.status = "approaching" if state == "deferred" else "berth_assigned"
        call.updated_at = decided_at
        self._decisions.append(decision)
        event_type = "berth_changed" if state == "changed" else "berth_assigned"
        self._events[f"POE-{len(self._events) + 1:04d}"] = PortOperationalEvent(
            id=f"POE-{len(self._events) + 1:04d}",
            type=event_type,
            port_id=self.port_id,
            port_call_id=call.id,
            vessel_id=call.vessel_id,
            berth_id=selected,
            occurred_at=decided_at,
            status="completed",
            severity="info",
            source="Dispatcher decision",
            confidence=1,
            data={"action": request.action, "recommended_berth_id": recommendation.recommended_berth_id},
            explanation=decision.explanation,
            created_by=request.operator,
            automated=False,
        )
        return decision.model_copy(deep=True)

    def list_decisions(self) -> list[BerthAssignmentDecision]:
        return [item.model_copy(deep=True) for item in self._decisions]

    def list_events(
        self,
        port_id: str | None = None,
        port_call_id: str | None = None,
    ) -> list[PortOperationalEvent]:
        if port_id is not None:
            self._require_port(port_id)
        items = list(self._events.values())
        if port_id:
            items = [item for item in items if item.port_id == port_id]
        if port_call_id:
            self.get_port_call(port_call_id)
            items = [item for item in items if item.port_call_id == port_call_id]
        items.sort(key=lambda item: item.occurred_at)
        return [item.model_copy(deep=True) for item in items]

    def run_simulation(self, request: PortSimulationRequest | dict[str, Any]) -> PortSimulationResult:
        if not isinstance(request, PortSimulationRequest):
            request = PortSimulationRequest.model_validate(request)
        baseline_wait = self._queue.average_wait_minutes
        baseline_peak = max(point.handling_pressure_percent for point in self._forecast.points)
        items = [item.model_copy(deep=True) for item in self._queue.items]
        affected: list[str]
        impacts: list[str]
        recommendations: list[str]
        if request.scenario == "vessel_delay":
            vessel_id = request.vessel_id or "caspian-star"
            delay = request.delay_minutes or 120
            if vessel_id != "caspian-star":
                raise HTTPException(status_code=404, detail="Demo vessel simulation not found")
            by_id = {item.vessel_id: item for item in items}
            by_id[vessel_id].eta = (_parse(by_id[vessel_id].eta) + timedelta(minutes=delay)).isoformat()
            ordered_ids = ["turan", "baku-express", "caspian-star", "caspian-wind"]
            items = [by_id[item_id] for item_id in ordered_ids]
            for index, item in enumerate(items, start=1):
                item.position = index
            simulated_wait = 151
            simulated_peak = 100
            congestion_change = 18
            affected = ["caspian-star", "baku-express"]
            impacts = [
                f"CASPIAN STAR ETA moves from 15:05 to {by_id[vessel_id].eta[11:16]}.",
                "BAKU EXPRESS moves ahead in the dynamic queue.",
                "Average waiting time increases from 1 h 42 min to 2 h 31 min.",
                "Berth #5 congestion indicator increases by 18%.",
            ]
            recommendations = ["Keep BAKU EXPRESS on berth #7", "Reconfirm berth #5 preparation window"]
        elif request.scenario == "berth_unavailable":
            berth_id = request.berth_id or "berth-5"
            if berth_id not in self._berths:
                raise HTTPException(status_code=404, detail="Berth not found")
            simulated_wait, simulated_peak, congestion_change = 168, 100, 22
            affected = ["caspian-star", "baku-express", "caspian-wind"]
            impacts = ["Berth #5 is removed from the planning horizon.", "Three calls require reassignment."]
            recommendations = ["Review berth #7 sequence", "Defer assignment until dispatcher review"]
        elif request.scenario == "service_extension":
            extension = request.service_extension_minutes or 60
            simulated_wait, simulated_peak, congestion_change = 132, 97, 11
            affected = ["caspian-star", "baku-express"]
            impacts = [f"CASPIAN STAR service window increases by {extension} minutes.", "The next berth #5 slot shifts."]
            recommendations = ["Notify the next call", "Evaluate berth #7 as an alternative"]
        else:
            for index, item in enumerate(items, start=1):
                item.position = index
            items.append(PortQueueItem(
                position=len(items) + 1,
                port_call_id="simulated-new-port-call",
                vessel_id="new-vessel",
                vessel_name=request.new_vessel_name or "UNPLANNED ARRIVAL",
                eta=request.new_vessel_eta or "2026-08-10T16:35:00+05:00",
                berth_id=None,
                berth_number=None,
                cargo_type="Unknown — compatibility data required",
                risk_score=0,
                operational_priority=50,
                expected_service_minutes=180,
                expected_wait_minutes=124,
                status="waiting",
                factors=["Simulated arrival", "Berth compatibility is not yet available"],
            ))
            simulated_wait, simulated_peak, congestion_change = 124, 96, 9
            affected = ["caspian-wind", "new-vessel"]
            impacts = ["An unplanned arrival is inserted into the queue.", "Two service windows overlap."]
            recommendations = ["Collect cargo and draught details", "Do not assign a berth before compatibility review"]
        queue = PortQueueSnapshot(
            port_id=self.port_id,
            generated_at=self._generated_at,
            average_wait_minutes=simulated_wait,
            dynamic=True,
            items=items,
            recalculation_reason=f"WHAT IF: {request.scenario}",
            disclaimer=SIMULATION_DISCLAIMER,
        )
        result = PortSimulationResult(
            id=f"SIM-{len(self._simulations) + 1:04d}",
            scenario=request.scenario,
            generated_at=self._generated_at,
            baseline_average_wait_minutes=baseline_wait,
            simulated_average_wait_minutes=simulated_wait,
            waiting_time_change_minutes=simulated_wait - baseline_wait,
            baseline_peak_load_percent=baseline_peak,
            simulated_peak_load_percent=simulated_peak,
            berth_congestion_change_percent=congestion_change,
            affected_vessel_ids=affected,
            simulated_queue=queue,
            impacts=impacts,
            recommendations=recommendations,
            state_changed=False,
            human_decision_required=True,
            disclaimer=SIMULATION_DISCLAIMER,
        )
        self._simulations[result.id] = result
        return result.model_copy(deep=True)

    def recalculate_for_weather(
        self,
        port_id: str = "aktau",
        *,
        berth_id: str = "berth-5",
        wind_mps: float = 22,
    ) -> WeatherRecalculationResult:
        self._require_port(port_id)
        if berth_id not in self._berths:
            raise HTTPException(status_code=404, detail="Berth not found")
        delay = 80 if wind_mps >= 20 else 30 if wind_mps >= 15 else 0
        restriction = WeatherRestriction(
            id="WR-AKTAU-701",
            berth_id=berth_id,
            active=delay > 0,
            operation_status="limited" if delay else "normal",
            reason=f"Wind {wind_mps:g} m/s affects cargo handling limits.",
            processing_delay_minutes=delay,
            started_at=self._generated_at,
            expected_end_at="2026-08-10T18:00:00+05:00" if delay else None,
            source=_source("Aktau port weather station", self._generated_at, .94, "reported"),
        )
        base = self.get_berth_recommendation("pc-aktau-143").service_prediction
        recalculated = base.model_copy(deep=True)
        recalculated.weather_delay_minutes = delay
        recalculated.total_minutes = base.total_minutes + delay
        recalculated.projected_release_at = (
            _parse(base.projected_service_start) + timedelta(minutes=recalculated.total_minutes)
        ).isoformat()
        recalculated.explanation = (
            f"The base 5 h service estimate includes an additional {delay} min weather restriction."
        )
        queue = self._queue.model_copy(deep=True)
        queue.average_wait_minutes = self._queue.average_wait_minutes + round(delay * .35)
        queue.recalculation_reason = "Weather restriction recalculation"
        points = [item.model_copy(deep=True) for item in self._forecast.points]
        for point, increase in zip(points, (4, 9, 14, 9)):
            point.handling_pressure_percent = min(100, point.handling_pressure_percent + increase)
            point.primary_driver = "Weather-limited berth service"
        forecast = self._forecast.model_copy(deep=True)
        forecast.points = points
        forecast.weather_restriction = restriction
        forecast.explanation = "Weather restriction propagated through service time, queue and load forecast."
        return WeatherRecalculationResult(
            port_id=port_id,
            restriction=restriction,
            previous_service_minutes=base.total_minutes,
            recalculated_service=recalculated,
            previous_average_wait_minutes=self._queue.average_wait_minutes,
            recalculated_queue=queue,
            recalculated_load_forecast=forecast,
            affected_port_call_ids=["pc-aktau-143", "pc-aktau-227"],
            explanation="The restriction is a planning recalculation; a dispatcher must approve operational changes.",
        )

    def record_actuals(
        self,
        port_call_id: str,
        payload: PortActualsInput | dict[str, Any],
    ) -> PortFeedbackRecord:
        if not isinstance(payload, PortActualsInput):
            payload = PortActualsInput.model_validate(payload)
        call = self._port_calls.get(port_call_id)
        if call is None:
            raise HTTPException(status_code=404, detail="Port call not found")
        ordered = [
            payload.actual_arrival,
            payload.berth_started_at,
            payload.service_started_at,
            payload.service_completed_at,
            payload.actual_departure,
        ]
        if ordered != sorted(ordered, key=_parse):
            raise HTTPException(status_code=400, detail="Actual port timestamps must be chronological")
        eta_error = _minutes(call.predicted_eta, payload.actual_arrival)
        actual_service = _minutes(payload.service_started_at, payload.service_completed_at)
        recorded_at = payload.actual_departure
        reported_cargo = QuantityObservation(
            value=call.reported_cargo_t,
            unit="t",
            source="Baku port declaration",
            source_timestamp="2026-08-10T07:42:00+05:00",
            confidence=.94,
            verification_status="reported",
        )
        verified_cargo = QuantityObservation(
            value=payload.verified_cargo_t,
            unit="t",
            source=payload.source,
            source_timestamp=recorded_at,
            confidence=.98,
            verification_status="verified",
        )
        reported_draught = QuantityObservation(
            value=call.reported_draught_m,
            unit="m",
            source="AIS draught report",
            source_timestamp="2026-08-10T17:40:00+05:00",
            confidence=.87,
            verification_status="reported",
        )
        verified_draught = QuantityObservation(
            value=payload.verified_draught_m,
            unit="m",
            source=payload.source,
            source_timestamp=recorded_at,
            confidence=.99,
            verification_status="verified",
        )
        event_ids = [f"POE-FB-{index}" for index in range(1, 6)]
        comparisons = [
            ActualVsPredictedMetric(
                metric="arrival",
                predicted=call.predicted_eta,
                actual=payload.actual_arrival,
                error=eta_error,
                unit="min",
                interpretation=f"Actual arrival was {eta_error:+d} min relative to the CI ETA.",
            ),
            ActualVsPredictedMetric(
                metric="service_duration",
                predicted=300,
                actual=actual_service,
                error=actual_service - 300,
                unit="min",
                interpretation=f"Actual service differed from the model by {actual_service - 300:+d} min.",
            ),
            ActualVsPredictedMetric(
                metric="cargo",
                predicted=call.reported_cargo_t,
                actual=payload.verified_cargo_t,
                error=payload.verified_cargo_t - call.reported_cargo_t,
                unit="t",
                interpretation="Reported and independently verified cargo remain separate observations.",
            ),
            ActualVsPredictedMetric(
                metric="draught",
                predicted=call.reported_draught_m,
                actual=payload.verified_draught_m,
                error=round(payload.verified_draught_m - call.reported_draught_m, 2),
                unit="m",
                interpretation="The port draught observation is fed back as verified evidence.",
            ),
        ]
        feedback = PortFeedbackRecord(
            id=f"PFR-{port_call_id}",
            port_call_id=port_call_id,
            vessel_id=call.vessel_id,
            voyage_id=call.voyage_id,
            recorded_at=recorded_at,
            recorded_by=payload.recorded_by,
            reported_cargo=reported_cargo,
            verified_cargo=verified_cargo,
            reported_draught=reported_draught,
            verified_draught=verified_draught,
            comparisons=comparisons,
            intelligence_update_targets=[
                "cargo_intelligence",
                "vessel_draught_model",
                "eta_accuracy_history",
                "service_time_history",
            ],
            emitted_event_ids=event_ids,
            closed_loop_complete=True,
            explanation=(
                "Aktau actuals close the sea-to-port loop while preserving reported and verified values separately."
            ),
            disclaimer="Verified port observations improve future models; they do not retroactively prove intent or misconduct.",
        )
        call.actual_arrival = payload.actual_arrival
        call.berth_started_at = payload.berth_started_at
        call.service_started_at = payload.service_started_at
        call.service_completed_at = payload.service_completed_at
        call.actual_departure = payload.actual_departure
        call.verified_cargo_t = payload.verified_cargo_t
        call.verified_draught_m = payload.verified_draught_m
        call.documents_verified = payload.documents_verified
        call.status = "departed"
        call.updated_at = recorded_at
        actual_timeline = [
            ("vessel_arrived", payload.actual_arrival, "Actual arrival", "Arrival recorded by Port Aktau"),
            ("berth_assigned", payload.berth_started_at, "Berth #5 occupied", "Dispatcher-confirmed berth operation"),
            ("service_started", payload.service_started_at, "Service started", "Cargo handling and documentation started"),
            ("service_completed", payload.service_completed_at, "Service completed", f"Actual duration {actual_service} min"),
            ("vessel_departed", payload.actual_departure, "Vessel departed", "PortCall completed; feedback published"),
        ]
        for index, (event_type, timestamp, title, detail) in enumerate(actual_timeline, start=1):
            call.timeline.append(PortTimelineEntry(
                id=event_ids[index - 1],
                event_type=event_type,
                actual_at=timestamp,
                berth_id="berth-5" if index > 1 else None,
                title=title,
                detail=detail,
                source=payload.source,
                verification_status="verified",
            ))
            self._events[event_ids[index - 1]] = PortOperationalEvent(
                id=event_ids[index - 1],
                type=event_type,
                port_id=self.port_id,
                port_call_id=port_call_id,
                vessel_id=call.vessel_id,
                berth_id="berth-5" if index > 1 else None,
                occurred_at=timestamp,
                status="completed",
                severity="info",
                source=payload.source,
                confidence=.99,
                data={"verification_status": "verified"},
                explanation=detail,
                created_by=payload.recorded_by,
                automated=False,
            )
        self._feedback[port_call_id] = feedback
        return feedback.model_copy(deep=True)

    def get_feedback(self, port_call_id: str) -> PortFeedbackRecord:
        self.get_port_call(port_call_id)
        item = self._feedback.get(port_call_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Port feedback not recorded")
        return item.model_copy(deep=True)

    def _require_port(self, port_id: str) -> None:
        if port_id.casefold() != self.port_id:
            raise HTTPException(status_code=404, detail="Port operations not found")

    def _seed_demo(self) -> None:
        self._weather = PortWeather(
            observed_at=self._generated_at,
            wind_mps=12.4,
            waves_m=.8,
            visibility_km=12,
            temperature_c=26,
            storm=False,
            source="Aktau port weather station (demo)",
            confidence=.94,
        )
        berth_specs = [
            (1, 210, 195, 8.2, ["Oil products"], ["Loading arms", "Pump station"], "occupied", "AKTAU MERCHANT", "09:10", "16:25", "KHAZAR WAVE", "16:40", []),
            (2, 150, 140, 4.5, ["General"], ["Mobile crane"], "available", None, None, None, None, "14:10", ["Draught <= 4.5 m"]),
            (3, 175, 165, 6.8, ["Grain", "General"], ["2 x portal crane", "Conveyor"], "occupied", "PORT WORKBOAT", "10:30", "14:35", "TURAN", "14:45", []),
            (5, 195, 180, 7.5, ["General", "Steel"], ["2 x portal crane", "Reach stacker"], "occupied", "TURAN CARRIER", "10:30", "14:35", "CASPIAN STAR", "14:45", []),
            (7, 185, 170, 6.9, ["General", "Steel", "Equipment"], ["Portal crane", "Ro-Ro ramp"], "available", None, None, None, "BAKU EXPRESS", "14:10", []),
            (8, 160, 150, 5.8, ["General"], ["Mobile crane"], "occupied", "KURYK TRADER", "08:45", "18:05", "VOLGA MARINE", "18:20", []),
            (9, 145, 135, 5.0, ["General"], ["Mobile crane"], "limited", "SERVICE BARGE", "11:10", "17:30", None, "17:45", ["Equipment inspection"]),
            (10, 205, 190, 7.2, ["Containers", "General"], ["STS crane", "Reach stacker"], "available", None, None, None, "SEA STEPPE", "14:10", []),
        ]
        for number, length, max_length, max_draught, cargo, equipment, status, current, started, completed, next_vessel, available, restrictions in berth_specs:
            berth_id = f"berth-{number}"
            self._berths[berth_id] = Berth(
                id=berth_id,
                port_id=self.port_id,
                number=number,
                name=f"Berth #{number}",
                length_m=length,
                max_vessel_length_m=max_length,
                max_draught_m=max_draught,
                cargo_types=cargo,
                equipment=equipment,
                operational_status=status,
                current_vessel_id=current.casefold().replace(" ", "-") if current else None,
                current_vessel_name=current,
                service_started_at=f"2026-08-10T{started}:00+05:00" if started else None,
                expected_completion_at=f"2026-08-10T{completed}:00+05:00" if completed else None,
                next_vessel_id=next_vessel.casefold().replace(" ", "-") if next_vessel else None,
                next_vessel_name=next_vessel,
                available_from=f"2026-08-10T{available}:00+05:00",
                restrictions=restrictions,
            )
        arrival_specs = [
            ("143", "caspian-star", "CASPIAN STAR", "14:30", "15:05", .87, "berth-5", 5, "Steel", 5000, 91, "critical", "high", 2),
            ("212", "turan", "TURAN", "14:15", "14:20", .91, "berth-3", 3, "Grain", 3400, 21, "low", "normal", 1),
            ("227", "baku-express", "BAKU EXPRESS", "15:25", "15:40", .84, "berth-7", 7, "General", 2100, 14, "low", "normal", 3),
            ("231", "caspian-wind", "CASPIAN WIND", "16:00", "16:10", .79, "berth-7", 7, "Equipment", 1780, 19, "low", "normal", 4),
            ("238", "khazar-wave", "KHAZAR WAVE", "17:30", "17:36", .88, "berth-1", 1, "Oil products", 7800, 28, "moderate", "normal", 5),
            ("242", "volga-marine", "VOLGA MARINE", "18:10", "18:18", .86, "berth-8", 8, "General", 3900, 8, "low", "normal", 6),
            ("247", "sea-steppe", "SEA STEPPE", "19:00", "19:12", .81, "berth-10", 10, "Containers", 4250, 11, "low", "normal", 7),
        ]
        for suffix, vessel_id, vessel_name, reported, predicted, confidence, berth_id, berth_number, cargo, mass, risk, level, attention, queue_position in arrival_specs:
            call_id = f"pc-aktau-{suffix}"
            predicted_iso = f"2026-08-10T{predicted}:00+05:00"
            reported_iso = f"2026-08-10T{reported}:00+05:00"
            window_minutes = 13 if vessel_id == "caspian-star" else 11
            eta = ETAPrediction(
                id=f"ETA-{suffix}",
                port_call_id=call_id,
                vessel_id=vessel_id,
                reported_eta=reported_iso,
                predicted_eta=predicted_iso,
                expected_delay_minutes=_minutes(reported_iso, predicted_iso),
                confidence=confidence,
                likely_window_start=(_parse(predicted_iso) - timedelta(minutes=window_minutes)).isoformat(),
                likely_window_end=(_parse(predicted_iso) + timedelta(minutes=13)).isoformat(),
                calculated_at=self._generated_at,
                previous_prediction="2026-08-10T15:12:00+05:00" if vessel_id == "caspian-star" else None,
                change_minutes=-7 if vessel_id == "caspian-star" else 0,
                factors=[
                    ETAPredictionFactor(name="distance", value="57 km remaining", effect_minutes=0, explanation="Distance is calculated from the latest valid AIS position.", source=_source("AIS current position", self._generated_at, .98, "reported")),
                    ETAPredictionFactor(name="speed", value="12.4 kn current / 11.8 kn historical", effect_minutes=8, explanation="Current and historical speeds provide a transparent travel-time baseline.", source=_source("CI behavior profile", self._generated_at, .91)),
                    ETAPredictionFactor(name="route", value="38 km deviation", effect_minutes=21, explanation="Observed route geometry adds travel time relative to the historical corridor.", source=_source("CI route analysis", self._generated_at, .92, "verified")),
                    ETAPredictionFactor(name="weather", value="wind 12.4 m/s / waves 0.8 m", effect_minutes=6, explanation="Current weather adds a limited delay allowance.", source=_source("Aktau weather station", self._generated_at, .94, "reported")),
                ],
                model_version=ETA_MODEL_VERSION,
                explanation=(
                    "The explainable ETA combines current position, distance, speed history, route state, behavior and weather."
                ),
                disclaimer="The predicted time is a planning estimate; use the likely window rather than treating it as an exact arrival.",
            )
            self._eta[vessel_id] = eta
            self._arrivals.append(ArrivalBoardEntry(
                port_call_id=call_id,
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                predicted_eta=predicted_iso,
                eta_confidence=confidence,
                berth_id=berth_id,
                berth_number=berth_number,
                berth_assignment_status="recommended",
                cargo_type=cargo,
                cargo_mass_t=mass,
                risk_score=risk,
                risk_level=level,
                attention_status=attention,
                port_call_status="approaching",
            ))
            self._port_calls[call_id] = PortCall(
                id=call_id,
                vessel_id=vessel_id,
                vessel_name=vessel_name,
                voyage_id="voy-001" if vessel_id == "caspian-star" else f"voy-{suffix}",
                port_id=self.port_id,
                reported_eta=reported_iso,
                predicted_eta=predicted_iso,
                berth_id=berth_id,
                berth_assignment_status="recommended",
                queue_position=queue_position,
                queue_entered_at=self._generated_at,
                status="approaching",
                risk_score=risk,
                risk_level=level,
                significant_event_count=7 if vessel_id == "caspian-star" else 1,
                cargo_type=cargo,
                reported_cargo_t=mass,
                reported_draught_m=4.5 if vessel_id == "caspian-star" else 4.2,
                timeline=[PortTimelineEntry(
                    id=f"PTE-{suffix}-01",
                    event_type="vessel_approaching",
                    actual_at="2026-08-10T12:00:00+05:00" if vessel_id == "caspian-star" else self._generated_at,
                    title="Vessel approaching Aktau",
                    detail="PortCall created from an active voyage and current AIS destination.",
                    source="CI port-call generator",
                    verification_status="verified",
                )],
                created_at="2026-08-10T12:00:00+05:00" if vessel_id == "caspian-star" else self._generated_at,
                updated_at=self._generated_at,
            )
        queue_specs = [
            (1, "pc-aktau-212", "turan", "TURAN", "14:20", "berth-3", 3, "Grain", 21, 50, 240, 35, "scheduled", ["Earliest compatible service window"]),
            (2, "pc-aktau-143", "caspian-star", "CASPIAN STAR", "15:05", "berth-5", 5, "Steel", 91, 96, 300, 42, "attention", ["High-risk pre-arrival review", "Berth #5 compatible"]),
            (3, "pc-aktau-227", "baku-express", "BAKU EXPRESS", "15:40", "berth-7", 7, "General", 14, 45, 210, 78, "scheduled", ["Moved from berth #5 to reduce overlap"]),
            (4, "pc-aktau-231", "caspian-wind", "CASPIAN WIND", "16:10", "berth-7", 7, "Equipment", 19, 42, 180, 93, "waiting", ["Queued after BAKU EXPRESS service window"]),
        ]
        items = [PortQueueItem(
            position=position,
            port_call_id=call_id,
            vessel_id=vessel_id,
            vessel_name=name,
            eta=f"2026-08-10T{eta}:00+05:00",
            berth_id=berth_id,
            berth_number=berth_number,
            cargo_type=cargo,
            risk_score=risk,
            operational_priority=priority,
            expected_service_minutes=service,
            expected_wait_minutes=wait,
            status=status,
            factors=factors,
        ) for position, call_id, vessel_id, name, eta, berth_id, berth_number, cargo, risk, priority, service, wait, status, factors in queue_specs]
        self._queue = PortQueueSnapshot(
            port_id=self.port_id,
            generated_at=self._generated_at,
            average_wait_minutes=102,
            dynamic=True,
            items=items,
            recalculation_reason="ETA, compatibility, service duration, weather and operational priority",
            disclaimer="Queue order is a planning recommendation and does not override dispatcher authority.",
        )
        service = ServiceTimePrediction(
            id="STP-pc-aktau-143",
            port_call_id="pc-aktau-143",
            vessel_id="caspian-star",
            berth_id="berth-5",
            cargo_type="Steel",
            cargo_mass_t=5000,
            historical_rate_tph=1250,
            cargo_handling_minutes=240,
            documentation_minutes=35,
            other_operations_minutes=25,
            weather_delay_minutes=0,
            total_minutes=300,
            confidence=.82,
            berth_available_from="2026-08-10T14:45:00+05:00",
            projected_service_start="2026-08-10T15:05:00+05:00",
            projected_release_at="2026-08-10T20:05:00+05:00",
            model_version=SERVICE_MODEL_VERSION,
            explanation="5,000 t / 1,250 t/h = 4 h handling, plus 35 min documentation and 25 min other operations.",
        )
        compatibility = self.check_berth_compatibility("pc-aktau-143", "berth-5")
        recommendation = BerthAssignmentRecommendation(
            id="BAR-pc-aktau-143",
            port_call_id="pc-aktau-143",
            vessel_id="caspian-star",
            recommended_berth_id="berth-5",
            recommended_berth_number=5,
            state="recommended",
            compatibility=compatibility,
            alternative_berth_ids=["berth-7"],
            queue_position=2,
            berth_available_from="2026-08-10T14:45:00+05:00",
            service_prediction=service,
            confidence=.92,
            reasons=[
                "142 m vessel length is below the 180 m limit",
                "5.0 m planning draught is below the 7.5 m limit",
                "Steel cargo is supported",
                "Berth is forecast available before the CI ETA",
            ],
            expected_effect="Prepare a compatible berth before arrival while maintaining a high-risk review checkpoint.",
            human_decision_required=True,
            generated_at=self._generated_at,
            disclaimer=PORT_DISCLAIMER,
        )
        self._recommendations[recommendation.id] = recommendation
        bottleneck = PortBottleneck(
            id="PBN-AKTAU-701",
            severity="critical",
            window_start="2026-08-10T16:00:00+05:00",
            window_end="2026-08-10T19:00:00+05:00",
            berth_ids=["berth-3", "berth-5"],
            expected_load_percent=91,
            primary_reason="Four vessels are predicted to arrive within 75 minutes.",
            affected_vessel_ids=["turan", "caspian-star", "baku-express", "caspian-wind"],
            confidence=.86,
        )
        operational_recommendation = PortOperationalRecommendation(
            id="POR-AKTAU-701",
            action="Move BAKU EXPRESS from berth #5 to berth #7",
            vessel_id="baku-express",
            from_berth_id="berth-5",
            to_berth_id="berth-7",
            average_wait_change_minutes=-42,
            load_before_percent=91,
            load_after_percent=76,
            confidence=.88,
            reasons=["Berth #7 supports general cargo", "Berth #7 is available", "Berth #5 is reserved for CASPIAN STAR"],
            human_decision_required=True,
            disclaimer=PORT_DISCLAIMER,
        )
        points = [
            PortLoadForecastPoint(horizon_hours=0, forecast_at="2026-08-10T14:00:00+05:00", handling_pressure_percent=42, confidence=.94, primary_driver="Five vessels currently in port"),
            PortLoadForecastPoint(horizon_hours=2, forecast_at="2026-08-10T16:00:00+05:00", handling_pressure_percent=58, confidence=.91, primary_driver="TURAN and CASPIAN STAR arrival windows"),
            PortLoadForecastPoint(horizon_hours=4, forecast_at="2026-08-10T18:00:00+05:00", handling_pressure_percent=74, confidence=.87, primary_driver="Overlapping cargo handling windows"),
            PortLoadForecastPoint(horizon_hours=6, forecast_at="2026-08-10T20:00:00+05:00", handling_pressure_percent=91, confidence=.82, primary_driver="Four arrivals within 75 minutes and berth #5 service"),
        ]
        self._forecast = PortLoadForecast(
            port_id=self.port_id,
            generated_at=self._generated_at,
            metric_label="Forecast handling demand (distinct from current berth utilization)",
            current_operational_utilization_percent=68,
            points=points,
            bottlenecks=[bottleneck],
            recommendations=[operational_recommendation],
            model_version=PORT_MODEL_VERSION,
            explanation="Incoming ETA, service duration, berth schedule, queue and weather are propagated into handling demand.",
        )
        self._overview = PortOperationsOverview(
            port_id=self.port_id,
            port_name="Port Aktau",
            generated_at=self._generated_at,
            port_load_percent=68,
            load_metric_label="Current berth and operational utilization",
            arriving_vessels=7,
            in_port=5,
            waiting=3,
            departing=2,
            average_wait_minutes=102,
            berths_available=3,
            berths_occupied=5,
            high_risk_arrivals=1,
            weather=self._weather,
            active_weather_restrictions=0,
            next_bottleneck=bottleneck,
            operational_recommendations=[operational_recommendation],
            disclaimer=PORT_DISCLAIMER,
        )
        event_specs = [
            ("vessel_approaching", "12:00", "info", "CASPIAN STAR is approaching Aktau"),
            ("eta_changed", "12:20", "warning", "CI ETA updated from 15:12 to 15:05"),
            ("vessel_arrived", "15:20", "info", "Demo actual arrival checkpoint"),
            ("vessel_waiting", "15:21", "info", "Vessel waits for dispatcher clearance"),
            ("berth_assigned", "15:35", "info", "Berth #5 assignment accepted by dispatcher"),
            ("berth_changed", "15:36", "info", "Alternative berth decision event supported"),
            ("service_started", "15:50", "info", "Cargo service started"),
            ("service_delayed", "16:10", "warning", "Service delay event supported"),
            ("service_completed", "20:32", "info", "Cargo service completed"),
            ("vessel_departed", "21:10", "info", "CASPIAN STAR departed"),
            ("port_congestion", "16:00", "critical", "Congestion expected from 16:00 to 19:00"),
            ("weather_restriction", "17:00", "warning", "Weather restriction lifecycle event supported"),
        ]
        for index, (event_type, time, severity, explanation) in enumerate(event_specs, start=1):
            event_id = f"POE-{index:04d}"
            self._events[event_id] = PortOperationalEvent(
                id=event_id,
                type=event_type,
                port_id=self.port_id,
                port_call_id="pc-aktau-143" if event_type not in {"port_congestion", "weather_restriction"} else None,
                vessel_id="caspian-star" if event_type not in {"port_congestion", "weather_restriction"} else None,
                berth_id="berth-5" if event_type in {"berth_assigned", "berth_changed", "service_started", "service_delayed", "service_completed"} else None,
                occurred_at=f"2026-08-10T{time}:00+05:00",
                status="active" if event_type in {"vessel_approaching", "port_congestion"} else "completed",
                severity=severity,
                source="CI Port Operations demo",
                confidence=.92,
                data={"demo_lifecycle": True},
                explanation=explanation,
                created_by="system" if event_type not in {"berth_assigned", "berth_changed"} else "demo-dispatcher",
                automated=event_type not in {"berth_assigned", "berth_changed"},
            )


port_operations = PortOperationsService()
