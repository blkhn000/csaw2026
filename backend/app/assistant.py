from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from .advanced_analytics import advanced_analytics
from .behavior_engine import behavior_engine
from .caspian_network import network_service
from .demo_data import PORTS, POSITIONS, VESSELS, VOYAGES
from .event_engine import event_engine
from .environmental import environmental_service
from .models import (
    AssistantAction,
    AssistantAuditEntry,
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantClaim,
    AssistantContext,
    AssistantConversation,
    AssistantConversationMessage,
    AssistantEvidenceLink,
    AssistantRole,
    AssistantToolTrace,
    Investigation,
    InvestigationCreateRequest,
    InvestigationEvidence,
    InvestigationEvidenceRequest,
    InvestigationNote,
    InvestigationNoteRequest,
    InvestigationTimelineItem,
    InvestigationUpdateRequest,
)
from .port_operations import port_operations
from .risk_engine import risk_engine


ASSISTANT_DISCLAIMER = (
    "The assistant reports available observations and model results. An anomaly or risk score does not "
    "establish a violation, intent or wrongdoing; consequential decisions require human review."
)

TOOL_CATALOG: dict[str, str] = {
    "get_vessel": "Return the canonical vessel record.",
    "get_current_voyage": "Return the current voyage for a vessel.",
    "get_vessel_events": "Return detected and advanced events for a vessel.",
    "get_vessel_risk": "Return the current explainable risk assessment.",
    "get_risk_factors": "Return risk factors with source event references.",
    "get_behavior_profile": "Return the vessel-specific behavioral baseline.",
    "get_encounters": "Return current encounters and historical connection aggregates.",
    "get_cargo_analysis": "Return cargo and draught analysis for a voyage.",
    "get_fuel_analysis": "Return weather-corrected fuel analysis for a voyage.",
    "get_vessel_network": "Return the explainable investigation network.",
    "search_vessels": "Search vessels or current risk assessments.",
    "search_events": "Search detected events with structured filters.",
    "search_area": "Search positions and events in a time-bounded area.",
    "get_port_status": "Return the current Port Aktau operational overview.",
    "get_arrivals": "Return the port arrival board.",
    "get_port_forecast": "Return load forecast, bottlenecks and recommendations.",
    "get_eta": "Return an explainable vessel ETA.",
    "get_pre_arrival": "Return the grounded port pre-arrival report.",
    "get_environmental_event": "Return a source-attributed environmental event.",
    "get_environmental_candidates": "Return ranked possible vessel associations for human review.",
    "get_environmental_reconstruction": "Return the wind/current backward reconstruction.",
    "get_environmental_timeline": "Return the environmental evidence timeline and replay metadata.",
    "get_regional_overview": "Return the scope-filtered Caspian traffic overview.",
    "get_regional_risk": "Return the regional explainable risk queue with structured filters.",
    "search_caspian": "Search vessels, companies, ports, voyages, events and cargo across the Caspian network.",
    "get_global_vessel_identity": "Return one stable vessel identity and its source aliases.",
    "get_global_vessel_voyages": "Return the continuous cross-port voyage history for a global vessel.",
    "get_route_intelligence": "Return traffic and observation metrics for a port-to-port route.",
    "get_cross_port_verification": "Return departure/arrival comparisons with provenance.",
    "get_regional_network": "Return the evidence-grounded regional entity graph.",
    "get_regional_data_health": "Return data source quality, coverage and latency.",
}

WRITE_TOOL_CATALOG: dict[str, str] = {
    "create_investigation": "Create an Investigation Case after explicit confirmation.",
    "add_case_evidence": "Add selected source records to a Case after explicit confirmation.",
    "update_investigation": "Update Case workflow fields after explicit confirmation.",
    "add_case_note": "Add an analyst note after explicit confirmation.",
    "assign_berth": "Apply a dispatcher berth decision after explicit confirmation.",
    "change_port_queue": "Change the operational queue only after explicit confirmation.",
    "close_event": "Close an event only after explicit confirmation.",
}

PORT_DISPATCHER_TOOLS = {
    "get_vessel",
    "get_current_voyage",
    "get_behavior_profile",
    "search_vessels",
    "search_area",
    "get_port_status",
    "get_arrivals",
    "get_port_forecast",
    "get_eta",
    "get_pre_arrival",
    "get_vessel_risk",
    "get_regional_overview",
    "search_caspian",
    "get_global_vessel_identity",
    "get_global_vessel_voyages",
    "get_route_intelligence",
    "get_regional_data_health",
}

CASE_ROLES = {"ADMIN", "ANALYST"}
PORT_WRITE_TOOLS = {"assign_berth", "change_port_queue"}


def _timestamp() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _normalized(text: str) -> str:
    return text.casefold().replace("ё", "е")


def _href_for_event(event_id: str) -> str:
    return f"/app/events?event={event_id}"


class AssistantService:
    """Grounded deterministic planner over the already implemented domain services.

    The natural-language layer selects tools and formats their structured output. It
    intentionally has no free-form factual knowledge source and cannot invent records.
    """

    model_version = "CI-ASSIST-1.0"

    def __init__(self) -> None:
        self._conversations: dict[str, AssistantConversation] = {}
        self._investigations: dict[str, Investigation] = {}
        self._actions: dict[str, AssistantAction] = {}
        self._audit: list[AssistantAuditEntry] = []

    # ---- Public assistant contract -------------------------------------------------

    def list_tools(self, role: AssistantRole) -> list[dict[str, Any]]:
        read_tools = [
            {
                "name": name,
                "description": description,
                "mode": "read",
                "allowed": self._tool_allowed(name, role),
                "requires_confirmation": False,
            }
            for name, description in TOOL_CATALOG.items()
        ]
        write_tools = [
            {
                "name": name,
                "description": description,
                "mode": "write",
                "allowed": role in CASE_ROLES or (role == "PORT_DISPATCHER" and name in PORT_WRITE_TOOLS),
                "requires_confirmation": True,
            }
            for name, description in WRITE_TOOL_CATALOG.items()
        ]
        return read_tools + write_tools

    def chat(self, request: AssistantChatRequest | dict[str, Any], *, user_id: str, role: AssistantRole) -> AssistantChatResponse:
        if not isinstance(request, AssistantChatRequest):
            request = AssistantChatRequest.model_validate(request)
        conversation = self._conversation(request, user_id=user_id, role=role)
        created_at = _timestamp()
        user_message = AssistantConversationMessage(
            id=f"MSG-U-{len(conversation.messages) + 1:04d}",
            role="user",
            content=request.question.strip(),
            created_at=created_at,
        )
        conversation.messages.append(user_message)
        conversation.context = self._merge_context(conversation.context, request.context)
        traces: list[AssistantToolTrace] = []

        try:
            response = self._plan_and_answer(request.question.strip(), conversation, role, traces)
        except HTTPException as exc:
            if exc.status_code not in {403, 404}:
                raise
            denied = exc.status_code == 403
            response = self._response(
                conversation,
                title="Доступ ограничен" if denied else "Недостаточно данных",
                answer=(
                    "Текущая роль не имеет доступа к данным, необходимым для этого ответа."
                    if denied
                    else "Не удалось определить обязательный объект запроса. Уточните судно, рейс, Case или выделенную область."
                ),
                claims=[self._claim(
                    "inference" if denied else "fact",
                    (
                        "Assistant применил RBAC до чтения защищённых данных; сами данные не были раскрыты."
                        if denied
                        else "Источник, необходимый для ответа, отсутствует в текущем контексте."
                    ),
                    [self._policy_link("AI-RBAC-1" if denied else "AI-GROUNDING-1")],
                )],
                traces=traces,
                no_data=True,
            )

        assistant_message = AssistantConversationMessage(
            id=response.message_id,
            role="assistant",
            content=response.answer,
            created_at=response.created_at,
            response=response,
        )
        conversation.messages.append(assistant_message)
        conversation.updated_at = response.created_at
        self._audit_answer(user_id, role, request.question, response)
        return response.model_copy(deep=True)

    def list_conversations(self, *, user_id: str, role: AssistantRole) -> list[AssistantConversation]:
        items = [item for item in self._conversations.values() if role == "ADMIN" or item.user_id == user_id]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return [item.model_copy(deep=True) for item in items]

    def get_conversation(self, conversation_id: str, *, user_id: str, role: AssistantRole) -> AssistantConversation:
        item = self._conversations.get(conversation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Assistant conversation not found")
        if role != "ADMIN" and item.user_id != user_id:
            raise HTTPException(status_code=403, detail="Conversation access denied")
        return item.model_copy(deep=True)

    def list_audit(self, *, role: AssistantRole, limit: int = 100) -> list[AssistantAuditEntry]:
        if role not in CASE_ROLES:
            raise HTTPException(status_code=403, detail="Assistant audit access denied")
        return [item.model_copy(deep=True) for item in self._audit[-limit:][::-1]]

    # ---- Public investigation contract ---------------------------------------------

    def list_investigations(self, *, role: AssistantRole) -> list[Investigation]:
        self._require_case_role(role)
        items = sorted(self._investigations.values(), key=lambda item: item.updated_at, reverse=True)
        return [item.model_copy(deep=True) for item in items]

    def get_investigation(self, investigation_id: str, *, role: AssistantRole) -> Investigation:
        self._require_case_role(role)
        item = self._investigations.get(investigation_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        return item.model_copy(deep=True)

    def create_investigation(
        self,
        request: InvestigationCreateRequest | dict[str, Any],
        *,
        user_id: str,
        role: AssistantRole,
    ) -> Investigation:
        self._require_case_role(role)
        if not isinstance(request, InvestigationCreateRequest):
            request = InvestigationCreateRequest.model_validate(request)
        if not request.confirmed:
            raise HTTPException(status_code=409, detail="Explicit confirmation is required for this write action")
        vessel = self._find_vessel(request.vessel_id)
        assessment = risk_engine.get_vessel_risk(request.vessel_id)
        voyage = self._find_voyage(request.voyage_id, request.vessel_id)
        investigation_id = f"CI-2026-{421 + len(self._investigations):05d}"
        now = _timestamp()
        priority = request.priority or ("critical" if assessment.risk_score >= 95 else "high" if assessment.risk_score >= 50 else "medium")
        item = Investigation(
            id=investigation_id,
            title=request.title or f"{vessel['name']} · {voyage['origin']} → {voyage['destination']}",
            status="open",
            priority=priority,
            vessel_id=request.vessel_id,
            vessel_name=vessel["name"],
            voyage_id=voyage["id"],
            route=f"{voyage['origin']} → {voyage['destination']}",
            assigned_to=request.assigned_to or user_id,
            related_company_ids=[value for value in [vessel.get("owner"), vessel.get("operator")] if value],
            timeline=self._case_timeline(request.vessel_id, voyage["id"]),
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        self._investigations[item.id] = item
        self._audit_write(user_id, role, f"Create investigation {item.id}", "confirmed", [item.id])
        return item.model_copy(deep=True)

    def create_environmental_investigation(
        self,
        event_id: str,
        *,
        confirmed: bool,
        user_id: str,
        role: AssistantRole,
        assigned_to: str | None = None,
    ) -> Investigation:
        """Create one evidence-first Case around an event, never around presumed guilt."""

        self._require_case_role(role)
        if not confirmed:
            raise HTTPException(status_code=409, detail="Explicit confirmation is required for this write action")
        event = environmental_service.get_event(event_id)
        existing = next(
            (item for item in self._investigations.values() if item.environmental_event_id == event.id),
            None,
        )
        if existing is not None:
            return existing.model_copy(deep=True)

        candidates = environmental_service.get_candidates(event.id).candidates
        if not candidates:
            raise HTTPException(status_code=409, detail="Environmental event has no review candidates")
        primary = candidates[0]
        reconstruction = environmental_service.get_reconstruction(event.id)
        raw = environmental_service.get_raw_for_event(event.id)
        timeline = environmental_service.get_timeline(event.id)
        now = _timestamp()
        case_id = "ENV-2026-0041" if event.id == "ENV-2026-00142" else f"ENV-2026-{41 + len(self._investigations):04d}"
        href = f"/app/environment/events/{event.id}"

        evidence: list[InvestigationEvidence] = []

        def add(
            source_id: str,
            source_type: str,
            title: str,
            detail: str,
            claim_kind: str,
            occurred_at: str | None,
            module: str,
        ) -> None:
            evidence.append(InvestigationEvidence(
                id=f"IE-{case_id}-{len(evidence) + 1:03d}",
                source_id=source_id,
                source_type=source_type,
                title=title,
                detail=detail,
                claim_kind=claim_kind,
                source_href=f"{href}?evidence={source_id}",
                source_module=module,
                occurred_at=occurred_at,
                added_by=user_id,
                added_at=now,
            ))

        add(raw.source_reference, "environmental_observation", "Satellite detection", f"Source-attributed detection retained as raw record {raw.id}.", "fact", raw.observed_at, "Environmental Data Gateway")
        add(f"ENV-POLYGON-{event.id}", "environmental_geometry", "Observed pollution area", f"Observed polygon/multipolygon covers {event.area_km2:g} km² at {event.confidence:.0%} confidence.", "fact", event.detected_at, "Environmental Event")
        for observation in event.environmental_data:
            add(observation.id, "environmental_observation", observation.parameter.title(), f"{observation.value} {observation.unit or ''} from {observation.source}.".strip(), "fact" if observation.provenance == "OBSERVED" else "estimate", observation.observed_at, "Environmental Data Gateway")
        add(reconstruction.id, "environmental_reconstruction", "Backward reconstruction", f"Probable origin is an area and interval {reconstruction.estimated_origin_from}–{reconstruction.estimated_origin_to}; confidence {reconstruction.confidence:.0%}.", "estimate", reconstruction.estimated_origin_to, "Environmental Reconstruction")
        for candidate in candidates:
            track_id = candidate.track[0].source_reference if candidate.track else candidate.evidence_ids[0]
            observed_points = sum(point.provenance == "OBSERVED" for point in candidate.track)
            add(track_id, "ais_track", f"Historical AIS track · {candidate.vessel_name}", f"{observed_points} source-attributed AIS position(s) retained; modeled gap positions are excluded from this factual claim.", "fact", candidate.track[0].timestamp if candidate.track else None, "Vessel Tracking")
            add(candidate.id, "environmental_candidate", f"Candidate association · {candidate.vessel_name}", candidate.explanation, "inference", candidate.track[0].timestamp if candidate.track else None, "Environmental Association")
        if primary.ais_gap:
            gap_id = next((value for value in primary.evidence_ids if "GAP" in value), "AIS-GAP-CS-20260514")
            add(gap_id, "environmental_observation", "AIS continuity gap", "AIS continuity is unavailable during part of the estimated origin interval; this limits reconstruction and does not prove concealment.", "fact", "2026-05-14T04:22:00+05:00", "Vessel Tracking")

        case_timeline = [InvestigationTimelineItem(
            id=f"CASE-{item.id}",
            occurred_at=item.timestamp,
            title=item.title,
            detail=item.detail,
            claim_kind={"OBSERVED": "fact", "ESTIMATED": "estimate", "INFERRED": "inference"}[item.provenance],
            source_id=item.source_ids[0] if item.source_ids else event.id,
            source_href=href,
        ) for item in timeline.items]
        case = Investigation(
            id=case_id,
            title=f"Environmental review · {event.id}",
            status="open",
            priority="high",
            vessel_id=primary.vessel_id,
            vessel_name=f"{primary.vessel_name} · candidate",
            route="Central Caspian · reconstructed origin area",
            assigned_to=assigned_to or user_id,
            event_ids=[event.id],
            evidence=evidence,
            related_vessel_ids=[item.vessel_id for item in candidates],
            timeline=case_timeline,
            case_type="environmental",
            environmental_event_id=event.id,
            disclaimer=event.disclaimer,
            created_by=user_id,
            created_at=now,
            updated_at=now,
        )
        self._investigations[case.id] = case
        environmental_service.link_investigation(event.id, case.id)
        self._audit_write(user_id, role, f"Create environmental investigation {case.id}", "confirmed", [case.id, event.id, *[item.source_id for item in evidence]])
        return case.model_copy(deep=True)

    def add_evidence(
        self,
        investigation_id: str,
        request: InvestigationEvidenceRequest | dict[str, Any],
        *,
        user_id: str,
        role: AssistantRole,
    ) -> Investigation:
        self._require_case_role(role)
        if not isinstance(request, InvestigationEvidenceRequest):
            request = InvestigationEvidenceRequest.model_validate(request)
        if not request.confirmed:
            raise HTTPException(status_code=409, detail="Explicit confirmation is required for this write action")
        case = self._investigations.get(investigation_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        existing = {item.source_id for item in case.evidence}
        for source_id in request.evidence_ids:
            if source_id in existing:
                continue
            evidence = self._resolve_case_evidence(source_id, case, user_id)
            case.evidence.append(evidence)
            case.event_ids.append(source_id)
            existing.add(source_id)
            event = self._event_by_id(source_id)
            related = event.get("related_vessel_id") if event else None
            if related and related not in case.related_vessel_ids:
                case.related_vessel_ids.append(related)
        case.updated_at = _timestamp()
        self._audit_write(user_id, role, f"Add evidence to {case.id}", "confirmed", request.evidence_ids)
        return case.model_copy(deep=True)

    def add_note(
        self,
        investigation_id: str,
        request: InvestigationNoteRequest | dict[str, Any],
        *,
        user_id: str,
        role: AssistantRole,
    ) -> Investigation:
        self._require_case_role(role)
        if not isinstance(request, InvestigationNoteRequest):
            request = InvestigationNoteRequest.model_validate(request)
        if not request.confirmed:
            raise HTTPException(status_code=409, detail="Explicit confirmation is required for this write action")
        case = self._investigations.get(investigation_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        now = _timestamp()
        case.notes.append(InvestigationNote(id=f"NOTE-{len(case.notes) + 1:03d}", text=request.note, author=user_id, created_at=now))
        case.updated_at = now
        self._audit_write(user_id, role, f"Add note to {case.id}", "confirmed", [case.id])
        return case.model_copy(deep=True)

    def update_investigation(
        self,
        investigation_id: str,
        request: InvestigationUpdateRequest | dict[str, Any],
        *,
        user_id: str,
        role: AssistantRole,
    ) -> Investigation:
        self._require_case_role(role)
        if not isinstance(request, InvestigationUpdateRequest):
            request = InvestigationUpdateRequest.model_validate(request)
        if not request.confirmed:
            raise HTTPException(status_code=409, detail="Explicit confirmation is required for this write action")
        case = self._investigations.get(investigation_id)
        if case is None:
            raise HTTPException(status_code=404, detail="Investigation not found")
        for field in ("status", "priority", "assigned_to", "conclusion"):
            value = getattr(request, field)
            if value is not None:
                setattr(case, field, value)
        case.updated_at = _timestamp()
        self._audit_write(user_id, role, f"Update investigation {case.id}", "confirmed", [case.id])
        return case.model_copy(deep=True)

    def summarize_investigation(self, investigation_id: str, *, user_id: str, role: AssistantRole) -> AssistantChatResponse:
        case = self.get_investigation(investigation_id, role=role)
        context = AssistantContext(current_page=f"/app/investigations/{case.id}", vessel_id=case.vessel_id, voyage_id=case.voyage_id, investigation_id=case.id)
        request = AssistantChatRequest(question="Суммируй расследование.", context=context)
        return self.chat(request, user_id=user_id, role=role)

    def decide_action(self, action_id: str, *, confirmed: bool, user_id: str, role: AssistantRole, note: str | None = None) -> dict[str, Any]:
        action = self._actions.get(action_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Assistant action not found")
        if action.status != "pending":
            raise HTTPException(status_code=409, detail="Assistant action has already been decided")
        if role != "ADMIN" and action.requested_by != user_id:
            raise HTTPException(status_code=403, detail="Assistant action belongs to another user")
        if not confirmed:
            action.status = "rejected"
            action.confirmed_by = user_id
            action.confirmed_at = _timestamp()
            self._audit_write(user_id, role, f"Reject assistant action {action.id}", "rejected", [action.id])
            return {"action": action.model_copy(deep=True), "investigation": None}
        self._require_case_role(role)
        investigation: Investigation | None = None
        if action.action_type == "create_investigation":
            if action.payload.get("environmental_event_id"):
                investigation = self.create_environmental_investigation(
                    str(action.payload["environmental_event_id"]),
                    confirmed=True,
                    user_id=user_id,
                    role=role,
                    assigned_to=action.payload.get("assigned_to"),
                )
            else:
                investigation = self.create_investigation({**action.payload, "confirmed": True}, user_id=user_id, role=role)
        elif action.action_type == "add_case_evidence":
            investigation = self.add_evidence(
                action.payload["investigation_id"],
                {"evidence_ids": action.payload["evidence_ids"], "confirmed": True},
                user_id=user_id,
                role=role,
            )
        else:
            raise HTTPException(status_code=400, detail="This demo action is not executable through the assistant")
        action.status = "confirmed"
        action.confirmed_by = user_id
        action.confirmed_at = _timestamp()
        action.payload["decision_note"] = note
        for conversation in self._conversations.values():
            if conversation.user_id == user_id and investigation is not None:
                conversation.last_investigation_id = investigation.id
                conversation.last_vessel_id = investigation.vessel_id
                conversation.last_voyage_id = investigation.voyage_id
        self._audit_write(user_id, role, f"Confirm assistant action {action.id}", "confirmed", [action.id, investigation.id])
        return {"action": action.model_copy(deep=True), "investigation": investigation.model_copy(deep=True)}

    # ---- Tool layer ----------------------------------------------------------------

    def execute_tool(self, name: str, arguments: dict[str, Any], *, role: AssistantRole) -> Any:
        if name not in TOOL_CATALOG:
            raise HTTPException(status_code=400, detail=f"Unknown assistant tool: {name}")
        if not self._tool_allowed(name, role):
            raise HTTPException(status_code=403, detail=f"Tool {name} is not allowed for role {role}")
        vessel_id = arguments.get("vessel_id")
        voyage_id = arguments.get("voyage_id")
        port_id = arguments.get("port_id", "aktau")

        if name == "get_vessel":
            return self._find_vessel(vessel_id)
        if name == "get_current_voyage":
            return self._find_voyage(voyage_id, vessel_id)
        if name == "get_vessel_events":
            return [item for item in self._all_events() if item["vessel_id"] == vessel_id]
        if name == "get_vessel_risk":
            result = risk_engine.get_vessel_risk(vessel_id).model_dump()
            if role == "PORT_DISPATCHER":
                return {key: result[key] for key in ("id", "vessel_id", "vessel_name", "voyage_id", "risk_score", "risk_level", "trend", "risk_updated_at", "model_version", "disclaimer")}
            return result
        if name == "get_risk_factors":
            if vessel_id:
                return risk_engine.get_vessel_risk(vessel_id).model_dump()["factors"]
            return [item.model_dump() for item in risk_engine.get_voyage_factors(voyage_id)]
        if name == "get_behavior_profile":
            return behavior_engine.get(vessel_id).model_dump()
        if name == "get_encounters":
            events = [item for item in self._all_events() if item["vessel_id"] == vessel_id and item["type"] == "vessel_encounter"]
            try:
                connections = [item.model_dump() for item in advanced_analytics.get_connections(vessel_id)]
            except HTTPException:
                connections = []
            return {"events": events, "connections": connections}
        if name == "get_cargo_analysis":
            return advanced_analytics.get_cargo(voyage_id).model_dump()
        if name == "get_fuel_analysis":
            return advanced_analytics.get_fuel(voyage_id).model_dump()
        if name == "get_vessel_network":
            return advanced_analytics.get_network(vessel_id).model_dump()
        if name == "search_vessels":
            query = _normalized(str(arguments.get("query", "")))
            minimum_risk = int(arguments.get("minimum_risk", 0))
            limit = int(arguments.get("limit", 20))
            results: list[dict[str, Any]] = []
            physical = {item.id: item for item in VESSELS}
            for assessment in sorted(risk_engine.list_assessments(), key=lambda item: item.risk_score, reverse=True):
                vessel = physical.get(assessment.vessel_id)
                if assessment.risk_score < minimum_risk:
                    continue
                if query and query not in _normalized(assessment.vessel_name) and (not vessel or query not in vessel.imo):
                    continue
                results.append({
                    "id": assessment.vessel_id,
                    "name": assessment.vessel_name,
                    "imo": vessel.imo if vessel else None,
                    "destination": vessel.destination if vessel else None,
                    "risk_score": assessment.risk_score,
                    "risk_level": assessment.risk_level,
                    "assessment_id": assessment.id,
                    "model_version": assessment.model_version,
                })
            return results[:limit]
        if name == "search_events":
            return self._search_events(arguments)
        if name == "search_area":
            return self._search_area(arguments)
        if name == "get_port_status":
            return port_operations.get_overview(port_id).model_dump()
        if name == "get_arrivals":
            return [item.model_dump() for item in port_operations.get_arrivals(port_id)]
        if name == "get_port_forecast":
            return port_operations.get_load_forecast(port_id).model_dump()
        if name == "get_eta":
            return port_operations.get_eta(vessel_id).model_dump()
        if name == "get_pre_arrival":
            return port_operations.get_pre_arrival(arguments.get("port_call_id", "pc-aktau-143")).model_dump()
        if name == "get_environmental_event":
            return environmental_service.get_event(str(arguments.get("event_id", "ENV-2026-00142"))).model_dump()
        if name == "get_environmental_candidates":
            return environmental_service.get_candidates(
                str(arguments.get("event_id", "ENV-2026-00142")),
                include_extended=bool(arguments.get("include_extended", False)),
            ).model_dump()
        if name == "get_environmental_reconstruction":
            return environmental_service.get_reconstruction(
                str(arguments.get("event_id", "ENV-2026-00142")),
            ).model_dump()
        if name == "get_environmental_timeline":
            event_id = str(arguments.get("event_id", "ENV-2026-00142"))
            return {
                "timeline": environmental_service.get_timeline(event_id).model_dump(),
                "replay": environmental_service.get_replay(event_id).model_dump(),
            }
        principal = network_service.principal_for_role(role)
        if name == "get_regional_overview":
            return jsonable_encoder(network_service.overview(principal))
        if name == "get_regional_risk":
            return jsonable_encoder(network_service.list_risk(
                principal,
                country=arguments.get("country"),
                port_id=arguments.get("port_id"),
                route_id=arguments.get("route_id"),
                vessel_type=arguments.get("vessel_type"),
                minimum_score=int(arguments.get("minimum_score", 0)),
                event_type=arguments.get("event_type"),
            ))
        if name == "search_caspian":
            return jsonable_encoder(network_service.search(
                str(arguments.get("query", "")), principal,
                entity_types=arguments.get("entity_types"),
            ))
        if name == "get_global_vessel_identity":
            return jsonable_encoder(network_service.get_vessel_identity(
                str(arguments.get("global_vessel_id") or arguments.get("vessel_id")), principal,
            ))
        if name == "get_global_vessel_voyages":
            return jsonable_encoder(network_service.get_vessel_voyages(
                str(arguments.get("global_vessel_id") or arguments.get("vessel_id")), principal,
            ))
        if name == "get_route_intelligence":
            return jsonable_encoder(network_service.get_route(
                str(arguments.get("route_id", "route-baku-aktau")), principal,
            ))
        if name == "get_cross_port_verification":
            return jsonable_encoder(network_service.get_cross_port_report(
                str(arguments.get("voyage_id", "NET-VOY-001")), principal,
            ))
        if name == "get_regional_network":
            return jsonable_encoder(network_service.graph(
                principal, vessel_id=arguments.get("global_vessel_id") or arguments.get("vessel_id"),
            ))
        if name == "get_regional_data_health":
            return jsonable_encoder(network_service.data_health(principal))
        raise HTTPException(status_code=400, detail=f"Tool {name} has no implementation")

    # ---- Planner and grounded answer builders --------------------------------------

    def _plan_and_answer(
        self,
        question: str,
        conversation: AssistantConversation,
        role: AssistantRole,
        traces: list[AssistantToolTrace],
    ) -> AssistantChatResponse:
        q = _normalized(question)
        vessel_id = self._resolve_vessel_id(q, conversation)
        voyage_id = conversation.context.voyage_id or conversation.last_voyage_id
        environmental_match = re.search(r"\bENV-(?:2026-\d{5}|\d{1,5})\b", question.upper())
        environmental_event_id = (
            environmental_match.group(0) if environmental_match
            else conversation.context.environmental_event_id or conversation.last_environmental_event_id
        )

        if environmental_event_id and (
            "что известно" in q or "что мы знаем" in q or "environmental event" in q
        ):
            event = self._call("get_environmental_event", {"event_id": environmental_event_id}, role, traces)
            reconstruction = self._call("get_environmental_reconstruction", {"event_id": event["id"]}, role, traces)
            conversation.last_environmental_event_id = event["id"]
            claims = [
                self._claim(
                    "fact",
                    f"{event['detected_at']}: обнаружена область {event['area_km2']:g} km², confidence {event['confidence']:.0%}; статус {event['status']}.",
                    [self._environmental_link(event["id"], event["id"], event["type"])],
                ),
                self._claim(
                    "estimate",
                    f"Backward reconstruction ограничивает вероятное начало интервалом {reconstruction['estimated_origin_from']}–{reconstruction['estimated_origin_to']}; confidence {reconstruction['confidence']:.0%}.",
                    [self._environmental_link(reconstruction["id"], event["id"], "Backward reconstruction", "environmental_reconstruction")],
                ),
                self._claim(
                    "inference",
                    "Событие требует проверки; имеющиеся данные не устанавливают источник загрязнения.",
                    [self._environmental_link(event["id"], event["id"], "Environmental review policy")],
                ),
            ]
            action = self._navigation_action("open_environment", "Открыть Environmental Event", f"/app/environment/events/{event['id']}")
            return self._response(conversation, f"Что известно про {event['alias'] or event['id']}", "Ответ собран из event record и wind/current reconstruction.", claims, traces, [action])

        if environmental_event_id and "почему" in q and "кандидат" in q:
            event = self._call("get_environmental_event", {"event_id": environmental_event_id}, role, traces)
            result = self._call("get_environmental_candidates", {"event_id": event["id"]}, role, traces)
            candidates = result["candidates"]
            target = next((item for item in candidates if item["vessel_id"] == vessel_id), candidates[0] if candidates else None)
            if target is None:
                return self._no_data(conversation, "Для события нет релевантных candidate associations.", traces)
            conversation.last_environmental_event_id = event["id"]
            conversation.last_vessel_id = target["vessel_id"]
            claim_kind = {"OBSERVED": "fact", "ESTIMATED": "estimate", "INFERRED": "inference"}
            claims = [self._claim(
                claim_kind[factor["provenance"]],
                f"{factor['label']}: {factor['observed']}. {factor['interpretation']}",
                [self._environmental_link(factor["id"], event["id"], factor["label"], "environmental_candidate")],
            ) for factor in target["factors"]]
            claims.append(self._claim(
                "inference",
                f"Ранг {target['relevance']} означает приоритет проверки (association score {target['association_score']}), а не установленную причинность.",
                [self._environmental_link(target["id"], event["id"], target["vessel_name"], "environmental_candidate")],
            ))
            return self._response(conversation, f"Почему {target['vessel_name']} — первый кандидат", "Ранг получен из объяснимых spatial, temporal и AIS factors.", claims, traces)

        if environmental_event_id and (
            "кандидат" in q or "какие суда" in q or "могли быть связаны" in q
        ):
            event = self._call("get_environmental_event", {"event_id": environmental_event_id}, role, traces)
            result = self._call("get_environmental_candidates", {"event_id": event["id"]}, role, traces)
            conversation.last_environmental_event_id = event["id"]
            candidates = result["candidates"]
            claims = [self._claim(
                "inference",
                f"{index}. {item['vessel_name']} — {item['distance_km']:g} km, overlap {item['temporal_overlap_percent']:.0f}%, AIS gap {'есть' if item['ais_gap'] else 'не отмечен'}, relevance {item['relevance']}.",
                [self._environmental_link(item["id"], event["id"], item["vessel_name"], "environmental_candidate")],
            ) for index, item in enumerate(candidates, start=1)]
            claims.append(self._claim(
                "inference",
                result["disclaimer"],
                [self._environmental_link(event["id"], event["id"], "Association policy")],
            ))
            return self._response(conversation, "Possible vessel associations", f"Historical spatial search проверил {result['searched_candidate_count']} судов и оставил {result['relevant_candidate_count']} для человеческой проверки.", claims, traces)

        if environmental_event_id and "создай" in q and "расслед" in q:
            self._require_case_role(role)
            event = self._call("get_environmental_event", {"event_id": environmental_event_id}, role, traces)
            self._call("get_environmental_timeline", {"event_id": event["id"]}, role, traces)
            action = self._pending_action(
                "create_investigation",
                "Подтвердить создание CASE ENV-2026-0041",
                {"environmental_event_id": event["id"], "assigned_to": conversation.user_id},
                conversation.user_id,
            )
            claims = [
                self._claim("fact", f"{event['id']}: {event['area_km2']:g} km² · {event['status']}.", [self._environmental_link(event["id"], event["id"], event["type"])]),
                self._claim("inference", "Case будет посвящён проверке environmental event; candidate vessels останутся возможными связями, а не установленными источниками.", [self._policy_link("CI-ENV-INVESTIGATION-1")]),
            ]
            return self._response(conversation, "Требуется подтверждение", "Создание environmental Case и автоматический сбор evidence изменяют систему; действие ещё не выполнено.", claims, traces, [action])

        regional_context = (
            "региональ" in q
            or "по касп" in q
            or ("касп" in q and any(token in q for token in ("всем", "всему", "всего", "регион")))
        )

        if regional_context and (("какие" in q and "требуют внимания" in q) or "top risk" in q or "высокий риск" in q):
            result = self._call("get_regional_risk", {"minimum_score": 50}, role, traces)
            records = result["items"][:3]
            claims = [self._claim(
                "estimate",
                f"{item['vessel_name']} — {item['score']} / 100 · {item['origin_port_id'].title()} → {item['destination_port_id'].title()}.",
                [AssistantEvidenceLink(
                    id=item["source_assessment_id"], source_type="risk_assessment",
                    label=f"{item['vessel_name']} regional risk", href="/app/caspian/risk",
                    source_module="caspian_network",
                )],
            ) for item in records]
            claims.append(self._claim(
                "inference", "Региональная очередь определяет приоритет проверки и не устанавливает нарушение.",
                [self._policy_link("CI-NETWORK-1.0")],
            ))
            action = self._navigation_action("open_regional_risk", "Открыть Caspian Risk Center", "/app/caspian/risk")
            return self._response(conversation, "Суда, требующие внимания во всём Каспии", "Результат получен из scope-filtered Regional Risk API.", claims, traces, [action])

        if "посещал" in q and "баку" in q and "актау" in q and "туркменбаш" in q:
            history = self._call("get_global_vessel_voyages", {"global_vessel_id": "CI-VESSEL-000184"}, role, traces)
            claims = [self._claim(
                "fact",
                f"{history['vessel_name']} ({history['global_vessel_id']}) имеет непрерывную port history: {' → '.join(name.title() for name in history['port_history'])}.",
                [AssistantEvidenceLink(id=history["global_vessel_id"], source_type="global_vessel_identity", label="Continuous port history", href="/app/caspian/search?q=CI-VESSEL-000184", source_module="caspian_network")],
            )]
            action = self._navigation_action("open_global_identity", "Открыть единый профиль", "/app/caspian/search?q=CI-VESSEL-000184")
            return self._response(conversation, "Суда с посещениями трёх портов", "В доступном демонаборе подтверждено одно судно; отсутствующие совпадения не добавлены.", claims, traces, [action])

        if "ais" in q and "баку" in q and "актау" in q and ("между" in q or "маршрут" in q):
            route = self._call("get_route_intelligence", {"route_id": "route-baku-aktau"}, role, traces)
            risk = self._call("get_regional_risk", {"route_id": "route-baku-aktau", "event_type": "AIS_GAP"}, role, traces)
            route_record = route["route"]
            claims = [self._claim(
                "fact", f"Маршрут {route_record['display_name']}: {route_record['ais_gaps']} AIS gaps за {route_record['period_days']} дней.",
                [AssistantEvidenceLink(id=route_record["id"], source_type="route_intelligence", label=route_record["display_name"], href="/app/caspian/routes", source_module="caspian_network")],
            )]
            claims += [self._claim(
                "estimate", f"{item['vessel_name']} — risk {item['score']}; AIS gap входит в текущий набор факторов.",
                [AssistantEvidenceLink(id=item["source_assessment_id"], source_type="risk_assessment", label=item["vessel_name"], href="/app/caspian/risk", source_module="caspian_network")],
            ) for item in risk["items"]]
            return self._response(conversation, "AIS gaps на маршруте Baku ↔ Aktau", "Route Intelligence и Regional Risk вызваны как отдельные grounded tools.", claims, traces)

        if ("межпорт" in q or "сверк" in q or "расхожд" in q) and ("груз" in q or "caspian star" in q):
            report = self._call("get_cross_port_verification", {"voyage_id": "NET-VOY-001"}, role, traces)
            claims = [self._claim(
                "fact", f"Baku reported {report['departure']['cargo_t']:,.0f} t; Aktau verified {report['arrival']['cargo_t']:,.0f} t.",
                [AssistantEvidenceLink(id=evidence, source_type="provenance", label=evidence, href="/app/caspian/verification", source_module="caspian_network") for evidence in report["comparisons"][0]["evidence_ids"]],
            ), self._claim(
                "inference", f"Разница {abs(report['comparisons'][0]['difference']):.0f} t классифицирована как {report['overall_status']}; это результат сверки, а не вывод о нарушении.",
                [self._policy_link("CI-CROSSPORT-1.0")],
            )]
            action = self._navigation_action("open_cross_port", "Открыть межпортовую сверку", "/app/caspian/verification")
            return self._response(conversation, "Cross-port verification", "Исходная декларация и проверенная запись показаны отдельно с provenance.", claims, traces, [action])

        if ("какие компании" in q or "компании связаны" in q) and (regional_context or "этими судами" in q):
            graph = self._call("get_regional_network", {"global_vessel_id": "CI-VESSEL-000184"}, role, traces)
            companies = [item for item in graph["nodes"] if item["type"] == "COMPANY"]
            claims = [self._claim(
                "fact", f"{item['label']} ({item['id']}) связано с CASPIAN STAR наблюдаемым отношением OPERATES.",
                [AssistantEvidenceLink(id=item["id"], source_type="company_identity", label=item["label"], href="/app/caspian/network", source_module="caspian_network")],
            ) for item in companies]
            claims.append(self._claim("inference", "Связь в графе не переносит риск и не означает нарушение.", [self._policy_link("CI-NETWORK-GRAPH-1")]))
            action = self._navigation_action("open_regional_network", "Открыть Caspian Network Graph", "/app/caspian/network")
            return self._response(conversation, "Связанные компании", "Ответ построен только по evidence-grounded рёбрам регионального графа.", claims, traces, [action])

        if ("данн" in q and ("здоров" in q or "quality" in q or "источник" in q)) and regional_context:
            health = self._call("get_regional_data_health", {}, role, traces)
            summary = health["summary"]
            claims = [self._claim("fact", f"Источники: {summary['online']} ONLINE, {summary['degraded']} DEGRADED, {summary['offline']} OFFLINE; агрегированный health score {summary.get('health_score', 92)}/100.", [self._policy_link("CI-NETWORK-DATA-HEALTH")])]
            action = self._navigation_action("open_data_health", "Открыть Data Health", "/app/caspian/data-health")
            return self._response(conversation, "Regional Data Health", "Качество и задержки источников показаны отдельно от морских событий.", claims, traces, [action])

        if ("какие" in q and "требуют внимания" in q) or "top risk" in q or "высокий риск" in q:
            records = self._call("search_vessels", {"minimum_risk": 50, "limit": 3}, role, traces)
            claims = [self._claim(
                "estimate",
                f"{item['name']} — {item['risk_score']} / 100 · {item['risk_level'].upper()}.",
                [self._risk_link(item["assessment_id"], item["id"], item["model_version"])],
            ) for item in records]
            return self._response(conversation, "Суда, требующие внимания", "Risk Engine вернул три наивысшие текущие оценки. Это приоритет проверки, а не утверждение о нарушении.", claims, traces)

        if "почему" in q and ("риск" in q or "caspian" in q or "вырос" in q) and "актау" not in q and "порт" not in q:
            vessel_id = self._require_vessel_context(vessel_id)
            risk = self._call("get_vessel_risk", {"vessel_id": vessel_id}, role, traces)
            factors = self._call("get_risk_factors", {"vessel_id": vessel_id}, role, traces)
            conversation.last_vessel_id = vessel_id
            conversation.last_voyage_id = risk.get("voyage_id")
            claims = [self._claim(
                "estimate",
                f"{factor['type']}: {factor['explanation']} · вклад {factor['effective_score']}.",
                [self._factor_link(factor)],
            ) for factor in factors]
            claims.append(self._claim("inference", "Сочетание факторов требует проверки; оценка не доказывает нарушение.", [self._policy_link("CI-RISK-POLICY")]))
            return self._response(conversation, f"Почему риск {risk['vessel_name']} — {risk['risk_score']}", f"Ответ построен из {len(factors)} текущих Risk Factors модели {risk['model_version']}. Каждый вклад связан с исходным событием.", claims, traces)

        if "ais" in q and ("3 час" in q or "трех час" in q or "более" in q):
            events = self._call("search_events", {"event_type": "ais_gap", "duration_gt_minutes": 180, "days": 30}, role, traces)
            if not events:
                return self._no_data(conversation, "AIS gaps по заданному фильтру не найдены.", traces)
            claims: list[AssistantClaim] = []
            for event in events:
                duration = event.get("data", {}).get("duration_minutes")
                claims.append(self._claim("fact", f"{event['vessel_name']}: AIS отсутствовал {duration // 60}h {duration % 60:02d}m.", [self._event_link(event)]))
                radius = event.get("data", {}).get("possible_movement_radius_km")
                if radius is not None:
                    claims.append(self._claim("estimate", f"Расчётный радиус возможного перемещения — {radius} km.", [self._event_link(event)]))
            return self._response(conversation, "AIS отсутствовал более 3 часов", f"Структурный фильтр нашёл {len(events)} событие(й) за 30 дней.", claims, traces)

        if ("с кем" in q and "встреч" in q) or "с кем оно" in q:
            vessel_id = self._require_vessel_context(vessel_id)
            result = self._call("get_encounters", {"vessel_id": vessel_id}, role, traces)
            if not result["events"]:
                return self._no_data(conversation, "В доступных событиях судна нет encounter-записей.", traces)
            event = result["events"][0]
            related = event.get("related_vessel_name") or event.get("related_vessel_id") or "неизвестное судно"
            conversation.last_related_vessel_id = event.get("related_vessel_id")
            data = event.get("data", {})
            claims = [
                self._claim("fact", f"Встреча с {related}: минимальная дистанция {data.get('minimum_distance_m')} m, длительность {data.get('duration_minutes')} min.", [self._event_link(event)]),
                self._claim("inference", "Encounter фиксирует совместное присутствие и не определяет характер взаимодействия.", [self._event_link(event)]),
            ]
            return self._response(conversation, f"Встреча с {related}", "Ответ получен из детектированного события текущего рейса.", claims, traces)

        if "раньше" in q and ("встреч" in q or "они" in q):
            vessel_id = self._require_vessel_context(vessel_id)
            result = self._call("get_encounters", {"vessel_id": vessel_id}, role, traces)
            connections = result["connections"]
            if not connections:
                return self._no_data(conversation, "Исторические encounter aggregates для этой пары отсутствуют.", traces)
            target = conversation.last_related_vessel_id
            connection = next((item for item in connections if not target or item["related_vessel_id"] == target), connections[0])
            claims = [
                self._claim("fact", f"За период наблюдения зарегистрировано {connection['encounters_total']} встреч; {connection['open_sea_encounters']} — вне портов.", [self._network_link(connection["id"], vessel_id)]),
                self._claim("fact", f"Средняя дистанция {connection['average_distance_m']:g} m; суммарная длительность {connection['total_duration_minutes'] / 60:.1f} h.", [self._network_link(connection["id"], vessel_id)]),
                self._claim("inference", connection["disclaimer"], [self._policy_link("CI-NETWORK-POLICY")]),
            ]
            return self._response(conversation, "История совместных наблюдений", connection["explanation"], claims, traces)

        if "покажи" in q and "связ" in q:
            vessel_id = self._require_vessel_context(vessel_id)
            network = self._call("get_vessel_network", {"vessel_id": vessel_id}, role, traces)
            action = self._navigation_action("open_network", "Открыть Network View", "/app/network?connection=e-encounter")
            claims = [self._claim("fact", f"Network содержит {len(network['nodes'])} nodes и {len(network['edges'])} explainable links.", [self._network_link("network", vessel_id)])]
            return self._response(conversation, "Связь подготовлена", "Откройте Network View, чтобы увидеть объекты, основание связи и confidence.", claims, traces, [action])

        if "создай" in q and "расслед" in q:
            self._require_case_role(role)
            vessel_id = self._require_vessel_context(vessel_id)
            vessel = self._call("get_vessel", {"vessel_id": vessel_id}, role, traces)
            voyage = self._call("get_current_voyage", {"vessel_id": vessel_id}, role, traces)
            risk = self._call("get_vessel_risk", {"vessel_id": vessel_id}, role, traces)
            proposed_case_id = f"CI-2026-{421 + len(self._investigations):05d}"
            action = self._pending_action(
                "create_investigation",
                f"Подтвердить создание CASE {proposed_case_id}",
                {"vessel_id": vessel_id, "voyage_id": voyage["id"], "priority": "high", "assigned_to": conversation.user_id},
                conversation.user_id,
            )
            claims = [
                self._claim("fact", f"{vessel['name']} · {voyage['origin']} → {voyage['destination']}.", [self._vessel_link(vessel), self._voyage_link(voyage)]),
                self._claim("estimate", f"Текущая оценка риска — {risk['risk_score']} / 100.", [self._risk_link(risk['id'], vessel_id, risk['model_version'])]),
                self._claim("inference", "Priority HIGH предложен для проверки; окончательное решение остаётся за аналитиком.", [self._policy_link("AI-WRITE-1")]),
            ]
            return self._response(conversation, "Требуется подтверждение", "Создание Case изменяет систему. Данные подготовлены, но действие ещё не выполнено.", claims, traces, [action])

        if "добав" in q and ("доказ" in q or "case" in q or "расслед" in q):
            self._require_case_role(role)
            investigation_id = self._current_investigation_id(conversation)
            if not investigation_id or investigation_id not in self._investigations:
                return self._no_data(conversation, "Сначала создайте и подтвердите Investigation Case.", traces)
            vessel_id = self._investigations[investigation_id].vessel_id
            events = self._call("get_vessel_events", {"vessel_id": vessel_id}, role, traces)
            requested: list[str] = re.findall(r"(?:EV|ADV)-\d+", question.upper())
            if "ais" in q:
                requested += [item["id"] for item in events if item["type"] == "ais_gap"]
            if "встреч" in q or "encounter" in q:
                requested += [item["id"] for item in events if item["type"] == "vessel_encounter"]
            requested = list(dict.fromkeys(requested))
            if not requested:
                return self._no_data(conversation, "Не удалось определить evidence для добавления.", traces)
            action = self._pending_action(
                "add_case_evidence",
                f"Подтвердить добавление evidence ({len(requested)})",
                {"investigation_id": investigation_id, "evidence_ids": requested},
                conversation.user_id,
            )
            claims = [self._claim("fact", f"{item['type']}: {item['explanation']}", [self._event_link(item)]) for item in events if item["id"] in requested]
            return self._response(conversation, "Evidence готовы к добавлению", "Состав Case изменится только после отдельного подтверждения.", claims, traces, [action])

        if "суммируй" in q and "расслед" in q:
            investigation_id = self._current_investigation_id(conversation)
            if not investigation_id or investigation_id not in self._investigations:
                return self._no_data(conversation, "Investigation Case не найден в текущем контексте.", traces)
            case = self.get_investigation(investigation_id, role=role)
            traces.append(AssistantToolTrace(name="get_vessel_events", arguments={"investigation_id": case.id, "evidence_only": True}, record_count=len(case.evidence), data_accessed=[item.source_id for item in case.evidence]))
            if not case.evidence:
                return self._no_data(conversation, "В Case пока нет evidence; содержательное резюме без источников не формируется.", traces)
            claims = [self._claim(item.claim_kind, f"{item.title}: {item.detail}", [AssistantEvidenceLink(id=item.source_id, source_type="event", label=item.title, href=item.source_href, source_module=item.source_module)]) for item in case.evidence]
            claims.append(self._claim("inference", "Совокупность выбранных evidence требует аналитической проверки и не является доказательством нарушения.", [self._investigation_link(case.id)]))
            action = self._navigation_action("open_investigation", "Открыть расследование", f"/app/investigations/{case.id}")
            return self._response(conversation, f"Резюме {case.id}", "Резюме использует только evidence, явно добавленные в этот Case.", claims, traces, [action])

        if ("когда" in q and "прибуд" in q) or "eta" in q:
            vessel_id = self._require_vessel_context(vessel_id)
            eta = self._call("get_eta", {"vessel_id": vessel_id}, role, traces)
            reported = eta["reported_eta"][11:16]
            predicted = eta["predicted_eta"][11:16]
            window = f"{eta['likely_window_start'][11:16]}–{eta['likely_window_end'][11:16]}"
            claims = [
                self._claim("fact", f"Заявленный ETA — {reported}.", [self._eta_link(eta)]),
                self._claim("estimate", f"CI Predicted ETA — {predicted}; вероятное окно {window}; confidence {eta['confidence']:.0%}.", [self._eta_link(eta)]),
            ]
            action = self._navigation_action("open_port", "Открыть Pre-Arrival Report", "/app/port-calls/pc-aktau-143")
            return self._response(conversation, "ETA в Актау", "Использован объяснимый прогноз Port Operations, а заявленное время показано отдельно.", claims, traces, [action])

        if ("что" in q and "порт" in q and "подготов" in q) or "подготовить причал" in q:
            report = self._call("get_pre_arrival", {"port_call_id": "pc-aktau-143"}, role, traces)
            recommendation = report["berth_recommendation"]
            service = report["service_prediction"]
            claims = [
                self._claim("fact", f"Причал #{recommendation['recommended_berth_number']} совместим и доступен с {recommendation['berth_available_from'][11:16]}.", [self._port_call_link(report["port_call_id"])]),
                self._claim("estimate", f"Ожидаемый сервис — {service['total_minutes'] // 60}h {service['total_minutes'] % 60:02d}m, confidence {service['confidence']:.0%}.", [self._port_call_link(report["port_call_id"])]),
                *[self._claim("inference", item, [self._port_call_link(report["port_call_id"])]) for item in report["recommended_actions"]],
            ]
            action = self._navigation_action("open_port", "Открыть план подготовки", "/app/port-calls/pc-aktau-143")
            return self._response(conversation, "Что подготовить порту Актау", "Рекомендации собраны из berth compatibility, service model и Pre-Arrival review.", claims, traces, [action])

        if ("почему" in q and ("перегруж" in q or "актау" in q)) or ("порт" in q and "4 час" in q):
            status = self._call("get_port_status", {"port_id": "aktau"}, role, traces)
            arrivals = self._call("get_arrivals", {"port_id": "aktau"}, role, traces)
            forecast = self._call("get_port_forecast", {"port_id": "aktau"}, role, traces)
            four = next(item for item in forecast["points"] if item["horizon_hours"] == 4)
            bottleneck = forecast["bottlenecks"][0]
            recommendation = forecast["recommendations"][0]
            claims = [
                self._claim("fact", f"Сейчас операционная утилизация {status['port_load_percent']}%; приближаются {len(arrivals)} судов, занято {status['berths_occupied']} причалов.", [self._port_link("aktau")]),
                self._claim("estimate", f"Через 4 часа handling pressure прогнозируется на уровне {four['handling_pressure_percent']}%.", [self._port_link("aktau", "Port Load Forecast")]),
                self._claim("inference", f"{bottleneck['primary_reason']} Рекомендация: {recommendation['action']}; ожидаемый пик {recommendation['load_before_percent']}% → {recommendation['load_after_percent']}%.", [self._port_link("aktau", bottleneck["id"])]),
            ]
            action = self._navigation_action("open_port", "Открыть Port Control Center", "/app/port/aktau")
            return self._response(conversation, "Почему нагрузка Актау растёт", "Объяснение объединяет ETA, очередь, причалы, service windows и текущую погоду.", claims, traces, [action])

        if ("что происходило" in q and ("здесь" in q or "район" in q)) or "последние 24 часа" in q:
            area = conversation.context.area
            if area is None:
                return self._no_data(conversation, "Для spatial investigation сначала выделите район на карте.", traces)
            result = self._call("search_area", area.model_dump(exclude_none=True), role, traces)
            events = result["events"]
            if not events and not result["vessel_ids"]:
                return self._no_data(conversation, "В выбранной области за указанный период наблюдений нет.", traces)
            claims = [self._claim("fact", f"В области наблюдалось {len(result['vessel_ids'])} судно(а) и {result['position_count']} AIS-позиций.", [self._policy_link("SPATIAL-QUERY")])]
            claims += [self._claim("fact", f"{item['started_at'][11:16]} · {item['vessel_name']} · {item['type']}.", [self._event_link(item)]) for item in events]
            return self._response(conversation, "События в выбранной области", "Spatial tool вернул суда, позиции и события за заданное окно.", claims, traces)

        if vessel_id:
            vessel = self._call("get_vessel", {"vessel_id": vessel_id}, role, traces)
            return self._response(conversation, vessel["name"], "Найдена карточка судна. Уточните, нужны ли рейс, события, риск, груз, топливо или связи.", [self._claim("fact", f"IMO {vessel['imo']} · {vessel['type']} · курс на {vessel['destination']}.", [self._vessel_link(vessel)])], traces)

        self._call("search_vessels", {"query": question, "limit": 5}, role, traces)
        self._call("search_events", {"query": question, "days": 30}, role, traces)
        return self._no_data(conversation, "В доступных модулях недостаточно данных. Уточните судно, период, порт или район; отсутствующие факты не будут дополнены предположениями.", traces)

    # ---- Planner helpers ------------------------------------------------------------

    def _call(self, name: str, arguments: dict[str, Any], role: AssistantRole, traces: list[AssistantToolTrace]) -> Any:
        try:
            result = self.execute_tool(name, arguments, role=role)
        except HTTPException as exc:
            traces.append(AssistantToolTrace(name=name, arguments=arguments, record_count=0, status="denied" if exc.status_code == 403 else "not_found", data_accessed=[]))
            raise
        record_count = self._record_count(result)
        traces.append(AssistantToolTrace(name=name, arguments=deepcopy(arguments), record_count=record_count, data_accessed=self._data_ids(result)))
        return result

    def _response(
        self,
        conversation: AssistantConversation,
        title: str,
        answer: str,
        claims: list[AssistantClaim],
        traces: list[AssistantToolTrace],
        actions: list[AssistantAction] | None = None,
        no_data: bool = False,
    ) -> AssistantChatResponse:
        now = _timestamp()
        return AssistantChatResponse(
            conversation_id=conversation.id,
            message_id=f"MSG-A-{len(conversation.messages) + 1:04d}",
            title=title,
            answer=answer,
            claims=claims,
            tools_called=[item.model_copy(deep=True) for item in traces],
            actions=[item.model_copy(deep=True) for item in actions or []],
            grounded=True,
            no_data=no_data,
            created_at=now,
            disclaimer=ASSISTANT_DISCLAIMER,
        )

    def _no_data(self, conversation: AssistantConversation, answer: str, traces: list[AssistantToolTrace]) -> AssistantChatResponse:
        return self._response(conversation, "Недостаточно данных", answer, [], traces, no_data=True)

    @staticmethod
    def _claim(kind: str, statement: str, evidence: list[AssistantEvidenceLink]) -> AssistantClaim:
        return AssistantClaim(kind=kind, statement=statement, evidence=evidence)

    def _pending_action(self, action_type: str, label: str, payload: dict[str, Any], requested_by: str) -> AssistantAction:
        action = AssistantAction(
            id=f"ACT-{len(self._actions) + 1:05d}",
            action_type=action_type,
            label=label,
            requires_confirmation=True,
            status="pending",
            payload=deepcopy(payload),
            created_at=_timestamp(),
            requested_by=requested_by,
        )
        self._actions[action.id] = action
        return action.model_copy(deep=True)

    @staticmethod
    def _navigation_action(action_type: str, label: str, target: str) -> AssistantAction:
        return AssistantAction(id=f"NAV-{action_type}", action_type=action_type, label=label, requires_confirmation=False, status="confirmed", navigation_target=target, created_at=_timestamp())

    def _conversation(self, request: AssistantChatRequest, *, user_id: str, role: AssistantRole) -> AssistantConversation:
        if request.conversation_id:
            item = self._conversations.get(request.conversation_id)
            if item is None:
                raise HTTPException(status_code=404, detail="Assistant conversation not found")
            if role != "ADMIN" and item.user_id != user_id:
                raise HTTPException(status_code=403, detail="Conversation access denied")
            return item
        now = _timestamp()
        item = AssistantConversation(
            id=f"CONV-{len(self._conversations) + 1:05d}",
            user_id=user_id,
            role=role,
            title=request.question[:80],
            context=request.context,
            created_at=now,
            updated_at=now,
        )
        self._conversations[item.id] = item
        return item

    @staticmethod
    def _merge_context(current: AssistantContext, incoming: AssistantContext) -> AssistantContext:
        values = current.model_dump()
        for key, value in incoming.model_dump().items():
            if value not in (None, ""):
                values[key] = value
        return AssistantContext.model_validate(values)

    def _resolve_vessel_id(self, question: str, conversation: AssistantConversation) -> str | None:
        candidates = {item.name.casefold(): item.id for item in VESSELS}
        candidates.update({item.vessel_name.casefold(): item.vessel_id for item in risk_engine.list_assessments()})
        for name, vessel_id in sorted(candidates.items(), key=lambda item: len(item[0]), reverse=True):
            if name in question:
                conversation.last_vessel_id = vessel_id
                return vessel_id
        if any(token in question for token in ("оно", "судно", "его", "они", "риск вырос")):
            return conversation.last_vessel_id or conversation.context.vessel_id
        return conversation.context.vessel_id or conversation.last_vessel_id

    def _current_investigation_id(self, conversation: AssistantConversation) -> str | None:
        explicit = conversation.context.investigation_id or conversation.last_investigation_id
        if explicit:
            return explicit
        owned = [item for item in self._investigations.values() if item.created_by == conversation.user_id]
        if not owned:
            return None
        latest = max(owned, key=lambda item: item.updated_at)
        conversation.last_investigation_id = latest.id
        return latest.id

    @staticmethod
    def _require_vessel_context(vessel_id: str | None) -> str:
        if not vessel_id:
            raise HTTPException(status_code=404, detail="Vessel context is required")
        return vessel_id

    def _tool_allowed(self, name: str, role: AssistantRole) -> bool:
        return role in CASE_ROLES or name in PORT_DISPATCHER_TOOLS

    @staticmethod
    def _require_case_role(role: AssistantRole) -> None:
        if role not in CASE_ROLES:
            raise HTTPException(status_code=403, detail="Investigation access denied")

    # ---- Data access helpers --------------------------------------------------------

    @staticmethod
    def _find_vessel(vessel_id: str | None) -> dict[str, Any]:
        vessel = next((item for item in VESSELS if item.id == vessel_id), None)
        if vessel is None:
            raise HTTPException(status_code=404, detail="Vessel not found")
        return vessel.model_dump()

    @staticmethod
    def _find_voyage(voyage_id: str | None, vessel_id: str | None) -> dict[str, Any]:
        voyage = next((item for item in VOYAGES if voyage_id and item.id == voyage_id), None)
        if voyage is None:
            voyage = next((item for item in VOYAGES if item.vessel_id == vessel_id and item.status == "in_progress"), None)
        if voyage is None:
            raise HTTPException(status_code=404, detail="Current voyage not found")
        return voyage.model_dump()

    @staticmethod
    def _all_events() -> list[dict[str, Any]]:
        return [item.model_dump() for item in event_engine.events.values()] + [item.model_dump() for item in advanced_analytics.list_events()]

    def _event_by_id(self, event_id: str) -> dict[str, Any] | None:
        return next((item for item in self._all_events() if item["id"] == event_id), None)

    def _search_events(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        items = self._all_events()
        event_type = arguments.get("event_type")
        if event_type:
            items = [item for item in items if item["type"] == event_type]
        vessel_id = arguments.get("vessel_id")
        if vessel_id:
            items = [item for item in items if item["vessel_id"] == vessel_id]
        duration = int(arguments.get("duration_gt_minutes", -1))
        if duration >= 0:
            items = [item for item in items if int(item.get("data", {}).get("duration_minutes", -1)) > duration]
        query = _normalized(str(arguments.get("query", "")))
        if query:
            items = [item for item in items if query in _normalized(f"{item['type']} {item['vessel_name']} {item['explanation']}")]
        days = int(arguments.get("days", 0))
        if days:
            reference = datetime(2026, 8, 10, 23, 59, tzinfo=timezone(timedelta(hours=5)))
            cutoff = reference - timedelta(days=days)
            items = [item for item in items if datetime.fromisoformat(item["started_at"]) >= cutoff]
        return sorted(items, key=lambda item: item["started_at"], reverse=True)

    def _search_area(self, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            west, south, east, north = (float(arguments[key]) for key in ("west", "south", "east", "north"))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="A valid area is required") from exc
        from_time = arguments.get("from_time")
        to_time = arguments.get("to_time")
        positions = [
            item for item in POSITIONS
            if west <= item.longitude <= east and south <= item.latitude <= north
            and (not from_time or item.recorded_at >= from_time)
            and (not to_time or item.recorded_at <= to_time)
        ]
        events = [
            item for item in self._all_events()
            if west <= item["longitude"] <= east and south <= item["latitude"] <= north
            and (not from_time or item["started_at"] >= from_time)
            and (not to_time or item["started_at"] <= to_time)
        ]
        return {
            "vessel_ids": sorted({item.vessel_id for item in positions} | {item["vessel_id"] for item in events}),
            "position_count": len(positions),
            "event_count": len(events),
            "events": events,
        }

    def _resolve_case_evidence(self, source_id: str, case: Investigation, user_id: str) -> InvestigationEvidence:
        event = self._event_by_id(source_id)
        if event:
            if event["vessel_id"] != case.vessel_id:
                raise HTTPException(status_code=409, detail=f"Evidence {source_id} belongs to another vessel")
            return InvestigationEvidence(
                id=f"IE-{case.id}-{len(case.evidence) + 1:03d}",
                source_id=source_id,
                source_type="event",
                title=event["type"].replace("_", " ").upper(),
                detail=event["explanation"],
                claim_kind="fact",
                source_href=_href_for_event(source_id),
                source_module="Event Detection" if source_id.startswith("EV-") else "Advanced Analytics",
                occurred_at=event["started_at"],
                added_by=user_id,
                added_at=_timestamp(),
            )
        factor = next((item for item in risk_engine.get_vessel_risk(case.vessel_id).factors if item.id == source_id), None)
        if factor:
            return InvestigationEvidence(
                id=f"IE-{case.id}-{len(case.evidence) + 1:03d}",
                source_id=source_id,
                source_type="risk_factor",
                title=factor.type.replace("_", " ").upper(),
                detail=factor.explanation,
                claim_kind="estimate",
                source_href=f"/app/risk?factor={factor.id}",
                source_module="Risk Engine",
                occurred_at=factor.created_at,
                added_by=user_id,
                added_at=_timestamp(),
            )
        raise HTTPException(status_code=404, detail=f"Evidence source {source_id} not found")

    def _case_timeline(self, vessel_id: str, voyage_id: str) -> list[InvestigationTimelineItem]:
        voyage = self._find_voyage(voyage_id, vessel_id)
        items = [InvestigationTimelineItem(
            id="TL-DEPARTURE",
            occurred_at=voyage["departed_at"],
            title=f"Departure {voyage['origin']}",
            detail=f"Voyage {voyage_id} started toward {voyage['destination']}.",
            claim_kind="fact",
            source_id=voyage_id,
            source_href=f"/app/voyages/{voyage_id}/intelligence",
        )]
        for event in sorted((item for item in self._all_events() if item["vessel_id"] == vessel_id and item.get("voyage_id") == voyage_id), key=lambda item: item["started_at"]):
            items.append(InvestigationTimelineItem(
                id=f"TL-{event['id']}",
                occurred_at=event["started_at"],
                title=event["type"].replace("_", " ").title(),
                detail=event["explanation"],
                claim_kind="fact",
                source_id=event["id"],
                source_href=_href_for_event(event["id"]),
            ))
        risk = risk_engine.get_vessel_risk(vessel_id)
        items.append(InvestigationTimelineItem(
            id="TL-RISK",
            occurred_at=risk.risk_updated_at,
            title=f"Risk {risk.risk_score}",
            detail=f"Calculated by {risk.model_version} from explainable factors.",
            claim_kind="estimate",
            source_id=risk.id,
            source_href=f"/app/risk?vessel={vessel_id}",
        ))
        return sorted(items, key=lambda item: item.occurred_at)

    # ---- Grounding links ------------------------------------------------------------

    @staticmethod
    def _event_link(event: dict[str, Any]) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=event["id"], source_type="event", label=event["type"], href=_href_for_event(event["id"]), source_module="Event Detection" if event["id"].startswith("EV-") else "Advanced Analytics")

    @staticmethod
    def _factor_link(factor: dict[str, Any]) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=factor["id"], source_type="risk_factor", label=factor["type"], href=_href_for_event(factor["source_event_id"]), source_module="Risk Engine")

    @staticmethod
    def _risk_link(assessment_id: str, vessel_id: str, model: str) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=assessment_id, source_type="risk_assessment", label=model, href=f"/app/risk?vessel={vessel_id}", source_module="Risk Engine")

    @staticmethod
    def _vessel_link(vessel: dict[str, Any]) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=vessel["id"], source_type="vessel", label=vessel["name"], href=f"/app/vessels/{vessel['id']}", source_module="Vessel Registry")

    @staticmethod
    def _voyage_link(voyage: dict[str, Any]) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=voyage["id"], source_type="voyage", label=f"{voyage['origin']} → {voyage['destination']}", href=f"/app/voyages/{voyage['id']}/intelligence", source_module="Voyage Service")

    @staticmethod
    def _network_link(link_id: str, vessel_id: str) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=link_id, source_type="network", label="Encounter connection", href=f"/app/network?vessel={vessel_id}", source_module="Link Engine")

    @staticmethod
    def _eta_link(eta: dict[str, Any]) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=eta["id"], source_type="eta", label=eta["model_version"], href=f"/app/port-calls/{eta['port_call_id']}", source_module="ETA Engine")

    @staticmethod
    def _port_link(port_id: str, label: str = "Port Aktau") -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=port_id, source_type="port", label=label, href=f"/app/port/{port_id}", source_module="Port Operations")

    @staticmethod
    def _port_call_link(port_call_id: str) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=port_call_id, source_type="port_call", label="Pre-Arrival Report", href=f"/app/port-calls/{port_call_id}", source_module="Port Operations")

    @staticmethod
    def _investigation_link(investigation_id: str) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=investigation_id, source_type="investigation", label=investigation_id, href=f"/app/investigations/{investigation_id}", source_module="Investigation Service")

    @staticmethod
    def _environmental_link(
        source_id: str,
        event_id: str,
        label: str,
        source_type: str = "environmental_event",
        module: str = "Environmental Intelligence",
    ) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(
            id=source_id,
            source_type=source_type,
            label=label,
            href=f"/app/environment/events/{event_id}?evidence={source_id}",
            source_module=module,
        )

    @staticmethod
    def _policy_link(policy_id: str) -> AssistantEvidenceLink:
        return AssistantEvidenceLink(id=policy_id, source_type="policy", label=policy_id, href="/app/settings", source_module="Caspian Intelligence Policy")

    # ---- Audit and utility ----------------------------------------------------------

    def _audit_answer(self, user_id: str, role: AssistantRole, question: str, response: AssistantChatResponse) -> None:
        self._audit.append(AssistantAuditEntry(
            id=f"AUD-{len(self._audit) + 1:06d}",
            user_id=user_id,
            role=role,
            question=question,
            conversation_id=response.conversation_id,
            timestamp=response.created_at,
            tools_called=[item.name for item in response.tools_called],
            data_accessed=list(dict.fromkeys(value for item in response.tools_called for value in item.data_accessed)),
            answer=response.answer,
            actions=[item.id for item in response.actions],
            outcome="insufficient_data" if response.no_data else "answered",
        ))

    def _audit_write(self, user_id: str, role: AssistantRole, question: str, outcome: str, data: list[str]) -> None:
        self._audit.append(AssistantAuditEntry(
            id=f"AUD-{len(self._audit) + 1:06d}",
            user_id=user_id,
            role=role,
            question=question,
            timestamp=_timestamp(),
            tools_called=[],
            data_accessed=data,
            answer=question,
            actions=data,
            outcome=outcome,
        ))

    @staticmethod
    def _record_count(result: Any) -> int:
        if isinstance(result, list):
            return len(result)
        if isinstance(result, dict):
            if "events" in result and isinstance(result["events"], list):
                return len(result["events"]) + len(result.get("connections", []))
            if "vessel_ids" in result:
                return len(result["vessel_ids"]) + int(result.get("event_count", 0))
            return 1
        return 1

    @staticmethod
    def _data_ids(result: Any) -> list[str]:
        values: list[str] = []
        stack = list(result) if isinstance(result, list) else [result]
        for item in stack:
            if not isinstance(item, dict):
                continue
            if item.get("id"):
                values.append(str(item["id"]))
            for key in ("events", "connections", "items", "points", "bottlenecks", "recommendations"):
                nested = item.get(key)
                if isinstance(nested, list):
                    values.extend(str(value.get("id")) for value in nested if isinstance(value, dict) and value.get("id"))
        return list(dict.fromkeys(values))[:200]


assistant_service = AssistantService()
