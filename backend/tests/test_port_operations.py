import unittest

from fastapi import HTTPException

from backend.app.port_operations import PORT_MODEL_VERSION, PortOperationsService


class PortOperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.port = PortOperationsService()

    def test_control_center_overview_and_arrivals_match_demo_contract(self) -> None:
        overview = self.port.get_overview()
        arrivals = self.port.get_arrivals()

        self.assertEqual(overview.port_load_percent, 68)
        self.assertEqual(
            (overview.arriving_vessels, overview.in_port, overview.waiting, overview.departing),
            (7, 5, 3, 2),
        )
        self.assertEqual(overview.average_wait_minutes, 102)
        self.assertEqual((overview.berths_available, overview.berths_occupied), (3, 5))
        self.assertEqual(overview.high_risk_arrivals, 1)
        self.assertEqual(len(arrivals), 7)
        self.assertEqual(self.port.get_high_risk_arrivals()[0].vessel_name, "CASPIAN STAR")
        self.assertEqual(self.port.get_high_risk_arrivals()[0].risk_score, 91)

    def test_eta_is_explainable_and_uses_a_likely_window(self) -> None:
        eta = self.port.get_eta("caspian-star")

        self.assertEqual(eta.reported_eta, "2026-08-10T14:30:00+05:00")
        self.assertEqual(eta.predicted_eta, "2026-08-10T15:05:00+05:00")
        self.assertEqual(eta.expected_delay_minutes, 35)
        self.assertEqual(eta.confidence, .87)
        self.assertEqual(eta.likely_window_start[11:16], "14:52")
        self.assertEqual(eta.likely_window_end[11:16], "15:18")
        self.assertEqual({item.name for item in eta.factors}, {"distance", "speed", "route", "weather"})
        self.assertIn("planning estimate", eta.disclaimer)

    def test_berth_compatibility_and_service_prediction_are_vessel_specific(self) -> None:
        recommendation = self.port.get_berth_recommendation("pc-aktau-143")
        berth_five = self.port.check_berth_compatibility("pc-aktau-143", "berth-5")
        berth_two = self.port.check_berth_compatibility("pc-aktau-143", "berth-2")
        service = recommendation.service_prediction

        self.assertTrue(berth_five.compatible)
        self.assertFalse(berth_two.compatible)
        self.assertGreaterEqual(len(berth_two.blocking_reasons), 2)
        self.assertEqual(recommendation.recommended_berth_number, 5)
        self.assertTrue(recommendation.human_decision_required)
        self.assertEqual(
            (service.cargo_handling_minutes, service.documentation_minutes, service.other_operations_minutes),
            (240, 35, 25),
        )
        self.assertEqual(service.total_minutes, 300)
        self.assertEqual(service.confidence, .82)
        self.assertEqual(service.berth_available_from[11:16], "14:45")
        self.assertEqual(service.projected_release_at[11:16], "20:05")

    def test_berth_assignment_is_a_human_decision_and_is_audited(self) -> None:
        decision = self.port.decide_berth({
            "port_call_id": "pc-aktau-143",
            "action": "accept",
            "operator": "aktau.dispatcher",
            "note": "Compatibility and pre-arrival review acknowledged",
        })
        call = self.port.get_port_call("pc-aktau-143")

        self.assertFalse(decision.automated)
        self.assertEqual(decision.selected_berth_id, "berth-5")
        self.assertEqual(call.berth_assignment_status, "confirmed")
        self.assertEqual(call.status, "berth_assigned")
        self.assertEqual(len(self.port.list_decisions()), 1)

        with self.assertRaises(HTTPException) as context:
            PortOperationsService().decide_berth({
                "port_call_id": "pc-aktau-143",
                "action": "change_berth",
                "operator": "aktau.dispatcher",
                "berth_id": "berth-2",
            })
        self.assertEqual(context.exception.status_code, 409)

    def test_dynamic_queue_forecast_bottleneck_and_recommendation(self) -> None:
        queue = self.port.get_queue()
        forecast = self.port.get_load_forecast()
        recommendation = forecast.recommendations[0]

        self.assertEqual([item.vessel_name for item in queue.items], ["TURAN", "CASPIAN STAR", "BAKU EXPRESS", "CASPIAN WIND"])
        self.assertEqual(queue.average_wait_minutes, 102)
        self.assertEqual([item.handling_pressure_percent for item in forecast.points], [42, 58, 74, 91])
        self.assertEqual(forecast.current_operational_utilization_percent, 68)
        self.assertIn("distinct", forecast.metric_label)
        self.assertEqual(forecast.bottlenecks[0].window_start[11:16], "16:00")
        self.assertEqual(forecast.bottlenecks[0].window_end[11:16], "19:00")
        self.assertEqual(recommendation.average_wait_change_minutes, -42)
        self.assertEqual((recommendation.load_before_percent, recommendation.load_after_percent), (91, 76))
        self.assertTrue(recommendation.human_decision_required)

    def test_weather_recalculation_propagates_through_service_queue_and_load(self) -> None:
        result = self.port.recalculate_for_weather(wind_mps=22)

        self.assertTrue(result.restriction.active)
        self.assertEqual(result.restriction.processing_delay_minutes, 80)
        self.assertEqual(result.previous_service_minutes, 300)
        self.assertEqual(result.recalculated_service.total_minutes, 380)
        self.assertEqual(result.recalculated_service.projected_release_at[11:16], "21:25")
        self.assertGreater(result.recalculated_queue.average_wait_minutes, result.previous_average_wait_minutes)
        self.assertEqual(result.recalculated_load_forecast.points[-1].handling_pressure_percent, 100)
        self.assertEqual(len(result.affected_port_call_ids), 2)

    def test_what_if_isolated_scenario_does_not_mutate_operational_state(self) -> None:
        baseline = self.port.get_queue()
        simulation = self.port.run_simulation({
            "scenario": "vessel_delay",
            "vessel_id": "caspian-star",
            "delay_minutes": 120,
        })
        after = self.port.get_queue()

        self.assertEqual(simulation.baseline_average_wait_minutes, 102)
        self.assertEqual(simulation.simulated_average_wait_minutes, 151)
        self.assertEqual(simulation.berth_congestion_change_percent, 18)
        self.assertEqual([item.vessel_name for item in simulation.simulated_queue.items], ["TURAN", "BAKU EXPRESS", "CASPIAN STAR", "CASPIAN WIND"])
        self.assertEqual(simulation.affected_vessel_ids, ["caspian-star", "baku-express"])
        self.assertFalse(simulation.state_changed)
        self.assertTrue(simulation.human_decision_required)
        self.assertEqual(after, baseline)

    def test_all_basic_what_if_scenarios_are_available(self) -> None:
        baseline = self.port.get_queue()
        berth = self.port.run_simulation({"scenario": "berth_unavailable", "berth_id": "berth-5"})
        service = self.port.run_simulation({"scenario": "service_extension", "service_extension_minutes": 60})
        arrival = self.port.run_simulation({
            "scenario": "new_vessel_arrival",
            "new_vessel_name": "UNPLANNED ARRIVAL",
            "new_vessel_eta": "2026-08-10T16:35:00+05:00",
        })

        self.assertEqual((berth.simulated_average_wait_minutes, berth.berth_congestion_change_percent), (168, 22))
        self.assertEqual((service.simulated_average_wait_minutes, service.berth_congestion_change_percent), (132, 11))
        self.assertEqual(len(arrival.simulated_queue.items), 5)
        self.assertEqual(arrival.simulated_queue.items[-1].vessel_name, "UNPLANNED ARRIVAL")
        self.assertIsNone(arrival.simulated_queue.items[-1].berth_id)
        self.assertFalse(arrival.state_changed)
        self.assertEqual(self.port.get_queue(), baseline)

    def test_pre_arrival_report_exposes_risk_before_arrival(self) -> None:
        report = self.port.get_pre_arrival("pc-aktau-143")

        self.assertEqual(report.risk_score, 91)
        self.assertEqual(report.attention_level, "high")
        self.assertEqual(report.significant_event_count, 7)
        self.assertEqual(report.berth_recommendation.recommended_berth_number, 5)
        self.assertEqual(report.service_prediction.total_minutes, 300)
        self.assertEqual(len(report.recommended_actions), 4)
        self.assertIn("does not establish", report.disclaimer)

    def test_actuals_close_loop_and_keep_reported_and_verified_values_separate(self) -> None:
        feedback = self.port.record_actuals("pc-aktau-143", {
            "actual_arrival": "2026-08-10T15:20:00+05:00",
            "berth_started_at": "2026-08-10T15:35:00+05:00",
            "service_started_at": "2026-08-10T15:50:00+05:00",
            "service_completed_at": "2026-08-10T20:32:00+05:00",
            "actual_departure": "2026-08-10T21:10:00+05:00",
            "verified_cargo_t": 4920,
            "verified_draught_m": 5.1,
            "documents_verified": True,
            "recorded_by": "aktau.operations",
        })
        call = self.port.get_port_call("pc-aktau-143")
        comparisons = {item.metric: item for item in feedback.comparisons}

        self.assertEqual(feedback.reported_cargo.value, 5000)
        self.assertEqual(feedback.reported_cargo.verification_status, "reported")
        self.assertEqual(feedback.verified_cargo.value, 4920)
        self.assertEqual(feedback.verified_cargo.verification_status, "verified")
        self.assertEqual(comparisons["arrival"].error, 15)
        self.assertEqual(comparisons["service_duration"].error, -18)
        self.assertTrue(feedback.closed_loop_complete)
        self.assertEqual(call.status, "departed")
        self.assertEqual(call.verified_draught_m, 5.1)
        self.assertEqual(self.port.get_feedback("pc-aktau-143"), feedback)

    def test_models_are_versioned_deep_copied_and_unknown_ids_are_404(self) -> None:
        self.assertEqual(self.port.model_version, PORT_MODEL_VERSION)
        overview = self.port.get_overview()
        overview.port_load_percent = 1
        self.assertEqual(self.port.get_overview().port_load_percent, 68)
        with self.assertRaises(HTTPException) as context:
            self.port.get_port_call("missing")
        self.assertEqual(context.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
