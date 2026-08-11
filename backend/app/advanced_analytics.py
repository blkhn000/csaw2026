from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException

from .models import (
    AdvancedRiskSignal,
    CargoConsistencyCheck,
    CargoDeclaration,
    CargoDraughtAssessment,
    CargoIntelligence,
    CargoProfile,
    CargoProfileItem,
    CargoTimelineItem,
    CompanyIntelligence,
    CompanyRiskHistoryPoint,
    CompanyVesselSummary,
    CompanyVoyageSummary,
    DetectedEvent,
    DraughtModel,
    DraughtConsistencyResult,
    EventStatus,
    EventStatusUpdate,
    EventType,
    FuelAnalysis,
    FuelProfile,
    GraphEdge,
    GraphNode,
    IntelligenceSummaryFactor,
    InvestigationNetwork,
    NumericRange,
    OperationalCorrection,
    QuantityObservation,
    SourceMetadata,
    VesselConnection,
    VoyageCostBreakdown,
    VoyageEconomics,
    VoyageIntelligenceSummary,
    WeatherCorrection,
)


ADVANCED_MODEL_VERSION = "CI-ADV-1.0"
ADVANCED_DISCLAIMER = (
    "Advanced analytics highlights inconsistencies that merit source verification. "
    "It does not establish undeclared cargo, misconduct, ownership control, or legal status."
)


class AdvancedAnalyticsService:
    """Deterministic Stage 6 cargo, fuel, economics and link intelligence service.

    The demo fixture is intentionally source-aware: every non-AIS observation is
    marked reported, estimated, verified, or unavailable. Public methods return
    deep copies so an API consumer cannot mutate the analytical state.
    """

    model_version = ADVANCED_MODEL_VERSION
    risk_contribution_cap = 7

    def __init__(self) -> None:
        self._cargo: dict[str, CargoIntelligence] = {}
        self._fuel: dict[str, FuelAnalysis] = {}
        self._economics: dict[str, VoyageEconomics] = {}
        self._intelligence: dict[str, VoyageIntelligenceSummary] = {}
        self._connections: dict[str, list[VesselConnection]] = {}
        self._networks: dict[str, InvestigationNetwork] = {}
        self._companies: dict[str, CompanyIntelligence] = {}
        self._company_vessels: dict[str, list[CompanyVesselSummary]] = {}
        self._events: dict[str, DetectedEvent] = {}
        self._signals: dict[str, AdvancedRiskSignal] = {}
        self._seed_demo()

    def get_cargo(self, voyage_id: str) -> CargoIntelligence:
        return self._copy_or_404(self._cargo, voyage_id, "Cargo intelligence not found")

    def apply_port_feedback(
        self,
        voyage_id: str,
        *,
        verified_cargo_t: float,
        verified_draught_m: float,
        observed_at: str,
        source: str = "Aktau port operations",
    ) -> CargoIntelligence:
        """Attach verified port observations without replacing reported facts."""

        if verified_cargo_t < 0 or verified_draught_m < 0:
            raise HTTPException(status_code=400, detail="Verified port values must be non-negative")
        cargo = self._cargo.get(voyage_id)
        if cargo is None:
            raise HTTPException(status_code=404, detail="Cargo intelligence not found")
        cargo.port_verified_cargo = QuantityObservation(
            value=verified_cargo_t,
            unit="t",
            source=source,
            source_timestamp=observed_at,
            confidence=.98,
            verification_status="verified",
        )
        cargo.port_verified_draught = QuantityObservation(
            value=verified_draught_m,
            unit="m",
            source=source,
            source_timestamp=observed_at,
            confidence=.99,
            verification_status="verified",
        )
        cargo.port_feedback_at = observed_at
        cargo.generated_at = observed_at
        cargo.timeline = [
            item for item in cargo.timeline
            if item.id not in {"CTL-143-07", "CTL-143-08"}
        ] + [
            CargoTimelineItem(
                id="CTL-143-07",
                timestamp=observed_at,
                type="cargo_verification",
                title="Cargo verified by Port Aktau",
                detail=f"{verified_cargo_t:,.0f} t verified; 5,000 t remains the reported declaration",
                source_reference="PFR-pc-aktau-143",
                confidence=.98,
            ),
            CargoTimelineItem(
                id="CTL-143-08",
                timestamp=observed_at,
                type="draught_verification",
                title="Arrival draught verified by Port Aktau",
                detail=f"{verified_draught_m:.1f} m verified observation",
                source_reference="PFR-pc-aktau-143",
                confidence=.99,
            ),
        ]
        cargo.source_quality = [item for item in cargo.source_quality if item.source != source] + [
            SourceMetadata(
                source=source,
                source_timestamp=observed_at,
                confidence=.98,
                verification_status="verified",
            )
        ]
        cargo.summary = (
            "Port Aktau feedback is attached as verified evidence while the original cargo declaration "
            "and AIS draught report remain preserved as separate reported observations."
        )
        return cargo.model_copy(deep=True)

    def get_fuel(self, voyage_id: str) -> FuelAnalysis:
        return self._copy_or_404(self._fuel, voyage_id, "Fuel intelligence not found")

    def get_economics(self, voyage_id: str) -> VoyageEconomics:
        return self._copy_or_404(self._economics, voyage_id, "Voyage economics not found")

    def get_intelligence(self, voyage_id: str) -> VoyageIntelligenceSummary:
        result = self._copy_or_404(self._intelligence, voyage_id, "Voyage intelligence not found")
        active_event_ids = {
            event.id for event in self._events.values()
            if event.voyage_id == voyage_id and event.status != "dismissed"
        }
        result.factors = [
            factor for factor in result.factors
            if not factor.source_event_id.startswith("ADV-") or factor.source_event_id in active_event_ids
        ]
        signals = self.risk_signals(result.vessel_id, voyage_id)
        result.advanced_adjustment = min(
            self.risk_contribution_cap,
            sum(signal.effective_score for signal in signals),
        )
        result.risk_score = min(100, result.base_risk_score + result.advanced_adjustment)
        result.significant_factor_count = len(result.factors)
        if result.advanced_adjustment != self.risk_contribution_cap:
            result.summary = (
                f"{len(result.factors)} significant factors remain after analyst review. "
                "The voyage still differs from parts of the historical profile and merits source verification."
            )
        return result

    def get_connections(self, vessel_id: str) -> list[VesselConnection]:
        if vessel_id not in self._connections:
            raise HTTPException(status_code=404, detail="Vessel connections not found")
        return [item.model_copy(deep=True) for item in self._connections[vessel_id]]

    def get_network(self, vessel_id: str) -> InvestigationNetwork:
        return self._copy_or_404(self._networks, vessel_id, "Vessel network not found")

    def get_company(self, company_id: str) -> CompanyIntelligence:
        return self._copy_or_404(self._companies, company_id, "Company not found")

    def get_company_vessels(self, company_id: str) -> list[CompanyVesselSummary]:
        self.get_company(company_id)
        return [item.model_copy(deep=True) for item in self._company_vessels.get(company_id, [])]

    @staticmethod
    def evaluate_draught_consistency(
        declared_mass_change_t: float,
        observed_change_m: float,
        model: DraughtModel,
    ) -> DraughtConsistencyResult:
        """Classify both declared-load mismatches and unexplained load changes.

        The expected range is vessel-specific and intentionally expressed as an
        absolute magnitude: loading and unloading have opposite signs, while
        the physical sensitivity range remains the same.
        """

        disclaimer = (
            "Draught consistency is an indicator for source review. It does not establish "
            "undeclared cargo, cargo legality, intent, or wrongdoing."
        )
        reference_count = abs(declared_mass_change_t) / max(model.tonnes_reference, 1)
        expected = NumericRange(
            minimum=round(reference_count * model.expected_change_per_reference.minimum, 2),
            maximum=round(reference_count * model.expected_change_per_reference.maximum, 2),
            unit="m",
        )
        observed_magnitude = abs(observed_change_m)
        if model.confidence < .35 or model.sample_count < 10:
            status = "insufficient_data"
            explanation = (
                "The vessel-specific model does not have enough reliable cargo operations "
                "to classify the observed draught change."
            )
        elif abs(declared_mass_change_t) < 1 and observed_magnitude >= .5:
            status = "unexplained_load_change"
            explanation = (
                f"No cargo mass change was reported, while draught changed by {observed_magnitude:.2f} m. "
                "Cargo operations, ballast, trim and source quality should be reviewed."
            )
        elif (
            observed_magnitude < max(0, expected.minimum - .1)
            or observed_magnitude > expected.maximum + .1
        ):
            status = "cargo_draught_mismatch"
            explanation = (
                f"Observed draught change {observed_magnitude:.2f} m is outside the vessel-specific "
                f"{expected.minimum:.2f}–{expected.maximum:.2f} m range for the reported mass change."
            )
        else:
            status = "consistent"
            explanation = (
                f"Observed draught change {observed_magnitude:.2f} m is consistent with the "
                f"vessel-specific {expected.minimum:.2f}–{expected.maximum:.2f} m range."
            )
        return DraughtConsistencyResult(
            declared_mass_change_t=declared_mass_change_t,
            observed_change_m=observed_change_m,
            expected_change_m=expected,
            status=status,
            confidence=model.confidence,
            explanation=explanation,
            disclaimer=disclaimer,
        )

    def list_events(
        self,
        *,
        vessel_id: str | None = None,
        event_type: EventType | None = None,
        status: EventStatus | None = None,
    ) -> list[DetectedEvent]:
        events: Iterable[DetectedEvent] = self._events.values()
        if vessel_id is not None:
            events = (event for event in events if event.vessel_id == vessel_id)
        if event_type is not None:
            events = (event for event in events if event.type == event_type)
        if status is not None:
            events = (event for event in events if event.status == status)
        return [event.model_copy(deep=True) for event in sorted(events, key=lambda item: item.started_at, reverse=True)]

    def get_event(self, event_id: str) -> DetectedEvent:
        return self._copy_or_404(self._events, event_id, "Advanced analytics event not found")

    def update_event_status(
        self,
        event_id: str,
        update: EventStatusUpdate | dict[str, object],
        reviewer: str,
    ) -> DetectedEvent:
        if not isinstance(update, EventStatusUpdate):
            update = EventStatusUpdate.model_validate(update)
        event = self._events.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Advanced analytics event not found")
        event.status = update.status
        event.reviewed_by = reviewer
        event.review_note = update.note
        return event.model_copy(deep=True)

    def risk_signals(self, vessel_id: str, voyage_id: str | None = None) -> list[AdvancedRiskSignal]:
        signals: list[AdvancedRiskSignal] = []
        for source in self._signals.values():
            if source.vessel_id != vessel_id or (voyage_id is not None and source.voyage_id != voyage_id):
                continue
            signal = source.model_copy(deep=True)
            event = self._events.get(signal.event_id)
            if event is None or event.status == "dismissed":
                signal.effective_score = 0
            signals.append(signal)
        signals.sort(key=lambda item: (item.source_timestamp, item.id))
        return signals

    def get_risk_signals(self, vessel_id: str, voyage_id: str | None = None) -> list[AdvancedRiskSignal]:
        return self.risk_signals(vessel_id, voyage_id)

    @staticmethod
    def _copy_or_404(store: dict[str, object], key: str, detail: str):
        item = store.get(key)
        if item is None:
            raise HTTPException(status_code=404, detail=detail)
        return item.model_copy(deep=True)  # type: ignore[attr-defined]

    def _seed_demo(self) -> None:
        cargo = self._seed_cargo()
        fuel = self._seed_fuel()
        economics = self._seed_economics()
        connections = self._seed_connections()
        self._seed_companies()
        network = self._seed_network()
        self._seed_events_and_signals()

        self._cargo[cargo.voyage_id] = cargo
        self._fuel[fuel.voyage_id] = fuel
        self._economics[economics.voyage_id] = economics
        self._connections["caspian-star"] = connections
        self._connections["turan"] = [
            connection.model_copy(
                update={
                    "id": "CON-turan-caspian-star",
                    "vessel_id": "turan",
                    "related_vessel_id": "caspian-star",
                    "related_vessel_name": "CASPIAN STAR",
                },
                deep=True,
            )
            for connection in connections
        ]
        self._networks["caspian-star"] = network
        self._intelligence["voy-001"] = self._build_intelligence(cargo, fuel, economics, connections)

    @staticmethod
    def _seed_cargo() -> CargoIntelligence:
        declaration = CargoDeclaration(
            id="CD-143-01",
            vessel_id="caspian-star",
            voyage_id="voy-001",
            cargo_type="steel",
            cargo_name="Steel products",
            declared_mass=5000,
            declared_volume=720,
            volume_unit="m3",
            origin_port="Baku",
            destination_port="Aktau",
            shipper="Baku Metals Export JSC",
            consignee="Aktau Industrial Supply LLP",
            declared_value=250000,
            currency="USD",
            document_reference="PORT-BAK-2026-0810-143",
            loaded_at="2026-08-10T07:35:00+05:00",
            source="Baku port declaration",
            source_timestamp="2026-08-10T07:42:00+05:00",
            confidence=.94,
            verification_status="reported",
        )
        profile = CargoProfile(
            vessel_id="caspian-star",
            generated_at="2026-08-10T17:42:00+05:00",
            voyage_count=63,
            confidence=.87,
            items=[
                CargoProfileItem(cargo_type="Steel", voyage_share=.41, voyage_count=26),
                CargoProfileItem(cargo_type="Grain", voyage_share=.27, voyage_count=17),
                CargoProfileItem(cargo_type="Equipment", voyage_share=.18, voyage_count=11),
                CargoProfileItem(cargo_type="Oil products", voyage_share=.09, voyage_count=6),
                CargoProfileItem(cargo_type="Other", voyage_share=.05, voyage_count=3),
            ],
            route_typical_cargo=["Steel", "Equipment", "General cargo"],
            current_cargo_historical_share=.41,
            interpretation=(
                "Steel is consistent with the vessel and route history; historical frequency is context, "
                "not proof that the current declaration is accurate."
            ),
        )
        draught_model = DraughtModel(
            vessel_id="caspian-star",
            model_version="CI-DRAUGHT-CS-1.0",
            expected_change_per_reference=NumericRange(minimum=.21, maximum=.26, unit="m per 1,000 t"),
            confidence=.87,
            confidence_level="high",
            sample_count=63,
            generated_at="2026-08-10T17:42:00+05:00",
            limitation=(
                "Vessel-specific historical model; trim, cargo distribution and reporting quality can change the result."
            ),
        )
        draught = CargoDraughtAssessment(
            vessel_id="caspian-star",
            voyage_id="voy-001",
            departure_draught_m=4.2,
            observed_draught_m=4.5,
            observed_change_m=.3,
            expected_change_m=NumericRange(minimum=1.05, maximum=1.30, unit="m"),
            expected_arrival_draught_m=NumericRange(minimum=5.25, maximum=5.50, unit="m"),
            mismatch=True,
            anomaly_type="cargo_draught_mismatch",
            deviation_from_expected_m=.75,
            model=draught_model,
            explanation=(
                "The observed 0.30 m change is below the vessel-specific 1.05–1.30 m range expected for "
                "the reported 5,000 t loading operation. Source data and trim should be reviewed."
            ),
            disclaimer=(
                "A draught mismatch is an inconsistency indicator. It does not establish undeclared or illegal cargo."
            ),
        )
        timeline = [
            CargoTimelineItem(id="CTL-143-01", timestamp="2026-08-10T07:42:00+05:00", type="cargo_declaration", title="Cargo reported", detail="5,000 t steel", source_reference=declaration.document_reference, confidence=.94),
            CargoTimelineItem(id="CTL-143-02", timestamp="2026-08-10T08:00:00+05:00", type="departure", title="Departure Baku", detail="Draught 4.2 m", source_reference="AIS pos-001", confidence=.96),
            CargoTimelineItem(id="CTL-143-03", timestamp="2026-08-10T14:10:00+05:00", type="ais_gap", title="AIS data gap", detail="3 h 15 min", source_reference="EV-2802", confidence=.98),
            CargoTimelineItem(id="CTL-143-04", timestamp="2026-08-10T17:28:00+05:00", type="vessel_encounter", title="Encounter with TURAN", detail="174 m; 2 h 47 min", source_reference="EV-2803", confidence=.93),
            CargoTimelineItem(id="CTL-143-05", timestamp="2026-08-10T17:40:00+05:00", type="draught_observation", title="Draught observation", detail="4.5 m; +0.3 m from departure", source_reference="AIS draught report", confidence=.87),
            CargoTimelineItem(id="CTL-143-06", timestamp="2026-08-10T18:42:00+05:00", type="voyage_state", title="Underway to Aktau", detail="Actual unloaded cargo is not yet available", source_reference="AIS pos-012", confidence=.96),
        ]
        checks = [
            CargoConsistencyCheck(type="cargo_vessel", status="consistent", confidence=.96, expected="Cargo within 11,820 t DWT and compatible with a cargo vessel", observed="5,000 t steel; 42% DWT utilization", explanation="The declared mass and cargo type are physically plausible for this vessel."),
            CargoConsistencyCheck(type="cargo_route", status="context", confidence=.82, expected="Steel, equipment or general cargo is historically typical", observed="Steel; 41% of the vessel's recorded cargo voyages", explanation="The route and cargo are historically consistent, which is contextual and does not verify the declaration."),
            CargoConsistencyCheck(type="cargo_draught", status="requires_review", confidence=.87, expected="Draught change 1.05–1.30 m", observed="Draught change 0.30 m", explanation=draught.explanation),
        ]
        return CargoIntelligence(
            vessel_id="caspian-star",
            voyage_id="voy-001",
            declaration=declaration,
            profile=profile,
            timeline=timeline,
            consistency_checks=checks,
            draught_assessment=draught,
            source_quality=[
                SourceMetadata(source="Baku port declaration", source_timestamp="2026-08-10T07:42:00+05:00", confidence=.94, verification_status="reported"),
                SourceMetadata(source="AIS draught report", source_timestamp="2026-08-10T17:40:00+05:00", confidence=.87, verification_status="reported"),
                SourceMetadata(source="Historical cargo/draught model", source_timestamp="2026-08-10T17:42:00+05:00", confidence=.87, verification_status="estimated"),
                SourceMetadata(source="Cargo value estimate", source_timestamp="2026-08-10T17:43:00+05:00", confidence=.62, verification_status="estimated"),
            ],
            generated_at="2026-08-10T17:45:00+05:00",
            summary=(
                "The declared cargo is plausible for the vessel and route, but the reported draught change "
                "does not align with the vessel-specific historical range and merits source review."
            ),
            disclaimer=ADVANCED_DISCLAIMER,
        )

    @staticmethod
    def _seed_fuel() -> FuelAnalysis:
        return FuelAnalysis(
            vessel_id="caspian-star",
            voyage_id="voy-001",
            profile=FuelProfile(
                vessel_id="caspian-star",
                engine="MAN 8L32/40",
                route="Baku → Aktau",
                typical_consumption=NumericRange(minimum=38, maximum=44, unit="t"),
                typical_cruising_speed=NumericRange(minimum=11, maximum=13, unit="kn"),
                confidence=.89,
                sample_count=47,
                model_version="CI-FUEL-CS-1.0",
            ),
            baseline_expected=NumericRange(minimum=34.5, maximum=40.0, unit="t"),
            weather_correction=WeatherCorrection(
                wind_kn=18,
                waves_m=1.4,
                current_kn=.4,
                multiplier=1.04,
                source="Caspian weather hindcast",
                source_timestamp="2026-08-10T17:30:00+05:00",
                confidence=.86,
                verification_status="estimated",
            ),
            operational_correction=OperationalCorrection(
                waiting_hours=2.2,
                maneuvering_hours=.8,
                average_speed_kn=11.7,
                multiplier=1.06,
                explanation="Waiting, maneuvering, average speed and current draught add a 6% operational allowance.",
            ),
            corrected_expected=NumericRange(minimum=38, maximum=44, unit="t"),
            reported=QuantityObservation(value=61, unit="t", source="Operator voyage report", source_timestamp="2026-08-10T17:32:00+05:00", confidence=.82, verification_status="reported"),
            estimated=QuantityObservation(value=42, unit="t", source="CI vessel-specific fuel model", source_timestamp="2026-08-10T17:44:00+05:00", confidence=.89, verification_status="estimated"),
            verified=QuantityObservation(value=None, unit="t", source="Bunker receipt", source_timestamp="2026-08-10T17:44:00+05:00", confidence=0, verification_status="not_available"),
            deviation_from_upper_percent=38.6,
            anomaly=True,
            confidence=.82,
            explanation=(
                "Reported consumption is 38.6% above the weather- and operation-corrected upper expected range. "
                "The report and voyage conditions should be verified."
            ),
            disclaimer=(
                "Fuel variance is an indirect indicator and may have operational, reporting, maintenance, or weather explanations."
            ),
        )

    @staticmethod
    def _seed_economics() -> VoyageEconomics:
        breakdown = VoyageCostBreakdown(
            fuel=82000,
            port_fees=54000,
            crew=38000,
            handling=91000,
            operating_cost=55000,
        )
        return VoyageEconomics(
            vessel_id="caspian-star",
            voyage_id="voy-001",
            cargo_value=QuantityObservation(value=250000, unit="USD", source="Market-based cargo value estimate", source_timestamp="2026-08-10T17:43:00+05:00", confidence=.62, verification_status="estimated"),
            cost_breakdown=breakdown,
            estimated_voyage_cost=320000,
            value_cost_ratio=.78,
            typical_ratio=NumericRange(minimum=2.4, maximum=4.8, unit="ratio"),
            anomaly=True,
            confidence=.68,
            explanation=(
                "The estimated cargo-value-to-voyage-cost ratio is 0.78 versus a historical 2.4–4.8 range. "
                "The declared economics appear unusual and should be checked against commercial terms."
            ),
            disclaimer=(
                "This approximate economic comparison is an indicator for review, not evidence of a violation or unprofitable intent."
            ),
        )

    @staticmethod
    def _seed_connections() -> list[VesselConnection]:
        return [
            VesselConnection(
                id="CON-caspian-star-turan",
                vessel_id="caspian-star",
                related_vessel_id="turan",
                related_vessel_name="TURAN",
                encounters_total=14,
                encounters_last_six_months=9,
                average_duration_minutes=81,
                average_distance_m=240,
                open_sea_encounters=11,
                port_encounters=3,
                total_duration_minutes=1122,
                observation_months=6,
                strength="high",
                confidence=.91,
                explanation=(
                    "Connection strength is HIGH because 14 encounters were observed; 11 were outside ports, "
                    "with 240 m average distance and 18 h 42 min total duration over six months."
                ),
                disclaimer=(
                    "Repeated proximity establishes an observed connection only. It does not establish common control or wrongdoing."
                ),
            )
        ]

    def _seed_companies(self) -> None:
        self._companies["company-a"] = CompanyIntelligence(
            id="company-a",
            name="Caspian Marine Co.",
            country="Kazakhstan",
            role="owner_operator",
            vessel_ids=["caspian-star", "caspian-wind"],
            voyage_count=126,
            ports=["Baku", "Aktau", "Kuryk", "Turkmenbashi"],
            cargo_types=["Steel", "Grain", "Equipment", "General cargo"],
            event_count=19,
            event_type_counts={"route_deviation": 5, "ais_gap": 4, "vessel_encounter": 6, "advanced": 4},
            average_risk_score=71,
            recent_voyages=[
                CompanyVoyageSummary(voyage_id="voy-001", vessel_id="caspian-star", vessel_name="CASPIAN STAR", route="Baku → Aktau", status="in_progress", risk_score=91, risk_level="critical"),
                CompanyVoyageSummary(voyage_id="voy-002", vessel_id="caspian-star", vessel_name="CASPIAN STAR", route="Aktau → Baku", status="completed", risk_score=18, risk_level="low"),
                CompanyVoyageSummary(voyage_id="V-174", vessel_id="caspian-wind", vessel_name="CASPIAN WIND", route="Turkmenbashi → Aktau", status="in_progress", risk_score=51, risk_level="high"),
            ],
            risk_history=[
                CompanyRiskHistoryPoint(recorded_at="2026-08-01T18:00:00+05:00", average_risk_score=29, high_priority_vessels=0, model_version="CI-RISK-1.0"),
                CompanyRiskHistoryPoint(recorded_at="2026-08-10T17:40:00+05:00", average_risk_score=67.5, high_priority_vessels=2, model_version="CI-RISK-1.0"),
                CompanyRiskHistoryPoint(recorded_at="2026-08-10T17:46:00+05:00", average_risk_score=71, high_priority_vessels=2, model_version="CI-RISK-2.0"),
            ],
            connection_ids=["company-b"],
            source="Demo corporate registry extract",
            source_timestamp="2026-08-10T16:00:00+05:00",
            confidence=.79,
            verification_status="reported",
            disclaimer=(
                "Corporate relationships are source-attributed records for analyst review and do not establish beneficial control."
            ),
        )
        self._companies["company-b"] = CompanyIntelligence(
            id="company-b",
            name="Turan Maritime Services",
            country="Azerbaijan",
            role="operator",
            vessel_ids=["turan"],
            voyage_count=74,
            ports=["Baku", "Aktau", "Alat"],
            cargo_types=["General cargo", "Equipment"],
            event_count=12,
            event_type_counts={"vessel_encounter": 7, "ais_gap": 3, "route_deviation": 2},
            average_risk_score=71,
            recent_voyages=[
                CompanyVoyageSummary(voyage_id="V-088", vessel_id="turan", vessel_name="TURAN", route="Aktau → Baku", status="in_progress", risk_score=71, risk_level="high"),
            ],
            risk_history=[
                CompanyRiskHistoryPoint(recorded_at="2026-08-01T18:00:00+05:00", average_risk_score=33, high_priority_vessels=0, model_version="CI-RISK-1.0"),
                CompanyRiskHistoryPoint(recorded_at="2026-08-10T17:36:00+05:00", average_risk_score=71, high_priority_vessels=1, model_version="CI-RISK-1.0"),
            ],
            connection_ids=["company-a"],
            source="Demo corporate registry extract",
            source_timestamp="2026-08-10T16:00:00+05:00",
            confidence=.76,
            verification_status="reported",
            disclaimer=(
                "Corporate relationships are source-attributed records for analyst review and do not establish beneficial control."
            ),
        )
        self._company_vessels["company-a"] = [
            CompanyVesselSummary(id="caspian-star", name="CASPIAN STAR", vessel_type="Cargo vessel", flag="Kazakhstan", relationship="owned_operated", risk_score=91, risk_level="critical", voyage_count=63, event_count=9),
            CompanyVesselSummary(id="caspian-wind", name="CASPIAN WIND", vessel_type="General cargo", flag="Kazakhstan", relationship="owned", risk_score=51, risk_level="high", voyage_count=44, event_count=6),
        ]
        self._company_vessels["company-b"] = [
            CompanyVesselSummary(id="turan", name="TURAN", vessel_type="Cargo vessel", flag="Azerbaijan", relationship="operated", risk_score=71, risk_level="high", voyage_count=52, event_count=7),
        ]

    @staticmethod
    def _seed_network() -> InvestigationNetwork:
        return InvestigationNetwork(
            root_id="caspian-star",
            generated_at="2026-08-10T17:46:00+05:00",
            nodes=[
                GraphNode(id="caspian-star", type="vessel", label="CASPIAN STAR", risk_score=91, metadata={"flag": "Kazakhstan"}),
                GraphNode(id="turan", type="vessel", label="TURAN", risk_score=71, metadata={"flag": "Azerbaijan"}),
                GraphNode(id="company-a", type="company", label="Caspian Marine Co."),
                GraphNode(id="company-b", type="company", label="Turan Maritime Services"),
                GraphNode(id="owner-a", type="owner", label="Caspian Marine Co."),
                GraphNode(id="baku", type="port", label="Baku"),
                GraphNode(id="aktau", type="port", label="Aktau"),
                GraphNode(id="cargo-steel", type="cargo", label="Steel — 5,000 t", metadata={"verification_status": "reported"}),
                GraphNode(id="voy-001", type="voyage", label="Voyage #143 · Baku → Aktau"),
            ],
            edges=[
                GraphEdge(id="GE-001", source_id="caspian-star", target_id="company-a", type="operated_by", confidence=.88, explanation="Operator recorded in the vessel profile.", evidence=["Vessel registry profile"]),
                GraphEdge(id="GE-002", source_id="caspian-star", target_id="owner-a", type="owned_by", confidence=.79, explanation="Reported ownership relationship requires registry verification.", evidence=["Demo corporate registry extract"]),
                GraphEdge(id="GE-003", source_id="caspian-star", target_id="turan", type="encountered", strength="high", confidence=.91, explanation="14 detected encounters, 11 outside ports, over six months.", evidence=["14 encounters", "18 h 42 min total", "240 m average distance"]),
                GraphEdge(id="GE-004", source_id="turan", target_id="company-b", type="operated_by", confidence=.76, explanation="Reported operator relationship.", evidence=["Demo corporate registry extract"]),
                GraphEdge(id="GE-005", source_id="voy-001", target_id="baku", type="visited", confidence=.98, explanation="Voyage departed Baku.", evidence=["AIS pos-001"]),
                GraphEdge(id="GE-006", source_id="voy-001", target_id="aktau", type="visited", confidence=.92, explanation="Aktau is the reported destination.", evidence=["Voyage declaration"]),
                GraphEdge(id="GE-007", source_id="caspian-star", target_id="cargo-steel", type="carried", confidence=.94, explanation="5,000 t steel was reported in the port declaration.", evidence=["PORT-BAK-2026-0810-143"]),
                GraphEdge(id="GE-008", source_id="company-a", target_id="company-b", type="related_to", strength="medium", confidence=.61, explanation="The companies are connected through repeated vessel encounters; this does not establish corporate control.", evidence=["CASPIAN STAR ↔ TURAN encounter aggregate"]),
                GraphEdge(id="GE-009", source_id="caspian-star", target_id="voy-001", type="related_to", confidence=.98, explanation="Voyage #143 is the current voyage reconstructed for CASPIAN STAR.", evidence=["Voyage continuity", "AIS positions", "Baku departure", "Aktau destination"]),
            ],
            disclaimer=ADVANCED_DISCLAIMER,
        )

    def _seed_events_and_signals(self) -> None:
        specifications = [
            ("ADV-6001", "cargo_anomaly", "Cargo declaration context requires review", "medium", .74, 8, 8, 1, 0, "cargo_consistency", True, ["Cargo value is estimated", "Cargo/draught comparison uses the same declaration"]),
            ("ADV-6002", "cargo_draught_mismatch", "Cargo / draught mismatch", "high", .87, 13, 13, 3, 3, "cargo_consistency", False, ["Reported cargo: 5,000 t steel", "Expected draught change: 1.05–1.30 m", "Observed change: 0.30 m", "63 vessel-specific samples"]),
            ("ADV-6003", "fuel_anomaly", "Fuel consumption outside corrected range", "high", .82, 9, 9, 2, 2, "voyage_energy", False, ["Expected: 38–44 t", "Reported: 61 t", "Weather correction: +4%", "Operational correction: +6%"]),
            ("ADV-6004", "economic_anomaly", "Voyage economics outside historical range", "medium", .68, 6, 6, 1, 1, "voyage_economics", False, ["Cargo value estimate: USD 250,000", "Voyage cost estimate: USD 320,000", "Ratio: 0.78 vs 2.4–4.8"]),
            ("ADV-6005", "unusual_connection", "Repeated vessel connection context", "medium", .84, 5, 5, 1, 1, "network_context", False, ["14 encounters", "11 outside ports", "18 h 42 min total duration"]),
        ]
        for index, (event_id, event_type, label, severity, confidence, base, adjusted, weighted, effective, group, deduped, evidence) in enumerate(specifications):
            started = f"2026-08-10T17:{41 + index:02d}:00+05:00"
            event = DetectedEvent(
                id=event_id,
                type=event_type,
                vessel_id="caspian-star",
                vessel_name="CASPIAN STAR",
                related_vessel_id="turan" if event_type == "unusual_connection" else None,
                related_vessel_name="TURAN" if event_type == "unusual_connection" else None,
                voyage_id="voy-001",
                started_at=started,
                ended_at=started,
                latitude=42.05,
                longitude=50.62,
                severity=severity,
                confidence=confidence,
                status="resolved",
                data={
                    "model_version": self.model_version,
                    "deduplication_group": group,
                    "confidence_weighted_score": weighted,
                    "effective_risk_contribution": effective,
                },
                explanation=self._event_explanation(event_type),
                factors=evidence,
                created_at=started,
            )
            self._events[event.id] = event
            self._signals[event.id] = AdvancedRiskSignal(
                id=f"RF-{event.id}",
                event_id=event.id,
                vessel_id=event.vessel_id,
                voyage_id=event.voyage_id or "voy-001",
                type=event.type,
                label=label,
                base_score=base,
                adjusted_score=adjusted,
                confidence_weighted_score=weighted,
                effective_score=effective,
                confidence=confidence,
                deduplication_group=group,
                deduplicated=deduped,
                source_timestamp=started,
                explanation=event.explanation,
                evidence=evidence,
            )

    @staticmethod
    def _event_explanation(event_type: EventType) -> str:
        descriptions = {
            "cargo_anomaly": "Cargo values and logistics include estimated fields that merit source verification; this signal is deduplicated against the stronger draught comparison.",
            "cargo_draught_mismatch": "Observed draught change is below the vessel-specific range expected from the reported loading operation. This is an inconsistency, not evidence of undeclared cargo.",
            "fuel_anomaly": "Reported fuel is above the weather- and operation-corrected range. Reporting and operational explanations remain possible.",
            "economic_anomaly": "Estimated voyage economics are outside the historical range and should be checked against commercial terms.",
            "unusual_connection": "Repeated encounters provide network context only and do not transfer another vessel's risk score.",
            "unexplained_load_change": "Draught changed without a corresponding reported cargo operation. Ballast, trim and source quality should be reviewed before drawing conclusions.",
        }
        return descriptions.get(event_type, "Structured analytical signal requires source review.")

    @staticmethod
    def _build_intelligence(
        cargo: CargoIntelligence,
        fuel: FuelAnalysis,
        economics: VoyageEconomics,
        connections: list[VesselConnection],
    ) -> VoyageIntelligenceSummary:
        factors = [
            IntelligenceSummaryFactor(type="route_deviation", title="Route deviation", severity="medium", confidence=.92, source_event_id="EV-2801", explanation="38 km deviation from the historical corridor."),
            IntelligenceSummaryFactor(type="ais_gap", title="AIS gap", severity="high", confidence=.98, source_event_id="EV-2802", explanation="AIS data was absent for 3 h 15 min in a high-coverage area."),
            IntelligenceSummaryFactor(type="vessel_encounter", title="Offshore vessel encounter", severity="high", confidence=.93, source_event_id="EV-2803", explanation="CASPIAN STAR and TURAN were observed 174 m apart for 2 h 47 min."),
            IntelligenceSummaryFactor(type="draught_change", title="Draught change", severity="medium", confidence=.96, source_event_id="EV-2804", explanation="Reported draught changed during the voyage and requires source-quality review."),
            IntelligenceSummaryFactor(type="cargo_draught_mismatch", title="Cargo / draught mismatch", severity="high", confidence=.87, source_event_id="ADV-6002", explanation="Observed 0.30 m versus vessel-specific expected 1.05–1.30 m."),
            IntelligenceSummaryFactor(type="fuel_anomaly", title="Unusual fuel consumption", severity="high", confidence=.82, source_event_id="ADV-6003", explanation="Reported 61 t versus corrected expected 38–44 t."),
            IntelligenceSummaryFactor(type="economic_anomaly", title="Economic consistency low", severity="medium", confidence=.68, source_event_id="ADV-6004", explanation="Estimated value/cost ratio 0.78 versus historical 2.4–4.8."),
        ]
        return VoyageIntelligenceSummary(
            vessel_id="caspian-star",
            vessel_name="CASPIAN STAR",
            voyage_id="voy-001",
            origin="Baku",
            destination="Aktau",
            route_deviation_km=38,
            ais_gap_minutes=195,
            encounter_vessel_name="TURAN",
            encounter_duration_minutes=167,
            cargo=cargo,
            fuel=fuel,
            economics=economics,
            connections=connections,
            factors=factors,
            significant_factor_count=7,
            base_risk_score=84,
            advanced_adjustment=7,
            risk_score=91,
            summary=(
                "7 significant factors were detected. The voyage differs substantially from parts of the vessel's "
                "historical profile. The combined observations merit analyst review and source verification."
            ),
            main_factor_titles=[
                "AIS gap",
                "Offshore vessel encounter",
                "Draught change",
                "Cargo / draught mismatch",
                "Unusual fuel consumption",
            ],
            generated_at="2026-08-10T17:46:00+05:00",
            disclaimer=ADVANCED_DISCLAIMER,
        )


advanced_analytics = AdvancedAnalyticsService()
