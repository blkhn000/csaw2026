"""Stage 10 regional Caspian Network service.

This is a provider-neutral, in-memory reference implementation.  It proves the
multi-country/multi-port contracts without pretending that national systems are
already connected.  Real adapters can replace ``DemoPortAdapter`` without
changing callers or the Stage 1-9 modules.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from datetime import datetime, timezone
import re
from typing import Any, Iterable

from fastapi import HTTPException

from .network_models import (
    AdapterStatus, CompanyIdentityResolutionRequest, CrossPortComparison,
    CrossPortObservation, CrossPortReport, DataConflict, DataConflictValue,
    DataSourceRecord, GlobalCompanyIdentity, GlobalVesselIdentity,
    IdentityResolutionResult, NetworkOrganization, NetworkPort, NetworkPrincipal,
    PortBerth, PortConfiguration, PortCoordinates, PortIntegrationStatus,
    PortMovement, PortStatus, ProvenanceRecord, RegionalAuditEntry,
    RegionalGraphEdge, RegionalGraphNode, RegionalRiskItem, RouteIntelligence,
    VesselIdentityHistoryItem, VesselIdentityResolutionRequest, VesselSourceAlias,
)


NETWORK_MODEL_VERSION = "CI-NETWORK-1.0"
NETWORK_DATASET_VERSION = "CI-NETWORK-DEMO-2026.08"
GENERATED_AT = "2026-08-10T10:05:00Z"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _company_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()
    words = [word for word in normalized.split() if word not in {"ltd", "limited", "llc", "co", "company"}]
    return " ".join(words)


def _text_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


class PortAdapter(ABC):
    """Standard contract every real port integration must implement."""

    port_id: str
    adapter_id: str

    @abstractmethod
    def fetch_arrivals(self) -> list[PortMovement]: ...

    @abstractmethod
    def fetch_departures(self) -> list[PortMovement]: ...

    @abstractmethod
    def fetch_berths(self) -> list[PortBerth]: ...

    @abstractmethod
    def fetch_cargo(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def fetch_documents(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def push_eta(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def push_alert(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class DemoPortAdapter(PortAdapter):
    """Deterministic adapter used only by the technical prototype."""

    def __init__(
        self,
        port_id: str,
        arrivals: list[PortMovement],
        departures: list[PortMovement],
        berths: list[PortBerth],
        *,
        status: str = "ONLINE",
    ) -> None:
        self.port_id = port_id
        self.adapter_id = f"adapter-{port_id}"
        self._arrivals = arrivals
        self._departures = departures
        self._berths = berths
        self.status = status

    def fetch_arrivals(self) -> list[PortMovement]:
        return deepcopy(self._arrivals)

    def fetch_departures(self) -> list[PortMovement]:
        return deepcopy(self._departures)

    def fetch_berths(self) -> list[PortBerth]:
        return deepcopy(self._berths)

    def fetch_cargo(self) -> list[dict[str, Any]]:
        return [
            {"movement_id": item.id, "cargo_type": item.cargo_type, "cargo_t": item.cargo_t, "source_ids": item.source_ids}
            for item in self._arrivals + self._departures if item.cargo_t is not None
        ]

    def fetch_documents(self) -> list[dict[str, Any]]:
        return [{"id": f"DOC-{self.port_id.upper()}-DEMO", "status": "DEMO_ONLY", "port_id": self.port_id}]

    def push_eta(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"accepted": True, "adapter_id": self.adapter_id, "kind": "ETA", "payload_id": payload.get("id")}

    def push_alert(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"accepted": True, "adapter_id": self.adapter_id, "kind": "ALERT", "payload_id": payload.get("id")}


class CaspianNetworkService:
    """Regional read model, entity resolver and access-scope enforcement."""

    def __init__(self) -> None:
        self.organizations = self._seed_organizations()
        self.ports = self._seed_ports()
        self.port_status = self._seed_port_status()
        self.vessels = self._seed_vessel_identities()
        self.companies = self._seed_company_identities()
        self.voyages = self._seed_voyages()
        self.risks = self._seed_risk()
        self.routes = self._seed_routes()
        self.sources = self._seed_sources()
        self.provenance = self._seed_provenance()
        self.conflicts = self._seed_conflicts()
        self._arrivals, self._departures, self._berths = self._seed_port_operations()
        self.adapters: dict[str, PortAdapter] = {
            port_id: DemoPortAdapter(
                port_id,
                self._arrivals.get(port_id, []),
                self._departures.get(port_id, []),
                self._berths.get(port_id, []),
                status="DEGRADED" if port_id == "baku" else "ONLINE",
            )
            for port_id in self.ports
        }
        self.audit_entries: list[RegionalAuditEntry] = [
            RegionalAuditEntry(
                id="NAUD-000001", timestamp="2026-08-10T09:32:00Z",
                user_id="analyst-142", organization_id="org-regional-ci", role="ANALYST",
                action="VIEW", resource_type="INVESTIGATION", resource_id="CI-2026-00984",
                data_scope=["region:caspian", "investigations:read"], outcome="ALLOWED",
                details={"source": "seeded demonstration audit event"},
            )
        ]

    # -- Access -----------------------------------------------------------------

    def principal_for_role(self, role: str) -> NetworkPrincipal:
        mapping = {
            "ADMIN": ("demo-admin", "org-regional-ci", ["*"], ["region:caspian", "sensitive:read", "audit:read", "write:confirmed"]),
            "ANALYST": ("demo-analyst", "org-regional-ci", ["network:read", "identity:resolve", "sensitive:read", "audit:read"], ["region:caspian", "ports:*", "investigations:read"]),
            "VIEWER": ("demo-viewer", "org-public", ["network:read"], ["region:caspian:public", "ports:public"]),
            "PORT_DISPATCHER": ("demo-port-dispatcher", "org-aktau-port", ["network:read", "port:operate"], ["port:aktau", "vessels:approaching:aktau"]),
        }
        if role not in mapping:
            raise HTTPException(status_code=401, detail="Unknown network role")
        user_id, organization_id, permissions, scopes = mapping[role]
        return NetworkPrincipal(
            user_id=user_id,
            organization=self.organizations[organization_id].model_copy(deep=True),
            role=role,
            permissions=permissions,
            data_scope=scopes,
        )

    @staticmethod
    def _has_permission(principal: NetworkPrincipal, permission: str) -> bool:
        return "*" in principal.permissions or permission in principal.permissions

    def require_permission(self, principal: NetworkPrincipal, permission: str) -> None:
        if not self._has_permission(principal, permission):
            self._record_audit(principal, "ACCESS", permission, None, "DENIED")
            raise HTTPException(status_code=403, detail=f"Permission {permission} is required")

    def require_port_access(self, principal: NetworkPrincipal, port_id: str) -> None:
        self._require_port(port_id)
        if principal.role == "PORT_DISPATCHER" and f"port:{port_id}" not in principal.data_scope:
            self._record_audit(principal, "VIEW", "PORT", port_id, "DENIED")
            raise HTTPException(status_code=403, detail="Port is outside the organization data scope")

    def get_access(self, principal: NetworkPrincipal) -> NetworkPrincipal:
        self._record_audit(principal, "VIEW", "ACCESS_SCOPE", principal.organization.id, "ALLOWED")
        return principal.model_copy(deep=True)

    # -- Registry and port engine ------------------------------------------------

    def list_ports(self, principal: NetworkPrincipal) -> list[NetworkPort]:
        self.require_permission(principal, "network:read")
        items = list(self.ports.values())
        if principal.role == "PORT_DISPATCHER":
            items = [item for item in items if f"port:{item.id}" in principal.data_scope]
        self._record_audit(principal, "LIST", "PORT", None, "ALLOWED", {"count": len(items)})
        return deepcopy(items)

    def get_port(self, port_id: str, principal: NetworkPrincipal | None = None) -> NetworkPort:
        item = self._require_port(port_id)
        if principal is not None:
            self.require_port_access(principal, port_id)
            self._record_audit(principal, "VIEW", "PORT", port_id, "ALLOWED")
        return item.model_copy(deep=True)

    def get_port_overview(self, port_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        self.require_port_access(principal, port_id)
        port = self._require_port(port_id)
        status = self.port_status[port_id]
        arrivals = self.adapters[port_id].fetch_arrivals()
        departures = self.adapters[port_id].fetch_departures()
        response = {
            "port_id": port.id,
            "name": port.name,
            "country": port.country,
            "load_percent": status.load_percent,
            "incoming": len(arrivals),
            "vessels": status.vessels,
            "data_quality": round(max(
                (self.sources[source_id].quality_score for source_id in port.data_source_ids if source_id in self.sources),
                default=0,
            ) * 100),
            "port": port.model_copy(deep=True),
            "status": status.model_copy(deep=True),
            "generated_at": GENERATED_AT,
            "timestamp_standard": "UTC",
            "local_timezone": port.timezone,
            "metrics": {
                "average_wait_minutes": {"aktau": 102, "baku": 126, "turkmenbashi": 54}.get(port_id, 76),
                "average_service_minutes": {"aktau": 312, "baku": 348, "turkmenbashi": 276}.get(port_id, 295),
                "port_load_percent": status.load_percent,
                "incoming": len(arrivals),
                "departures": len(departures),
                "high_risk_arrivals": status.high_risk_arrivals,
            },
            "arrivals": arrivals,
            "departures": departures,
            "integration_status": port.integration_status.model_copy(deep=True),
            "source_ids": port.data_source_ids,
        }
        self._record_audit(principal, "VIEW", "PORT_OVERVIEW", port_id, "ALLOWED")
        return deepcopy(response)

    def get_port_arrivals(self, port_id: str, principal: NetworkPrincipal) -> list[PortMovement]:
        self.require_port_access(principal, port_id)
        result = self.adapters[port_id].fetch_arrivals()
        self._record_audit(principal, "LIST", "PORT_ARRIVAL", port_id, "ALLOWED", {"count": len(result)})
        return result

    def get_port_departures(self, port_id: str, principal: NetworkPrincipal) -> list[PortMovement]:
        self.require_port_access(principal, port_id)
        result = self.adapters[port_id].fetch_departures()
        self._record_audit(principal, "LIST", "PORT_DEPARTURE", port_id, "ALLOWED", {"count": len(result)})
        return result

    def get_port_berths(self, port_id: str, principal: NetworkPrincipal) -> list[PortBerth]:
        self.require_port_access(principal, port_id)
        result = self.adapters[port_id].fetch_berths()
        self._record_audit(principal, "LIST", "PORT_BERTH", port_id, "ALLOWED", {"count": len(result)})
        return result

    def get_port_queue(self, port_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        arrivals = self.get_port_arrivals(port_id, principal)
        items = [
            {
                "position": index,
                "movement_id": item.id,
                "global_vessel_id": item.global_vessel_id,
                "vessel_name": item.vessel_name,
                "eta": item.predicted_at,
                "berth_id": item.berth_id,
                "risk_score": item.risk_score,
                "status": "ATTENTION" if item.risk_score >= 75 else "SCHEDULED",
            }
            for index, item in enumerate(sorted(arrivals, key=lambda value: (-value.risk_score, value.predicted_at)), 1)
        ]
        return {
            "port_id": port_id,
            "generated_at": GENERATED_AT,
            "dynamic": True,
            "average_wait_minutes": self.get_port_overview(port_id, principal)["metrics"]["average_wait_minutes"],
            "items": items,
            "disclaimer": "Queue is a planning recommendation; a dispatcher remains responsible for decisions.",
        }

    def get_port_forecast(self, port_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        self.require_port_access(principal, port_id)
        base = self.port_status[port_id].load_percent
        points = [
            {"at": f"2026-08-10T{hour:02d}:00:00Z", "load_percent": max(5, min(98, base + delta)), "arrivals": max(1, 4 + delta // 5)}
            for hour, delta in ((10, 0), (12, 5), (14, 11), (16, 7), (18, -3), (20, -12))
        ]
        self._record_audit(principal, "VIEW", "PORT_FORECAST", port_id, "ALLOWED")
        return {
            "port_id": port_id, "generated_at": GENERATED_AT, "horizon_hours": 10,
            "points": points, "peak": max(points, key=lambda item: item["load_percent"]),
            "model_version": "CI-PORT-NETWORK-1.0", "provenance": "ESTIMATED",
        }

    def get_port_configuration(self, port_id: str, principal: NetworkPrincipal) -> PortConfiguration:
        self.require_port_access(principal, port_id)
        return self._require_port(port_id).configuration.model_copy(deep=True)

    def get_port_integration(self, port_id: str, principal: NetworkPrincipal) -> PortIntegrationStatus:
        self.require_port_access(principal, port_id)
        return self._require_port(port_id).integration_status.model_copy(deep=True)

    def get_port_intelligence(self, port_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        overview = self.get_port_overview(port_id, principal)
        return {
            "port_id": port_id,
            "period_days": 30,
            "average_wait_minutes": overview["metrics"]["average_wait_minutes"],
            "average_service_minutes": overview["metrics"]["average_service_minutes"],
            "load_percent": overview["metrics"]["port_load_percent"],
            "incoming": overview["metrics"]["incoming"],
            "high_risk_arrivals": overview["metrics"]["high_risk_arrivals"],
            "port_calls_30d": 84 if port_id == "aktau" else 96 if port_id == "baku" else 47,
            "on_time_percent": 82 if port_id == "aktau" else 76 if port_id == "baku" else 88,
            "generated_at": GENERATED_AT,
        }

    def compare_ports(self, port_ids: list[str], principal: NetworkPrincipal) -> dict[str, Any]:
        if not 2 <= len(port_ids) <= 5:
            raise HTTPException(status_code=422, detail="Compare between two and five ports")
        items = [self.get_port_intelligence(port_id, principal) for port_id in dict.fromkeys(port_ids)]
        return {
            "port_ids": [item["port_id"] for item in items], "period_days": 30,
            "items": items,
            "best_waiting_time_port_id": min(items, key=lambda item: item["average_wait_minutes"])["port_id"],
            "highest_load_port_id": max(items, key=lambda item: item["load_percent"])["port_id"],
            "generated_at": GENERATED_AT,
        }

    # -- Regional dashboard ------------------------------------------------------

    def overview(self, principal: NetworkPrincipal) -> dict[str, Any]:
        self.require_permission(principal, "network:read")
        statuses = self.list_port_status(principal)
        risks = self.list_risk(principal)["items"]
        routes = self.list_routes(principal)
        result = {
            "generated_at": GENERATED_AT,
            "dataset_version": NETWORK_DATASET_VERSION,
            "model_version": NETWORK_MODEL_VERSION,
            "region": {"id": "caspian", "name": "Caspian Sea", "countries": 5, "ports_registered": len(self.ports)},
            "metrics": {
                "vessels_active": 482, "voyages_today": 127, "port_calls": 84,
                "high_risk": 11, "ais_gaps": 23, "encounters": 17,
                "environmental_events": 2,
            },
            "port_statuses": statuses,
            "priority_vessels": risks[:3],
            "top_routes": routes[:3],
            "data_health": self.data_health(principal, audit=False)["summary"],
            "provenance": "DEMO_AGGREGATE",
        }
        if principal.role == "PORT_DISPATCHER":
            result["metrics"] = {
                "vessels_active": statuses[0].vessels if statuses else 0,
                "voyages_today": len(self._arrivals.get("aktau", [])) + len(self._departures.get("aktau", [])),
                "port_calls": len(self._arrivals.get("aktau", [])),
                "high_risk": len(risks), "ais_gaps": 1, "encounters": 1, "environmental_events": 0,
            }
        self._record_audit(principal, "VIEW", "NETWORK_OVERVIEW", "caspian", "ALLOWED")
        return deepcopy(result)

    def list_port_status(self, principal: NetworkPrincipal) -> list[PortStatus]:
        self.require_permission(principal, "network:read")
        result = list(self.port_status.values())
        if principal.role == "PORT_DISPATCHER":
            result = [item for item in result if f"port:{item.port_id}" in principal.data_scope]
        return deepcopy(result)

    def regional_map(self, principal: NetworkPrincipal) -> dict[str, Any]:
        ports = self.list_port_status(principal)
        allowed_port_ids = {item.port_id for item in ports}
        vessels = [
            {"id": "CI-VESSEL-000184", "legacy_vessel_id": "caspian-star", "name": "CASPIAN STAR", "lat": 42.31, "lon": 50.74, "risk_score": 91, "destination_port_id": "aktau", "source_id": "source-kz-ais"},
            {"id": "CI-VESSEL-000241", "legacy_vessel_id": "turan", "name": "TURAN", "lat": 41.86, "lon": 51.02, "risk_score": 84, "destination_port_id": "baku", "source_id": "source-tm-ais"},
            {"id": "CI-VESSEL-000317", "legacy_vessel_id": "volga-marine", "name": "VOLGA MARINE", "lat": 43.16, "lon": 48.91, "risk_score": 78, "destination_port_id": "aktau", "source_id": "source-kz-ais"},
            {"id": "CI-VESSEL-000322", "legacy_vessel_id": "khazar-wave", "name": "KHAZAR WAVE", "lat": 40.82, "lon": 50.21, "risk_score": 28, "destination_port_id": "baku", "source_id": "source-az-ais"},
        ]
        if principal.role == "PORT_DISPATCHER":
            vessels = [item for item in vessels if item["destination_port_id"] in allowed_port_ids]
        voyages = [item for item in self.voyages if principal.role != "PORT_DISPATCHER" or item["destination_port_id"] in allowed_port_ids]
        return {
            "generated_at": GENERATED_AT,
            "ports": ports,
            "vessels": deepcopy(vessels),
            "voyages": deepcopy(voyages),
            "risk_events": [
                {"id": "EV-2841", "type": "AIS_GAP", "global_vessel_id": "CI-VESSEL-000184", "lat": 41.9, "lon": 50.5, "occurred_at": "2026-08-10T09:10:00Z"},
                {"id": "EN-884", "type": "ENCOUNTER", "global_vessel_id": "CI-VESSEL-000184", "lat": 42.0, "lon": 50.6, "occurred_at": "2026-08-10T12:28:00Z"},
            ],
            "environmental_events": [] if principal.role == "PORT_DISPATCHER" else [
                {"id": "ENV-2026-00142", "type": "OIL_POLLUTION", "lat": 42.16, "lon": 50.62, "confidence": .87, "status": "UNDER REVIEW"},
            ],
            "coverage": self.coverage(principal, audit=False)["layers"],
        }

    def list_risk(
        self,
        principal: NetworkPrincipal,
        *,
        country: str | None = None,
        port_id: str | None = None,
        route_id: str | None = None,
        vessel_type: str | None = None,
        minimum_score: int = 0,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        self.require_permission(principal, "network:read")
        items = list(self.risks)
        if principal.role == "PORT_DISPATCHER":
            items = [item for item in items if item.destination_port_id == "aktau"]
        if country:
            port_ids = {item.id for item in self.ports.values() if item.country.casefold() == country.casefold()}
            items = [item for item in items if item.origin_port_id in port_ids or item.destination_port_id in port_ids]
        if port_id:
            self.require_port_access(principal, port_id)
            items = [item for item in items if port_id in {item.origin_port_id, item.destination_port_id}]
        if route_id:
            items = [item for item in items if item.route_id == route_id]
        if vessel_type:
            items = [item for item in items if item.vessel_type.casefold() == vessel_type.casefold()]
        if event_type:
            items = [item for item in items if event_type.casefold() in {value.casefold() for value in item.event_types}]
        items = [item for item in items if item.score >= minimum_score]
        items.sort(key=lambda item: item.score, reverse=True)
        self._record_audit(principal, "LIST", "REGIONAL_RISK", None, "ALLOWED", {"count": len(items)})
        return {
            "generated_at": GENERATED_AT,
            "total": len(items),
            "items": deepcopy(items),
            "filters": {"country": country, "port_id": port_id, "route_id": route_id, "vessel_type": vessel_type, "minimum_score": minimum_score, "event_type": event_type},
            "scope": principal.data_scope,
            "disclaimer": "Risk identifies signals requiring review; it is not a finding of wrongdoing.",
        }

    def list_routes(self, principal: NetworkPrincipal) -> list[RouteIntelligence]:
        self.require_permission(principal, "network:read")
        items = list(self.routes.values())
        if principal.role == "PORT_DISPATCHER":
            items = [item for item in items if "aktau" in {item.origin_port_id, item.destination_port_id}]
        return deepcopy(sorted(items, key=lambda item: item.voyages, reverse=True))

    def get_route(self, route_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        item = self.routes.get(route_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Regional route not found")
        if principal.role == "PORT_DISPATCHER" and "aktau" not in {item.origin_port_id, item.destination_port_id}:
            raise HTTPException(status_code=403, detail="Route is outside the organization data scope")
        voyages = [value for value in self.voyages if value["route_id"] == route_id]
        self._record_audit(principal, "VIEW", "ROUTE", route_id, "ALLOWED")
        return {"route": item.model_copy(deep=True), "voyages": deepcopy(voyages), "generated_at": GENERATED_AT}

    # -- Global identity ---------------------------------------------------------

    def get_vessel_identity(self, vessel_id: str, principal: NetworkPrincipal) -> GlobalVesselIdentity:
        self.require_permission(principal, "network:read")
        item = self._resolve_identity(vessel_id)
        self._record_audit(principal, "VIEW", "VESSEL_IDENTITY", item.caspian_vessel_id, "ALLOWED")
        return item.model_copy(deep=True)

    def get_vessel_identity_history(self, vessel_id: str, principal: NetworkPrincipal) -> list[VesselIdentityHistoryItem]:
        return self.get_vessel_identity(vessel_id, principal).identity_history

    def get_vessel_voyages(self, vessel_id: str, principal: NetworkPrincipal) -> dict[str, Any]:
        identity = self.get_vessel_identity(vessel_id, principal)
        items = [item for item in self.voyages if item["global_vessel_id"] == identity.caspian_vessel_id]
        if principal.role == "PORT_DISPATCHER":
            items = [item for item in items if "aktau" in {item["origin_port_id"], item["destination_port_id"]}]
        return {
            "global_vessel_id": identity.caspian_vessel_id,
            "vessel_name": identity.canonical_name,
            "voyages": deepcopy(items),
            "port_history": ["baku", "aktau", "turkmenbashi", "aktau", "baku"],
            "continuous_identity": True,
        }

    def resolve_vessel_identity(
        self, request: VesselIdentityResolutionRequest | dict[str, Any], principal: NetworkPrincipal,
    ) -> IdentityResolutionResult:
        if not isinstance(request, VesselIdentityResolutionRequest):
            request = VesselIdentityResolutionRequest.model_validate(request)
        self.require_permission(principal, "identity:resolve")
        candidates: list[tuple[float, GlobalVesselIdentity, list[str], list[str]]] = []
        for identity in self.vessels.values():
            score = 0.0
            matched_on: list[str] = []
            conflicts: list[str] = []
            known_imos = {identity.imo, *(item.imo for item in identity.source_aliases if item.imo)}
            known_mmsis = {identity.mmsi, *(item.mmsi for item in identity.source_aliases if item.mmsi), *(item.mmsi for item in identity.identity_history)}
            known_names = {identity.canonical_name, *(item.name for item in identity.source_aliases), *(item.name for item in identity.identity_history)}
            if request.imo and request.imo in known_imos:
                score += .70; matched_on.append("imo")
            if request.mmsi and request.mmsi in known_mmsis:
                score += .65; matched_on.append("mmsi")
            if request.call_sign and _text_key(request.call_sign) == _text_key(identity.call_sign):
                score += .35; matched_on.append("call_sign")
            if request.name and any(_text_key(request.name) == _text_key(value) for value in known_names):
                score += .30; matched_on.append("name")
            if request.length_m and abs(request.length_m - identity.length_m) <= 3:
                score += .10; matched_on.append("length")
            if request.width_m and abs(request.width_m - identity.width_m) <= 2:
                score += .08; matched_on.append("width")
            if matched_on and request.flag and request.flag.casefold() != identity.flag.casefold():
                conflicts.append("flag")
            if matched_on:
                candidates.append((min(.99, score), identity, matched_on, conflicts))
        candidates.sort(key=lambda value: value[0], reverse=True)
        if not candidates:
            result = IdentityResolutionResult(
                entity_type="VESSEL", global_id=None, matched=False, confidence=0,
                status="NO_MATCH", matched_on=[], conflicting_fields=[], candidates=[],
                explanation="No existing identity has enough matching evidence. Manual review is required before creating a new global identity.",
            )
        else:
            confidence, identity, matched_on, conflicts = candidates[0]
            strong = "imo" in matched_on or "mmsi" in matched_on or len(matched_on) >= 3
            confirmed = strong and confidence >= .65 and not conflicts
            status = "CONFIRMED" if confirmed else "PROBABLE" if confidence >= .45 else "REVIEW_REQUIRED"
            result = IdentityResolutionResult(
                entity_type="VESSEL", global_id=identity.caspian_vessel_id,
                matched=confidence >= .30, confidence=confidence, status=status,
                matched_on=matched_on, conflicting_fields=conflicts,
                candidates=[{"global_id": item.caspian_vessel_id, "name": item.canonical_name, "confidence": candidate_score} for candidate_score, item, _, _ in candidates[:3]],
                explanation="Resolution uses IMO, MMSI, call sign, normalized name, dimensions and identity history; conflicting strong fields prevent automatic confirmation.",
            )
        self._record_audit(principal, "RESOLVE", "VESSEL_IDENTITY", result.global_id, "ALLOWED", {"status": result.status})
        return result

    def get_company(self, company_id: str, principal: NetworkPrincipal) -> GlobalCompanyIdentity:
        self.require_permission(principal, "network:read")
        item = self.companies.get(company_id)
        if item is None:
            key = _company_key(company_id)
            item = next((value for value in self.companies.values() if key in {_company_key(value.canonical_name), *(_company_key(alias) for alias in value.aliases)}), None)
        if item is None:
            raise HTTPException(status_code=404, detail="Global company identity not found")
        self._record_audit(principal, "VIEW", "COMPANY_IDENTITY", item.caspian_company_id, "ALLOWED")
        return item.model_copy(deep=True)

    def resolve_company_identity(
        self, request: CompanyIdentityResolutionRequest | dict[str, Any], principal: NetworkPrincipal,
    ) -> IdentityResolutionResult:
        if not isinstance(request, CompanyIdentityResolutionRequest):
            request = CompanyIdentityResolutionRequest.model_validate(request)
        self.require_permission(principal, "identity:resolve")
        key = _company_key(request.name)
        matches = []
        for company in self.companies.values():
            names = {_company_key(company.canonical_name), *(_company_key(alias) for alias in company.aliases)}
            matched_on = []
            confidence = 0.0
            if key in names:
                confidence += .82; matched_on.append("normalized_name")
            if request.registration_number and request.registration_number in company.registration_numbers:
                confidence += .17; matched_on.append("registration_number")
            if request.country and request.country.casefold() == company.country.casefold():
                confidence += .05; matched_on.append("country")
            if matched_on:
                matches.append((min(.99, confidence), company, matched_on))
        matches.sort(key=lambda item: item[0], reverse=True)
        if not matches:
            result = IdentityResolutionResult(
                entity_type="COMPANY", global_id=None, matched=False, confidence=0,
                status="NO_MATCH", matched_on=[], conflicting_fields=[], candidates=[],
                explanation="No normalized company alias or registration number matched.",
            )
        else:
            confidence, company, matched_on = matches[0]
            result = IdentityResolutionResult(
                entity_type="COMPANY", global_id=company.caspian_company_id, matched=True,
                confidence=confidence, status="CONFIRMED" if confidence >= .82 else "PROBABLE",
                matched_on=matched_on, conflicting_fields=[],
                candidates=[{"global_id": value.caspian_company_id, "name": value.canonical_name, "confidence": score} for score, value, _ in matches[:3]],
                explanation="Company aliases are normalized without legal-form punctuation; registration numbers remain the strongest confirmation signal.",
            )
        self._record_audit(principal, "RESOLVE", "COMPANY_IDENTITY", result.global_id, "ALLOWED", {"status": result.status})
        return result

    # -- Cross-port verification -------------------------------------------------

    def get_cross_port_report(self, voyage_id: str, principal: NetworkPrincipal) -> CrossPortReport:
        self.require_permission(principal, "sensitive:read")
        voyage_aliases = {"voy-001": "NET-VOY-001", "VOY-2026-143": "NET-VOY-001"}
        voyage_id = voyage_aliases.get(voyage_id, voyage_id)
        voyage = next((item for item in self.voyages if item["id"] == voyage_id), None)
        if voyage is None:
            raise HTTPException(status_code=404, detail="Port-to-port voyage not found")
        if voyage_id != "NET-VOY-001":
            raise HTTPException(status_code=404, detail="Cross-port verification is not available for this voyage")
        relevant = [item.model_copy(deep=True) for item in self.provenance if item.entity_id == voyage_id]
        departure = CrossPortObservation(
            port_id="baku", observed_at="2026-08-10T04:02:00Z", cargo_t=5000,
            draught_m=5.2, shipper="Caspian Steel Export", consignee="Aktau Metals",
            document_ids=["DOC-BAKU-771"], status="REPORTED", source_ids=["source-baku-port"],
        )
        arrival = CrossPortObservation(
            port_id="aktau", observed_at="2026-08-11T10:18:00Z", cargo_t=4920,
            draught_m=5.1, shipper="Caspian Steel Export", consignee="Aktau Metals",
            document_ids=["DOC-AKTAU-884"], status="VERIFIED", source_ids=["source-aktau-port"],
        )
        comparisons = [
            CrossPortComparison(
                field_name="cargo_t", departure_value=5000, arrival_value=4920,
                difference=-80, unit="t", tolerance=100, status="WITHIN_TOLERANCE",
                explanation="The 80 t difference is 1.6% and remains within the configured 2% voyage tolerance.",
                evidence_ids=["PROV-CARGO-BAKU-001", "PROV-CARGO-AKTAU-001"],
            ),
            CrossPortComparison(
                field_name="draught_m", departure_value=5.2, arrival_value=5.1,
                difference=-.1, unit="m", tolerance=.25, status="WITHIN_TOLERANCE",
                explanation="Verified draught change remains within measurement and voyage tolerance.",
                evidence_ids=["PROV-DRAUGHT-BAKU-001", "PROV-DRAUGHT-AKTAU-001"],
            ),
            CrossPortComparison(
                field_name="documents", departure_value="DOC-BAKU-771", arrival_value="DOC-AKTAU-884",
                status="WITHIN_TOLERANCE", explanation="Shipper, consignee and cargo type match across declarations.",
                evidence_ids=["DOC-BAKU-771", "DOC-AKTAU-884"],
            ),
        ]
        result = CrossPortReport(
            voyage_id=voyage_id, global_vessel_id="CI-VESSEL-000184", vessel_name="CASPIAN STAR",
            origin_port_id="baku", destination_port_id="aktau", departure=departure, arrival=arrival,
            comparisons=comparisons, overall_status="WITHIN_TOLERANCE", provenance=relevant,
            next_voyage_id="NET-VOY-002", generated_at=GENERATED_AT,
            disclaimer="A mismatch is an analytical signal for human review and is not evidence of a violation.",
        )
        self._record_audit(principal, "VIEW", "CROSS_PORT_REPORT", voyage_id, "ALLOWED", {"sources": ["source-baku-port", "source-aktau-port"]})
        return result

    # -- Provenance, source health and coverage ---------------------------------

    def list_sources(self, principal: NetworkPrincipal) -> list[DataSourceRecord]:
        self.require_permission(principal, "network:read")
        items = list(self.sources.values())
        if principal.role == "PORT_DISPATCHER":
            items = [item for item in items if item.id in {"source-kz-ais", "source-aktau-port", "source-weather"}]
        return deepcopy(items)

    def list_provenance(self, entity_type: str, entity_id: str, principal: NetworkPrincipal) -> list[ProvenanceRecord]:
        self.require_permission(principal, "sensitive:read")
        result = [item for item in self.provenance if item.entity_type.casefold() == entity_type.casefold() and item.entity_id == entity_id]
        self._record_audit(principal, "VIEW", "PROVENANCE", entity_id, "ALLOWED", {"count": len(result)})
        return deepcopy(result)

    def list_conflicts(self, principal: NetworkPrincipal, status: str | None = None) -> list[DataConflict]:
        self.require_permission(principal, "sensitive:read")
        result = self.conflicts
        if status:
            result = [item for item in result if item.status.casefold() == status.casefold()]
        self._record_audit(principal, "LIST", "DATA_CONFLICT", None, "ALLOWED", {"count": len(result)})
        return deepcopy(result)

    def data_health(self, principal: NetworkPrincipal, *, audit: bool = True) -> dict[str, Any]:
        items = self.list_sources(principal)
        counts = {state: sum(item.status == state for item in items) for state in ("ONLINE", "DEGRADED", "OFFLINE")}
        result = {
            "generated_at": GENERATED_AT,
            "summary": {
                "status": "DEGRADED" if counts["DEGRADED"] or counts["OFFLINE"] else "ONLINE",
                "health_score": 92,
                **{key.casefold(): value for key, value in counts.items()},
            },
            "sources": items,
            "quality_note": "Coverage and source latency must be considered when interpreting AIS gaps.",
        }
        if audit:
            self._record_audit(principal, "VIEW", "DATA_HEALTH", "caspian", "ALLOWED")
        return result

    def coverage(self, principal: NetworkPrincipal, *, audit: bool = True) -> dict[str, Any]:
        self.require_permission(principal, "network:read")
        layers = [
            {"id": "COV-AIS-CENTRAL", "type": "AIS", "quality": "HIGH", "coverage_percent": 94, "geometry": {"type": "Polygon", "coordinates": [[[48.0, 39.0], [53.5, 39.0], [53.5, 45.0], [48.0, 45.0], [48.0, 39.0]]]}, "source_ids": ["source-kz-ais", "source-az-ais", "source-tm-ais"]},
            {"id": "COV-AIS-NORTH", "type": "AIS", "quality": "MEDIUM", "coverage_percent": 68, "geometry": {"type": "Polygon", "coordinates": [[[46.8, 44.0], [50.5, 44.0], [50.5, 47.0], [46.8, 47.0], [46.8, 44.0]]]}, "source_ids": ["source-kz-ais"]},
            {"id": "COV-ENV-REGIONAL", "type": "ENVIRONMENTAL", "quality": "MEDIUM", "coverage_percent": 82, "geometry": {"type": "Polygon", "coordinates": [[[47.0, 36.5], [54.0, 36.5], [54.0, 47.0], [47.0, 47.0], [47.0, 36.5]]]}, "source_ids": ["source-satellite"]},
            {"id": "COV-PORT-NODES", "type": "PORT_INTEGRATION", "quality": "MIXED", "coverage_percent": 70, "port_ids": list(self.ports), "source_ids": [item.id for item in self.sources.values() if item.source_type == "PORT"]},
        ]
        if principal.role == "PORT_DISPATCHER":
            layers = [item for item in layers if item["type"] != "ENVIRONMENTAL"]
        if audit:
            self._record_audit(principal, "VIEW", "DATA_COVERAGE", "caspian", "ALLOWED")
        return {"generated_at": GENERATED_AT, "layers": deepcopy(layers), "risk_interpretation": "Low AIS coverage reduces the evidential weight of a detected gap."}

    def list_adapters(self, principal: NetworkPrincipal) -> list[AdapterStatus]:
        self.require_permission(principal, "network:read")
        port_ids = list(self.ports)
        if principal.role == "PORT_DISPATCHER":
            port_ids = ["aktau"]
        return [
            AdapterStatus(
                id=self.adapters[port_id].adapter_id, port_id=port_id,
                adapter_type="DEMO_PORT_ADAPTER", version="1.0",
                status="DEGRADED" if port_id == "baku" else "ONLINE",
                capabilities=["fetch_arrivals", "fetch_departures", "fetch_berths", "fetch_cargo", "fetch_documents", "push_eta", "push_alert"],
                last_success_at="2026-08-10T10:04:40Z",
                last_error="Berth feed delayed by 12 minutes" if port_id == "baku" else None,
            )
            for port_id in port_ids
        ]

    def observability(self, principal: NetworkPrincipal) -> dict[str, Any]:
        self.require_permission(principal, "sensitive:read")
        return {
            "generated_at": GENERATED_AT,
            "api": {"status": "ONLINE", "p95_ms": 84, "error_rate_percent": .1},
            "ingestion": {"ais_messages_per_second": 1260, "queue_lag": 18, "failed_integrations": 1},
            "processing": {"event_p95_ms": 118, "risk_p95_ms": 92, "ai_tool_errors_1h": 0},
            "storage": {"database_load_percent": 42, "track_partitions": 36, "spatial_indexes": "READY", "time_indexes": "READY"},
            "realtime": {"websocket_connections": 37},
            "event_bus": {"implementation": "IN_MEMORY_DEMO", "production_target": "KAFKA_OR_REDPANDA", "topics": ["ais", "behavior", "risk", "environment", "port"]},
            "retention": {"hot_days": 90, "warm_days": 730, "cold_archive": True, "durable_entities": ["events", "voyages", "risk", "investigations"]},
        }

    # -- Search and network graph ------------------------------------------------

    def search(self, query: str, principal: NetworkPrincipal, entity_types: list[str] | None = None) -> dict[str, Any]:
        self.require_permission(principal, "network:read")
        key = query.casefold().strip()
        compact = _text_key(query)
        requested = {value.casefold() for value in entity_types or []}

        def enabled(group: str) -> bool:
            return not requested or group.casefold() in requested or group.rstrip("s").casefold() in requested

        groups: dict[str, list[dict[str, Any]]] = {
            "vessels": [], "companies": [], "ports": [], "voyages": [], "events": [],
            "investigations": [], "environmental_events": [], "cargo": [],
        }
        if enabled("vessels"):
            for item in self.vessels.values():
                haystack = " ".join([
                    item.caspian_vessel_id, item.legacy_vessel_id, item.canonical_name, item.imo, item.mmsi, item.call_sign,
                    *(alias.source_vessel_id for alias in item.source_aliases),
                    *(history.mmsi for history in item.identity_history),
                ])
                if compact in _text_key(haystack):
                    groups["vessels"].append({"id": item.caspian_vessel_id, "legacy_vessel_id": item.legacy_vessel_id, "name": item.canonical_name, "imo": item.imo, "mmsi": item.mmsi, "href": f"/app/vessels/{item.legacy_vessel_id}"})
        if enabled("companies"):
            for item in self.companies.values():
                if compact in _text_key(" ".join([item.canonical_name, *item.aliases, *item.registration_numbers])):
                    groups["companies"].append({"id": item.caspian_company_id, "name": item.canonical_name, "country": item.country, "href": f"/app/network?company={item.caspian_company_id}"})
        if enabled("ports"):
            ports = self.list_ports(principal)
            for item in ports:
                if compact in _text_key(f"{item.id} {item.name} {item.country}"):
                    groups["ports"].append({"id": item.id, "name": item.name, "country": item.country, "href": f"/app/ports/{item.id}"})
        if enabled("voyages"):
            for item in self.voyages:
                if compact in _text_key(f"{item['id']} {item['vessel_name']} {item['origin_port_id']} {item['destination_port_id']}"):
                    if principal.role != "PORT_DISPATCHER" or "aktau" in {item["origin_port_id"], item["destination_port_id"]}:
                        groups["voyages"].append({**deepcopy(item), "href": f"/app/voyages/{item['id']}"})
        seeded_events = [
            {"id": "EV-2841", "type": "AIS_GAP", "vessel": "CASPIAN STAR", "route": "Baku Aktau"},
            {"id": "EN-884", "type": "ENCOUNTER", "vessel": "CASPIAN STAR TURAN", "route": "Baku Aktau"},
        ]
        if enabled("events"):
            groups["events"] = [{**item, "href": f"/app/events/{item['id']}"} for item in seeded_events if compact in _text_key(" ".join(item.values()))]
        if principal.role in {"ADMIN", "ANALYST"}:
            if enabled("investigations") and compact in _text_key("CI-2026-00984 CASPIAN STAR Baku Aktau cargo discrepancy"):
                groups["investigations"].append({"id": "CI-2026-00984", "title": "CASPIAN STAR regional investigation", "ports": ["baku", "aktau"], "href": "/app/investigations/CI-2026-00984"})
            if enabled("environmental_events") and compact in _text_key("ENV-2026-00142 ENV-142 oil pollution CASPIAN STAR"):
                groups["environmental_events"].append({"id": "ENV-2026-00142", "type": "OIL_POLLUTION", "status": "UNDER REVIEW", "href": "/app/environment/events/ENV-2026-00142"})
            if enabled("cargo") and compact in _text_key("CASPIAN STAR Steel 5000 4920 Baku Aktau"):
                groups["cargo"].append({"id": "NET-VOY-001", "global_vessel_id": "CI-VESSEL-000184", "departure_cargo_t": 5000, "arrival_cargo_t": 4920, "status": "WITHIN_TOLERANCE", "href": "/app/network/verification/NET-VOY-001"})
        total = sum(len(items) for items in groups.values())
        self._record_audit(principal, "SEARCH", "REGIONAL_SEARCH", None, "ALLOWED", {"query": query, "result_count": total})
        return {"query": query, "total": total, "groups": groups, "scope": principal.data_scope, "generated_at": GENERATED_AT}

    def graph(self, principal: NetworkPrincipal, vessel_id: str | None = None) -> dict[str, Any]:
        self.require_permission(principal, "sensitive:read")
        nodes = [
            RegionalGraphNode(id="CI-COMPANY-00421", type="COMPANY", label="Caspian Shipping Ltd.", country="Kazakhstan"),
            RegionalGraphNode(id="CI-VESSEL-000184", type="VESSEL", label="CASPIAN STAR", country="Kazakhstan", risk_score=91),
            RegionalGraphNode(id="CI-VESSEL-000241", type="VESSEL", label="TURAN", country="Turkmenistan", risk_score=84),
            RegionalGraphNode(id="baku", type="PORT", label="Baku", country="Azerbaijan"),
            RegionalGraphNode(id="aktau", type="PORT", label="Aktau", country="Kazakhstan"),
            RegionalGraphNode(id="turkmenbashi", type="PORT", label="Turkmenbashi", country="Turkmenistan"),
            RegionalGraphNode(id="route-baku-aktau", type="ROUTE", label="Baku ↔ Aktau"),
            RegionalGraphNode(id="cargo-steel", type="CARGO", label="Steel / 5,000 t"),
        ]
        edges = [
            RegionalGraphEdge(id="NEDGE-001", source="CI-COMPANY-00421", target="CI-VESSEL-000184", relationship="OPERATES", evidence_ids=["PROV-IDENTITY-001"]),
            RegionalGraphEdge(id="NEDGE-002", source="CI-VESSEL-000184", target="baku", relationship="VISITED", evidence_ids=["NET-VOY-001"]),
            RegionalGraphEdge(id="NEDGE-003", source="CI-VESSEL-000184", target="aktau", relationship="VISITED", evidence_ids=["NET-VOY-001"]),
            RegionalGraphEdge(id="NEDGE-004", source="CI-VESSEL-000184", target="turkmenbashi", relationship="VISITED", evidence_ids=["NET-VOY-002"]),
            RegionalGraphEdge(id="NEDGE-005", source="CI-VESSEL-000184", target="CI-VESSEL-000241", relationship="ENCOUNTERED", weight=14, first_seen_at="2025-02-10T11:00:00Z", last_seen_at="2026-08-10T12:28:00Z", evidence_ids=["EN-884"]),
            RegionalGraphEdge(id="NEDGE-006", source="CI-VESSEL-000184", target="route-baku-aktau", relationship="SAILED_ROUTE", weight=37, evidence_ids=["NET-VOY-001"]),
            RegionalGraphEdge(id="NEDGE-007", source="CI-VESSEL-000184", target="cargo-steel", relationship="CARRIED", evidence_ids=["PROV-CARGO-BAKU-001"]),
            RegionalGraphEdge(id="NEDGE-008", source="baku", target="route-baku-aktau", relationship="CONNECTS"),
            RegionalGraphEdge(id="NEDGE-009", source="aktau", target="route-baku-aktau", relationship="CONNECTS"),
        ]
        if vessel_id:
            identity = self._resolve_identity(vessel_id)
            connected = {identity.caspian_vessel_id}
            for edge in edges:
                if edge.source == identity.caspian_vessel_id:
                    connected.add(edge.target)
                if edge.target == identity.caspian_vessel_id:
                    connected.add(edge.source)
            nodes = [node for node in nodes if node.id in connected]
            edges = [edge for edge in edges if edge.source in connected and edge.target in connected]
        self._record_audit(principal, "VIEW", "REGIONAL_GRAPH", vessel_id, "ALLOWED")
        return {"generated_at": GENERATED_AT, "nodes": deepcopy(nodes), "edges": deepcopy(edges), "scope": "REGIONAL", "evidence_grounded": True}

    # -- Audit -------------------------------------------------------------------

    def list_audit(self, principal: NetworkPrincipal, limit: int = 100) -> list[RegionalAuditEntry]:
        self.require_permission(principal, "audit:read")
        self._record_audit(principal, "LIST", "AUDIT", None, "ALLOWED", {"limit": limit})
        return deepcopy(self.audit_entries[-limit:][::-1])

    def _record_audit(
        self,
        principal: NetworkPrincipal,
        action: str,
        resource_type: str,
        resource_id: str | None,
        outcome: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.audit_entries.append(RegionalAuditEntry(
            id=f"NAUD-{len(self.audit_entries) + 1:06d}", timestamp=_utc_now(),
            user_id=principal.user_id, organization_id=principal.organization.id,
            role=principal.role, action=action, resource_type=resource_type,
            resource_id=resource_id, data_scope=list(principal.data_scope), outcome=outcome,
            details=details or {},
        ))

    # -- Internal lookup ---------------------------------------------------------

    def _require_port(self, port_id: str) -> NetworkPort:
        item = self.ports.get(port_id.casefold())
        if item is None:
            raise HTTPException(status_code=404, detail="Regional port not found")
        return item

    def _resolve_identity(self, vessel_id: str) -> GlobalVesselIdentity:
        compact = _text_key(vessel_id)
        for item in self.vessels.values():
            values = [
                item.caspian_vessel_id, item.legacy_vessel_id, item.imo, item.mmsi, item.call_sign,
                *(alias.source_vessel_id for alias in item.source_aliases),
                *(history.mmsi for history in item.identity_history),
            ]
            if compact in {_text_key(value) for value in values}:
                return item
        raise HTTPException(status_code=404, detail="Global vessel identity not found")

    # -- Seed data ---------------------------------------------------------------

    @staticmethod
    def _seed_organizations() -> dict[str, NetworkOrganization]:
        items = [
            NetworkOrganization(id="org-regional-ci", name="Caspian Intelligence Regional Platform", organization_type="REGIONAL_PLATFORM", home_port_ids=[]),
            NetworkOrganization(id="org-aktau-port", name="Aktau Port", country="Kazakhstan", organization_type="PORT", home_port_ids=["aktau"]),
            NetworkOrganization(id="org-baku-port", name="Baku International Sea Trade Port", country="Azerbaijan", organization_type="PORT", home_port_ids=["baku", "alat"]),
            NetworkOrganization(id="org-turkmenbashi-port", name="Turkmenbashi International Seaport", country="Turkmenistan", organization_type="PORT", home_port_ids=["turkmenbashi"]),
            NetworkOrganization(id="org-public", name="Public Regional Viewer", organization_type="PUBLIC", home_port_ids=[]),
        ]
        return {item.id: item for item in items}

    @staticmethod
    def _seed_ports() -> dict[str, NetworkPort]:
        specs = [
            ("aktau", "Aktau", "Kazakhstan", "KZ", 43.65, 51.16, "Asia/Aqtau", "+05:00", 8, 7.5, "OPERATIONAL", "CONNECTED", "CONNECTED"),
            ("kuryk", "Kuryk", "Kazakhstan", "KZ", 43.20, 51.65, "Asia/Aqtau", "+05:00", 5, 7.0, "OPERATIONAL", "PARTIAL", "PARTIAL"),
            ("bautino", "Bautino", "Kazakhstan", "KZ", 44.53, 50.24, "Asia/Aqtau", "+05:00", 4, 5.5, "LIMITED", "PARTIAL", "NOT_CONNECTED"),
            ("baku", "Baku", "Azerbaijan", "AZ", 40.37, 49.89, "Asia/Baku", "+04:00", 12, 9.5, "BUSY", "PARTIAL", "CONNECTED"),
            ("alat", "Alat", "Azerbaijan", "AZ", 39.95, 49.41, "Asia/Baku", "+04:00", 7, 8.5, "OPERATIONAL", "CONNECTED", "PARTIAL"),
            ("turkmenbashi", "Turkmenbashi", "Turkmenistan", "TM", 40.02, 52.97, "Asia/Ashgabat", "+05:00", 6, 7.2, "OPERATIONAL", "CONNECTED", "PARTIAL"),
            ("astrakhan", "Astrakhan", "Russia", "RU", 46.35, 48.04, "Europe/Astrakhan", "+04:00", 9, 5.2, "LIMITED", "PARTIAL", "NOT_CONNECTED"),
            ("makhachkala", "Makhachkala", "Russia", "RU", 42.97, 47.50, "Europe/Moscow", "+03:00", 8, 8.0, "OPERATIONAL", "PARTIAL", "PARTIAL"),
            ("anzali", "Anzali", "Iran", "IR", 37.47, 49.47, "Asia/Tehran", "+03:30", 7, 6.5, "OPERATIONAL", "PARTIAL", "NOT_CONNECTED"),
            ("amirabad", "Amirabad", "Iran", "IR", 36.85, 53.37, "Asia/Tehran", "+03:30", 10, 8.5, "BUSY", "PARTIAL", "PARTIAL"),
        ]
        result = {}
        for port_id, name, country, code, lat, lon, tz, offset, berths, draught, status, berth_status, docs_status in specs:
            source_id = f"source-{port_id}-port"
            result[port_id] = NetworkPort(
                id=port_id, name=name, country=country, country_code=code,
                coordinates=PortCoordinates(latitude=lat, longitude=lon), timezone=tz,
                utc_offset=offset, port_type="COMMERCIAL_SEAPORT",
                capabilities=["General cargo", "Bulk", "Ro-Ro"] + (["Oil products"] if port_id in {"aktau", "baku", "turkmenbashi", "makhachkala"} else []),
                anchorage_zones=[f"{port_id}-anchorage-main"], navigation_zones=[f"{port_id}-approach-channel"],
                data_source_ids=[source_id, "source-weather"], operational_status=status,
                integration_status=PortIntegrationStatus(
                    ais="CONNECTED" if port_id in {"aktau", "baku", "turkmenbashi", "alat"} else "PARTIAL",
                    port_calls="CONNECTED" if port_id in {"aktau", "baku", "turkmenbashi"} else "PARTIAL",
                    berths=berth_status, cargo="CONNECTED" if port_id in {"aktau", "baku", "turkmenbashi"} else "PARTIAL",
                    documents=docs_status, adapter_id=f"adapter-{port_id}", last_sync_at="2026-08-10T10:04:40Z",
                ),
                configuration=PortConfiguration(
                    berth_count=berths, cargo_capabilities=["General cargo", "Bulk", "Ro-Ro"],
                    maximum_draught_m=draught, operational_rules=["VTS clearance required", "Valid pre-arrival report required"],
                    queue_policy="ETA + berth compatibility + operational priority",
                    weather_restrictions=["Suspend exposed operations when wind exceeds configured limit"],
                    working_hours="24/7", service_models=["bulk", "general", "ro-ro"], configuration_version="CI-PORT-CONFIG-1.0",
                ),
            )
        return result

    @staticmethod
    def _seed_port_status() -> dict[str, PortStatus]:
        specs = {
            "aktau": (68, 7, 5, 14, 1, "NORMAL"), "kuryk": (51, 4, 3, 8, 0, "NORMAL"),
            "bautino": (35, 2, 1, 3, 0, "LIMITED"), "baku": (74, 9, 8, 19, 2, "BUSY"),
            "alat": (46, 5, 4, 9, 0, "NORMAL"), "turkmenbashi": (42, 4, 5, 8, 1, "NORMAL"),
            "astrakhan": (61, 6, 5, 11, 1, "LIMITED"), "makhachkala": (55, 5, 4, 10, 1, "NORMAL"),
            "anzali": (58, 6, 5, 12, 1, "NORMAL"), "amirabad": (63, 7, 6, 13, 1, "BUSY"),
        }
        coordinates = {
            "aktau": (43.65, 51.16), "kuryk": (43.20, 51.65), "bautino": (44.53, 50.24),
            "baku": (40.37, 49.89), "alat": (39.95, 49.41), "turkmenbashi": (40.02, 52.97),
            "astrakhan": (46.35, 48.04), "makhachkala": (42.97, 47.50), "anzali": (37.47, 49.47), "amirabad": (36.85, 53.37),
        }
        names = {"aktau": ("Aktau", "Kazakhstan"), "kuryk": ("Kuryk", "Kazakhstan"), "bautino": ("Bautino", "Kazakhstan"), "baku": ("Baku", "Azerbaijan"), "alat": ("Alat", "Azerbaijan"), "turkmenbashi": ("Turkmenbashi", "Turkmenistan"), "astrakhan": ("Astrakhan", "Russia"), "makhachkala": ("Makhachkala", "Russia"), "anzali": ("Anzali", "Iran"), "amirabad": ("Amirabad", "Iran")}
        return {
            port_id: PortStatus(
                port_id=port_id, name=names[port_id][0], country=names[port_id][1],
                latitude=coordinates[port_id][0], longitude=coordinates[port_id][1],
                load_percent=values[0], arrivals=values[1], departures=values[2], vessels=values[3],
                high_risk_arrivals=values[4], status=values[5], updated_at=GENERATED_AT,
            )
            for port_id, values in specs.items()
        }

    @staticmethod
    def _seed_vessel_identities() -> dict[str, GlobalVesselIdentity]:
        vessels = [
            GlobalVesselIdentity(
                caspian_vessel_id="CI-VESSEL-000184", legacy_vessel_id="caspian-star", canonical_name="CASPIAN STAR",
                imo="9384721", mmsi="436000118", call_sign="UNCS", flag="Kazakhstan", vessel_type="Cargo vessel",
                length_m=142, width_m=21, owner_company_id="CI-COMPANY-00421", operator_company_id="CI-COMPANY-00421",
                source_aliases=[
                    VesselSourceAlias(source_id="source-kz-ais", source_vessel_id="vessel_184", name="CASPIAN STAR II", mmsi="436000118", imo="9384721", first_seen_at="2024-01-01T00:00:00Z", last_seen_at=GENERATED_AT, match_status="CONFIRMED"),
                    VesselSourceAlias(source_id="source-baku-port", source_vessel_id="ship_782", name="CASPIAN STAR", mmsi="436123456", imo="9384721", first_seen_at="2024-03-12T00:00:00Z", last_seen_at="2026-08-10T04:02:00Z", match_status="CONFIRMED"),
                    VesselSourceAlias(source_id="source-aktau-port", source_vessel_id="AKT-VC-00918", name="CASPIAN STAR", mmsi="436000118", imo="9384721", first_seen_at="2025-01-04T00:00:00Z", last_seen_at=GENERATED_AT, match_status="CONFIRMED"),
                ],
                identity_history=[
                    VesselIdentityHistoryItem(valid_from="2024-01-01T00:00:00Z", valid_to="2024-12-31T23:59:59Z", name="CASPIAN STAR", mmsi="436123456", flag="Kazakhstan", call_sign="UNCS", owner_company_id="CI-COMPANY-00421", operator_company_id="CI-COMPANY-00421", change_reason="Initial regional identity", source_ids=["source-baku-port"]),
                    VesselIdentityHistoryItem(valid_from="2025-01-01T00:00:00Z", valid_to="2025-12-31T23:59:59Z", name="CASPIAN STAR II", mmsi="436000118", flag="Kazakhstan", call_sign="UNCS", owner_company_id="CI-COMPANY-00421", operator_company_id="CI-COMPANY-00421", change_reason="Name and MMSI updated; IMO and dimensions confirmed continuity", source_ids=["source-kz-ais", "source-aktau-port"]),
                    VesselIdentityHistoryItem(valid_from="2026-01-01T00:00:00Z", name="CASPIAN STAR", mmsi="436000118", flag="Kazakhstan", call_sign="UNCS", owner_company_id="CI-COMPANY-00421", operator_company_id="CI-COMPANY-00421", change_reason="Operator record reverified and current operational name confirmed", source_ids=["source-kz-ais", "source-aktau-port", "source-baku-port"]),
                ], resolution_confidence=.99, resolution_status="CONFIRMED", updated_at=GENERATED_AT,
            ),
            GlobalVesselIdentity(
                caspian_vessel_id="CI-VESSEL-000241", legacy_vessel_id="turan", canonical_name="TURAN", imo="9418821", mmsi="434001241", call_sign="EZTR", flag="Turkmenistan", vessel_type="General cargo", length_m=131, width_m=19, owner_company_id="CI-COMPANY-00488", operator_company_id="CI-COMPANY-00488",
                source_aliases=[VesselSourceAlias(source_id="source-tm-ais", source_vessel_id="TM-SHIP-241", name="TURAN", mmsi="434001241", imo="9418821", first_seen_at="2024-02-01T00:00:00Z", last_seen_at=GENERATED_AT, match_status="CONFIRMED")],
                identity_history=[VesselIdentityHistoryItem(valid_from="2024-02-01T00:00:00Z", name="TURAN", mmsi="434001241", flag="Turkmenistan", call_sign="EZTR", owner_company_id="CI-COMPANY-00488", operator_company_id="CI-COMPANY-00488", change_reason="Initial regional identity", source_ids=["source-tm-ais"])], resolution_confidence=.98, resolution_status="CONFIRMED", updated_at=GENERATED_AT,
            ),
            GlobalVesselIdentity(
                caspian_vessel_id="CI-VESSEL-000317", legacy_vessel_id="volga-marine", canonical_name="VOLGA MARINE", imo="9142202", mmsi="273451810", call_sign="UBVM", flag="Russia", vessel_type="General cargo", length_m=128, width_m=18, owner_company_id="CI-COMPANY-00502", operator_company_id="CI-COMPANY-00502",
                source_aliases=[VesselSourceAlias(source_id="source-kz-ais", source_vessel_id="RU-317", name="VOLGA MARINE", mmsi="273451810", imo="9142202", first_seen_at="2024-01-01T00:00:00Z", last_seen_at=GENERATED_AT, match_status="CONFIRMED")],
                identity_history=[VesselIdentityHistoryItem(valid_from="2024-01-01T00:00:00Z", name="VOLGA MARINE", mmsi="273451810", flag="Russia", call_sign="UBVM", owner_company_id="CI-COMPANY-00502", operator_company_id="CI-COMPANY-00502", change_reason="Initial regional identity", source_ids=["source-kz-ais"])], resolution_confidence=.98, resolution_status="CONFIRMED", updated_at=GENERATED_AT,
            ),
            GlobalVesselIdentity(
                caspian_vessel_id="CI-VESSEL-000322", legacy_vessel_id="khazar-wave", canonical_name="KHAZAR WAVE", imo="9261840", mmsi="423000712", call_sign="4JHW", flag="Azerbaijan", vessel_type="Oil tanker", length_m=155, width_m=24, owner_company_id="CI-COMPANY-00511", operator_company_id="CI-COMPANY-00511",
                source_aliases=[VesselSourceAlias(source_id="source-az-ais", source_vessel_id="AZ-322", name="KHAZAR WAVE", mmsi="423000712", imo="9261840", first_seen_at="2024-01-01T00:00:00Z", last_seen_at=GENERATED_AT, match_status="CONFIRMED")],
                identity_history=[VesselIdentityHistoryItem(valid_from="2024-01-01T00:00:00Z", name="KHAZAR WAVE", mmsi="423000712", flag="Azerbaijan", call_sign="4JHW", owner_company_id="CI-COMPANY-00511", operator_company_id="CI-COMPANY-00511", change_reason="Initial regional identity", source_ids=["source-az-ais"])], resolution_confidence=.98, resolution_status="CONFIRMED", updated_at=GENERATED_AT,
            ),
        ]
        return {item.caspian_vessel_id: item for item in vessels}

    @staticmethod
    def _seed_company_identities() -> dict[str, GlobalCompanyIdentity]:
        items = [
            GlobalCompanyIdentity(caspian_company_id="CI-COMPANY-00421", canonical_name="Caspian Shipping Ltd.", country="Kazakhstan", company_type="OWNER_OPERATOR", aliases=["CASPIAN SHIPPING LTD", "Caspian Shipping Limited", "Caspian Shipping Ltd."], registration_numbers=["KZ-BIN-040421"], vessel_ids=["CI-VESSEL-000184"], related_company_ids=[], resolution_confidence=.99, updated_at=GENERATED_AT),
            GlobalCompanyIdentity(caspian_company_id="CI-COMPANY-00488", canonical_name="Turkmen Maritime Lines", country="Turkmenistan", company_type="OWNER_OPERATOR", aliases=["TML", "Turkmen Maritime Lines Ltd."], registration_numbers=["TM-REG-488"], vessel_ids=["CI-VESSEL-000241"], related_company_ids=[], resolution_confidence=.98, updated_at=GENERATED_AT),
            GlobalCompanyIdentity(caspian_company_id="CI-COMPANY-00502", canonical_name="Volga Fleet", country="Russia", company_type="OWNER_OPERATOR", aliases=["Volga Fleet LLC"], registration_numbers=["RU-REG-502"], vessel_ids=["CI-VESSEL-000317"], related_company_ids=[], resolution_confidence=.98, updated_at=GENERATED_AT),
            GlobalCompanyIdentity(caspian_company_id="CI-COMPANY-00511", canonical_name="ASCO", country="Azerbaijan", company_type="OPERATOR", aliases=["Azerbaijan Caspian Shipping Company", "ASCO LLC"], registration_numbers=["AZ-REG-511"], vessel_ids=["CI-VESSEL-000322"], related_company_ids=[], resolution_confidence=.99, updated_at=GENERATED_AT),
        ]
        return {item.caspian_company_id: item for item in items}

    @staticmethod
    def _seed_voyages() -> list[dict[str, Any]]:
        return [
            {"id": "NET-VOY-001", "global_vessel_id": "CI-VESSEL-000184", "legacy_vessel_id": "caspian-star", "vessel_name": "CASPIAN STAR", "origin_port_id": "baku", "destination_port_id": "aktau", "route_id": "route-baku-aktau", "departed_at": "2026-08-10T04:00:00Z", "predicted_arrival_at": "2026-08-11T10:05:00Z", "arrived_at": "2026-08-11T10:18:00Z", "status": "COMPLETED", "source_ids": ["source-baku-port", "source-kz-ais", "source-aktau-port"]},
            {"id": "NET-VOY-002", "global_vessel_id": "CI-VESSEL-000184", "legacy_vessel_id": "caspian-star", "vessel_name": "CASPIAN STAR", "origin_port_id": "aktau", "destination_port_id": "turkmenbashi", "route_id": "route-aktau-turkmenbashi", "departed_at": "2026-08-12T05:30:00Z", "predicted_arrival_at": "2026-08-13T03:10:00Z", "arrived_at": None, "status": "PLANNED", "source_ids": ["source-aktau-port", "source-turkmenbashi-port"]},
            {"id": "NET-VOY-003", "global_vessel_id": "CI-VESSEL-000241", "legacy_vessel_id": "turan", "vessel_name": "TURAN", "origin_port_id": "turkmenbashi", "destination_port_id": "baku", "route_id": "route-turkmenbashi-baku", "departed_at": "2026-08-09T02:15:00Z", "predicted_arrival_at": "2026-08-10T13:40:00Z", "arrived_at": None, "status": "IN_PROGRESS", "source_ids": ["source-tm-ais", "source-baku-port"]},
            {"id": "NET-VOY-004", "global_vessel_id": "CI-VESSEL-000317", "legacy_vessel_id": "volga-marine", "vessel_name": "VOLGA MARINE", "origin_port_id": "astrakhan", "destination_port_id": "aktau", "route_id": "route-astrakhan-aktau", "departed_at": "2026-08-08T04:00:00Z", "predicted_arrival_at": "2026-08-11T07:30:00Z", "arrived_at": None, "status": "IN_PROGRESS", "source_ids": ["source-kz-ais", "source-aktau-port"]},
        ]

    @staticmethod
    def _seed_risk() -> list[RegionalRiskItem]:
        return [
            RegionalRiskItem(global_vessel_id="CI-VESSEL-000184", legacy_vessel_id="caspian-star", vessel_name="CASPIAN STAR", score=91, level="CRITICAL", origin_port_id="baku", destination_port_id="aktau", route_id="route-baku-aktau", vessel_type="Cargo vessel", event_types=["ROUTE_DEVIATION", "AIS_GAP", "ENCOUNTER", "DRAUGHT_CHANGE", "FUEL_ANOMALY", "ENVIRONMENTAL_CONTEXT"], source_assessment_id="RA-caspian-star", updated_at="2026-08-10T13:05:00Z"),
            RegionalRiskItem(global_vessel_id="CI-VESSEL-000241", legacy_vessel_id="turan", vessel_name="TURAN", score=84, level="CRITICAL", origin_port_id="turkmenbashi", destination_port_id="baku", route_id="route-turkmenbashi-baku", vessel_type="General cargo", event_types=["ENCOUNTER", "AIS_GAP"], source_assessment_id="RA-turan-regional", updated_at="2026-08-10T12:45:00Z"),
            RegionalRiskItem(global_vessel_id="CI-VESSEL-000317", legacy_vessel_id="volga-marine", vessel_name="VOLGA MARINE", score=78, level="HIGH", origin_port_id="astrakhan", destination_port_id="aktau", route_id="route-astrakhan-aktau", vessel_type="General cargo", event_types=["ROUTE_DEVIATION", "CARGO_MISMATCH"], source_assessment_id="RA-volga-regional", updated_at="2026-08-10T12:20:00Z"),
            RegionalRiskItem(global_vessel_id="CI-VESSEL-000322", legacy_vessel_id="khazar-wave", vessel_name="KHAZAR WAVE", score=28, level="MODERATE", origin_port_id="aktau", destination_port_id="baku", route_id="route-baku-aktau", vessel_type="Oil tanker", event_types=["SPEED_ANOMALY"], source_assessment_id="RA-khazar-regional", updated_at="2026-08-10T11:20:00Z"),
        ]

    @staticmethod
    def _seed_routes() -> dict[str, RouteIntelligence]:
        specs = [
            ("route-baku-aktau", "baku", "aktau", "Baku ↔ Aktau", 284, 1754, 42, 17, 21, 8, 4380, 37, 8.4),
            ("route-aktau-turkmenbashi", "aktau", "turkmenbashi", "Aktau ↔ Turkmenbashi", 148, 1320, 31, 8, 11, 3, 3920, 18, 4.2),
            ("route-turkmenbashi-baku", "turkmenbashi", "baku", "Turkmenbashi ↔ Baku", 176, 1980, 38, 12, 15, 5, 4100, 22, 6.1),
            ("route-astrakhan-aktau", "astrakhan", "aktau", "Astrakhan ↔ Aktau", 92, 3560, 55, 9, 7, 4, 3700, 14, -2.3),
        ]
        return {
            values[0]: RouteIntelligence(
                id=values[0], origin_port_id=values[1], destination_port_id=values[2], display_name=values[3],
                period_days=30, voyages=values[4], average_duration_minutes=values[5], average_delay_minutes=values[6],
                ais_gaps=values[7], encounters=values[8], high_risk_voyages=values[9], average_cargo_t=values[10],
                active_vessels=values[11], trend_percent=values[12], source_ids=["source-regional-platform"], generated_at=GENERATED_AT,
            ) for values in specs
        }

    @staticmethod
    def _seed_sources() -> dict[str, DataSourceRecord]:
        items = [
            DataSourceRecord(id="source-kz-ais", name="Kazakhstan AIS", source_type="AIS", organization_id="org-regional-ci", status="ONLINE", quality_score=.96, coverage="Kazakhstan and central Caspian", latency_seconds=8, last_update_at="2026-08-10T10:04:52Z", authoritative_for=["positions", "identity observations"], adapter_id="adapter-ais-kz"),
            DataSourceRecord(id="source-az-ais", name="Azerbaijan AIS", source_type="AIS", organization_id="org-baku-port", status="ONLINE", quality_score=.94, coverage="Azerbaijan coastal waters", latency_seconds=12, last_update_at="2026-08-10T10:04:48Z", authoritative_for=["positions"], adapter_id="adapter-ais-az"),
            DataSourceRecord(id="source-tm-ais", name="Turkmenistan AIS", source_type="AIS", organization_id="org-turkmenbashi-port", status="ONLINE", quality_score=.91, coverage="Turkmenistan coastal waters", latency_seconds=18, last_update_at="2026-08-10T10:04:42Z", authoritative_for=["positions"], adapter_id="adapter-ais-tm"),
            DataSourceRecord(id="source-aktau-port", name="Aktau Port", source_type="PORT", organization_id="org-aktau-port", status="ONLINE", quality_score=.98, coverage="Aktau port operations", latency_seconds=5, last_update_at="2026-08-10T10:04:55Z", authoritative_for=["arrivals", "berths", "verified cargo", "verified draught", "documents"], adapter_id="adapter-aktau"),
            DataSourceRecord(id="source-baku-port", name="Baku Port", source_type="PORT", organization_id="org-baku-port", status="DEGRADED", quality_score=.84, coverage="Baku port operations", latency_seconds=720, last_update_at="2026-08-10T09:52:00Z", authoritative_for=["departures", "cargo declarations", "documents"], adapter_id="adapter-baku"),
            DataSourceRecord(id="source-turkmenbashi-port", name="Turkmenbashi Port", source_type="PORT", organization_id="org-turkmenbashi-port", status="ONLINE", quality_score=.91, coverage="Turkmenbashi port operations", latency_seconds=30, last_update_at="2026-08-10T10:04:30Z", authoritative_for=["arrivals", "departures", "cargo"], adapter_id="adapter-turkmenbashi"),
            DataSourceRecord(id="source-weather", name="Regional Weather Provider", source_type="WEATHER", organization_id="org-regional-ci", status="ONLINE", quality_score=.93, coverage="Caspian Sea", latency_seconds=90, last_update_at="2026-08-10T10:03:30Z", authoritative_for=["weather", "wind", "currents"], adapter_id="adapter-weather"),
            DataSourceRecord(id="source-satellite", name="Satellite Provider A", source_type="ENVIRONMENTAL", organization_id="org-regional-ci", status="ONLINE", quality_score=.87, coverage="Caspian Sea scenes", latency_seconds=1800, last_update_at="2026-08-10T09:35:00Z", authoritative_for=["environmental observations"], adapter_id="adapter-satellite"),
            DataSourceRecord(id="source-operator", name="Vessel Operator Declarations", source_type="OPERATOR", organization_id="org-regional-ci", status="ONLINE", quality_score=.76, coverage="Participating operators", latency_seconds=240, last_update_at="2026-08-10T10:01:00Z", authoritative_for=["reported cargo", "voyage declarations"], adapter_id="adapter-operator"),
            DataSourceRecord(id="source-regional-platform", name="Caspian Intelligence", source_type="PLATFORM", organization_id="org-regional-ci", status="ONLINE", quality_score=.95, coverage="Regional analytical outputs", latency_seconds=2, last_update_at="2026-08-10T10:04:58Z", authoritative_for=["resolved identities", "route aggregates", "risk estimates"], adapter_id="internal"),
        ]
        return {item.id: item for item in items}

    @staticmethod
    def _seed_provenance() -> list[ProvenanceRecord]:
        return [
            ProvenanceRecord(id="PROV-CARGO-BAKU-001", entity_type="VOYAGE", entity_id="NET-VOY-001", field_name="departure_cargo", value=5000, unit="t", source_id="source-baku-port", received_at="2026-08-10T04:02:00Z", status="REPORTED", quality_score=.90),
            ProvenanceRecord(id="PROV-DRAUGHT-BAKU-001", entity_type="VOYAGE", entity_id="NET-VOY-001", field_name="departure_draught", value=5.2, unit="m", source_id="source-baku-port", received_at="2026-08-10T04:02:00Z", status="REPORTED", quality_score=.90),
            ProvenanceRecord(id="PROV-CARGO-AKTAU-001", entity_type="VOYAGE", entity_id="NET-VOY-001", field_name="arrival_cargo", value=4920, unit="t", source_id="source-aktau-port", received_at="2026-08-11T10:18:00Z", status="VERIFIED", quality_score=.98),
            ProvenanceRecord(id="PROV-DRAUGHT-AKTAU-001", entity_type="VOYAGE", entity_id="NET-VOY-001", field_name="arrival_draught", value=5.1, unit="m", source_id="source-aktau-port", received_at="2026-08-11T10:18:00Z", status="VERIFIED", quality_score=.98),
            ProvenanceRecord(id="PROV-CARGO-BAKU-002", entity_type="VOYAGE", entity_id="NET-VOY-CONFLICT-04", field_name="departure_cargo", value=5000, unit="t", source_id="source-baku-port", received_at="2026-08-08T07:00:00Z", status="REPORTED", quality_score=.90),
            ProvenanceRecord(id="PROV-CARGO-OPERATOR-002", entity_type="VOYAGE", entity_id="NET-VOY-CONFLICT-04", field_name="departure_cargo", value=4800, unit="t", source_id="source-operator", received_at="2026-08-08T07:05:00Z", status="REPORTED", quality_score=.76),
        ]

    @staticmethod
    def _seed_conflicts() -> list[DataConflict]:
        return [DataConflict(
            id="CONFLICT-CARGO-004", entity_type="VOYAGE", entity_id="NET-VOY-CONFLICT-04", field_name="departure_cargo",
            values=[
                DataConflictValue(provenance_id="PROV-CARGO-BAKU-002", source_id="source-baku-port", value=5000, unit="t", status="REPORTED"),
                DataConflictValue(provenance_id="PROV-CARGO-OPERATOR-002", source_id="source-operator", value=4800, unit="t", status="REPORTED"),
            ], severity="MEDIUM", status="OPEN", explanation="The source values differ by 200 t; no verified measurement is available, so neither value was silently overwritten.", created_at="2026-08-08T07:05:00Z",
        )]

    def _seed_port_operations(self) -> tuple[dict[str, list[PortMovement]], dict[str, list[PortMovement]], dict[str, list[PortBerth]]]:
        arrivals: dict[str, list[PortMovement]] = {}
        departures: dict[str, list[PortMovement]] = {}
        berths: dict[str, list[PortBerth]] = {}
        representative = [
            ("CI-VESSEL-000184", "CASPIAN STAR", "NET-VOY-001", 91),
            ("CI-VESSEL-000241", "TURAN", "NET-VOY-003", 84),
            ("CI-VESSEL-000317", "VOLGA MARINE", "NET-VOY-004", 78),
        ]
        for position, port in enumerate(self.ports.values()):
            port_arrivals = []
            port_departures = []
            for index in range(3):
                vessel_id, name, voyage_id, risk = representative[(position + index) % len(representative)]
                if port.id == "aktau" and index == 0:
                    vessel_id, name, voyage_id, risk = representative[0]
                if port.id == "baku" and index == 0:
                    vessel_id, name, voyage_id, risk = representative[1]
                port_arrivals.append(PortMovement(
                    id=f"ARR-{port.id.upper()}-{index + 1:03d}", port_id=port.id,
                    global_vessel_id=vessel_id, vessel_name=name, voyage_id=voyage_id,
                    movement_type="ARRIVAL", predicted_at=f"2026-08-{10 + (index // 2):02d}T{12 + index * 2:02d}:05:00Z",
                    reported_at=f"2026-08-{10 + (index // 2):02d}T{11 + index * 2:02d}:55:00Z",
                    berth_id=f"{port.id}-berth-{index + 1}", cargo_type="Steel" if index == 0 else "General cargo",
                    cargo_t=4920 if port.id == "aktau" and index == 0 else 3200 + index * 450,
                    draught_m=5.1 if port.id == "aktau" and index == 0 else 4.4 + index * .3,
                    risk_score=risk, status="APPROACHING", source_ids=port.data_source_ids[:1],
                ))
                port_departures.append(PortMovement(
                    id=f"DEP-{port.id.upper()}-{index + 1:03d}", port_id=port.id,
                    global_vessel_id=vessel_id, vessel_name=name, voyage_id=voyage_id,
                    movement_type="DEPARTURE", predicted_at=f"2026-08-10T{13 + index * 2:02d}:20:00Z",
                    reported_at=f"2026-08-10T{13 + index * 2:02d}:00:00Z",
                    berth_id=f"{port.id}-berth-{index + 1}", cargo_type="Steel" if index == 0 else "General cargo",
                    cargo_t=5000 if port.id == "baku" and vessel_id == "CI-VESSEL-000184" else 3300 + index * 400,
                    draught_m=5.2 if port.id == "baku" and vessel_id == "CI-VESSEL-000184" else 4.5 + index * .3,
                    risk_score=risk, status="SCHEDULED", source_ids=port.data_source_ids[:1],
                ))
            if port.id == "baku":
                port_departures[0] = PortMovement(
                    id="DEP-BAKU-001", port_id="baku", global_vessel_id="CI-VESSEL-000184", vessel_name="CASPIAN STAR", voyage_id="NET-VOY-001", movement_type="DEPARTURE",
                    predicted_at="2026-08-10T04:00:00Z", reported_at="2026-08-10T04:00:00Z", berth_id="baku-berth-1", cargo_type="Steel", cargo_t=5000, draught_m=5.2, risk_score=35, status="DEPARTED", source_ids=["source-baku-port"],
                )
            arrivals[port.id] = port_arrivals
            departures[port.id] = port_departures
            berths[port.id] = [
                PortBerth(
                    id=f"{port.id}-berth-{index}", port_id=port.id, name=f"Berth #{index}",
                    status="OCCUPIED" if index == 1 else "AVAILABLE", max_length_m=180 + index * 10,
                    max_draught_m=min(port.configuration.maximum_draught_m, 5.5 + index * .5),
                    cargo_types=port.configuration.cargo_capabilities,
                    current_vessel_id=port_arrivals[0].global_vessel_id if index == 1 else None,
                    available_at="2026-08-10T14:35:00Z" if index == 1 else GENERATED_AT,
                )
                for index in range(1, min(port.configuration.berth_count, 4) + 1)
            ]
        return arrivals, departures, berths


network_service = CaspianNetworkService()
