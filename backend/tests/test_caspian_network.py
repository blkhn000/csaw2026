import unittest

from fastapi import HTTPException

from backend.app.assistant import AssistantService
from backend.app.caspian_network import (
    NETWORK_DATASET_VERSION,
    NETWORK_MODEL_VERSION,
    CaspianNetworkService,
)
from backend.app.main import app


class CaspianNetworkServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.network = CaspianNetworkService()
        self.analyst = self.network.principal_for_role("ANALYST")
        self.dispatcher = self.network.principal_for_role("PORT_DISPATCHER")

    def test_regional_overview_matches_stage_ten_demo_contract(self) -> None:
        result = self.network.overview(self.analyst)
        self.assertEqual(result["model_version"], NETWORK_MODEL_VERSION)
        self.assertEqual(result["dataset_version"], NETWORK_DATASET_VERSION)
        self.assertEqual(result["metrics"], {
            "vessels_active": 482,
            "voyages_today": 127,
            "port_calls": 84,
            "high_risk": 11,
            "ais_gaps": 23,
            "encounters": 17,
            "environmental_events": 2,
        })
        self.assertEqual(result["region"]["countries"], 5)
        self.assertGreaterEqual(result["region"]["ports_registered"], 9)
        self.assertTrue(result["generated_at"].endswith("Z"))

    def test_one_port_engine_contract_works_for_three_ports(self) -> None:
        for port_id in ("aktau", "baku", "turkmenbashi"):
            port = self.network.get_port(port_id, self.analyst)
            overview = self.network.get_port_overview(port_id, self.analyst)
            arrivals = self.network.get_port_arrivals(port_id, self.analyst)
            berths = self.network.get_port_berths(port_id, self.analyst)
            forecast = self.network.get_port_forecast(port_id, self.analyst)
            self.assertEqual(port.id, port_id)
            self.assertEqual(overview["port_id"], port_id)
            self.assertTrue(arrivals)
            self.assertTrue(berths)
            self.assertTrue(forecast["points"])
            self.assertEqual(port.configuration.configuration_version, "CI-PORT-CONFIG-1.0")

    def test_global_vessel_identity_resolves_cross_source_aliases_and_history(self) -> None:
        identity = self.network.get_vessel_identity("ship_782", self.analyst)
        self.assertEqual(identity.caspian_vessel_id, "CI-VESSEL-000184")
        self.assertEqual(identity.legacy_vessel_id, "caspian-star")
        self.assertGreaterEqual(len(identity.source_aliases), 3)
        self.assertGreaterEqual(len(identity.identity_history), 3)
        result = self.network.resolve_vessel_identity({
            "source_id": "source-baku-port",
            "source_vessel_id": "ship_782",
            "imo": "9384721",
            "mmsi": "436000118",
            "name": "CASPIAN STAR II",
        }, self.analyst)
        self.assertTrue(result.matched)
        self.assertEqual(result.global_id, "CI-VESSEL-000184")
        self.assertEqual(result.status, "CONFIRMED")

    def test_company_alias_resolution_returns_one_global_company(self) -> None:
        identities = []
        for alias in ("CASPIAN SHIPPING LTD", "Caspian Shipping Limited", "Caspian Shipping Ltd."):
            result = self.network.resolve_company_identity({"name": alias}, self.analyst)
            self.assertTrue(result.matched)
            identities.append(result.global_id)
        self.assertEqual(set(identities), {"CI-COMPANY-00421"})

    def test_cross_port_report_preserves_both_sources_and_exact_difference(self) -> None:
        report = self.network.get_cross_port_report("NET-VOY-001", self.analyst)
        cargo = next(item for item in report.comparisons if item.field_name == "cargo_t")
        draught = next(item for item in report.comparisons if item.field_name == "draught_m")
        self.assertEqual(report.departure.port_id, "baku")
        self.assertEqual(report.arrival.port_id, "aktau")
        self.assertEqual(report.departure.cargo_t, 5000)
        self.assertEqual(report.arrival.cargo_t, 4920)
        self.assertEqual(cargo.difference, -80)
        self.assertEqual(cargo.status, "WITHIN_TOLERANCE")
        self.assertAlmostEqual(draught.difference, -.1)
        self.assertEqual(report.next_voyage_id, "NET-VOY-002")
        self.assertEqual({item.status for item in report.provenance}, {"REPORTED", "VERIFIED"})

    def test_risk_routes_graph_search_health_and_coverage_are_regional(self) -> None:
        risks = self.network.list_risk(self.analyst)["items"]
        self.assertEqual([(item.vessel_name, item.score) for item in risks[:3]], [
            ("CASPIAN STAR", 91), ("TURAN", 84), ("VOLGA MARINE", 78),
        ])
        route = self.network.get_route("route-baku-aktau", self.analyst)["route"]
        self.assertEqual(route.voyages, 284)
        self.assertEqual(route.ais_gaps, 17)
        graph = self.network.graph(self.analyst, vessel_id="CI-VESSEL-000184")
        self.assertTrue(graph["evidence_grounded"])
        self.assertTrue(any(edge.relationship == "ENCOUNTERED" and edge.weight == 14 for edge in graph["edges"]))
        search = self.network.search("436000118", self.analyst)
        self.assertEqual(search["groups"]["vessels"][0]["id"], "CI-VESSEL-000184")
        self.assertGreaterEqual(self.network.data_health(self.analyst)["summary"]["online"], 3)
        self.assertTrue(self.network.coverage(self.analyst)["layers"])

    def test_organization_data_scope_blocks_internal_foreign_port_data(self) -> None:
        self.assertEqual(self.network.get_port_overview("aktau", self.dispatcher)["port_id"], "aktau")
        with self.assertRaises(HTTPException) as denied:
            self.network.get_port_overview("baku", self.dispatcher)
        self.assertEqual(denied.exception.status_code, 403)
        with self.assertRaises(HTTPException) as graph_denied:
            self.network.graph(self.dispatcher)
        self.assertEqual(graph_denied.exception.status_code, 403)
        scoped = self.network.overview(self.dispatcher)
        self.assertEqual([item.port_id for item in scoped["port_statuses"]], ["aktau"])
        self.assertIn("port:aktau", scoped["scope"] if "scope" in scoped else self.dispatcher.data_scope)

    def test_adapter_registry_conflicts_provenance_and_observability_are_explicit(self) -> None:
        adapters = self.network.list_adapters(self.analyst)
        self.assertGreaterEqual(len(adapters), 9)
        self.assertIn("fetch_arrivals", adapters[0].capabilities)
        conflicts = self.network.list_conflicts(self.analyst)
        self.assertTrue(conflicts)
        self.assertGreaterEqual(len(conflicts[0].values), 2)
        provenance = self.network.list_provenance("VOYAGE", "NET-VOY-001", self.analyst)
        self.assertGreaterEqual(len(provenance), 4)
        observability = self.network.observability(self.analyst)
        self.assertEqual(observability["event_bus"]["implementation"], "IN_MEMORY_DEMO")
        self.assertEqual(observability["retention"]["hot_days"], 90)


class CaspianNetworkAssistantAndApiTests(unittest.TestCase):
    def test_stage_ten_api_contract_and_version_are_published(self) -> None:
        self.assertEqual(app.version, "0.10.0")
        paths = set(app.openapi()["paths"])
        required = {
            "/api/v1/network/overview", "/api/v1/network/map", "/api/v1/network/risk",
            "/api/v1/network/routes", "/api/v1/network/ports", "/api/v1/network/ports/compare",
            "/api/v1/network/vessels/{vessel_id}/identity",
            "/api/v1/network/identity/vessels/resolve",
            "/api/v1/network/voyages/{voyage_id}/cross-port",
            "/api/v1/network/graph", "/api/v1/network/search",
            "/api/v1/network/data-health", "/api/v1/network/coverage",
            "/api/v1/network/access/me", "/api/v1/ports/{port_id}/forecast",
            "/api/v1/ports/{port_id}/configuration",
        }
        self.assertFalse(required - paths)
        self.assertIn("/ws/network", {route.path for route in app.routes})

    def test_assistant_exposes_and_uses_grounded_regional_tools(self) -> None:
        service = AssistantService()
        catalogue = {item["name"] for item in service.list_tools("ANALYST")}
        self.assertTrue({
            "get_regional_overview", "get_regional_risk", "search_caspian",
            "get_global_vessel_identity", "get_global_vessel_voyages",
            "get_route_intelligence", "get_cross_port_verification",
            "get_regional_network", "get_regional_data_health",
        }.issubset(catalogue))
        response = service.chat(
            {"question": "Какие суда требуют внимания во всем Каспии?", "context": {}},
            user_id="demo-analyst", role="ANALYST",
        )
        self.assertTrue(response.grounded)
        self.assertFalse(response.no_data)
        self.assertEqual(response.tools_called[0].name, "get_regional_risk")
        self.assertIn("CASPIAN STAR", response.claims[0].statement)
        self.assertTrue(all(claim.evidence for claim in response.claims))

        natural_variant = service.chat(
            {"question": "Какие суда по всему Каспию требуют внимания?", "context": {}},
            user_id="demo-analyst", role="ANALYST",
        )
        self.assertEqual(natural_variant.tools_called[0].name, "get_regional_risk")


if __name__ == "__main__":
    unittest.main()
