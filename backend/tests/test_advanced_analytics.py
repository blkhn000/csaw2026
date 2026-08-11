import unittest
from datetime import datetime

from fastapi import HTTPException

from backend.app.advanced_analytics import (
    ADVANCED_DISCLAIMER,
    ADVANCED_MODEL_VERSION,
    AdvancedAnalyticsService,
)
from backend.app.event_engine import EventDetectionEngine
from backend.app.models import (
    CargoIntelligence,
    CompanyIntelligence,
    FuelAnalysis,
    InvestigationNetwork,
    RiskFactorReviewRequest,
    VoyageEconomics,
    VoyageIntelligenceSummary,
)
from backend.app.risk_engine import MODEL_VERSION, RiskEngine


class AdvancedAnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analytics = AdvancedAnalyticsService()

    def test_cargo_declaration_profile_timeline_and_source_quality(self) -> None:
        cargo = self.analytics.get_cargo("voy-001")

        self.assertIsInstance(cargo, CargoIntelligence)
        self.assertEqual(cargo.declaration.declared_mass, 5000)
        self.assertEqual(cargo.declaration.cargo_type, "steel")
        self.assertEqual(cargo.declaration.source, "Baku port declaration")
        self.assertEqual(cargo.declaration.verification_status, "reported")
        self.assertEqual(cargo.declaration.confidence, .94)
        datetime.fromisoformat(cargo.declaration.source_timestamp)
        self.assertEqual(len(cargo.timeline), 6)
        self.assertEqual(cargo.timeline[2].source_reference, "EV-2802")
        self.assertAlmostEqual(sum(item.voyage_share for item in cargo.profile.items), 1.0)
        self.assertEqual(cargo.profile.items[0].cargo_type, "Steel")
        self.assertEqual(cargo.profile.current_cargo_historical_share, .41)
        self.assertEqual(
            {item.verification_status for item in cargo.source_quality},
            {"reported", "estimated"},
        )

    def test_verified_port_feedback_is_added_without_overwriting_reported_cargo(self) -> None:
        updated = self.analytics.apply_port_feedback(
            "voy-001",
            verified_cargo_t=4920,
            verified_draught_m=5.1,
            observed_at="2026-08-10T21:10:00+05:00",
        )

        self.assertEqual(updated.declaration.declared_mass, 5000)
        self.assertEqual(updated.declaration.verification_status, "reported")
        self.assertEqual(updated.port_verified_cargo.value, 4920)
        self.assertEqual(updated.port_verified_cargo.verification_status, "verified")
        self.assertEqual(updated.port_verified_draught.value, 5.1)
        self.assertEqual(updated.port_verified_draught.verification_status, "verified")
        self.assertEqual(updated.port_feedback_at, "2026-08-10T21:10:00+05:00")
        self.assertEqual(updated.timeline[-2].type, "cargo_verification")
        self.assertEqual(updated.timeline[-1].type, "draught_verification")

    def test_vessel_specific_draught_model_is_explainable(self) -> None:
        analysis = self.analytics.get_cargo("voy-001").draught_assessment
        model = analysis.model

        self.assertEqual(model.vessel_id, "caspian-star")
        self.assertEqual(model.sample_count, 63)
        self.assertEqual(model.confidence, .87)
        self.assertEqual(model.confidence_level, "high")
        self.assertEqual(
            (model.expected_change_per_reference.minimum, model.expected_change_per_reference.maximum),
            (.21, .26),
        )
        self.assertTrue(analysis.mismatch)
        self.assertEqual(analysis.anomaly_type, "cargo_draught_mismatch")
        self.assertEqual(analysis.observed_change_m, .3)
        self.assertEqual((analysis.expected_change_m.minimum, analysis.expected_change_m.maximum), (1.05, 1.30))
        self.assertIn("does not establish", analysis.disclaimer.lower())

        reverse = self.analytics.evaluate_draught_consistency(0, 1.2, model)
        self.assertEqual(reverse.status, "unexplained_load_change")
        self.assertEqual((reverse.expected_change_m.minimum, reverse.expected_change_m.maximum), (0, 0))
        self.assertIn("no cargo mass change", reverse.explanation.lower())
        self.assertIn("does not establish", reverse.disclaimer.lower())

        insufficient_model = model.model_copy(update={"confidence": .21, "confidence_level": "insufficient", "sample_count": 4})
        insufficient = self.analytics.evaluate_draught_consistency(5000, .3, insufficient_model)
        self.assertEqual(insufficient.status, "insufficient_data")

    def test_fuel_model_distinguishes_reported_estimated_and_verified(self) -> None:
        fuel = self.analytics.get_fuel("voy-001")

        self.assertIsInstance(fuel, FuelAnalysis)
        self.assertEqual((fuel.corrected_expected.minimum, fuel.corrected_expected.maximum), (38, 44))
        self.assertEqual(fuel.weather_correction.multiplier, 1.04)
        self.assertEqual(fuel.operational_correction.multiplier, 1.06)
        self.assertEqual((fuel.reported.value, fuel.reported.verification_status), (61, "reported"))
        self.assertEqual((fuel.estimated.value, fuel.estimated.verification_status), (42, "estimated"))
        self.assertIsNone(fuel.verified.value)
        self.assertEqual(fuel.verified.verification_status, "not_available")
        self.assertEqual(fuel.deviation_from_upper_percent, 38.6)
        self.assertTrue(fuel.anomaly)
        self.assertIn("may have", fuel.disclaimer.lower())

    def test_economics_has_exact_cost_decomposition_and_cautious_result(self) -> None:
        economics = self.analytics.get_economics("voy-001")
        breakdown = economics.cost_breakdown

        self.assertIsInstance(economics, VoyageEconomics)
        self.assertEqual(
            breakdown.fuel + breakdown.port_fees + breakdown.crew + breakdown.handling + breakdown.operating_cost,
            320000,
        )
        self.assertEqual(economics.estimated_voyage_cost, 320000)
        self.assertEqual(economics.cargo_value.value, 250000)
        self.assertEqual(economics.cargo_value.verification_status, "estimated")
        self.assertEqual(economics.value_cost_ratio, .78)
        self.assertEqual((economics.typical_ratio.minimum, economics.typical_ratio.maximum), (2.4, 4.8))
        self.assertTrue(economics.anomaly)
        self.assertIn("not evidence", economics.disclaimer.lower())

    def test_connections_and_network_are_evidence_backed_without_risk_transfer(self) -> None:
        connection = self.analytics.get_connections("caspian-star")[0]
        network = self.analytics.get_network("caspian-star")

        self.assertEqual(connection.related_vessel_name, "TURAN")
        self.assertEqual(connection.encounters_total, 14)
        self.assertEqual(connection.encounters_last_six_months, 9)
        self.assertEqual(connection.open_sea_encounters, 11)
        self.assertEqual(connection.total_duration_minutes, 1122)
        self.assertEqual(connection.strength, "high")
        self.assertIn("14 encounters", connection.explanation)
        self.assertIn("does not establish", connection.disclaimer.lower())
        self.assertIsInstance(network, InvestigationNetwork)
        self.assertEqual(len(network.nodes), 9)
        self.assertEqual(len(network.edges), 9)
        vessel_edge = next(item for item in network.edges if item.type == "encountered")
        self.assertEqual(vessel_edge.evidence[0], "14 encounters")
        self.assertTrue(any(item.source_id == "caspian-star" and item.target_id == "voy-001" for item in network.edges))
        self.assertFalse(any("risk transfer" in item.explanation.lower() for item in network.edges))

    def test_company_contract_returns_deep_copies_and_unknown_is_404(self) -> None:
        company = self.analytics.get_company("company-a")
        vessels = self.analytics.get_company_vessels("company-a")

        self.assertIsInstance(company, CompanyIntelligence)
        self.assertEqual(company.name, "Caspian Marine Co.")
        self.assertEqual([item.id for item in vessels], ["caspian-star", "caspian-wind"])
        self.assertEqual(company.recent_voyages[0].voyage_id, "voy-001")
        self.assertEqual(company.risk_history[-1].average_risk_score, 71)
        self.assertEqual(company.risk_history[-1].model_version, "CI-RISK-2.0")
        self.assertEqual(company.event_type_counts["advanced"], 4)
        company.name = "MUTATED"
        vessels[0].name = "MUTATED"
        self.assertEqual(self.analytics.get_company("company-a").name, "Caspian Marine Co.")
        self.assertEqual(self.analytics.get_company_vessels("company-a")[0].name, "CASPIAN STAR")
        with self.assertRaises(HTTPException) as context:
            self.analytics.get_company("missing-company")
        self.assertEqual(context.exception.status_code, 404)

    def test_advanced_event_types_have_public_review_contract_and_recalculate_signals(self) -> None:
        events = self.analytics.list_events(vessel_id="caspian-star")
        self.assertEqual(
            {item.type for item in events},
            {
                "cargo_anomaly",
                "cargo_draught_mismatch",
                "fuel_anomaly",
                "economic_anomaly",
                "unusual_connection",
            },
        )
        original = self.analytics.get_event("ADV-6003")
        original.explanation = "MUTATED"
        self.assertNotEqual(self.analytics.get_event("ADV-6003").explanation, "MUTATED")

        reviewed = self.analytics.update_event_status(
            "ADV-6003",
            {"status": "reviewed", "note": "Report requested"},
            "fuel.analyst",
        )
        self.assertEqual((reviewed.status, reviewed.reviewed_by, reviewed.review_note), ("reviewed", "fuel.analyst", "Report requested"))
        dismissed = self.analytics.update_event_status(
            "ADV-6003",
            {"status": "dismissed", "note": "Bunker receipt reconciled"},
            "senior.analyst",
        )
        self.assertEqual(dismissed.status, "dismissed")
        signal = next(item for item in self.analytics.risk_signals("caspian-star", "voy-001") if item.type == "fuel_anomaly")
        self.assertEqual(signal.effective_score, 0)

        engine = RiskEngine(EventDetectionEngine(), self.analytics)
        self.assertEqual(engine.get_vessel_risk("caspian-star").risk_score, 89)

    def test_risk_engine_preserves_stage_five_84_and_caps_advanced_context_at_seven(self) -> None:
        engine = RiskEngine(EventDetectionEngine(), self.analytics)
        assessment = engine.get_vessel_risk("caspian-star")
        advanced = [item for item in assessment.factors if item.stage == 6]

        self.assertEqual(MODEL_VERSION, "CI-RISK-2.0")
        self.assertEqual(assessment.base_risk_score, 84)
        self.assertEqual(assessment.advanced_adjustment, 7)
        self.assertEqual(assessment.advanced_adjustment_cap, 7)
        self.assertEqual(assessment.risk_score, 91)
        self.assertEqual([item.adjusted_score for item in advanced], [13, 9, 6, 5])
        self.assertEqual([item.effective_score for item in advanced], [3, 2, 1, 1])
        self.assertEqual(sum(item.effective_score for item in advanced), 7)
        self.assertEqual(len({item.source_event_id for item in advanced}), 4)
        self.assertTrue(all(item.confidence_weighted_score is not None for item in advanced))
        self.assertNotIn("cargo_anomaly", {item.type for item in advanced})

        reviewed = engine.review_factor(
            "RF-ADV-6004",
            RiskFactorReviewRequest(status="FALSE POSITIVE", comment="Commercial terms verified"),
            "economics.analyst",
        )
        self.assertEqual(reviewed.effective_score, 0)
        self.assertEqual(engine.get_vessel_risk("caspian-star").risk_score, 90)

    def test_structured_summary_and_models_are_api_ready(self) -> None:
        summary = self.analytics.get_intelligence("voy-001")

        self.assertIsInstance(summary, VoyageIntelligenceSummary)
        self.assertEqual(summary.significant_factor_count, 7)
        self.assertEqual((summary.base_risk_score, summary.advanced_adjustment, summary.risk_score), (84, 7, 91))
        self.assertEqual(len(summary.main_factor_titles), 5)
        self.assertIn("merit analyst review", summary.summary.lower())
        self.assertEqual(summary.disclaimer, ADVANCED_DISCLAIMER)
        self.assertEqual(self.analytics.model_version, ADVANCED_MODEL_VERSION)

        payloads = [
            self.analytics.get_cargo("voy-001").model_dump(mode="json"),
            self.analytics.get_fuel("voy-001").model_dump(mode="json"),
            self.analytics.get_economics("voy-001").model_dump(mode="json"),
            summary.model_dump(mode="json"),
            self.analytics.get_network("caspian-star").model_dump(mode="json"),
            self.analytics.get_company("company-a").model_dump(mode="json"),
        ]
        self.assertTrue(all(isinstance(payload, dict) for payload in payloads))
        self.assertTrue(all(payload for payload in payloads))

        summary.summary = "MUTATED"
        self.assertNotEqual(self.analytics.get_intelligence("voy-001").summary, "MUTATED")


if __name__ == "__main__":
    unittest.main()
