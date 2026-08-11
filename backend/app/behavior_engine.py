from datetime import datetime, timezone
from hashlib import sha256

from fastapi import HTTPException

from .demo_data import VESSELS
from .models import (
    BehaviorProfile, BehaviorRange, CurrentComparison, DraughtHistoryItem,
    PortBehaviorProfile, RouteBehaviorProfile, SpeedBehaviorProfile, StopAreaProfile,
)


class BehaviorEngine:
    """Builds explainable per-vessel baselines from completed-voyage aggregates.

    The demo implementation is deterministic. Its output contract is the same one
    used by a future PostGIS aggregate repository.
    """

    def __init__(self) -> None:
        self._cache: dict[str, BehaviorProfile] = {}

    def get(self, vessel_id: str) -> BehaviorProfile:
        if vessel_id not in self._cache:
            self._cache[vessel_id] = self.build(vessel_id)
        return self._cache[vessel_id]

    def recalculate(self, vessel_id: str) -> BehaviorProfile:
        profile = self.build(vessel_id)
        self._cache[vessel_id] = profile
        return profile

    @staticmethod
    def confidence(voyages: int, months: int) -> tuple[float, str]:
        sample_score = min(1.0, voyages / 100)
        history_score = min(1.0, months / 18)
        value = round((sample_score * .78 + history_score * .22) * .94, 2)
        level = "high" if value >= .8 else "developing" if value >= .35 else "insufficient"
        return value, level

    def build(self, vessel_id: str) -> BehaviorProfile:
        vessel = next((item for item in VESSELS if item.id == vessel_id), None)
        if not vessel:
            raise HTTPException(status_code=404, detail="Vessel not found")
        if vessel_id == "caspian-star":
            return self._caspian_star()

        seed = int(sha256(vessel_id.encode()).hexdigest()[:6], 16)
        voyages = 8 + seed % 55
        months = 3 + seed % 14
        confidence, level = self.confidence(voyages, months)
        average = round(max(7.5, vessel.speed or 10.4), 1)
        return BehaviorProfile(
            vessel_id=vessel.id, generated_at=datetime.now(timezone.utc).isoformat(),
            confidence=confidence, confidence_level=level, voyages_analyzed=voyages,
            observation_months=months, distance_tracked_km=round(voyages * 344.7),
            total_sailing_hours=round(voyages * 27.4), total_port_hours=round(voyages * 8.2),
            stops_at_sea=max(1, voyages // 7), historical_ais_gaps=max(0, voyages // 18),
            main_route_id="route-main",
            routes=[RouteBehaviorProfile(id="route-main", origin="Baku", destination=vessel.destination, voyage_count=max(3, int(voyages*.62)), share=.62, typical_distance=BehaviorRange(minimum=330, maximum=410, unit="km"), typical_duration=BehaviorRange(minimum=24, maximum=33, unit="h"), typical_speed=BehaviorRange(minimum=max(1,average-1), maximum=average+1, unit="kn"), typical_stops=BehaviorRange(minimum=0, maximum=1, unit="stops"), typical_departure="06:00–12:00", typical_arrival="10:00–18:00", corridor=[[49.89,40.37],[50.2,41.1],[50.74,42.31]])],
            speed_profiles=[SpeedBehaviorProfile(phase="open_sea", average=average, median=average-.1, p95=average+1.1, typical_range=BehaviorRange(minimum=average-1, maximum=average+1, unit="kn"), sample_count=voyages*42, distribution=[2,4,9,18,31,42,38,25,10,4])],
            ports=[PortBehaviorProfile(port_id="baku",port_name="Baku",visits=max(2,voyages//3),share=.42,median_stay_hours=7.1,typical_stay=BehaviorRange(minimum=4,maximum=12,unit="h"),usual=True),PortBehaviorProfile(port_id="destination",port_name=vessel.destination,visits=max(2,voyages//3),share=.39,median_stay_hours=7.8,typical_stay=BehaviorRange(minimum=5,maximum=13,unit="h"),usual=True)],
            stop_areas=[], average_stop_minutes=21, draught_typical=BehaviorRange(minimum=max(1,vessel.draught-.5),maximum=vessel.draught+.5,unit="m"), draught_history=[],
            departure_pattern=[8,52,32,8], voyages_by_day=[12,15,14,13,10,5,3], activity_cells=[[40.37,49.89,.8],[41.2,50.2,.7],[42.31,50.74,.9]],
            current_comparison=[CurrentComparison(parameter="Speed",typical=f"{average-1:.1f}–{average+1:.1f} kn",current=f"{vessel.speed:.1f} kn")],
        )

    def _caspian_star(self) -> BehaviorProfile:
        confidence, level = self.confidence(143, 18)
        return BehaviorProfile(
            vessel_id="caspian-star", generated_at=datetime.now(timezone.utc).isoformat(),
            confidence=confidence, confidence_level=level, voyages_analyzed=143,
            observation_months=18, distance_tracked_km=31420,
            total_sailing_hours=3810, total_port_hours=1280,
            stops_at_sea=27, historical_ais_gaps=8, main_route_id="baku-aktau",
            routes=[
                RouteBehaviorProfile(id="baku-aktau", origin="Baku", destination="Aktau", voyage_count=82, share=.57, typical_distance=BehaviorRange(minimum=380,maximum=405,unit="km"), typical_duration=BehaviorRange(minimum=27,maximum=31,unit="h"), typical_speed=BehaviorRange(minimum=11.2,maximum=13.1,unit="kn"), typical_stops=BehaviorRange(minimum=0,maximum=1,unit="stops"), typical_departure="06:00–11:00", typical_arrival="10:00–17:00", corridor=[[49.89,40.37],[50.08,40.86],[50.29,41.34],[50.51,41.87],[50.74,42.31]]),
                RouteBehaviorProfile(id="aktau-baku", origin="Aktau", destination="Baku", voyage_count=41, share=.29, typical_distance=BehaviorRange(minimum=382,maximum=408,unit="km"), typical_duration=BehaviorRange(minimum=28,maximum=32,unit="h"), typical_speed=BehaviorRange(minimum=10.9,maximum=12.8,unit="kn"), typical_stops=BehaviorRange(minimum=0,maximum=1,unit="stops"), typical_departure="07:00–12:00", typical_arrival="11:00–18:00", corridor=[[50.74,42.31],[50.51,41.87],[50.29,41.34],[50.08,40.86],[49.89,40.37]]),
                RouteBehaviorProfile(id="aktau-turkmenbashi", origin="Aktau", destination="Turkmenbashi", voyage_count=14, share=.10, typical_distance=BehaviorRange(minimum=285,maximum=310,unit="km"), typical_duration=BehaviorRange(minimum=24,maximum=29,unit="h"), typical_speed=BehaviorRange(minimum=9.1,maximum=11.3,unit="kn"), typical_stops=BehaviorRange(minimum=0,maximum=2,unit="stops"), typical_departure="05:00–10:00", typical_arrival="09:00–16:00", corridor=[[50.74,42.31],[51.4,41.4],[52.2,40.6],[52.97,40.02]]),
            ],
            speed_profiles=[
                SpeedBehaviorProfile(phase="open_sea",average=12.1,median=12.0,p95=13.8,typical_range=BehaviorRange(minimum=11.2,maximum=13.1,unit="kn"),sample_count=48220,distribution=[1,2,3,5,9,18,34,57,81,96,82,54,27,11,4]),
                SpeedBehaviorProfile(phase="maneuvering",average=3.2,median=2.9,p95=5.4,typical_range=BehaviorRange(minimum=1.2,maximum=5.1,unit="kn"),sample_count=8840,distribution=[8,24,58,91,76,43,19,7]),
                SpeedBehaviorProfile(phase="anchorage",average=.3,median=.2,p95=.8,typical_range=BehaviorRange(minimum=0,maximum=1,unit="kn"),sample_count=4210,distribution=[91,54,22,8,2]),
            ],
            ports=[
                PortBehaviorProfile(port_id="aktau",port_name="Aktau",visits=61,share=.43,median_stay_hours=6.8,typical_stay=BehaviorRange(minimum=4,maximum=11,unit="h"),usual=True),
                PortBehaviorProfile(port_id="baku",port_name="Baku",visits=57,share=.40,median_stay_hours=7.2,typical_stay=BehaviorRange(minimum=4.5,maximum=12,unit="h"),usual=True),
                PortBehaviorProfile(port_id="turkmenbashi",port_name="Turkmenbashi",visits=18,share=.13,median_stay_hours=8.4,typical_stay=BehaviorRange(minimum=5,maximum=14,unit="h"),usual=True),
                PortBehaviorProfile(port_id="kuryk",port_name="Kuryk",visits=5,share=.035,median_stay_hours=5.9,typical_stay=BehaviorRange(minimum=3,maximum=9,unit="h"),usual=False),
                PortBehaviorProfile(port_id="other",port_name="Other",visits=2,share=.015,median_stay_hours=4.1,typical_stay=BehaviorRange(minimum=2,maximum=7,unit="h"),usual=False),
            ],
            stop_areas=[StopAreaProfile(id="stop-1",latitude=41.52,longitude=50.32,stops=12,average_duration_minutes=19,radius_km=3.2),StopAreaProfile(id="stop-2",latitude=40.94,longitude=50.09,stops=7,average_duration_minutes=27,radius_km=2.4),StopAreaProfile(id="stop-3",latitude=41.88,longitude=50.54,stops=5,average_duration_minutes=31,radius_km=2.8)],
            average_stop_minutes=24, draught_typical=BehaviorRange(minimum=4.5,maximum=5.1,unit="m"),
            draught_history=[DraughtHistoryItem(voyage_id="140",origin="Aktau",destination="Baku",departure_draught=4.7,arrival_draught=4.8),DraughtHistoryItem(voyage_id="141",origin="Baku",destination="Aktau",departure_draught=5.2,arrival_draught=4.1),DraughtHistoryItem(voyage_id="142",origin="Aktau",destination="Turkmenbashi",departure_draught=4.3,arrival_draught=4.4),DraughtHistoryItem(voyage_id="143",origin="Baku",destination="Aktau",departure_draught=4.8,arrival_draught=4.8)],
            departure_pattern=[7,58,29,6], voyages_by_day=[18,24,22,25,19,9,5], activity_cells=[[40.37,49.89,1],[40.75,50.02,.72],[41.15,50.18,.64],[41.55,50.34,.91],[41.9,50.53,.75],[42.31,50.74,1],[40.02,52.97,.31]],
            current_comparison=[CurrentComparison(parameter="Speed",typical="11.2–13.1 kn",current="12.4 kn"),CurrentComparison(parameter="Distance",typical="380–405 km",current="258 km so far"),CurrentComparison(parameter="Duration",typical="27–31 h",current="16 h so far"),CurrentComparison(parameter="Stops",typical="0–1",current="0"),CurrentComparison(parameter="Route",typical="Baku → Aktau",current="Baku → Aktau"),CurrentComparison(parameter="Draught",typical="4.5–5.1 m",current="4.8 m")],
        )


behavior_engine = BehaviorEngine()
