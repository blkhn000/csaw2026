import unittest
from datetime import datetime

from backend.app.event_engine import EventDetectionEngine
from backend.app.models import RiskFactorReviewRequest, Vessel
from backend.app.risk_engine import MODEL_VERSION, RiskEngine


class RiskEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RiskEngine(EventDetectionEngine())

    def test_level_boundaries_cover_zero_to_one_hundred(self) -> None:
        cases = {
            0: "low",
            24: "low",
            25: "moderate",
            49: "moderate",
            50: "high",
            74: "high",
            75: "critical",
            100: "critical",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(self.engine.level_for_score(score), expected)

    def test_caspian_star_score_has_exact_explainable_decomposition(self) -> None:
        assessment = self.engine.get_vessel_risk("caspian-star")
        stage_five = {factor.type: factor.effective_score for factor in assessment.factors if factor.stage == 5}
        stage_six = {factor.type: factor.effective_score for factor in assessment.factors if factor.stage == 6}

        self.assertEqual(
            stage_five,
            {
                "route_deviation": 12,
                "ais_gap": 22,
                "vessel_encounter": 17,
                "draught_change": 18,
            },
        )
        self.assertEqual(
            stage_six,
            {
                "cargo_draught_mismatch": 3,
                "fuel_anomaly": 2,
                "economic_anomaly": 1,
                "unusual_connection": 1,
            },
        )
        self.assertEqual(assessment.base_risk_score, 84)
        self.assertEqual(assessment.advanced_adjustment, 7)
        self.assertEqual(assessment.advanced_adjustment_cap, 7)
        self.assertEqual(assessment.factor_score, 76)
        self.assertEqual(assessment.correlation_adjustment, 15)
        self.assertEqual(assessment.risk_score, 91)
        self.assertEqual(assessment.risk_level, "critical")
        self.assertEqual(assessment.model_version, MODEL_VERSION)
        self.assertEqual(len({factor.source_event_id for factor in assessment.factors}), 8)
        self.assertIn("Stage 5 operational/event subtotal 84/100", assessment.explanation)

    def test_correlations_are_applied_once_and_capped(self) -> None:
        assessment = self.engine.get_vessel_risk("caspian-star")

        self.assertEqual(sum(item.raw_score for item in assessment.correlations), 18)
        self.assertEqual(sum(item.applied_score for item in assessment.correlations), 15)
        self.assertEqual([item.applied_score for item in assessment.correlations], [4, 6, 5])
        self.assertTrue(assessment.correlations[-1].capped)

    def test_stage_five_timeline_is_deterministic(self) -> None:
        history = self.engine.get_history("caspian-star")

        self.assertEqual([item.risk_score for item in history], [12, 27, 35, 54, 68, 84, 91])
        self.assertEqual(
            [datetime.fromisoformat(item.recorded_at).strftime("%H:%M") for item in history],
            ["08:00", "13:20", "14:10", "17:25", "17:30", "17:40", "17:46"],
        )
        self.assertEqual(
            [item.risk_level for item in history],
            ["low", "moderate", "moderate", "high", "high", "critical", "critical"],
        )
        self.assertTrue(all(item.model_version == "CI-RISK-1.0" for item in history[:-1]))
        self.assertEqual(history[-1].model_version, "CI-RISK-2.0")

    def test_scenario_wording_requires_review_and_never_asserts_guilt(self) -> None:
        assessment = self.engine.get_vessel_risk("caspian-star")
        scenario = assessment.scenarios[0]

        self.assertEqual(scenario.title, "PATTERN REQUIRES REVIEW")
        self.assertEqual(scenario.score_adjustment, 0)
        self.assertIn("does not establish", scenario.explanation.lower())
        self.assertNotIn("illegal transfer detected", scenario.explanation.lower())
        self.assertIn("not evidence of wrongdoing", assessment.disclaimer.lower())

    def test_high_priority_list_matches_demo_ranking(self) -> None:
        items = self.engine.high_priority()

        self.assertEqual(
            [(item.vessel_name, item.risk_score, item.risk_level) for item in items[:4]],
            [
                ("CASPIAN STAR", 91, "critical"),
                ("TURAN", 71, "high"),
                ("BAKU EXPRESS", 63, "high"),
                ("CASPIAN WIND", 51, "high"),
            ],
        )
        self.assertEqual([item.priority_rank for item in items[:4]], [1, 2, 3, 4])

    def test_analyst_review_changes_only_effective_score_and_is_audited(self) -> None:
        reviewed = self.engine.review_factor(
            "RF-EV-2801",
            RiskFactorReviewRequest(status="FALSE POSITIVE", comment="Position source was duplicated"),
            "qa.analyst",
        )
        assessment = self.engine.get_vessel_risk("caspian-star")

        self.assertEqual(reviewed.adjusted_score, 12)
        self.assertEqual(reviewed.effective_score, 0)
        self.assertEqual(reviewed.review_status, "false_positive")
        self.assertEqual(reviewed.reviewed_by, "qa.analyst")
        self.assertIsNotNone(reviewed.reviewed_at)
        self.assertEqual(assessment.base_risk_score, 71)
        self.assertEqual(assessment.advanced_adjustment, 7)
        self.assertEqual(assessment.risk_score, 78)
        self.assertEqual(assessment.risk_level, "critical")
        self.assertEqual(assessment.scenarios, [])
        self.assertEqual(self.engine.get_history("caspian-star")[-1].risk_score, 78)

    def test_synthetic_priority_factor_review_preserves_remaining_assessment(self) -> None:
        reviewed = self.engine.review_factor(
            "RF-turan-1",
            RiskFactorReviewRequest(status="NORMAL OPERATION", comment="Scheduled rendezvous"),
            "priority.analyst",
        )
        turan = self.engine.get_vessel_risk("turan")

        self.assertEqual(reviewed.effective_score, 0)
        self.assertEqual(reviewed.review_status, "normal_operation")
        self.assertEqual(reviewed.reviewed_by, "priority.analyst")
        self.assertEqual(turan.voyage_id, "V-088")
        self.assertEqual(len(turan.factors), 3)
        self.assertEqual(turan.factor_score, 38)
        self.assertEqual(turan.correlation_adjustment, 0)
        self.assertEqual(turan.risk_score, 38)
        self.assertEqual(turan.risk_level, "moderate")
        self.assertEqual(self.engine.get_vessel_risk("baku-express").risk_score, 63)
        self.assertEqual(self.engine.get_vessel_risk("caspian-wind").risk_score, 51)

        restored = self.engine.review_factor(
            "RF-turan-1",
            RiskFactorReviewRequest(status="CONFIRMED RELEVANT", comment="Evidence verified"),
            "senior.analyst",
        )
        self.assertEqual(restored.effective_score, 24)
        self.assertEqual(self.engine.get_vessel_risk("turan").risk_score, 71)

    def test_factor_lifecycle_decay_reduces_risk_without_deleting_evidence(self) -> None:
        updated = self.engine.apply_decay("2026-08-20T18:42:00+05:00")
        caspian = next(item for item in updated if item.vessel_id == "caspian-star")

        self.assertLess(caspian.risk_score, 91)
        self.assertEqual(len(caspian.factors), 8)
        self.assertTrue(all(item.lifecycle == "historical" for item in caspian.factors))
        self.assertTrue(all(item.effective_score < item.adjusted_score for item in caspian.factors))

    def test_current_vessel_state_has_safe_defaults_and_is_updated(self) -> None:
        vessel = Vessel(
            id="test", imo="1", mmsi="2", name="TEST", type="cargo", flag="KZ",
            length=1, width=1, deadweight=1, owner="A", operator="A", latitude=0,
            longitude=0, speed=0, course=0, heading=0, draught=0, destination="B",
            reported_eta="", calculated_eta="", navigation_status="unknown", last_position_at="",
        )
        self.assertEqual((vessel.risk_score, vessel.risk_level, vessel.risk_updated_at), (0, "low", None))

        assessment = self.engine.get_vessel_risk("caspian-star")
        from backend.app.demo_data import VESSELS

        live_vessel = next(item for item in VESSELS if item.id == "caspian-star")
        self.assertEqual(live_vessel.risk_score, assessment.risk_score)
        self.assertEqual(live_vessel.risk_level, assessment.risk_level)

    def test_configuration_and_last_ten_voyages_are_versioned(self) -> None:
        configuration = self.engine.get_configuration()
        voyages = self.engine.voyage_history("caspian-star")

        self.assertEqual(configuration.model_version, MODEL_VERSION)
        self.assertEqual(configuration.correlation_cap, 15)
        self.assertEqual(configuration.advanced_contribution_cap, 7)
        self.assertEqual(configuration.level_thresholds["critical"], [75, 100])
        self.assertEqual(len(voyages), 10)
        self.assertTrue(all(item.model_version == MODEL_VERSION for item in voyages))


if __name__ == "__main__":
    unittest.main()
