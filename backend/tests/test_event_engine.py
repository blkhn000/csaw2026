import unittest

from backend.app.event_engine import EventDetectionEngine


class EventDetectionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = EventDetectionEngine()

    def test_all_stage_four_detectors_create_events(self) -> None:
        detected_types = {event.type for event in self.engine.events.values()}
        self.assertEqual(
            detected_types,
            {
                "route_deviation",
                "ais_gap",
                "unusual_stop",
                "unexpected_speed",
                "vessel_encounter",
                "draught_change",
            },
        )

    def test_severity_and_confidence_are_independent(self) -> None:
        ais_gap = next(event for event in self.engine.events.values() if event.type == "ais_gap")
        self.assertEqual(ais_gap.severity, "high")
        self.assertGreaterEqual(ais_gap.confidence, 0.9)
        self.assertEqual(ais_gap.status, "resolved")

    def test_live_positions_do_not_rewrite_detected_event_evidence(self) -> None:
        from datetime import datetime, timezone
        from backend.app.demo_data import VESSELS

        route_event = next(event for event in self.engine.events.values() if event.type == "route_deviation")
        detected_deviation = route_event.data["current_deviation_km"]

        self.engine.detect_route_deviation(VESSELS[0], 41.34, 50.80, datetime.now(timezone.utc))

        self.assertEqual(route_event.data["current_deviation_km"], detected_deviation)

    def test_correlates_same_voyage_events(self) -> None:
        group = next(iter(self.engine.groups.values()))
        self.assertEqual(group.vessel_id, "caspian-star")
        self.assertEqual(group.voyage_id, "voy-001")
        self.assertEqual(len(group.event_ids), 4)

    def test_short_ais_gap_is_not_an_event(self) -> None:
        from datetime import datetime, timedelta, timezone
        from backend.app.demo_data import VESSELS

        start = datetime.now(timezone.utc)
        event = self.engine.detect_ais_gap(VESSELS[0], start, start + timedelta(minutes=8), 42.1, 50.5)
        self.assertIsNone(event)

    def test_active_ais_gap_is_resolved_when_signal_returns(self) -> None:
        from datetime import datetime, timedelta, timezone
        from backend.app.demo_data import VESSELS

        vessel = VESSELS[2]
        now = datetime.now(timezone.utc)
        vessel.last_position_at = (now - timedelta(minutes=25)).isoformat()
        started = self.engine.start_ais_gap(vessel, now, "high")
        self.assertIsNotNone(started)
        restored = self.engine.resolve_active_gap(vessel, now + timedelta(minutes=2))
        self.assertEqual(restored.status, "resolved")
        self.assertIsNotNone(restored.ended_at)


if __name__ == "__main__":
    unittest.main()
