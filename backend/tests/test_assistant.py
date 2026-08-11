import unittest

from fastapi import HTTPException
from backend.app.assistant import AssistantService
from backend.app.main import app, assistant_chat, assistant_tools, health, login
from backend.app.models import AssistantChatRequest, LoginRequest


class AssistantServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = AssistantService()
        self.user_id = "analyst-test"
        self.conversation_id: str | None = None

    def chat(self, question: str, *, context: dict | None = None, role: str = "ANALYST"):
        response = self.service.chat(
            {
                "question": question,
                "conversation_id": self.conversation_id,
                "context": context or {},
            },
            user_id=self.user_id,
            role=role,
        )
        self.conversation_id = response.conversation_id
        return response

    def test_tool_layer_exposes_all_required_reads_and_separate_confirmed_writes(self) -> None:
        tools = self.service.list_tools("ANALYST")
        names = {item["name"] for item in tools}
        required = {
            "get_vessel", "get_current_voyage", "get_vessel_events", "get_vessel_risk",
            "get_risk_factors", "get_behavior_profile", "get_encounters", "get_cargo_analysis",
            "get_fuel_analysis", "get_vessel_network", "search_vessels", "search_events",
            "search_area", "get_port_status", "get_arrivals", "get_port_forecast",
        }
        self.assertTrue(required.issubset(names))
        writes = [item for item in tools if item["mode"] == "write"]
        self.assertEqual(len(writes), 7)
        self.assertTrue(all(item["requires_confirmation"] for item in writes))
        dispatcher = {item["name"]: item for item in self.service.list_tools("PORT_DISPATCHER")}
        self.assertTrue(dispatcher["assign_berth"]["allowed"])
        self.assertTrue(dispatcher["change_port_queue"]["allowed"])
        self.assertFalse(dispatcher["create_investigation"]["allowed"])
        viewer = {item["name"]: item for item in self.service.list_tools("VIEWER")}
        self.assertTrue(viewer["get_port_status"]["allowed"])
        self.assertFalse(viewer["get_risk_factors"]["allowed"])

    def test_attention_and_risk_explanation_are_grounded_in_domain_results(self) -> None:
        attention = self.chat("Какие суда сейчас требуют внимания?")
        self.assertEqual([claim.statement.split(" — ")[0] for claim in attention.claims], [
            "CASPIAN STAR", "TURAN", "BAKU EXPRESS",
        ])
        self.assertEqual([claim.statement.split(" — ")[1].split(" /")[0] for claim in attention.claims], ["91", "71", "63"])
        self.assertEqual([tool.name for tool in attention.tools_called], ["search_vessels"])
        self.assertTrue(all(claim.evidence for claim in attention.claims))

        explanation = self.chat("Почему CASPIAN STAR?")
        self.assertIn("— 91", explanation.title)
        self.assertIn("8 текущих Risk Factors", explanation.answer)
        self.assertEqual([tool.name for tool in explanation.tools_called], ["get_vessel_risk", "get_risk_factors"])
        self.assertEqual(len(explanation.claims), 9)
        self.assertTrue(all(claim.evidence for claim in explanation.claims))
        factor_sources = {claim.evidence[0].id for claim in explanation.claims[:-1]}
        self.assertIn("RF-EV-2802", factor_sources)
        self.assertIn("RF-ADV-6005", factor_sources)

    def test_natural_language_filter_and_conversation_context(self) -> None:
        gaps = self.chat("Покажи суда, у которых AIS отсутствовал более 3 часов за последние 30 дней.")
        self.assertFalse(gaps.no_data)
        self.assertEqual(gaps.tools_called[0].arguments["duration_gt_minutes"], 180)
        self.assertTrue(any("3h 15m" in claim.statement for claim in gaps.claims))

        self.chat("Почему CASPIAN STAR?")
        encounter = self.chat("С кем оно встречалось?")
        self.assertIn("TURAN", encounter.title)
        self.assertTrue(any("174" in claim.statement and "167" in claim.statement for claim in encounter.claims))
        history = self.chat("Они встречались раньше?")
        self.assertTrue(any("14 встреч" in claim.statement for claim in history.claims))
        self.assertTrue(any("18.7 h" in claim.statement for claim in history.claims))

    def test_case_write_flow_requires_confirmation_and_summary_uses_only_evidence(self) -> None:
        proposal = self.chat("Создай расследование по CASPIAN STAR.")
        self.assertEqual(self.service.list_investigations(role="ANALYST"), [])
        action = proposal.actions[0]
        self.assertEqual(action.status, "pending")
        self.assertTrue(action.requires_confirmation)

        decided = self.service.decide_action(
            action.id, confirmed=True, user_id=self.user_id, role="ANALYST",
        )
        case = decided["investigation"]
        self.assertEqual(case.id, "CI-2026-00421")
        self.assertEqual(case.priority, "high")
        self.assertEqual(case.evidence, [])

        evidence_proposal = self.chat("Добавь AIS gap и встречу в доказательства.")
        evidence_action = evidence_proposal.actions[0]
        self.assertEqual(evidence_action.payload["evidence_ids"], ["EV-2802", "EV-2803"])
        decided = self.service.decide_action(
            evidence_action.id, confirmed=True, user_id=self.user_id, role="ANALYST",
        )
        self.assertEqual([item.source_id for item in decided["investigation"].evidence], ["EV-2802", "EV-2803"])

        summary = self.chat("Суммируй расследование.")
        self.assertEqual(summary.title, "Резюме CI-2026-00421")
        self.assertEqual({link.id for claim in summary.claims[:-1] for link in claim.evidence}, {"EV-2802", "EV-2803"})
        self.assertTrue(any(claim.kind == "inference" for claim in summary.claims))

    def test_write_action_is_bound_to_requesting_user_and_cannot_be_replayed(self) -> None:
        action = self.chat("Создай расследование по CASPIAN STAR.").actions[0]
        with self.assertRaises(HTTPException) as denied:
            self.service.decide_action(action.id, confirmed=True, user_id="another-analyst", role="ANALYST")
        self.assertEqual(denied.exception.status_code, 403)

        self.service.decide_action(action.id, confirmed=False, user_id=self.user_id, role="ANALYST")
        with self.assertRaises(HTTPException) as replay:
            self.service.decide_action(action.id, confirmed=True, user_id=self.user_id, role="ANALYST")
        self.assertEqual(replay.exception.status_code, 409)

    def test_port_dispatcher_gets_port_answers_but_not_security_factor_details(self) -> None:
        port = self.chat("Почему Актау будет перегружен через 4 часа?", role="PORT_DISPATCHER")
        self.assertFalse(port.no_data)
        self.assertEqual([tool.name for tool in port.tools_called], ["get_port_status", "get_arrivals", "get_port_forecast"])

        protected = self.chat(
            "Почему риск CASPIAN STAR?",
            context={"vessel_id": "caspian-star"},
            role="PORT_DISPATCHER",
        )
        self.assertTrue(protected.no_data)
        self.assertEqual(protected.title, "Доступ ограничен")
        self.assertTrue(any(tool.name == "get_risk_factors" and tool.status == "denied" for tool in protected.tools_called))
        self.assertNotIn("AIS gap", protected.answer)

    def test_spatial_answer_requires_area_and_returns_only_selected_bounds(self) -> None:
        missing = self.chat("Что происходило здесь за последние 24 часа?")
        self.assertTrue(missing.no_data)
        area = self.chat("Что происходило здесь за последние 24 часа?", context={
            "current_page": "/app/map",
            "area": {
                "west": 49, "south": 40, "east": 53.5, "north": 44.5,
                "from_time": "2026-08-09T19:00:00+05:00",
                "to_time": "2026-08-10T19:00:00+05:00",
            },
        })
        self.assertFalse(area.no_data)
        self.assertEqual(area.tools_called[0].name, "search_area")
        self.assertTrue(all(claim.evidence for claim in area.claims))

    def test_no_data_and_audit_never_fabricate_an_answer(self) -> None:
        response = self.chat("Какой цвет корпуса у неизвестного судна?")
        self.assertTrue(response.no_data)
        self.assertEqual(response.claims, [])
        audit = self.service.list_audit(role="ANALYST")
        self.assertEqual(audit[0].question, "Какой цвет корпуса у неизвестного судна?")
        self.assertEqual(audit[0].outcome, "insufficient_data")
        self.assertEqual(audit[0].tools_called, ["search_vessels", "search_events"])


class AssistantApiTests(unittest.TestCase):
    def test_stage_eight_routes_and_rbac_contract_are_published(self) -> None:
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/assistant/chat", paths)
        self.assertIn("/api/v1/investigations/{investigation_id}/evidence", paths)
        self.assertGreaterEqual(len(assistant_tools("ANALYST")["tools"]), 23)
        chat = assistant_chat(AssistantChatRequest(question="Какие суда сейчас требуют внимания?"), "ANALYST")
        self.assertEqual(chat.claims[0].statement.split(" — ")[0], "CASPIAN STAR")
        self.assertEqual(health()["platform_version"], "0.10.0")

        dispatcher = login(LoginRequest(email="dispatcher@aktau.kz", password="demo"))
        self.assertEqual(dispatcher.access_token, "ci-demo-port-dispatcher")
        self.assertEqual(dispatcher.role, "PORT_DISPATCHER")


if __name__ == "__main__":
    unittest.main()
