import unittest

from fastapi import HTTPException

from backend.app.environmental import EnvironmentalIntelligenceService
from backend.app.assistant import AssistantService
from backend.app.main import app, health
from backend.app.models import (
    AssistantChatRequest, AssistantContext, EnvironmentalRawIngestRequest,
    EnvironmentalReviewRequest,
)


class EnvironmentalIntelligenceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EnvironmentalIntelligenceService()

    def test_environmental_center_has_required_operational_counts(self) -> None:
        result = self.service.list_events()
        self.assertEqual(result.total, 21)
        self.assertEqual(result.active_count, 4)
        self.assertEqual(result.high_priority_count, 1)
        self.assertEqual(result.in_investigation_count, 2)
        self.assertEqual(result.resolved_count, 17)
        self.assertEqual(result.items[0].id, "ENV-2026-00142")

        investigations = self.service.list_events("INVESTIGATION")
        self.assertEqual(investigations.total, 2)
        self.assertTrue(all(item.status == "INVESTIGATION" for item in investigations.items))

    def test_detailed_event_has_geometry_provenance_and_separate_raw_source(self) -> None:
        event = self.service.get_event("ENV-142")
        self.assertEqual(event.id, "ENV-2026-00142")
        self.assertEqual(event.type, "OIL_POLLUTION")
        self.assertEqual(event.detected_at, "2026-05-14T08:40:00+05:00")
        self.assertEqual(event.area_km2, 3.4)
        self.assertEqual(event.confidence, .87)
        self.assertEqual(event.status, "UNDER REVIEW")
        self.assertEqual(event.geometry.type, "Polygon")
        self.assertEqual(event.geometry.coordinates[0][0], event.geometry.coordinates[0][-1])
        self.assertEqual({item.provenance for item in event.environmental_data}, {"ESTIMATED"})

        raw = self.service.get_raw_for_event(event.id)
        self.assertEqual(raw.id, event.raw_data_id)
        self.assertEqual(raw.input_type, "PREPROCESSED_SATELLITE")
        self.assertTrue(raw.checksum.startswith("sha256:"))
        self.assertEqual(raw.event_id, event.id)

        event.status = "RESOLVED"
        raw.payload["area_km2"] = 999
        self.assertEqual(self.service.get_event(event.id).status, "UNDER REVIEW")
        self.assertEqual(self.service.get_raw_for_event(event.id).payload["area_km2"], 3.4)

    def test_historical_search_reduces_twelve_candidates_to_three_relevant_vessels(self) -> None:
        normal = self.service.get_candidates("ENV-142")
        self.assertEqual(normal.searched_candidate_count, 12)
        self.assertEqual(normal.relevant_candidate_count, 3)
        self.assertEqual(len(normal.candidates), 3)
        self.assertEqual(normal.extended_candidates, [])
        self.assertEqual(
            [(item.vessel_name, item.distance_km, item.temporal_overlap_percent, item.relevance) for item in normal.candidates],
            [
                ("CASPIAN STAR", .8, 94, "HIGH"),
                ("TURAN", 2.4, 72, "MEDIUM"),
                ("BAKU EXPRESS", 7.1, 31, "LOW"),
            ],
        )
        self.assertTrue(normal.candidates[0].ais_gap)
        self.assertTrue(all(item.provenance == "INFERRED" for item in normal.candidates))
        self.assertTrue(all(item.evidence_ids for item in normal.candidates))
        self.assertIn("not establish", normal.disclaimer)

        extended = self.service.get_candidates("ENV-142", include_extended=True)
        self.assertEqual(len(extended.extended_candidates), 9)
        self.assertTrue(all(item.relevance == "EXCLUDED" for item in extended.extended_candidates))

    def test_risk_context_is_explicit_and_does_not_replace_canonical_risk(self) -> None:
        context = self.service.get_risk_context("ENV-142", "caspian-star")
        self.assertEqual(context.maritime_risk_score, 91)
        self.assertEqual(context.environmental_adjustment_raw, 8)
        self.assertEqual(context.environmental_adjustment_effective, 8)
        self.assertEqual(context.combined_context_score, 99)
        self.assertEqual(context.status, "UNDER REVIEW")
        self.assertEqual(context.provenance, "INFERRED")
        self.assertIn("ENV-2026-00142", context.source_ids)
        self.assertEqual(
            {factor.code for factor in context.factors},
            {
                "ENVIRONMENTAL_PROXIMITY", "ENVIRONMENTAL_TIME_OVERLAP",
                "ENVIRONMENTAL_ROUTE_MATCH", "ENVIRONMENTAL_ASSOCIATION",
            },
        )
        self.assertEqual(sum(factor.contribution for factor in context.factors), 8)
        self.assertTrue(all(factor.source_ids for factor in context.factors))
        self.assertEqual(context.model_version, "CI-ENV-RISK-1.0")
        self.assertIn("not written into the canonical CI-RISK-2.0", context.disclaimer)
        with self.assertRaises(HTTPException) as missing:
            self.service.get_risk_context("ENV-142", "turan")
        self.assertEqual(missing.exception.status_code, 404)

    def test_backward_reconstruction_keeps_origin_as_interval_and_area(self) -> None:
        reconstruction = self.service.get_reconstruction("ENV-142")
        self.assertEqual(reconstruction.estimated_origin_from, "2026-05-14T03:20:00+05:00")
        self.assertEqual(reconstruction.estimated_origin_to, "2026-05-14T05:40:00+05:00")
        self.assertEqual(reconstruction.origin_geometry.type, "MultiPolygon")
        self.assertEqual(reconstruction.current_geometry.type, "Polygon")
        self.assertEqual(reconstruction.wind.value, 14)
        self.assertEqual(reconstruction.current.value, .7)
        self.assertEqual(len(reconstruction.steps), 4)
        self.assertTrue(all(step.provenance == "ESTIMATED" for step in reconstruction.steps))
        self.assertIn("not an exact time", reconstruction.limitation)

    def test_timeline_and_replay_label_observed_estimated_and_inferred_data(self) -> None:
        timeline = self.service.get_timeline("ENV-142")
        self.assertEqual(timeline.items[0].timestamp, "2026-05-14T03:20:00+05:00")
        self.assertEqual(timeline.items[-2].timestamp, "2026-05-14T08:40:00+05:00")
        self.assertEqual(
            {item.provenance for item in timeline.items},
            {"OBSERVED", "ESTIMATED", "INFERRED"},
        )
        self.assertTrue(all(item.source_ids for item in timeline.items))

        replay = self.service.get_replay("ENV-142")
        self.assertEqual(replay.started_at, "2026-05-14T03:00:00+05:00")
        self.assertEqual(replay.ended_at, "2026-05-14T08:40:00+05:00")
        self.assertEqual(replay.step_minutes, 40)
        self.assertEqual(len(replay.frames), 10)
        self.assertTrue(all(len(frame.vessels) == 3 for frame in replay.frames))
        self.assertTrue(any(not frame.vessels[0].ais_available for frame in replay.frames))
        self.assertTrue(any(frame.vessels[0].provenance == "ESTIMATED" for frame in replay.frames))

    def test_vessel_environment_profile_contains_may_march_and_january_history(self) -> None:
        profile = self.service.get_vessel_environment("caspian-star")
        self.assertEqual(profile.vessel_name, "CASPIAN STAR")
        self.assertEqual(profile.candidate_event_count, 3)
        self.assertEqual([item.occurred_at[5:7] for item in profile.history], ["05", "03", "01"])
        self.assertEqual(profile.history[0].relationship, "CANDIDATE")
        self.assertEqual(profile.history[1].relationship, "CLEARED")
        self.assertTrue(all(item.source_ids for item in profile.history))

    def test_gateway_adapter_retains_raw_provider_payload_and_normalizes_event(self) -> None:
        self.service.gateway.register_adapter(
            "vendor-x",
            lambda payload: {
                "type": payload["finding"],
                "title": payload["label"],
                "geometry": payload["shape"],
                "center": payload["centroid"],
                "area_km2": payload["area"],
                "priority": "MEDIUM",
            },
        )
        vendor_payload = {
            "finding": "FLOATING_WASTE",
            "label": "Provider-specific observation",
            "shape": {
                "type": "Polygon",
                "coordinates": [[[51.0, 43.0], [51.1, 43.0], [51.1, 43.1], [51.0, 43.0]]],
            },
            "centroid": {"latitude": 43.04, "longitude": 51.05},
            "area": 1.8,
            "provider_only_field": "retained only in raw data",
        }
        event = self.service.create_event(
            EnvironmentalRawIngestRequest(
                provider="vendor-x", input_type="EXTERNAL_API",
                observed_at="2026-05-15T08:00:00+05:00",
                source_reference="VENDOR-X-991", payload=vendor_payload, confidence=.76,
            ),
            created_by="analyst-test",
        )
        self.assertEqual(event.type, "FLOATING_WASTE")
        self.assertEqual(event.id, "ENV-2026-00146")
        self.assertEqual(self.service.get_event("ENV-143").title, "Floating material observation")
        self.assertEqual(self.service.list_events().total, 22)
        raw = self.service.get_raw_for_event(event.id)
        self.assertEqual(raw.payload["provider_only_field"], "retained only in raw data")
        self.assertNotIn("provider_only_field", event.model_dump())
        self.assertEqual(raw.created_by, "analyst-test")

    def test_invalid_geometry_and_unknown_records_fail_explicitly(self) -> None:
        request = EnvironmentalRawIngestRequest(
            provider="manual", input_type="MANUAL",
            observed_at="2026-05-15T08:00:00+05:00", source_reference="MANUAL-1",
            payload={"center": {"latitude": 43, "longitude": 51}, "area_km2": 1},
        )
        with self.assertRaises(HTTPException) as invalid:
            self.service.create_event(request, created_by="analyst-test")
        self.assertEqual(invalid.exception.status_code, 422)
        invalid.payload = {
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[201, 43], [51.1, 43], [51.1, 43.1], [201, 43]]],
            },
            "center": {"latitude": 43, "longitude": 51},
            "area_km2": 1,
        }
        with self.assertRaises(HTTPException) as outside_wgs84:
            self.service.create_event(request, created_by="analyst-test")
        self.assertEqual(outside_wgs84.exception.status_code, 422)
        with self.assertRaises(HTTPException) as missing:
            self.service.get_event("ENV-DOES-NOT-EXIST")
        self.assertEqual(missing.exception.status_code, 404)

    def test_human_review_and_investigation_link_are_auditable_writes(self) -> None:
        result = self.service.review_event(
            "ENV-142",
            EnvironmentalReviewRequest(
                outcome="LIKELY POLLUTION", source_classification="UNKNOWN",
                note="Signature remains likely, but the source is not verified.",
            ),
            reviewer="analyst-test",
        )
        self.assertEqual(result.event.status, "UNDER REVIEW")
        self.assertEqual(result.review.provenance, "OBSERVED")
        self.assertEqual(self.service.list_reviews("ENV-142")[0].reviewer, "analyst-test")

        linked = self.service.link_investigation("ENV-142", "ENV-2026-0041")
        self.assertEqual(linked.status, "INVESTIGATION")
        self.assertEqual(linked.investigation_id, "ENV-2026-0041")

        dismissed = self.service.review_event(
            "ENV-142",
            EnvironmentalReviewRequest(
                outcome="FALSE POSITIVE", source_classification="VERIFIED EXTERNAL FINDING",
                note="External validation identified a look-alike surface pattern.",
            ),
            reviewer="senior-analyst",
        )
        self.assertEqual(dismissed.event.status, "FALSE POSITIVE")


class EnvironmentalAssistantIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assistant = AssistantService()
        self.context = AssistantContext(
            current_page="/app/environment/events/ENV-2026-00142",
            environmental_event_id="ENV-2026-00142",
        )

    def ask(self, question: str):
        return self.assistant.chat(
            AssistantChatRequest(question=question, context=self.context),
            user_id="environment-analyst",
            role="ANALYST",
        )

    def test_grounded_environmental_conversation_uses_tools_and_evidence(self) -> None:
        known = self.ask("Что известно про ENV-142?")
        self.assertEqual(
            [item.name for item in known.tools_called],
            ["get_environmental_event", "get_environmental_reconstruction"],
        )
        self.assertTrue(all(claim.evidence for claim in known.claims))
        self.assertTrue(any(claim.kind == "estimate" for claim in known.claims))

        candidates = self.ask("Какие суда могли быть связаны?")
        self.assertEqual(candidates.tools_called[-1].record_count, 1)
        self.assertEqual(len(candidates.claims), 4)
        self.assertTrue(all(claim.kind == "inference" for claim in candidates.claims))
        self.assertIn("CASPIAN STAR", candidates.claims[0].statement)

        why = self.ask("Почему CASPIAN STAR первый кандидат?")
        self.assertEqual(why.title, "Почему CASPIAN STAR — первый кандидат")
        self.assertEqual({claim.kind for claim in why.claims}, {"fact", "estimate", "inference"})
        self.assertTrue(all(claim.evidence[0].href.startswith("/app/environment/") for claim in why.claims))

    def test_environmental_case_requires_confirmation_and_collects_only_grounded_evidence(self) -> None:
        proposal = self.ask("Создай расследование по ENV-142.")
        self.assertEqual(len(proposal.actions), 1)
        action = proposal.actions[0]
        self.assertTrue(action.requires_confirmation)
        self.assertEqual(action.status, "pending")

        result = self.assistant.decide_action(
            action.id,
            confirmed=True,
            user_id="environment-analyst",
            role="ANALYST",
        )
        case = result["investigation"]
        self.assertEqual(case.id, "ENV-2026-0041")
        self.assertEqual(case.case_type, "environmental")
        self.assertEqual(case.environmental_event_id, "ENV-2026-00142")
        self.assertGreaterEqual(len(case.evidence), 10)
        self.assertEqual(len(case.timeline), 9)
        self.assertEqual({item.claim_kind for item in case.evidence}, {"fact", "estimate", "inference"})
        self.assertTrue(all(item.source_href.startswith("/app/environment/") for item in case.evidence))

    def test_stage_nine_routes_and_version_are_published(self) -> None:
        paths = app.openapi()["paths"]
        required = {
            "/api/v1/environment/events",
            "/api/v1/environment/events/{event_id}",
            "/api/v1/environment/events/{event_id}/candidates",
            "/api/v1/environment/events/{event_id}/reconstruction",
            "/api/v1/environment/events/{event_id}/timeline",
            "/api/v1/environment/events/{event_id}/replay",
            "/api/v1/environment/events/{event_id}/review",
            "/api/v1/environment/events/{event_id}/investigation",
            "/api/v1/vessels/{vessel_id}/environment",
        }
        self.assertTrue(required.issubset(paths))
        self.assertEqual(app.version, "0.10.0")
        self.assertEqual(health()["platform_version"], "0.10.0")


if __name__ == "__main__":
    unittest.main()
