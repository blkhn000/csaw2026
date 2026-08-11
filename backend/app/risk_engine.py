from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from fastapi import HTTPException

from .advanced_analytics import advanced_analytics
from .demo_data import VESSELS, VOYAGES
from .event_engine import event_engine
from .models import (
    DetectedEvent,
    FactorReviewStatus,
    RiskAssessment,
    RiskCorrelationAdjustment,
    RiskFactor,
    RiskFactorReviewRequest,
    RiskLevel,
    RiskModelConfiguration,
    RiskRule,
    RiskScenario,
    RiskSnapshot,
    VoyageRiskSummary,
)


MODEL_VERSION = "CI-RISK-2.0"
STAGE_FIVE_MODEL_VERSION = "CI-RISK-1.0"
DISCLAIMER = (
    "Risk score prioritizes analyst attention. It is not evidence of wrongdoing, "
    "intent, cargo type, or legal status and must be reviewed with source data."
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _level(score: int) -> RiskLevel:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


class RiskEngine:
    """Deterministic, explainable Stage 5 risk model.

    Event detection remains the source of facts. This engine only prioritizes
    those facts, applies context and correlations, and keeps the resulting
    assessment auditable. It deliberately does not infer guilt or cargo.
    """

    model_version = MODEL_VERSION
    correlation_cap = 15

    _review_multipliers: dict[str | None, float] = {
        None: 1.0,
        "confirmed_relevant": 1.0,
        "normal_operation": 0.0,
        "false_positive": 0.0,
        "needs_more_data": 0.5,
    }
    _lifecycle_multipliers = {"active": 1.0, "recent": 0.5, "historical": 0.25}

    def __init__(self, source: Any | None = None, advanced_source: Any | None = None) -> None:
        self._event_source = source or event_engine
        self._advanced_source = advanced_source or advanced_analytics
        self._assessments: dict[str, RiskAssessment] = {}
        self._history: dict[str, list[RiskSnapshot]] = {}
        self._reviews: dict[str, dict[str, str | None]] = {}
        self._voyage_archive: dict[str, list[VoyageRiskSummary]] = {}
        self._last_assessed_at: dict[str, datetime] = {}
        self._demo_as_of = datetime.fromisoformat("2026-08-10T18:42:00+05:00")
        self._configuration = self._build_configuration()
        self._seed_demo()

    @staticmethod
    def level_for_score(score: int) -> RiskLevel:
        return _level(max(0, min(100, int(score))))

    def list(self, level: RiskLevel | Iterable[RiskLevel] | None = None) -> list[RiskAssessment]:
        levels: set[str] | None
        if level is None:
            levels = None
        elif isinstance(level, str):
            levels = {level.lower()}
        else:
            levels = {item.lower() for item in level}
        items = [item for item in self._assessments.values() if levels is None or item.risk_level in levels]
        items.sort(key=lambda item: (-item.risk_score, item.vessel_name))
        return [item.model_copy(deep=True) for item in items]

    def list_assessments(self, level: RiskLevel | Iterable[RiskLevel] | None = None) -> list[RiskAssessment]:
        return self.list(level)

    def current(self, vessel_id: str) -> RiskAssessment:
        assessment = self._assessments.get(vessel_id)
        if assessment is None and any(vessel.id == vessel_id for vessel in VESSELS):
            assessment = self.recalculate(vessel_id)
        if assessment is None:
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        return assessment.model_copy(deep=True)

    def get_vessel_risk(self, vessel_id: str) -> RiskAssessment:
        return self.current(vessel_id)

    def history(self, vessel_id: str) -> list[RiskSnapshot]:
        if vessel_id not in self._assessments and vessel_id not in self._history:
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        return [item.model_copy(deep=True) for item in self._history.get(vessel_id, [])]

    def get_history(self, vessel_id: str) -> list[RiskSnapshot]:
        return self.history(vessel_id)

    def voyage(self, voyage_id: str) -> RiskAssessment:
        assessment = next((item for item in self._assessments.values() if item.voyage_id == voyage_id), None)
        if assessment is None:
            voyage = next((item for item in VOYAGES if item.id == voyage_id), None)
            if voyage:
                assessment = self.recalculate(voyage.vessel_id, voyage_id=voyage_id)
        if assessment is None:
            raise HTTPException(status_code=404, detail="Voyage risk assessment not found")
        result = assessment.model_copy(deep=True)
        result.scope = "voyage"
        return result

    def get_voyage_risk(self, voyage_id: str) -> RiskAssessment:
        return self.voyage(voyage_id)

    def factors(self, voyage_id: str) -> list[RiskFactor]:
        return [factor.model_copy(deep=True) for factor in self.voyage(voyage_id).factors]

    def get_voyage_factors(self, voyage_id: str) -> list[RiskFactor]:
        return self.factors(voyage_id)

    def high_priority(self, limit: int = 10, minimum_score: int = 50) -> list[RiskAssessment]:
        items = [item for item in self.list() if item.risk_score >= minimum_score]
        for rank, item in enumerate(items[: max(0, limit)], start=1):
            item.priority_rank = rank
        return items[: max(0, limit)]

    def rules(self) -> RiskModelConfiguration:
        return self._configuration.model_copy(deep=True)

    def get_configuration(self) -> RiskModelConfiguration:
        return self.rules()

    def voyage_history(self, vessel_id: str, limit: int = 10) -> list[VoyageRiskSummary]:
        if vessel_id not in self._assessments and vessel_id not in self._voyage_archive:
            raise HTTPException(status_code=404, detail="Risk assessment not found")
        return [item.model_copy(deep=True) for item in self._voyage_archive.get(vessel_id, [])[:limit]]

    def review_factor(
        self,
        factor_id: str,
        review: RiskFactorReviewRequest | dict[str, Any],
        reviewer: str | None = None,
    ) -> RiskFactor:
        if not isinstance(review, RiskFactorReviewRequest):
            review = RiskFactorReviewRequest.model_validate(review)
        owner = next(
            (
                assessment.vessel_id
                for assessment in self._assessments.values()
                if any(factor.id == factor_id for factor in assessment.factors)
            ),
            None,
        )
        if owner is None:
            raise HTTPException(status_code=404, detail="Risk factor not found")
        reviewed_at = datetime.now(timezone.utc).isoformat()
        self._reviews[factor_id] = {
            "status": review.status,
            "comment": review.comment,
            "reviewed_by": reviewer or review.reviewed_by or "analyst",
            "reviewed_at": reviewed_at,
        }
        self.recalculate(
            owner,
            reason=f"Analyst review: {review.status}",
            at=datetime.now(timezone.utc),
        )
        updated = next(factor for factor in self._assessments[owner].factors if factor.id == factor_id)
        return updated.model_copy(deep=True)

    def recalculate(
        self,
        vessel_id: str,
        reason: str | None = None,
        *,
        voyage_id: str | None = None,
        at: datetime | str | None = None,
        record_history: bool = True,
    ) -> RiskAssessment:
        vessel = next((item for item in VESSELS if item.id == vessel_id), None)
        existing = self._assessments.get(vessel_id)
        if vessel is None and existing is None:
            raise HTTPException(status_code=404, detail="Vessel not found")

        if isinstance(at, str):
            as_of = _parse_timestamp(at)
        elif at is not None:
            as_of = at
        else:
            candidates = [self._demo_as_of, datetime.now(timezone.utc)]
            if vessel_id in self._last_assessed_at:
                candidates.append(self._last_assessed_at[vessel_id])
            as_of = max(candidates)
        if existing is not None:
            as_of = max(as_of, _parse_timestamp(existing.risk_updated_at))
        if vessel_id in self._last_assessed_at:
            as_of = max(as_of, self._last_assessed_at[vessel_id])
        source_events = self._events_for(vessel_id, voyage_id)
        if not source_events and existing is not None and existing.factors:
            return self._recalculate_stored_assessment(
                existing,
                as_of,
                reason=reason or "Risk factors recalculated",
                record_history=record_history,
            )
        resolved_voyage_id = voyage_id or self._resolve_voyage_id(vessel_id, source_events)
        factor_by_event: dict[str, RiskFactor] = {}
        for event in sorted(source_events, key=lambda item: item.started_at):
            factor_by_event[event.id] = self._factor_from_event(event, resolved_voyage_id, as_of, source_events)
        stage_five_factors = list(factor_by_event.values())
        correlations = self._correlate(stage_five_factors)
        correlation_score = sum(item.applied_score for item in correlations)
        stage_five_factor_score = sum(factor.effective_score for factor in stage_five_factors)
        base_risk_score = min(100, stage_five_factor_score + correlation_score)
        advanced_factors = self._advanced_factors(vessel_id, resolved_voyage_id, as_of)
        advanced_adjustment = min(
            self._advanced_source.risk_contribution_cap,
            sum(factor.effective_score for factor in advanced_factors),
        )
        factors = stage_five_factors + advanced_factors
        factor_score = stage_five_factor_score + advanced_adjustment
        score = min(100, base_risk_score + advanced_adjustment)
        scenarios = self._scenarios(vessel_id, resolved_voyage_id, stage_five_factors, as_of)

        previous = existing.risk_score if existing else self._previous_history_score(vessel_id)
        delta = score - previous
        trend = "rising" if delta > 0 else "falling" if delta < 0 else "stable"
        vessel_name = vessel.name if vessel else existing.vessel_name
        assessment = RiskAssessment(
            id=f"RA-{vessel_id}-{resolved_voyage_id or 'current'}",
            scope="voyage" if resolved_voyage_id else "vessel",
            vessel_id=vessel_id,
            vessel_name=vessel_name,
            voyage_id=resolved_voyage_id,
            risk_score=score,
            risk_level=_level(score),
            previous_score=previous,
            change_1h=delta if existing else self._demo_delta(vessel_id, "1h"),
            change_4h=delta if existing else self._demo_delta(vessel_id, "4h"),
            trend=trend if existing else ("rising" if self._demo_delta(vessel_id, "4h") > 0 else "stable"),
            factor_score=factor_score,
            correlation_adjustment=correlation_score,
            factors=factors,
            correlations=correlations,
            scenarios=scenarios,
            explanation=(
                f"Stage 5 operational/event subtotal {base_risk_score}/100 "
                f"({stage_five_factor_score} factor points + {correlation_score} correlation points) plus "
                f"{advanced_adjustment} confidence-weighted, deduplicated Stage 6 context points = {score}/100."
            ),
            disclaimer=DISCLAIMER,
            risk_updated_at=as_of.isoformat(),
            model_version=self.model_version,
            priority_rank=existing.priority_rank if existing else None,
            base_risk_score=base_risk_score,
            advanced_adjustment=advanced_adjustment,
            advanced_adjustment_cap=self._advanced_source.risk_contribution_cap,
        )
        self._assessments[vessel_id] = assessment
        self._last_assessed_at[vessel_id] = as_of
        if vessel is not None:
            vessel.risk_score = score
            vessel.risk_level = assessment.risk_level
            vessel.risk_updated_at = assessment.risk_updated_at

        if record_history and (existing is None or existing.risk_score != score):
            self._history.setdefault(vessel_id, []).append(
                RiskSnapshot(
                    id=f"RS-{vessel_id}-{len(self._history.get(vessel_id, [])) + 1:03d}",
                    vessel_id=vessel_id,
                    voyage_id=resolved_voyage_id,
                    risk_score=score,
                    risk_level=assessment.risk_level,
                    recorded_at=as_of.isoformat(),
                    reason=reason or "Risk factors recalculated",
                    model_version=self.model_version,
                )
            )
        return assessment.model_copy(deep=True)

    def apply_decay(self, now: datetime | str | None = None) -> list[RiskAssessment]:
        """Advance factor lifecycle and return assessments whose source facts were recalculated."""

        as_of = _parse_timestamp(now) if isinstance(now, str) else now or datetime.now(timezone.utc)
        updated: list[RiskAssessment] = []
        for vessel_id in sorted(self._assessments):
            updated.append(self.recalculate(vessel_id, reason="Risk lifecycle decay", at=as_of))
        return updated

    def _recalculate_stored_assessment(
        self,
        existing: RiskAssessment,
        as_of: datetime,
        *,
        reason: str,
        record_history: bool,
    ) -> RiskAssessment:
        """Re-score demo factors that intentionally have no Event Engine records."""

        factors: list[RiskFactor] = []
        for source in existing.factors:
            factor = source.model_copy(deep=True)
            age_hours = max(0.0, (as_of - _parse_timestamp(factor.created_at)).total_seconds() / 3600)
            factor.lifecycle = "active" if age_hours <= 12 else "recent" if age_hours <= 72 else "historical"
            review = self._reviews.get(factor.id)
            factor.review_status = review.get("status") if review else None
            factor.reviewed_by = review.get("reviewed_by") if review else None
            factor.reviewed_at = review.get("reviewed_at") if review else None
            factor.review_comment = review.get("comment") if review else None
            review_multiplier = self._review_multipliers[factor.review_status]
            lifecycle_multiplier = self._lifecycle_multipliers[factor.lifecycle]
            factor.effective_score = round(factor.adjusted_score * review_multiplier * lifecycle_multiplier)
            factors.append(factor)

        remaining = self.correlation_cap
        factors_by_type = {factor.type: factor for factor in factors}
        correlations: list[RiskCorrelationAdjustment] = []
        for source in existing.correlations:
            correlation = source.model_copy(deep=True)
            related = [factors_by_type.get(event_type) for event_type in correlation.event_types]
            if any(factor is None or factor.effective_score == 0 for factor in related):
                correlation.applied_score = 0
                correlation.capped = False
            else:
                strength = min(
                    factor.effective_score / max(1, factor.adjusted_score)
                    for factor in related
                    if factor is not None
                )
                lifecycle_score = round(correlation.raw_score * strength)
                correlation.applied_score = min(lifecycle_score, remaining)
                correlation.capped = correlation.applied_score < lifecycle_score
                remaining -= correlation.applied_score
            correlations.append(correlation)

        factor_score = sum(factor.effective_score for factor in factors)
        correlation_score = sum(item.applied_score for item in correlations)
        score = min(100, factor_score + correlation_score)
        delta = score - existing.risk_score
        assessment = existing.model_copy(
            update={
                "risk_score": score,
                "risk_level": _level(score),
                "previous_score": existing.risk_score,
                "change_1h": delta,
                "change_4h": delta,
                "trend": "rising" if delta > 0 else "falling" if delta < 0 else "stable",
                "factor_score": factor_score,
                "correlation_adjustment": correlation_score,
                "factors": factors,
                "correlations": correlations,
                "explanation": (
                    f"{factor_score} factor points plus {correlation_score} correlation points = {score}/100."
                ),
                "risk_updated_at": as_of.isoformat(),
                "base_risk_score": score,
                "advanced_adjustment": 0,
                "advanced_adjustment_cap": self._advanced_source.risk_contribution_cap,
            },
            deep=True,
        )
        self._assessments[existing.vessel_id] = assessment
        self._last_assessed_at[existing.vessel_id] = as_of
        if record_history and score != existing.risk_score:
            self._history.setdefault(existing.vessel_id, []).append(
                RiskSnapshot(
                    id=f"RS-{existing.vessel_id}-{len(self._history.get(existing.vessel_id, [])) + 1:03d}",
                    vessel_id=existing.vessel_id,
                    voyage_id=existing.voyage_id,
                    risk_score=score,
                    risk_level=assessment.risk_level,
                    recorded_at=as_of.isoformat(),
                    reason=reason,
                    model_version=self.model_version,
                )
            )
        return assessment.model_copy(deep=True)

    def _events_for(self, vessel_id: str, voyage_id: str | None) -> list[DetectedEvent]:
        events = [event for event in self._event_source.events.values() if event.vessel_id == vessel_id]
        if voyage_id and not voyage_id.endswith("-current"):
            events = [event for event in events if event.voyage_id == voyage_id]
        return events

    def _advanced_factors(
        self,
        vessel_id: str,
        voyage_id: str | None,
        as_of: datetime,
    ) -> list[RiskFactor]:
        """Translate independent Stage 6 signals without changing Stage 5 scoring rules."""

        result: list[RiskFactor] = []
        for signal in self._advanced_source.risk_signals(vessel_id, voyage_id):
            if signal.deduplicated:
                continue
            age_hours = max(0.0, (as_of - _parse_timestamp(signal.source_timestamp)).total_seconds() / 3600)
            lifecycle = "active" if age_hours <= 12 else "recent" if age_hours <= 72 else "historical"
            review = self._reviews.get(signal.id)
            review_status = review.get("status") if review else None
            review_multiplier = self._review_multipliers[review_status]
            lifecycle_multiplier = self._lifecycle_multipliers[lifecycle]
            effective = round(signal.effective_score * review_multiplier * lifecycle_multiplier)
            result.append(
                RiskFactor(
                    id=signal.id,
                    vessel_id=signal.vessel_id,
                    voyage_id=signal.voyage_id,
                    type=signal.type,
                    label=signal.label,
                    base_score=signal.base_score,
                    adjusted_score=signal.adjusted_score,
                    effective_score=effective,
                    confidence=signal.confidence,
                    source_event_id=signal.event_id,
                    explanation=signal.explanation,
                    evidence=list(signal.evidence),
                    lifecycle=lifecycle,
                    created_at=signal.source_timestamp,
                    review_status=review_status,
                    reviewed_by=review.get("reviewed_by") if review else None,
                    reviewed_at=review.get("reviewed_at") if review else None,
                    review_comment=review.get("comment") if review else None,
                    stage=6,
                    confidence_weighted_score=signal.confidence_weighted_score,
                    deduplication_group=signal.deduplication_group,
                    deduplicated=False,
                )
            )
        return result

    @staticmethod
    def _resolve_voyage_id(vessel_id: str, events: list[DetectedEvent]) -> str | None:
        if vessel_id == "caspian-star":
            return "voy-001"
        if events:
            return f"voy-{vessel_id}-current"
        return None

    def _factor_from_event(
        self,
        event: DetectedEvent,
        voyage_id: str | None,
        as_of: datetime,
        voyage_events: list[DetectedEvent],
    ) -> RiskFactor:
        base_score, adjusted_score, label, explanation = self._score_event(event, voyage_events)
        lifecycle = self._lifecycle(event, as_of)
        review = self._reviews.get(f"RF-{event.id}")
        review_status = review.get("status") if review else None
        review_multiplier = self._review_multipliers[review_status]
        lifecycle_multiplier = self._lifecycle_multipliers[lifecycle]
        effective = round(adjusted_score * review_multiplier * lifecycle_multiplier)
        if event.status == "dismissed":
            effective = 0
        return RiskFactor(
            id=f"RF-{event.id}",
            vessel_id=event.vessel_id,
            voyage_id=voyage_id,
            type=event.type,
            label=label,
            base_score=base_score,
            adjusted_score=adjusted_score,
            effective_score=effective,
            confidence=event.confidence,
            source_event_id=event.id,
            explanation=explanation,
            evidence=list(event.factors),
            lifecycle=lifecycle,
            created_at=event.started_at,
            review_status=review_status,
            reviewed_by=review.get("reviewed_by") if review else None,
            reviewed_at=review.get("reviewed_at") if review else None,
            review_comment=review.get("comment") if review else None,
        )

    @staticmethod
    def _score_event(event: DetectedEvent, voyage_events: list[DetectedEvent]) -> tuple[int, int, str, str]:
        data = event.data
        if event.type == "route_deviation":
            deviation = float(data.get("current_deviation_km", 0))
            percentile = float(data.get("historical_percentile", 0))
            adjusted = 6 + (4 if deviation >= 24 else 2) + (2 if percentile >= 95 else 1)
            return 6, adjusted, "Route outside historical corridor", (
                f"Observed deviation is {deviation:.1f} km; context raises the base score from 6 to {adjusted}."
            )
        if event.type == "ais_gap":
            minutes = float(data.get("duration_minutes", 0))
            coverage = str(data.get("coverage", "unknown")).lower()
            adjusted = 10 + (8 if minutes >= 180 else 4 if minutes >= 60 else 2) + (4 if coverage == "high" else 1)
            return 10, adjusted, "Extended AIS data gap", (
                f"AIS data was absent for {minutes:.0f} minutes in {coverage.upper()} coverage; "
                f"context raises the base score from 10 to {adjusted}."
            )
        if event.type == "vessel_encounter":
            distance = float(data.get("minimum_distance_m", 9999))
            duration = float(data.get("duration_minutes", 0))
            speed = max(float(data.get("average_speed_a_kn", 99)), float(data.get("average_speed_b_kn", 99)))
            open_sea = data.get("location_context") == "open_sea"
            adjusted = 7 + (4 if distance <= 250 else 2) + (3 if duration >= 60 else 1) + (2 if speed <= 1 else 0) + (1 if open_sea else 0)
            return 7, adjusted, "Prolonged close vessel encounter", (
                f"Minimum distance {distance:.0f} m for {duration:.0f} minutes at low speed; "
                f"context raises the base score from 7 to {adjusted}."
            )
        if event.type == "draught_change":
            change = abs(float(data.get("change_m", 0)))
            open_sea = data.get("location_context") == "open_sea"
            types = {item.type for item in voyage_events if item.started_at <= event.started_at}
            adjusted = 5 + (4 if change >= 0.8 else 2) + (3 if open_sea else 0)
            adjusted += 3 if "ais_gap" in types else 0
            adjusted += 3 if "vessel_encounter" in types else 0
            return 5, adjusted, "Draught change in voyage context", (
                f"Reported draught changed by {change:.1f} m outside port after related observations; "
                f"context raises the base score from 5 to {adjusted}."
            )
        if event.type == "unusual_stop":
            duration = float(data.get("duration_minutes", 0))
            typical = float(data.get("typical_duration_minutes", 30))
            open_sea = data.get("location_context") == "open_sea"
            adjusted = 5 + (3 if duration >= typical * 2 else 1) + (2 if open_sea else 0)
            return 5, adjusted, "Stop outside normal operating areas", (
                f"The stop lasted {duration:.0f} minutes versus a typical {typical:.0f}; adjusted score {adjusted}."
            )
        duration = float(data.get("duration_minutes", 0))
        adjusted = 3 + (2 if duration >= 30 else 1) + 1
        return 3, adjusted, "Speed outside behavioral range", (
            f"Speed remained outside the behavioral range for {duration:.0f} minutes; adjusted score {adjusted}."
        )

    @staticmethod
    def _lifecycle(event: DetectedEvent, as_of: datetime) -> str:
        age_hours = max(0.0, (as_of - _parse_timestamp(event.started_at)).total_seconds() / 3600)
        if age_hours <= 12:
            return "active"
        if age_hours <= 72:
            return "recent"
        return "historical"

    def _correlate(self, factors: list[RiskFactor]) -> list[RiskCorrelationAdjustment]:
        active_factors = {factor.type: factor for factor in factors if factor.effective_score > 0}
        definitions = [
            ("route-gap", ["route_deviation", "ais_gap"], 4, "Route deviation followed by an AIS gap"),
            ("gap-encounter", ["ais_gap", "vessel_encounter"], 6, "AIS gap followed by a close encounter"),
            ("encounter-draught", ["vessel_encounter", "draught_change"], 8, "Encounter followed by a draught change"),
        ]
        remaining = self.correlation_cap
        result: list[RiskCorrelationAdjustment] = []
        for rule_id, event_types, raw_score, explanation in definitions:
            if not set(event_types).issubset(active_factors):
                continue
            strength = min(
                active_factors[event_type].effective_score / max(1, active_factors[event_type].adjusted_score)
                for event_type in event_types
            )
            lifecycle_score = round(raw_score * strength)
            applied = min(lifecycle_score, remaining)
            result.append(
                RiskCorrelationAdjustment(
                    id=f"RC-{rule_id}",
                    event_types=event_types,
                    raw_score=raw_score,
                    applied_score=applied,
                    explanation=(
                        explanation
                        if strength == 1
                        else f"{explanation}; lifecycle/review strength {strength:.0%}"
                    ),
                    capped=applied < lifecycle_score,
                )
            )
            remaining -= applied
            if remaining <= 0:
                break
        return result

    @staticmethod
    def _scenarios(
        vessel_id: str,
        voyage_id: str | None,
        factors: list[RiskFactor],
        as_of: datetime,
    ) -> list[RiskScenario]:
        required = {"route_deviation", "ais_gap", "vessel_encounter", "draught_change"}
        available = {factor.type for factor in factors if factor.effective_score > 0}
        if not required.issubset(available):
            return []
        source_ids = [factor.source_event_id for factor in factors if factor.type in required]
        return [
            RiskScenario(
                id=f"RSC-{vessel_id}-{voyage_id or 'current'}",
                vessel_id=vessel_id,
                voyage_id=voyage_id,
                type="POTENTIAL_OFFSHORE_TRANSFER_PATTERN",
                title="PATTERN REQUIRES REVIEW",
                confidence=0.88,
                score_adjustment=0,
                source_event_ids=source_ids,
                explanation=(
                    "The sequence resembles a pattern that merits analyst review, but may have legitimate "
                    "operational explanations. It does not establish an illegal transfer or wrongdoing."
                ),
                created_at=as_of.isoformat(),
            )
        ]

    def _seed_demo(self) -> None:
        self._history["caspian-star"] = self._caspian_history()
        self.recalculate("caspian-star", voyage_id="voy-001", record_history=False)
        self._assessments["caspian-star"].previous_score = 84
        self._assessments["caspian-star"].change_1h = 7
        self._assessments["caspian-star"].change_4h = 37
        self._assessments["caspian-star"].trend = "rising"

        for vessel_id in ("khazar-wave", "volga-marine"):
            self.recalculate(vessel_id, record_history=False)

        self._add_synthetic_assessment(
            vessel_id="turan",
            vessel_name="TURAN",
            voyage_id="V-088",
            score=71,
            previous=59,
            change_1h=12,
            change_4h=12,
            correlation=9,
            factor_specs=[
                ("vessel_encounter", 9, 24, "Repeated encounter with CASPIAN STAR"),
                ("ais_gap", 8, 18, "Incomplete position sequence"),
                ("route_deviation", 7, 20, "Movement outside the usual corridor"),
            ],
            updated_at="2026-08-10T17:36:00+05:00",
        )
        self._add_synthetic_assessment(
            vessel_id="baku-express",
            vessel_name="BAKU EXPRESS",
            voyage_id="V-221",
            score=63,
            previous=63,
            change_1h=0,
            change_4h=0,
            correlation=7,
            factor_specs=[
                ("route_deviation", 8, 22, "Route outside a stable historical corridor"),
                ("unusual_stop", 7, 16, "Stop outside port and known waiting areas"),
                ("unexpected_speed", 6, 18, "Speed inconsistent with the voyage phase"),
            ],
            updated_at="2026-08-10T17:22:00+05:00",
        )
        self._add_synthetic_assessment(
            vessel_id="caspian-wind",
            vessel_name="CASPIAN WIND",
            voyage_id="V-174",
            score=51,
            previous=46,
            change_1h=5,
            change_4h=5,
            correlation=5,
            factor_specs=[
                ("ais_gap", 9, 19, "AIS gap longer than the vessel baseline"),
                ("unusual_stop", 8, 15, "Stop outside a usual operating area"),
                ("route_deviation", 6, 12, "Position outside the route corridor"),
            ],
            updated_at="2026-08-10T17:18:00+05:00",
        )
        self._seed_voyage_archive()

    def _add_synthetic_assessment(
        self,
        *,
        vessel_id: str,
        vessel_name: str,
        voyage_id: str,
        score: int,
        previous: int,
        change_1h: int,
        change_4h: int,
        correlation: int,
        factor_specs: list[tuple[str, int, int, str]],
        updated_at: str,
    ) -> None:
        factors: list[RiskFactor] = []
        for index, (factor_type, base, adjusted, explanation) in enumerate(factor_specs, start=1):
            factors.append(
                RiskFactor(
                    id=f"RF-{vessel_id}-{index}",
                    vessel_id=vessel_id,
                    voyage_id=voyage_id,
                    type=factor_type,
                    label=explanation,
                    base_score=base,
                    adjusted_score=adjusted,
                    effective_score=adjusted,
                    confidence=max(0.78, 0.94 - index * 0.03),
                    source_event_id=f"SYN-{vessel_id}-{index}",
                    explanation=explanation,
                    evidence=["Deterministic Stage 5 demonstration evidence"],
                    lifecycle="active",
                    created_at=updated_at,
                )
            )
        factor_score = sum(item.effective_score for item in factors)
        if factor_score + correlation != score:
            raise ValueError(f"Synthetic risk decomposition for {vessel_id} is not exact")
        correlation_item = RiskCorrelationAdjustment(
            id=f"RC-{vessel_id}",
            event_types=[factors[0].type, factors[1].type],
            raw_score=correlation,
            applied_score=correlation,
            explanation="Contextual relationship between independent event factors",
        )
        self._assessments[vessel_id] = RiskAssessment(
            id=f"RA-{vessel_id}-{voyage_id}",
            vessel_id=vessel_id,
            vessel_name=vessel_name,
            voyage_id=voyage_id,
            risk_score=score,
            risk_level=_level(score),
            previous_score=previous,
            change_1h=change_1h,
            change_4h=change_4h,
            trend="rising" if score > previous else "stable" if score == previous else "falling",
            factor_score=factor_score,
            correlation_adjustment=correlation,
            factors=factors,
            correlations=[correlation_item],
            explanation=f"{factor_score} factor points plus {correlation} correlation points = {score}/100.",
            disclaimer=DISCLAIMER,
            risk_updated_at=updated_at,
            model_version=self.model_version,
            base_risk_score=score,
            advanced_adjustment=0,
            advanced_adjustment_cap=self._advanced_source.risk_contribution_cap,
        )
        self._history[vessel_id] = [
            RiskSnapshot(
                id=f"RS-{vessel_id}-001",
                vessel_id=vessel_id,
                voyage_id=voyage_id,
                risk_score=previous,
                risk_level=_level(previous),
                recorded_at=(datetime.fromisoformat(updated_at) - timedelta(hours=2)).isoformat(),
                reason="Previous calculated state",
                model_version=self.model_version,
            ),
            RiskSnapshot(
                id=f"RS-{vessel_id}-002",
                vessel_id=vessel_id,
                voyage_id=voyage_id,
                risk_score=score,
                risk_level=_level(score),
                recorded_at=updated_at,
                reason="Current contextual assessment",
                model_version=self.model_version,
            ),
        ]

    @staticmethod
    def _demo_delta(vessel_id: str, window: str) -> int:
        values = {
            "caspian-star": {"1h": 30, "4h": 30},
            "turan": {"1h": 12, "4h": 12},
            "baku-express": {"1h": 0, "4h": 0},
            "caspian-wind": {"1h": 5, "4h": 5},
        }
        return values.get(vessel_id, {}).get(window, 0)

    def _previous_history_score(self, vessel_id: str) -> int:
        history = self._history.get(vessel_id, [])
        return history[-2].risk_score if len(history) >= 2 else history[-1].risk_score if history else 0

    def _caspian_history(self) -> list[RiskSnapshot]:
        entries = [
            ("08:00", 12, "Voyage started; ordinary operational baseline", None, STAGE_FIVE_MODEL_VERSION),
            ("13:20", 27, "Route deviation entered the assessment", "EV-2801", STAGE_FIVE_MODEL_VERSION),
            ("14:10", 35, "AIS data gap started", "EV-2802", STAGE_FIVE_MODEL_VERSION),
            ("17:25", 54, "AIS restored after 3 h 15 min", "EV-2802", STAGE_FIVE_MODEL_VERSION),
            ("17:30", 68, "Prolonged close encounter correlated", "EV-2803", STAGE_FIVE_MODEL_VERSION),
            ("17:40", 84, "Draught change and capped Stage 5 correlation", "EV-2804", STAGE_FIVE_MODEL_VERSION),
            ("17:46", 91, "Confidence-weighted and deduplicated Stage 6 context added", "ADV-6002", self.model_version),
        ]
        return [
            RiskSnapshot(
                id=f"RS-caspian-star-{index:03d}",
                vessel_id="caspian-star",
                voyage_id="voy-001",
                risk_score=score,
                risk_level=_level(score),
                recorded_at=f"2026-08-10T{clock}:00+05:00",
                reason=reason,
                source_event_id=event_id,
                model_version=model_version,
            )
            for index, (clock, score, reason, event_id, model_version) in enumerate(entries, start=1)
        ]

    def _seed_voyage_archive(self) -> None:
        scores = [31, 18, 22, 41, 16, 27, 35, 19, 24, 29]
        self._voyage_archive["caspian-star"] = [
            VoyageRiskSummary(
                id=f"VRS-{143 - index}",
                vessel_id="caspian-star",
                voyage_id=f"voy-{143 - index}",
                origin="Aktau" if index % 2 == 0 else "Baku",
                destination="Baku" if index % 2 == 0 else "Aktau",
                completed_at=(datetime.fromisoformat("2026-08-09T18:00:00+05:00") - timedelta(days=index)).isoformat(),
                risk_score=score,
                risk_level=_level(score),
                model_version=self.model_version,
            )
            for index, score in enumerate(scores)
        ]

    def _build_configuration(self) -> RiskModelConfiguration:
        rules = [
            RiskRule(id="factor-ais-gap", name="AIS gap context", description="Duration and expected coverage modify the base score.", category="factor", parameters={"base": 10, "extended_gap": 8, "high_coverage": 4}),
            RiskRule(id="factor-route", name="Route context", description="Deviation magnitude and historical rarity modify the base score.", category="factor", parameters={"base": 6, "large_deviation": 4, "rare": 2}),
            RiskRule(id="factor-encounter", name="Encounter context", description="Distance, duration, speed and location modify the base score.", category="factor", parameters={"base": 7, "maximum": 17}),
            RiskRule(id="factor-draught", name="Draught context", description="Magnitude, location and preceding observations modify the base score.", category="factor", parameters={"base": 5, "maximum": 18}),
            RiskRule(id="correlation-route-gap", name="Route + AIS gap", description="Applied once when both independent facts are present.", category="correlation", parameters={"score": 4}),
            RiskRule(id="correlation-gap-encounter", name="AIS gap + encounter", description="Applied once when both independent facts are present.", category="correlation", parameters={"score": 6}),
            RiskRule(id="correlation-encounter-draught", name="Encounter + draught", description="Applied once when both independent facts are present.", category="correlation", parameters={"score": 8}),
            RiskRule(id="advanced-cargo-draught", name="Cargo / draught context", description="Vessel-specific draught consistency contributes only after confidence weighting and cargo-signal deduplication.", category="factor", parameters={"raw_strength": 13, "effective_demo_contribution": 3, "deduplication_group": "cargo_consistency"}),
            RiskRule(id="advanced-fuel", name="Fuel context", description="Weather- and operation-corrected fuel variance is an indirect review indicator.", category="factor", parameters={"raw_strength": 9, "effective_demo_contribution": 2}),
            RiskRule(id="advanced-economics", name="Economic context", description="Estimated voyage economics receive a low capped contribution because source confidence is limited.", category="factor", parameters={"raw_strength": 6, "effective_demo_contribution": 1}),
            RiskRule(id="advanced-network", name="Related vessel context", description="Repeated encounters contribute a small context factor and never transfer another vessel's score.", category="factor", parameters={"raw_strength": 5, "effective_demo_contribution": 1}),
            RiskRule(id="advanced-cap", name="Advanced analytics cap", description="Confidence-weighted and deduplicated Stage 6 signals can add no more than seven points.", category="correlation", parameters={"maximum": self._advanced_source.risk_contribution_cap}),
            RiskRule(id="lifecycle-decay", name="Factor lifecycle", description="Factors move ACTIVE to RECENT to HISTORICAL and decay without deletion.", category="lifecycle", parameters={"active_hours": 12, "recent_hours": 72, "recent_multiplier": 0.5, "historical_multiplier": 0.25}),
        ]
        return RiskModelConfiguration(
            model_version=self.model_version,
            updated_at="2026-08-10T00:00:00+05:00",
            level_thresholds={"low": [0, 24], "moderate": [25, 49], "high": [50, 74], "critical": [75, 100]},
            correlation_cap=self.correlation_cap,
            decay_hours={"active": 12, "recent": 72, "historical": None},
            review_multipliers={key or "unreviewed": value for key, value in self._review_multipliers.items()},
            rules=rules,
            disclaimer=DISCLAIMER,
            advanced_contribution_cap=self._advanced_source.risk_contribution_cap,
        )


risk_engine = RiskEngine()
