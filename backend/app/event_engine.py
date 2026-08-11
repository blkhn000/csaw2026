import math
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from .behavior_engine import behavior_engine
from .demo_data import VESSELS
from .models import DetectedEvent, EventGroup, EventStatusUpdate, Position, Vessel


def _parse(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result if result.tzinfo else result.replace(tzinfo=timezone.utc)


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _point_segment_km(lat: float, lon: float, a: list[float], b: list[float]) -> float:
    mean_lat = math.radians((lat + a[1] + b[1]) / 3)
    scale_x, scale_y = 111.32 * math.cos(mean_lat), 110.57
    px, py = lon * scale_x, lat * scale_y
    ax, ay, bx, by = a[0] * scale_x, a[1] * scale_y, b[0] * scale_x, b[1] * scale_y
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class EventDetectionEngine:
    def __init__(self) -> None:
        self.events: dict[str, DetectedEvent] = {}
        self.groups: dict[str, EventGroup] = {}
        self._counter = 2800
        self._group_counter = 440
        self._speed_started: dict[str, datetime] = {}
        self._stop_started: dict[str, datetime] = {}
        self._last_draught: dict[str, float] = {}
        self._encounter_started: dict[tuple[str, str], datetime] = {}
        self.seed_demo_from_observations()

    def _event(
        self, event_type: str, vessel: Vessel, started_at: datetime, latitude: float,
        longitude: float, severity: str, confidence: float, data: dict[str, Any],
        explanation: str, factors: list[str], *, ended_at: datetime | None = None,
        related: Vessel | None = None, status: str = "active", voyage_id: str = "voy-001",
    ) -> DetectedEvent:
        self._counter += 1
        event = DetectedEvent(
            id=f"EV-{self._counter}", type=event_type, vessel_id=vessel.id, vessel_name=vessel.name,
            related_vessel_id=related.id if related else None, related_vessel_name=related.name if related else None,
            voyage_id=voyage_id, started_at=started_at.isoformat(), ended_at=ended_at.isoformat() if ended_at else None,
            latitude=latitude, longitude=longitude, severity=severity, confidence=confidence,
            status=status, data=data, explanation=explanation, factors=factors,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.events[event.id] = event
        return event

    def detect_route_deviation(self, vessel: Vessel, latitude: float, longitude: float, at: datetime) -> DetectedEvent | None:
        profile = behavior_engine.get(vessel.id)
        if profile.confidence < .35 or not profile.routes:
            return None
        route = next((r for r in profile.routes if r.id == profile.main_route_id), profile.routes[0])
        deviation = min(_point_segment_km(latitude, longitude, a, b) for a, b in zip(route.corridor, route.corridor[1:]))
        typical_max = 8.0 if vessel.id == "caspian-star" else 15.0
        if deviation <= typical_max:
            return None
        existing = self._active("route_deviation", vessel.id)
        if existing:
            # A detected event is an auditable snapshot. Live telemetry belongs
            # to the position stream and must not rewrite evidence that an
            # existing risk assessment was calculated from.
            return None
        percentile = min(99.9, 90 + deviation / max(typical_max, 1) * 2)
        return self._event("route_deviation", vessel, at, latitude, longitude, "medium", profile.confidence,
            {"current_deviation_km": round(deviation,1), "typical_deviation_km": f"0–{typical_max:g}", "historical_percentile": round(percentile,1), "voyages_analyzed": route.voyage_count},
            f"Судно находится в {deviation:.1f} км от исторического коридора маршрута {route.origin} → {route.destination}.",
            [f"Исторический коридор: ±{typical_max:g} км", f"Текущее отклонение: {deviation:.1f} км", f"Основано на {route.voyage_count} рейсах"])

    def detect_unexpected_speed(self, vessel: Vessel, speed: float, phase: str, at: datetime, lat: float, lon: float) -> DetectedEvent | None:
        profile = behavior_engine.get(vessel.id)
        speed_profile = next((p for p in profile.speed_profiles if p.phase == phase), profile.speed_profiles[0])
        outside = speed < speed_profile.typical_range.minimum or speed > speed_profile.typical_range.maximum
        if not outside:
            self._speed_started.pop(vessel.id, None)
            return None
        started = self._speed_started.setdefault(vessel.id, at)
        duration = (at - started).total_seconds() / 60
        if duration < 30 or self._active("unexpected_speed", vessel.id):
            return None
        return self._event("unexpected_speed", vessel, started, lat, lon, "medium", min(.96, profile.confidence),
            {"current_speed_kn": speed, "typical_speed_kn": f"{speed_profile.typical_range.minimum}–{speed_profile.typical_range.maximum}", "duration_minutes": round(duration), "voyage_phase": phase},
            f"Скорость {speed:.1f} kn сохранялась вне типичного диапазона более {duration:.0f} минут.",
            [f"Фаза рейса: {phase}", f"Обычно: {speed_profile.typical_range.minimum}–{speed_profile.typical_range.maximum} kn", f"Сейчас: {speed:.1f} kn"])

    def detect_unusual_stop(self, vessel: Vessel, speed: float, at: datetime, lat: float, lon: float, context: str = "open_sea") -> DetectedEvent | None:
        if speed >= .8 or context in {"port", "anchorage", "known_waiting_zone"}:
            self._stop_started.pop(vessel.id, None)
            return None
        started = self._stop_started.setdefault(vessel.id, at)
        duration = (at - started).total_seconds() / 60
        profile = behavior_engine.get(vessel.id)
        typical = max(20, profile.average_stop_minutes)
        in_known_area = any(_distance_km(lat, lon, area.latitude, area.longitude) <= area.radius_km for area in profile.stop_areas)
        if duration <= typical * 2 or in_known_area or self._active("unusual_stop", vessel.id):
            return None
        return self._event("unusual_stop", vessel, started, lat, lon, "medium", min(.94, profile.confidence),
            {"speed_kn": speed, "duration_minutes": round(duration), "typical_duration_minutes": typical, "location_context": context, "historical_stop_area": False},
            f"Судно почти неподвижно в открытом море {duration:.0f} минут вне известных зон остановок.",
            ["Контекст: открытое море", "Не порт и не якорная зона", f"Типичная остановка: до {typical} минут"])

    def detect_draught_change(self, vessel: Vessel, draught: float, at: datetime, lat: float, lon: float) -> DetectedEvent | None:
        previous = self._last_draught.get(vessel.id)
        self._last_draught[vessel.id] = draught
        if previous is None or abs(draught - previous) < .5:
            return None
        change = draught - previous
        return self._event("draught_change", vessel, at, lat, lon, "low", .96,
            {"before_m": previous, "after_m": draught, "change_m": round(change,1), "location_context": "open_sea"},
            f"Получено изменение заявленной осадки с {previous:.1f} до {draught:.1f} м.",
            [f"Изменение: {change:+.1f} м", "Положение: вне порта", "Требуется проверка качества исходных данных"], status="resolved")

    def detect_ais_gap(self, vessel: Vessel, last_at: datetime, restored_at: datetime, lat: float, lon: float, coverage: str = "high") -> DetectedEvent | None:
        minutes = (restored_at - last_at).total_seconds() / 60
        if minutes < 15:
            return None
        length = "extended" if minutes > 180 else "long" if minutes > 60 else "medium"
        possible_radius = vessel.speed * (minutes / 60) * 1.852
        severity = "high" if minutes > 180 and coverage == "high" else "medium"
        return self._event("ais_gap", vessel, last_at, lat, lon, severity, .98,
            {"duration_minutes": round(minutes), "gap_class": length, "coverage": coverage, "possible_movement_radius_km": round(possible_radius,1), "last_position_at": last_at.isoformat(), "restored_at": restored_at.isoformat()},
            f"Данные AIS отсутствовали {minutes/60:.0f} ч {minutes%60:.0f} мин в зоне с покрытием {coverage.upper()}.",
            [f"Последняя позиция: {last_at.strftime('%H:%M')}", f"Сигнал восстановлен: {restored_at.strftime('%H:%M')}", f"Возможный радиус движения: {possible_radius:.0f} км", f"Качество покрытия: {coverage.upper()}"], ended_at=restored_at, status="resolved")

    def start_ais_gap(self, vessel: Vessel, now: datetime, coverage: str = "unknown") -> DetectedEvent | None:
        if vessel.navigation_status != "underway" or self._active("ais_gap", vessel.id):
            return None
        last_at = _parse(vessel.last_position_at)
        minutes = (now - last_at).total_seconds() / 60
        if minutes < 15:
            return None
        return self._event("ais_gap", vessel, last_at, vessel.latitude, vessel.longitude, "medium", .9,
            {"duration_minutes": round(minutes), "gap_class": "medium" if minutes < 60 else "long", "coverage": coverage, "last_position_at": last_at.isoformat()},
            f"Новые AIS-позиции не поступают {minutes:.0f} минут.",
            [f"Последняя позиция: {last_at.strftime('%H:%M:%S')}", f"Текущая длительность: {minutes:.0f} минут", f"Покрытие района: {coverage.upper()}"])

    def resolve_active_gap(self, vessel: Vessel, restored_at: datetime) -> DetectedEvent | None:
        event = self._active("ais_gap", vessel.id)
        if not event:
            return None
        event.ended_at = restored_at.isoformat()
        event.status = "resolved"
        minutes = (restored_at - _parse(event.started_at)).total_seconds() / 60
        event.data["duration_minutes"] = round(minutes)
        event.data["restored_at"] = restored_at.isoformat()
        event.explanation = f"AIS-поток восстановлен после отсутствия данных продолжительностью {minutes:.0f} минут."
        return event

    def detect_encounter(self, vessel: Vessel, related: Vessel, started: datetime, ended: datetime, minimum_distance_m: float, speed_a: float, speed_b: float, lat: float, lon: float) -> DetectedEvent | None:
        duration = (ended - started).total_seconds() / 60
        if minimum_distance_m > 500 or duration < 20 or max(speed_a, speed_b) > 2:
            return None
        previous = 3 if vessel.id == "caspian-star" else 0
        return self._event("vessel_encounter", vessel, started, lat, lon, "medium", .93,
            {"minimum_distance_m": minimum_distance_m, "duration_minutes": round(duration), "average_speed_a_kn": speed_a, "average_speed_b_kn": speed_b, "location_context": "open_sea", "previous_encounters": previous},
            f"Суда находились на минимальном расстоянии {minimum_distance_m:.0f} м при низкой скорости в течение {duration/60:.1f} ч.",
            [f"Минимальная дистанция: {minimum_distance_m:.0f} м", f"Продолжительность: {duration/60:.1f} ч", f"Скорость: {speed_a:.1f} / {speed_b:.1f} kn", f"Предыдущие наблюдения: {previous}"], ended_at=ended, related=related, status="resolved")

    def process_position(self, position: Position, vessel: Vessel) -> list[DetectedEvent]:
        at = _parse(position.recorded_at)
        created = [
            self.detect_route_deviation(vessel, position.latitude, position.longitude, at),
            self.detect_unexpected_speed(vessel, position.speed, "open_sea", at, position.latitude, position.longitude),
            self.detect_unusual_stop(vessel, position.speed, at, position.latitude, position.longitude),
        ]
        if vessel.draught:
            created.append(self.detect_draught_change(vessel, vessel.draught, at, position.latitude, position.longitude))
        events = [event for event in created if event]
        if events:
            self.correlate(vessel.id, "voy-001")
        return events

    def process_encounters(self, vessel: Vessel, fleet: list[Vessel], at: datetime) -> list[DetectedEvent]:
        created: list[DetectedEvent] = []
        for other in fleet:
            if other.id == vessel.id:
                continue
            pair = tuple(sorted((vessel.id, other.id)))
            distance = _distance_km(vessel.latitude, vessel.longitude, other.latitude, other.longitude)
            qualifying = distance <= .5 and max(vessel.speed, other.speed) <= 2
            if not qualifying:
                self._encounter_started.pop(pair, None)
                continue
            started = self._encounter_started.setdefault(pair, at)
            if (at - started).total_seconds() < 20 * 60:
                continue
            already = next((event for event in self.events.values() if event.type == "vessel_encounter" and {event.vessel_id,event.related_vessel_id} == set(pair) and event.status == "active"), None)
            if not already:
                event = self.detect_encounter(vessel, other, started, at, distance * 1000, vessel.speed, other.speed, vessel.latitude, vessel.longitude)
                if event:
                    event.status = "active"
                    created.append(event)
        return created

    def correlate(self, vessel_id: str, voyage_id: str) -> EventGroup | None:
        related = sorted((event for event in self.events.values() if event.vessel_id == vessel_id and event.voyage_id == voyage_id), key=lambda e: e.started_at)
        if len(related) < 2:
            return None
        existing = next((group for group in self.groups.values() if group.vessel_id == vessel_id and group.voyage_id == voyage_id), None)
        vessel = next(v for v in VESSELS if v.id == vessel_id)
        if existing:
            existing.event_ids = [event.id for event in related]
            existing.event_types = list(dict.fromkeys(event.type for event in related))
            for event in related:
                event.group_id = existing.id
            return existing
        self._group_counter += 1
        group = EventGroup(id=f"EG-{self._group_counter}", vessel_id=vessel_id, vessel_name=vessel.name, voyage_id=voyage_id, started_at=related[0].started_at, ended_at=related[-1].ended_at, event_ids=[event.id for event in related], event_types=list(dict.fromkeys(event.type for event in related)), explanation=f"{len(related)} связанных событий в контексте одного рейса. Требуется совместный просмотр фактов.")
        self.groups[group.id] = group
        for event in related:
            event.group_id = group.id
        return group

    def update_status(self, event_id: str, update: EventStatusUpdate, user: str) -> DetectedEvent:
        event = self.events.get(event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        event.status = update.status
        event.reviewed_by, event.review_note = user, update.note
        return event

    def _active(self, event_type: str, vessel_id: str) -> DetectedEvent | None:
        return next((event for event in self.events.values() if event.type == event_type and event.vessel_id == vessel_id and event.status == "active"), None)

    def seed_demo_from_observations(self) -> None:
        star, khazar, volga = VESSELS[0], VESSELS[1], VESSELS[2]
        # TURAN is an intelligence/network entity in the demo dataset rather
        # than one of the three vessels in the live AIS feed.  Keep the
        # encounter evidence aligned with Risk and Network instead of relying
        # on the positional order of VESSELS (which previously selected
        # KHAZAR WAVE by accident).
        turan = Vessel(
            id="turan", imo="9217748", mmsi="423001143", name="TURAN",
            type="Cargo vessel", flag="Azerbaijan", length=138, width=20,
            deadweight=10_400, owner="Turan Maritime Services",
            operator="Turan Maritime Services", latitude=42.04,
            longitude=50.61, speed=.4, course=44, heading=44, draught=4.3,
            destination="Aktau", reported_eta="14:15", calculated_eta="14:20",
            navigation_status="underway", last_position_at="2026-08-10T17:28:00+05:00",
        )
        tz = timezone(timedelta(hours=5))
        route = self.detect_route_deviation(star, 41.34, 50.75, datetime(2026,8,10,13,20,tzinfo=tz))
        self.detect_ais_gap(star, datetime(2026,8,10,14,10,tzinfo=tz), datetime(2026,8,10,17,25,tzinfo=tz), 41.89, 50.52, "high")
        self.detect_encounter(star, turan, datetime(2026,8,10,17,28,tzinfo=tz), datetime(2026,8,10,20,15,tzinfo=tz), 174, .3, .4, 42.04, 50.61)
        self._last_draught[star.id] = 4.1
        self.detect_draught_change(star, 5.0, datetime(2026,8,10,17,40,tzinfo=tz), 42.05, 50.62)
        self._speed_started[volga.id] = datetime(2026,8,10,12,0,tzinfo=tz)
        self.detect_unexpected_speed(volga, 2.9, "open_sea", datetime(2026,8,10,12,42,tzinfo=tz), 43.1, 48.95)
        self._stop_started[khazar.id] = datetime(2026,8,10,11,20,tzinfo=tz)
        self.detect_unusual_stop(khazar, .3, datetime(2026,8,10,12,34,tzinfo=tz), 40.82, 50.21)
        self.correlate(star.id, "voy-001")


event_engine = EventDetectionEngine()
