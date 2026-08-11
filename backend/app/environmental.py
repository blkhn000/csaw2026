from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any

from fastapi import HTTPException

from .models import (
    Coordinates,
    EnvironmentalAssociationFactor,
    EnvironmentalCandidate,
    EnvironmentalCandidateSearchResult,
    EnvironmentalEvent,
    EnvironmentalEventList,
    EnvironmentalGeometry,
    EnvironmentalObservation,
    EnvironmentalRawData,
    EnvironmentalRawIngestRequest,
    EnvironmentalReconstruction,
    EnvironmentalReconstructionStep,
    EnvironmentalReplay,
    EnvironmentalReplayFrame,
    EnvironmentalReplayVessel,
    EnvironmentalReview,
    EnvironmentalReviewRequest,
    EnvironmentalReviewResult,
    EnvironmentalRiskContext,
    EnvironmentalTimeline,
    EnvironmentalTimelineItem,
    EnvironmentalTrackPoint,
    VesselEnvironmentProfile,
    VesselEnvironmentalHistoryItem,
)


ENVIRONMENTAL_MODEL_VERSION = "CI-ENV-1.0"
ENVIRONMENTAL_RISK_MODEL_VERSION = "CI-ENV-RISK-1.0"
ENVIRONMENTAL_DISCLAIMER = (
    "Environmental association identifies vessels whose historical movement is relevant to review. "
    "It does not establish a pollution source, legal responsibility, intent, or misconduct."
)


def _polygon(center_lon: float, center_lat: float, width: float, height: float) -> EnvironmentalGeometry:
    west, east = center_lon - width / 2, center_lon + width / 2
    south, north = center_lat - height / 2, center_lat + height / 2
    return EnvironmentalGeometry(
        type="Polygon",
        coordinates=[[[west, south], [east, south], [east, north], [west, north], [west, south]]],
    )


def _multi_polygon(center_lon: float, center_lat: float) -> EnvironmentalGeometry:
    first = _polygon(center_lon - .012, center_lat, .042, .026).coordinates
    second = _polygon(center_lon + .026, center_lat + .011, .024, .018).coordinates
    return EnvironmentalGeometry(type="MultiPolygon", coordinates=[first, second])


class EnvironmentalDataGateway:
    """Provider-neutral gateway retaining raw payloads before normalization.

    Providers can register an adapter without changing the environmental event
    service. The default adapter accepts the documented normalized field names,
    which covers external APIs, preprocessed satellite products, manual entries,
    and deterministic demo inputs.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    def register_adapter(
        self, provider: str, adapter: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        self._adapters[provider.casefold()] = adapter

    def capture_raw(
        self,
        request: EnvironmentalRawIngestRequest,
        *,
        raw_id: str,
        created_by: str,
        received_at: str,
    ) -> EnvironmentalRawData:
        canonical = json.dumps(request.payload, sort_keys=True, separators=(",", ":"), default=str)
        return EnvironmentalRawData(
            id=raw_id,
            provider=request.provider,
            input_type=request.input_type,
            received_at=received_at,
            observed_at=request.observed_at,
            source_reference=request.source_reference,
            payload=request.payload,
            checksum=f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}",
            created_by=created_by,
        )

    def normalize(
        self,
        request: EnvironmentalRawIngestRequest,
        *,
        event_id: str,
        raw_id: str,
        created_at: str,
    ) -> EnvironmentalEvent:
        adapter = self._adapters.get(request.provider.casefold(), lambda payload: payload)
        payload = adapter(dict(request.payload))
        geometry_value = payload.get("geometry")
        if not geometry_value:
            raise HTTPException(status_code=422, detail="Environmental payload requires GeoJSON geometry")
        try:
            geometry = EnvironmentalGeometry.model_validate(geometry_value)
            center_value = payload.get("center") or {}
            center = Coordinates(
                latitude=float(center_value["latitude"]),
                longitude=float(center_value["longitude"]),
            )
            area_km2 = float(payload["area_km2"])
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid normalized environmental payload: {exc}") from exc

        event_type = str(payload.get("type", "UNKNOWN_POLLUTION")).upper().replace(" ", "_")
        observations = [EnvironmentalObservation.model_validate(item) for item in payload.get("environmental_data", [])]
        return EnvironmentalEvent(
            id=event_id,
            alias=payload.get("alias"),
            type=event_type,
            title=payload.get("title", "Environmental finding requires analysis"),
            detected_at=payload.get("detected_at", request.observed_at),
            estimated_started_at=payload.get("estimated_started_at"),
            estimated_ended_at=payload.get("estimated_ended_at"),
            geometry=geometry,
            center=center,
            area_km2=area_km2,
            detection_source=payload.get("detection_source", request.provider),
            source_reference=request.source_reference,
            raw_data_id=raw_id,
            confidence=float(payload.get("confidence", request.confidence)),
            status=payload.get("status", "DETECTED"),
            priority=payload.get("priority", "MEDIUM"),
            environmental_data=observations,
            provenance=payload.get("provenance", "OBSERVED"),
            summary=payload.get(
                "summary",
                "A source-attributed environmental finding was recorded and requires human review.",
            ),
            disclaimer=payload.get("disclaimer", ENVIRONMENTAL_DISCLAIMER),
            created_at=created_at,
            updated_at=created_at,
        )


class EnvironmentalIntelligenceService:
    model_version = ENVIRONMENTAL_MODEL_VERSION

    def __init__(self) -> None:
        self.gateway = EnvironmentalDataGateway()
        self._events: dict[str, EnvironmentalEvent] = {}
        self._aliases: dict[str, str] = {}
        self._raw_data: dict[str, EnvironmentalRawData] = {}
        self._candidate_results: dict[str, EnvironmentalCandidateSearchResult] = {}
        self._reconstructions: dict[str, EnvironmentalReconstruction] = {}
        self._timelines: dict[str, EnvironmentalTimeline] = {}
        self._replays: dict[str, EnvironmentalReplay] = {}
        self._vessel_profiles: dict[str, VesselEnvironmentProfile] = {}
        self._reviews: dict[str, list[EnvironmentalReview]] = {}
        # Demo center already reserves event/raw numbers through 145. New provider
        # ingests must never overwrite ENV-143..145 in the in-memory registry.
        self._event_counter = 145
        self._raw_counter = 145
        self._review_counter = 40
        self._seed_demo()

    def list_events(self, status: str | None = None) -> EnvironmentalEventList:
        all_items = list(self._events.values())
        filtered = [item for item in all_items if status is None or item.status == status]
        filtered.sort(key=lambda item: item.detected_at, reverse=True)
        active_statuses = {"DETECTED", "ANALYZING", "UNDER REVIEW", "INVESTIGATION"}
        result = EnvironmentalEventList(
            items=[item.model_copy(deep=True) for item in filtered],
            total=len(filtered),
            active_count=sum(item.status in active_statuses for item in all_items),
            high_priority_count=sum(
                item.status in active_statuses and item.priority in {"HIGH", "CRITICAL"}
                for item in all_items
            ),
            in_investigation_count=sum(item.status == "INVESTIGATION" for item in all_items),
            resolved_count=sum(item.status == "RESOLVED" for item in all_items),
        )
        return result.model_copy(deep=True)

    def get_event(self, event_id: str) -> EnvironmentalEvent:
        resolved_id = self._aliases.get(event_id.upper(), event_id)
        return self._copy_or_404(self._events, resolved_id, "Environmental event not found")

    def create_event(
        self, request: EnvironmentalRawIngestRequest, *, created_by: str,
    ) -> EnvironmentalEvent:
        self._event_counter += 1
        self._raw_counter += 1
        now = datetime.now(timezone.utc).isoformat()
        event_id = f"ENV-{datetime.now(timezone.utc).year}-{self._event_counter:05d}"
        raw_id = f"ENV-RAW-{self._raw_counter:05d}"
        raw = self.gateway.capture_raw(
            request, raw_id=raw_id, created_by=created_by, received_at=now,
        )
        event = self.gateway.normalize(
            request, event_id=event_id, raw_id=raw_id, created_at=now,
        )
        raw.event_id = event.id
        self._raw_data[raw.id] = raw
        self._events[event.id] = event
        if event.alias:
            self._aliases[event.alias.upper()] = event.id
        return event.model_copy(deep=True)

    def get_raw_for_event(self, event_id: str) -> EnvironmentalRawData:
        event = self.get_event(event_id)
        return self._copy_or_404(self._raw_data, event.raw_data_id, "Environmental raw data not found")

    def get_candidates(
        self, event_id: str, *, include_extended: bool = False,
    ) -> EnvironmentalCandidateSearchResult:
        event = self.get_event(event_id)
        result = self._copy_or_404(
            self._candidate_results, event.id, "Environmental candidates not found",
        )
        if not include_extended:
            result.extended_candidates = []
        return result

    def get_reconstruction(self, event_id: str) -> EnvironmentalReconstruction:
        event = self.get_event(event_id)
        return self._copy_or_404(
            self._reconstructions, event.id, "Environmental reconstruction not found",
        )

    def get_timeline(self, event_id: str) -> EnvironmentalTimeline:
        event = self.get_event(event_id)
        return self._copy_or_404(self._timelines, event.id, "Environmental timeline not found")

    def get_replay(self, event_id: str) -> EnvironmentalReplay:
        event = self.get_event(event_id)
        return self._copy_or_404(self._replays, event.id, "Environmental replay not found")

    def get_vessel_environment(self, vessel_id: str) -> VesselEnvironmentProfile:
        return self._copy_or_404(
            self._vessel_profiles, vessel_id, "Vessel environmental history not found",
        )

    def get_risk_context(self, event_id: str, vessel_id: str) -> EnvironmentalRiskContext:
        result = self.get_candidates(event_id, include_extended=True)
        candidate = next(
            (item for item in result.candidates + result.extended_candidates if item.vessel_id == vessel_id),
            None,
        )
        if candidate is None or candidate.risk_context is None:
            raise HTTPException(status_code=404, detail="Environmental risk context not found")
        return candidate.risk_context.model_copy(deep=True)

    def review_event(
        self,
        event_id: str,
        request: EnvironmentalReviewRequest,
        *,
        reviewer: str,
    ) -> EnvironmentalReviewResult:
        resolved_id = self._aliases.get(event_id.upper(), event_id)
        event = self._events.get(resolved_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Environmental event not found")
        self._review_counter += 1
        reviewed_at = datetime.now(timezone.utc).isoformat()
        review = EnvironmentalReview(
            id=f"ENV-REV-{self._review_counter:04d}",
            event_id=event.id,
            outcome=request.outcome,
            source_classification=request.source_classification,
            note=request.note,
            reviewer=reviewer,
            reviewed_at=reviewed_at,
        )
        self._reviews.setdefault(event.id, []).append(review)
        if request.outcome == "FALSE POSITIVE":
            event.status = "FALSE POSITIVE"
        elif request.outcome == "CONFIRMED POLLUTION":
            event.status = "INVESTIGATION"
        else:
            event.status = "UNDER REVIEW"
        event.updated_at = reviewed_at
        return EnvironmentalReviewResult(
            event=event.model_copy(deep=True), review=review.model_copy(deep=True),
        )

    def list_reviews(self, event_id: str) -> list[EnvironmentalReview]:
        event = self.get_event(event_id)
        return [item.model_copy(deep=True) for item in self._reviews.get(event.id, [])]

    def link_investigation(self, event_id: str, investigation_id: str) -> EnvironmentalEvent:
        resolved_id = self._aliases.get(event_id.upper(), event_id)
        event = self._events.get(resolved_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Environmental event not found")
        event.investigation_id = investigation_id
        event.status = "INVESTIGATION"
        event.updated_at = datetime.now(timezone.utc).isoformat()
        return event.model_copy(deep=True)

    @staticmethod
    def _copy_or_404(store: dict[str, Any], key: str, detail: str):
        value = store.get(key)
        if value is None:
            raise HTTPException(status_code=404, detail=detail)
        return value.model_copy(deep=True)

    def _seed_demo(self) -> None:
        event = self._seed_primary_event()
        self._events[event.id] = event
        self._aliases[event.alias or "ENV-142"] = event.id
        self._seed_center_events()
        self._candidate_results[event.id] = self._seed_candidates(event)
        self._reconstructions[event.id] = self._seed_reconstruction(event)
        self._timelines[event.id] = self._seed_timeline(event)
        self._replays[event.id] = self._seed_replay(event)
        self._seed_vessel_profiles(event)

    def _seed_primary_event(self) -> EnvironmentalEvent:
        raw_id = "ENV-RAW-00142"
        payload = {
            "type": "OIL_POLLUTION",
            "geometry": _polygon(51.060, 43.210, .054, .038).model_dump(),
            "center": {"latitude": 43.210, "longitude": 51.060},
            "area_km2": 3.4,
            "confidence": .87,
            "product": "preprocessed satellite observation",
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self._raw_data[raw_id] = EnvironmentalRawData(
            id=raw_id,
            event_id="ENV-2026-00142",
            provider="Caspian EO Gateway",
            input_type="PREPROCESSED_SATELLITE",
            received_at="2026-05-14T08:43:00+05:00",
            observed_at="2026-05-14T08:40:00+05:00",
            source_reference="SAT-S1-20260514-0840-142",
            payload=payload,
            checksum=f"sha256:{sha256(canonical.encode('utf-8')).hexdigest()}",
            created_by="environment-gateway",
        )
        environmental_data = [
            EnvironmentalObservation(
                id="ENV-OBS-142-WIND", category="wind", parameter="surface wind speed",
                value=14.0, unit="kn", direction_degrees=105,
                observed_at="2026-05-14T08:30:00+05:00", source="Caspian weather analysis",
                source_reference="WX-20260514-0830", confidence=.84, provenance="ESTIMATED",
            ),
            EnvironmentalObservation(
                id="ENV-OBS-142-CURRENT", category="current", parameter="surface current speed",
                value=.7, unit="kn", direction_degrees=310,
                observed_at="2026-05-14T08:30:00+05:00", source="Caspian current hindcast",
                source_reference="CUR-20260514-0830", confidence=.78, provenance="ESTIMATED",
            ),
            EnvironmentalObservation(
                id="ENV-OBS-142-WAVES", category="weather", parameter="significant wave height",
                value=2.1, unit="m", direction_degrees=118,
                observed_at="2026-05-14T08:30:00+05:00", source="Caspian weather analysis",
                source_reference="WX-20260514-0830", confidence=.82, provenance="ESTIMATED",
            ),
        ]
        return EnvironmentalEvent(
            id="ENV-2026-00142", alias="ENV-142", type="OIL_POLLUTION",
            title="Oil-like pollution signature", detected_at="2026-05-14T08:40:00+05:00",
            estimated_started_at="2026-05-14T03:20:00+05:00",
            estimated_ended_at="2026-05-14T05:40:00+05:00",
            geometry=_polygon(51.060, 43.210, .054, .038),
            center=Coordinates(latitude=43.210, longitude=51.060), area_km2=3.4,
            detection_source="Preprocessed satellite observation",
            source_reference="SAT-S1-20260514-0840-142", raw_data_id=raw_id,
            confidence=.87, status="UNDER REVIEW", priority="HIGH",
            environmental_data=environmental_data, provenance="OBSERVED",
            summary=(
                "An oil-like surface signature covering approximately 3.4 km² was observed at 08:40. "
                "Its classification and possible source remain under human review."
            ),
            disclaimer=ENVIRONMENTAL_DISCLAIMER,
            created_at="2026-05-14T08:43:00+05:00", updated_at="2026-05-14T09:12:00+05:00",
        )

    def _seed_center_events(self) -> None:
        # Together with ENV-2026-00142 this yields 4 active, 1 high priority,
        # 2 in investigation, and 17 resolved records for the Environmental Center.
        active_specs = [
            (143, "FLOATING_WASTE", "Floating material observation", "ANALYZING", "MEDIUM", "2026-05-13T16:20:00+05:00"),
            (144, "UNKNOWN_POLLUTION", "Coastal water anomaly", "INVESTIGATION", "MEDIUM", "2026-05-12T11:05:00+05:00"),
            (145, "ALGAE_BLOOM", "Bloom-like spectral observation", "INVESTIGATION", "LOW", "2026-05-11T09:25:00+05:00"),
        ]
        resolved_specs = [
            (100 + index, "OIL_POLLUTION" if index % 3 == 0 else "FLOATING_WASTE", f"Resolved environmental observation {index + 1}", "RESOLVED", "MEDIUM" if index < 4 else "LOW", f"2026-{month:02d}-{day:02d}T10:00:00+05:00")
            for index, (month, day) in enumerate(
                [(5, 9), (5, 7), (5, 2), (4, 28), (4, 21), (4, 14), (4, 3), (3, 29), (3, 18), (3, 8), (2, 25), (2, 17), (2, 5), (1, 28), (1, 22), (1, 14), (1, 4)]
            )
        ]
        for index, event_type, title, status, priority, detected_at in active_specs + resolved_specs:
            event_id = f"ENV-2026-{index:05d}"
            raw_id = f"ENV-RAW-{index:05d}"
            geometry = _polygon(50.1 + index % 7 * .22, 41.2 + index % 5 * .31, .025, .018)
            center = Coordinates(
                latitude=geometry.coordinates[0][0][1] + .009,
                longitude=geometry.coordinates[0][0][0] + .0125,
            )
            raw_payload = {"type": event_type, "geometry": geometry.model_dump(), "area_km2": 1.2}
            checksum_payload = json.dumps(raw_payload, sort_keys=True, separators=(",", ":"))
            self._raw_data[raw_id] = EnvironmentalRawData(
                id=raw_id, event_id=event_id, provider="Environmental demo feed", input_type="DEMO",
                received_at=detected_at, observed_at=detected_at,
                source_reference=f"ENV-DEMO-{index:05d}", payload=raw_payload,
                checksum=f"sha256:{sha256(checksum_payload.encode('utf-8')).hexdigest()}",
                created_by="demo-seed",
            )
            self._events[event_id] = EnvironmentalEvent(
                id=event_id, alias=f"ENV-{index}", type=event_type, title=title,
                detected_at=detected_at, geometry=geometry, center=center,
                area_km2=round(1.2 + index % 6 * .35, 2), detection_source="Environmental demo feed",
                source_reference=f"ENV-DEMO-{index:05d}", raw_data_id=raw_id,
                confidence=round(.61 + index % 5 * .05, 2), status=status, priority=priority,
                summary="Source-attributed environmental observation retained for operational history.",
                disclaimer=ENVIRONMENTAL_DISCLAIMER, created_at=detected_at, updated_at=detected_at,
            )
            self._aliases[f"ENV-{index}"] = event_id

    def _seed_candidates(self, event: EnvironmentalEvent) -> EnvironmentalCandidateSearchResult:
        candidates = [
            self._candidate(
                event, "ENV-CAND-142-CS", "caspian-star", "CASPIAN STAR", .8, 94, True,
                "HIGH", 86, "2026-05-14T03:35:00+05:00", 43.164, 51.018, 4.2, 56,
                ["TRACK-CS-20260514", "AIS-GAP-CS-20260514", event.id],
                risk=(91, 8, 99),
            ),
            self._candidate(
                event, "ENV-CAND-142-TU", "turan", "TURAN", 2.4, 72, False,
                "MEDIUM", 64, "2026-05-14T04:10:00+05:00", 43.143, 51.004, 6.1, 42,
                ["TRACK-TURAN-20260514", event.id],
            ),
            self._candidate(
                event, "ENV-CAND-142-BE", "baku-express", "BAKU EXPRESS", 7.1, 31, False,
                "LOW", 31, "2026-05-14T04:45:00+05:00", 43.094, 50.962, 10.4, 37,
                ["TRACK-BAKU-EXPRESS-20260514", event.id],
            ),
        ]
        excluded_names = [
            ("absheron", "ABSHERON"), ("khazar-wave", "KHAZAR WAVE"),
            ("volga-spirit", "VOLGA SPIRIT"), ("aktau-trader", "AKTAU TRADER"),
            ("caspian-wind", "CASPIAN WIND"), ("alatau", "ALATAU"),
            ("karabakh", "KARABAKH"), ("derbent", "DERBENT"), ("mangystau", "MANGYSTAU"),
        ]
        extended = [
            self._candidate(
                event, f"ENV-CAND-142-X{index}", vessel_id, name,
                11.0 + index * 2.3, max(2, 23 - index * 2), False, "EXCLUDED", max(2, 21 - index * 2),
                f"2026-05-14T0{3 + index % 5}:10:00+05:00",
                43.03 + index * .018, 50.82 + index * .025, 8 + index * .4, 25 + index * 8,
                [f"TRACK-{vessel_id.upper()}-20260514", event.id],
            )
            for index, (vessel_id, name) in enumerate(excluded_names, start=1)
        ]
        return EnvironmentalCandidateSearchResult(
            event_id=event.id,
            search_started_at="2026-05-14T02:20:00+05:00",
            search_ended_at="2026-05-14T08:40:00+05:00",
            searched_candidate_count=12, relevant_candidate_count=3,
            candidates=candidates, extended_candidates=extended,
            method=(
                "Historical AIS tracks were intersected with the reconstructed origin envelope and scored by "
                "distance, time overlap, movement direction, vessel type, speed, route, AIS gaps, stops, and prior context."
            ),
            disclaimer=ENVIRONMENTAL_DISCLAIMER,
        )

    def _candidate(
        self,
        event: EnvironmentalEvent,
        candidate_id: str,
        vessel_id: str,
        vessel_name: str,
        distance_km: float,
        overlap: float,
        ais_gap: bool,
        relevance: str,
        score: int,
        at: str,
        lat: float,
        lon: float,
        speed: float,
        course: float,
        evidence_ids: list[str],
        *,
        risk: tuple[int, int, int] | None = None,
    ) -> EnvironmentalCandidate:
        factors = [
            EnvironmentalAssociationFactor(
                id=f"{candidate_id}-DIST", label="Distance to reconstructed origin",
                observed=f"{distance_km:.1f} km", contribution=max(0, 36 - round(distance_km * 3)),
                provenance="ESTIMATED", source_ids=["ENV-REC-00142", evidence_ids[0]],
                interpretation="Smaller distance raises review relevance but does not establish source attribution.",
            ),
            EnvironmentalAssociationFactor(
                id=f"{candidate_id}-TIME", label="Temporal overlap",
                observed=f"{overlap:.0f}%", contribution=round(overlap * .32),
                provenance="INFERRED", source_ids=["ENV-REC-00142", evidence_ids[0]],
                interpretation="The vessel track overlaps part of the estimated origin interval.",
            ),
            EnvironmentalAssociationFactor(
                id=f"{candidate_id}-AIS", label="AIS continuity",
                observed="Gap observed" if ais_gap else "Track available",
                contribution=20 if ais_gap else 0, provenance="OBSERVED",
                source_ids=[evidence_ids[1] if ais_gap else evidence_ids[0]],
                interpretation=(
                    "Missing AIS limits reconstruction and requires review; it does not prove concealment."
                    if ais_gap else "Available AIS supports the historical track comparison."
                ),
            ),
        ]
        risk_context = None
        if risk:
            maritime, adjustment, combined = risk
            risk_factors = [
                EnvironmentalAssociationFactor(
                    id="ENV-RF-142-CS-PROXIMITY", code="ENVIRONMENTAL_PROXIMITY",
                    label="Environmental proximity", observed=f"{distance_km:.1f} km from reconstructed origin",
                    contribution=3, provenance="ESTIMATED", source_ids=["ENV-REC-00142", evidence_ids[0]],
                    interpretation="Close passage raises review priority but does not identify a pollution source.",
                ),
                EnvironmentalAssociationFactor(
                    id="ENV-RF-142-CS-TIME", code="ENVIRONMENTAL_TIME_OVERLAP",
                    label="Environmental time overlap", observed=f"{overlap:.0f}% overlap",
                    contribution=2, provenance="INFERRED", source_ids=["ENV-REC-00142", evidence_ids[0]],
                    interpretation="Temporal overlap is model-derived and remains an association, not causation.",
                ),
                EnvironmentalAssociationFactor(
                    id="ENV-RF-142-CS-ROUTE", code="ENVIRONMENTAL_ROUTE_MATCH",
                    label="Environmental route match", observed="Movement direction consistent with review corridor",
                    contribution=1, provenance="INFERRED", source_ids=["ENV-REC-00142", evidence_ids[0]],
                    interpretation="Route consistency is supporting context and cannot establish responsibility.",
                ),
                EnvironmentalAssociationFactor(
                    id="ENV-RF-142-CS-ASSOCIATION", code="ENVIRONMENTAL_ASSOCIATION",
                    label="Environmental association", observed=f"{relevance} relevance · score {score}",
                    contribution=2, provenance="INFERRED", source_ids=[event.id, candidate_id, *evidence_ids],
                    interpretation="Aggregate association is capped and pending analyst review.",
                ),
            ]
            risk_context = EnvironmentalRiskContext(
                id="ENV-RISK-142-CS", event_id=event.id, vessel_id=vessel_id,
                maritime_risk_score=maritime, environmental_adjustment_raw=adjustment,
                environmental_adjustment_effective=adjustment,
                combined_context_score=combined, status="UNDER REVIEW", factors=risk_factors,
                source_ids=[event.id, candidate_id, "ENV-REC-00142", *evidence_ids],
                model_version=ENVIRONMENTAL_RISK_MODEL_VERSION,
                explanation=(
                    "The existing maritime score remains unchanged. Four traceable environmental factors total +8 "
                    "and raise analyst-review priority to 99 while source association remains unconfirmed."
                ),
                disclaimer=(
                    "The +8 value is contextual and under review. It is not written into the canonical CI-RISK-2.0 "
                    "assessment and does not establish that the vessel caused the observation."
                ),
            )
        return EnvironmentalCandidate(
            id=candidate_id, event_id=event.id, vessel_id=vessel_id, vessel_name=vessel_name,
            distance_km=distance_km, temporal_overlap_percent=overlap, ais_gap=ais_gap,
            relevance=relevance, association_score=score, factors=factors,
            track=[
                EnvironmentalTrackPoint(
                    timestamp=at, latitude=lat, longitude=lon, speed_kn=speed,
                    course_degrees=course, source_reference=evidence_ids[0],
                ),
                EnvironmentalTrackPoint(
                    timestamp="2026-05-14T05:40:00+05:00", latitude=lat + .026,
                    longitude=lon + .031, speed_kn=max(.2, speed - .8),
                    course_degrees=course, source_reference=evidence_ids[0],
                    provenance="ESTIMATED" if ais_gap else "OBSERVED",
                ),
            ],
            evidence_ids=evidence_ids, risk_context=risk_context,
            explanation=(
                f"{vessel_name} is ranked {relevance} for review from historical spatial and temporal overlap. "
                "The ranking is an association estimate, not a finding of causation."
            ),
            disclaimer=ENVIRONMENTAL_DISCLAIMER,
        )

    def _seed_reconstruction(self, event: EnvironmentalEvent) -> EnvironmentalReconstruction:
        origin = _multi_polygon(51.015, 43.166)
        wind = event.environmental_data[0]
        current = event.environmental_data[1]
        steps = [
            EnvironmentalReconstructionStep(
                timestamp="2026-05-14T03:20:00+05:00", geometry=origin,
                center=Coordinates(latitude=43.166, longitude=51.015), area_km2=.9,
            ),
            EnvironmentalReconstructionStep(
                timestamp="2026-05-14T05:40:00+05:00", geometry=_polygon(51.026, 43.178, .038, .026),
                center=Coordinates(latitude=43.178, longitude=51.026), area_km2=1.5,
            ),
            EnvironmentalReconstructionStep(
                timestamp="2026-05-14T07:00:00+05:00", geometry=_polygon(51.043, 43.194, .046, .032),
                center=Coordinates(latitude=43.194, longitude=51.043), area_km2=2.4,
            ),
            EnvironmentalReconstructionStep(
                timestamp=event.detected_at, geometry=event.geometry,
                center=event.center, area_km2=event.area_km2,
            ),
        ]
        return EnvironmentalReconstruction(
            id="ENV-REC-00142", event_id=event.id, current_geometry=event.geometry,
            origin_geometry=origin, estimated_origin_from="2026-05-14T03:20:00+05:00",
            estimated_origin_to="2026-05-14T05:40:00+05:00", wind=wind, current=current,
            weather=[event.environmental_data[2]], steps=steps, confidence=.73,
            model_version=ENVIRONMENTAL_MODEL_VERSION,
            method=(
                "Backward surface-drift reconstruction using source geometry, wind, surface current, "
                "wave conditions, and uncertainty growth."
            ),
            limitation=(
                "The origin is an interval and area envelope, not an exact time or release point. "
                "Weather and current inputs are modeled estimates."
            ),
            disclaimer=ENVIRONMENTAL_DISCLAIMER,
        )

    def _seed_timeline(self, event: EnvironmentalEvent) -> EnvironmentalTimeline:
        items = [
            ("ENV-TL-142-01", "2026-05-14T03:20:00+05:00", "ORIGIN_WINDOW", "Estimated origin interval opens", "Backward reconstruction places the earliest plausible origin in the modeled envelope.", None, ["ENV-REC-00142"], "ESTIMATED"),
            ("ENV-TL-142-02", "2026-05-14T03:35:00+05:00", "VESSEL_POSITION", "CASPIAN STAR near origin envelope", "Historical AIS position is 0.8 km from the reconstructed origin envelope.", "caspian-star", ["TRACK-CS-20260514"], "OBSERVED"),
            ("ENV-TL-142-03", "2026-05-14T04:10:00+05:00", "VESSEL_POSITION", "TURAN crosses search area", "Historical AIS track overlaps 72% of the relevant time-space window.", "turan", ["TRACK-TURAN-20260514"], "OBSERVED"),
            ("ENV-TL-142-04", "2026-05-14T04:22:00+05:00", "AIS_GAP", "CASPIAN STAR AIS gap begins", "AIS continuity is unavailable during part of the estimated origin interval.", "caspian-star", ["AIS-GAP-CS-20260514"], "OBSERVED"),
            ("ENV-TL-142-05", "2026-05-14T05:40:00+05:00", "ORIGIN_WINDOW", "Estimated origin interval closes", "The reconstruction does not support a more precise release time.", None, ["ENV-REC-00142"], "ESTIMATED"),
            ("ENV-TL-142-06", "2026-05-14T06:05:00+05:00", "AIS_GAP", "CASPIAN STAR AIS returns", "AIS data resumes after the candidate origin interval.", "caspian-star", ["AIS-GAP-CS-20260514"], "OBSERVED"),
            ("ENV-TL-142-07", "2026-05-14T07:00:00+05:00", "WEATHER", "Drift envelope updated", "Wind, current, and wave estimates move and expand the modeled surface area.", None, ["ENV-OBS-142-WIND", "ENV-OBS-142-CURRENT", "ENV-OBS-142-WAVES"], "ESTIMATED"),
            ("ENV-TL-142-08", event.detected_at, "DETECTION", "Oil-like signature detected", "A 3.4 km² surface signature was observed with 87% detection confidence.", None, [event.source_reference], "OBSERVED"),
            ("ENV-TL-142-09", "2026-05-14T09:12:00+05:00", "ANALYSIS", "Candidate ranking generated", "12 historical candidates were searched and 3 retained as relevant for human review.", None, ["ENV-CAND-142-CS", "ENV-CAND-142-TU", "ENV-CAND-142-BE"], "INFERRED"),
        ]
        return EnvironmentalTimeline(
            event_id=event.id,
            items=[
                EnvironmentalTimelineItem(
                    id=item_id, timestamp=timestamp, type=item_type, title=title, detail=detail,
                    vessel_id=vessel_id, source_ids=source_ids, provenance=provenance,
                )
                for item_id, timestamp, item_type, title, detail, vessel_id, source_ids, provenance in items
            ],
        )

    def _seed_replay(self, event: EnvironmentalEvent) -> EnvironmentalReplay:
        times = [
            "2026-05-14T03:00:00+05:00", "2026-05-14T03:40:00+05:00",
            "2026-05-14T04:20:00+05:00", "2026-05-14T05:00:00+05:00",
            "2026-05-14T05:40:00+05:00", "2026-05-14T06:20:00+05:00",
            "2026-05-14T07:00:00+05:00", "2026-05-14T07:40:00+05:00",
            "2026-05-14T08:20:00+05:00", event.detected_at,
        ]
        frames: list[EnvironmentalReplayFrame] = []
        for index, timestamp in enumerate(times):
            progress = index / (len(times) - 1)
            center_lon = 51.005 + .055 * progress
            center_lat = 43.158 + .052 * progress
            geometry = _polygon(center_lon, center_lat, .022 + .032 * progress, .016 + .022 * progress)
            caspian_gap = 2 <= index <= 4
            frames.append(EnvironmentalReplayFrame(
                timestamp=timestamp, pollution_geometry=geometry,
                vessels=[
                    EnvironmentalReplayVessel(
                        vessel_id="caspian-star", vessel_name="CASPIAN STAR",
                        latitude=43.145 + .013 * index, longitude=50.995 + .019 * index,
                        speed_kn=0 if caspian_gap else 4.2, course_degrees=56,
                        ais_available=not caspian_gap,
                        provenance="ESTIMATED" if caspian_gap else "OBSERVED",
                    ),
                    EnvironmentalReplayVessel(
                        vessel_id="turan", vessel_name="TURAN",
                        latitude=43.126 + .011 * index, longitude=50.984 + .017 * index,
                        speed_kn=6.1, course_degrees=42,
                    ),
                    EnvironmentalReplayVessel(
                        vessel_id="baku-express", vessel_name="BAKU EXPRESS",
                        latitude=43.072 + .009 * index, longitude=50.932 + .014 * index,
                        speed_kn=10.4, course_degrees=37,
                    ),
                ],
                wind_direction_degrees=105, current_direction_degrees=310,
                provenance="ESTIMATED",
            ))
        return EnvironmentalReplay(
            event_id=event.id, started_at=times[0], ended_at=times[-1], step_minutes=40,
            frames=frames,
            disclaimer=(
                "Pollution geometry and positions during an AIS gap are modeled estimates. "
                "Observed AIS points and estimated frames are labeled separately."
            ),
        )

    def _seed_vessel_profiles(self, event: EnvironmentalEvent) -> None:
        self._vessel_profiles["caspian-star"] = VesselEnvironmentProfile(
            vessel_id="caspian-star", vessel_name="CASPIAN STAR",
            candidate_event_count=3, reviewed_event_count=2,
            history=[
                VesselEnvironmentalHistoryItem(
                    id="VEH-CS-20260514", environmental_event_id=event.id,
                    occurred_at="2026-05-14T03:35:00+05:00", event_type="OIL_POLLUTION",
                    relationship="CANDIDATE", relevance="HIGH", distance_km=.8,
                    title="Candidate in environmental review",
                    detail="94% temporal overlap and an AIS gap; association remains under review.",
                    provenance="INFERRED", source_ids=[event.id, "ENV-CAND-142-CS", "AIS-GAP-CS-20260514"],
                ),
                VesselEnvironmentalHistoryItem(
                    id="VEH-CS-20260318", environmental_event_id="ENV-2026-00108",
                    occurred_at="2026-03-18T13:10:00+05:00", event_type="FLOATING_WASTE",
                    relationship="CLEARED", relevance="LOW", distance_km=6.9,
                    title="Reviewed and cleared",
                    detail="Available AIS showed no meaningful temporal overlap after analyst review.",
                    provenance="OBSERVED", source_ids=["ENV-2026-00108", "ENV-REV-0018"],
                ),
                VesselEnvironmentalHistoryItem(
                    id="VEH-CS-20260122", environmental_event_id="ENV-2026-00114",
                    occurred_at="2026-01-22T09:40:00+05:00", event_type="FLOATING_WASTE",
                    relationship="NEARBY", relevance="LOW", distance_km=9.3,
                    title="Nearby vessel, low relevance",
                    detail="The track was outside the reconstructed origin envelope.",
                    provenance="INFERRED", source_ids=["ENV-2026-00114", "TRACK-CS-20260122"],
                ),
            ],
            generated_at="2026-05-14T09:12:00+05:00", disclaimer=ENVIRONMENTAL_DISCLAIMER,
        )
        for vessel_id, vessel_name, candidate_id, distance, relevance in [
            ("turan", "TURAN", "ENV-CAND-142-TU", 2.4, "MEDIUM"),
            ("baku-express", "BAKU EXPRESS", "ENV-CAND-142-BE", 7.1, "LOW"),
        ]:
            self._vessel_profiles[vessel_id] = VesselEnvironmentProfile(
                vessel_id=vessel_id, vessel_name=vessel_name,
                candidate_event_count=1, reviewed_event_count=0,
                history=[VesselEnvironmentalHistoryItem(
                    id=f"VEH-{vessel_id.upper()}-20260514", environmental_event_id=event.id,
                    occurred_at="2026-05-14T04:10:00+05:00", event_type="OIL_POLLUTION",
                    relationship="CANDIDATE", relevance=relevance, distance_km=distance,
                    title="Candidate in environmental review",
                    detail="Historical movement was retained for analyst review; no causation finding was made.",
                    provenance="INFERRED", source_ids=[event.id, candidate_id],
                )],
                generated_at="2026-05-14T09:12:00+05:00", disclaimer=ENVIRONMENTAL_DISCLAIMER,
            )


environmental_service = EnvironmentalIntelligenceService()
