from .models import Port, Position, Vessel, Voyage

VESSELS = [
    Vessel(id="caspian-star", imo="9384721", mmsi="436000118", name="CASPIAN STAR", type="Cargo vessel", flag="Kazakhstan", length=142, width=21, deadweight=11820, owner="Caspian Marine Co.", operator="Caspian Marine Co.", latitude=42.31, longitude=50.74, speed=12.4, course=47, heading=49, draught=4.8, destination="Aktau", reported_eta="15:05", calculated_eta="15:12", navigation_status="underway", last_position_at="2026-08-10T14:40:00+05:00"),
    Vessel(id="khazar-wave", imo="9261840", mmsi="423000712", name="KHAZAR WAVE", type="Oil tanker", flag="Azerbaijan", length=155, width=24, deadweight=13400, owner="Khazar Shipping", operator="ASCO", latitude=40.82, longitude=50.21, speed=9.8, course=344, heading=341, draught=6.2, destination="Baku", reported_eta="18:40", calculated_eta="18:47", navigation_status="underway", last_position_at="2026-08-10T14:38:00+05:00"),
    Vessel(id="volga-marine", imo="9142202", mmsi="273451810", name="VOLGA MARINE", type="General cargo", flag="Russia", length=128, width=18, deadweight=7900, owner="Volga Fleet", operator="Volga Fleet", latitude=43.16, longitude=48.91, speed=7.1, course=158, heading=160, draught=3.9, destination="Makhachkala", reported_eta="21:30", calculated_eta="21:25", navigation_status="underway", last_position_at="2026-08-10T14:41:00+05:00"),
]

PORTS = [
    Port(id="aktau", name="Aktau", country="Kazakhstan", latitude=43.65, longitude=51.16, status="operational"),
    Port(id="kuryk", name="Kuryk", country="Kazakhstan", latitude=43.20, longitude=51.65, status="operational"),
    Port(id="baku", name="Baku", country="Azerbaijan", latitude=40.37, longitude=49.89, status="busy"),
    Port(id="alat", name="Alat", country="Azerbaijan", latitude=39.95, longitude=49.41, status="operational"),
    Port(id="turkmenbashi", name="Turkmenbashi", country="Turkmenistan", latitude=40.02, longitude=52.97, status="operational"),
    Port(id="astrakhan", name="Astrakhan", country="Russia", latitude=46.35, longitude=48.04, status="limited"),
    Port(id="makhachkala", name="Makhachkala", country="Russia", latitude=42.97, longitude=47.50, status="operational"),
    Port(id="anzali", name="Anzali", country="Iran", latitude=37.47, longitude=49.47, status="operational"),
    Port(id="amirabad", name="Amirabad", country="Iran", latitude=36.85, longitude=53.37, status="busy"),
]

VOYAGES = [
    Voyage(id="voy-001", vessel_id="caspian-star", origin="Baku", destination="Aktau", departed_at="2026-08-10T08:00:00+05:00", distance_km=387, status="in_progress"),
    Voyage(id="voy-002", vessel_id="caspian-star", origin="Aktau", destination="Baku", departed_at="2026-08-06T07:42:00+05:00", arrived_at="2026-08-06T19:18:00+05:00", distance_km=391, status="completed"),
]

POSITIONS = [
    Position(id="pos-001", vessel_id="caspian-star", mmsi="436000118", latitude=40.37, longitude=49.89, speed=0, course=47, heading=47, navigation_status="moored", recorded_at="2026-08-10T08:00:00+05:00"),
    Position(id="pos-002", vessel_id="caspian-star", mmsi="436000118", latitude=40.53, longitude=49.96, speed=8.4, course=28, heading=29, navigation_status="underway", recorded_at="2026-08-10T08:35:00+05:00"),
    Position(id="pos-003", vessel_id="caspian-star", mmsi="436000118", latitude=40.76, longitude=50.03, speed=11.2, course=20, heading=21, navigation_status="underway", recorded_at="2026-08-10T09:20:00+05:00"),
    Position(id="pos-004", vessel_id="caspian-star", mmsi="436000118", latitude=41.04, longitude=50.13, speed=11.7, course=24, heading=24, navigation_status="underway", recorded_at="2026-08-10T10:15:00+05:00"),
    Position(id="pos-005", vessel_id="caspian-star", mmsi="436000118", latitude=41.31, longitude=50.25, speed=11.8, course=27, heading=28, navigation_status="underway", recorded_at="2026-08-10T11:10:00+05:00"),
    Position(id="pos-006", vessel_id="caspian-star", mmsi="436000118", latitude=41.51, longitude=50.31, speed=0.7, course=31, heading=31, navigation_status="stopped", recorded_at="2026-08-10T12:10:00+05:00"),
    Position(id="pos-007", vessel_id="caspian-star", mmsi="436000118", latitude=41.52, longitude=50.32, speed=0.5, course=31, heading=31, navigation_status="stopped", recorded_at="2026-08-10T12:24:00+05:00"),
    Position(id="pos-008", vessel_id="caspian-star", mmsi="436000118", latitude=41.74, longitude=50.44, speed=11.6, course=36, heading=37, navigation_status="underway", recorded_at="2026-08-10T13:20:00+05:00"),
    Position(id="pos-009", vessel_id="caspian-star", mmsi="436000118", latitude=41.89, longitude=50.52, speed=11.8, course=39, heading=39, navigation_status="underway", recorded_at="2026-08-10T14:10:00+05:00"),
    Position(id="pos-010", vessel_id="caspian-star", mmsi="436000118", latitude=42.04, longitude=50.61, speed=12.0, course=42, heading=42, navigation_status="underway", recorded_at="2026-08-10T17:25:00+05:00"),
    Position(id="pos-011", vessel_id="caspian-star", mmsi="436000118", latitude=42.18, longitude=50.68, speed=12.2, course=45, heading=46, navigation_status="underway", recorded_at="2026-08-10T18:05:00+05:00"),
    Position(id="pos-012", vessel_id="caspian-star", mmsi="436000118", latitude=42.31, longitude=50.74, speed=12.4, course=47, heading=49, navigation_status="underway", recorded_at="2026-08-10T18:42:00+05:00"),
]
