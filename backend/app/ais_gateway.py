import math
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from .demo_data import POSITIONS, VESSELS
from .models import NormalizedAISMessage, Position


FIELD_ALIASES = {
    "mmsi": ("mmsi", "MMSI", "ship_id"),
    "latitude": ("latitude", "lat", "LAT"),
    "longitude": ("longitude", "lon", "lng", "LON"),
    "speed": ("speed", "sog", "SOG"),
    "course": ("course", "cog", "COG"),
    "heading": ("heading", "hdg", "HDG"),
    "timestamp": ("timestamp", "time", "ts", "received_at"),
    "navigation_status": ("navigation_status", "nav_status", "status"),
    "destination": ("destination", "dest"),
    "eta": ("eta", "ETA"),
    "draught": ("draught", "draft"),
}


def _pick(payload: dict[str, Any], field: str, default: Any = None) -> Any:
    return next((payload[key] for key in FIELD_ALIASES[field] if key in payload), default)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


class AISGateway:
    """Provider-neutral ingestion boundary used before durable storage."""

    def __init__(self) -> None:
        self.raw_messages: list[dict[str, Any]] = []
        self._seen: set[str] = set()

    def normalize(self, provider: str, payload: dict[str, Any]) -> NormalizedAISMessage:
        self.raw_messages.append({"provider": provider, "received_at": datetime.now(timezone.utc).isoformat(), "payload": payload})
        try:
            mmsi = str(_pick(payload, "mmsi"))
            latitude = float(_pick(payload, "latitude"))
            longitude = float(_pick(payload, "longitude"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail="MMSI and valid coordinates are required")
        if not mmsi or mmsi == "None":
            raise HTTPException(status_code=422, detail="Missing MMSI")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise HTTPException(status_code=422, detail="Coordinates outside valid range")

        raw_time = _pick(payload, "timestamp")
        try:
            timestamp = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00")) if raw_time else datetime.now(timezone.utc)
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid timestamp")
        speed = float(_pick(payload, "speed", 0) or 0)
        notes: list[str] = []
        if speed < 0 or speed > 70:
            notes.append("impossible_speed")
        signature = f"{mmsi}:{timestamp.isoformat()}:{latitude:.6f}:{longitude:.6f}"
        if signature in self._seen:
            notes.append("duplicate_message")
        self._seen.add(signature)
        vessel = next((item for item in VESSELS if item.mmsi == mmsi), None)
        previous = next((item for item in reversed(POSITIONS) if vessel and item.vessel_id == vessel.id), None)
        if previous:
            previous_time = datetime.fromisoformat(previous.recorded_at.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            if previous_time.tzinfo is None:
                previous_time = previous_time.replace(tzinfo=timezone.utc)
            elapsed_hours = (timestamp - previous_time).total_seconds() / 3600
            if elapsed_hours <= 0:
                notes.append("old_message")
            else:
                implied_knots = haversine_km(previous.latitude, previous.longitude, latitude, longitude) / 1.852 / elapsed_hours
                if implied_knots > 80:
                    notes.append("impossible_jump")

        return NormalizedAISMessage(
            mmsi=mmsi, timestamp=timestamp, latitude=latitude, longitude=longitude,
            speed=speed, course=float(_pick(payload, "course", 0) or 0),
            heading=float(_pick(payload, "heading")) if _pick(payload, "heading") is not None else None,
            navigation_status=str(_pick(payload, "navigation_status", "unknown")),
            destination=_pick(payload, "destination"), eta=_pick(payload, "eta"),
            draught=float(_pick(payload, "draught")) if _pick(payload, "draught") is not None else None,
            source=provider, quality_status="suspicious" if notes else "valid", quality_notes=notes,
        )

    def persist(self, message: NormalizedAISMessage) -> Position:
        vessel = next((item for item in VESSELS if item.mmsi == message.mmsi), None)
        if not vessel:
            raise HTTPException(status_code=404, detail="Vessel MMSI is not registered")
        point = Position(
            id=f"pos-{len(POSITIONS) + 1:06d}", vessel_id=vessel.id, mmsi=message.mmsi,
            latitude=message.latitude, longitude=message.longitude, speed=message.speed,
            course=message.course, heading=message.heading,
            navigation_status=message.navigation_status, source=message.source,
            quality_status=message.quality_status, recorded_at=message.timestamp.isoformat(),
            received_at=datetime.now(timezone.utc).isoformat(),
        )
        POSITIONS.append(point)
        if message.quality_status == "valid":
            vessel.latitude, vessel.longitude = message.latitude, message.longitude
            vessel.speed, vessel.course = message.speed, message.course
            vessel.heading = message.heading or message.course
            vessel.last_position_at = message.timestamp.isoformat()
            if message.destination:
                vessel.destination = message.destination
            if message.draught is not None:
                vessel.draught = message.draught
        return point


gateway = AISGateway()
