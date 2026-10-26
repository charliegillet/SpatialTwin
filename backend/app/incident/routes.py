"""/api/incident: local-only, provider-free incident state, approvals, virtual-device faults and an SSE stream.

GET  /api/incident                 -> IncidentState
POST /api/incident/hazards         -> {venue_id, expected_plan_revision, hazards}; 409 stale_plan, 422 planner codes
POST /api/incident/approve         -> {plan_revision, candidate_hash, door_states}; 409 stale_plan, 422 plan_not_valid
POST /api/incident/faults          -> {gate_id, fault}
POST /api/incident/faults/clear    -> {gate_id?}
POST /api/incident/reset
POST /api/incident/failsafe        -> {armed, window_seconds?}; the unattended fail-safe (off by default)
GET  /api/incident/events          -> SSE (id:, Last-Event-ID replay, ": ping" every 10 s)

Mount (backend/app/main.py, lead): `app.include_router(build_incident_router())`
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.app.incident.manager import IncidentError, IncidentManager
from backend.app.incident.models import (
    ApprovalRecord, ApproveRequest, ClearFaultRequest, FailSafeRequest, FailSafeView, FaultRequest, HazardsRequest,
    IncidentState,
)

_default_manager: Optional[IncidentManager] = None


def default_manager() -> IncidentManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = IncidentManager()
    return _default_manager


def set_default_manager(manager: Optional[IncidentManager]) -> None:
    """Test hook, like set_venue_registry."""
    global _default_manager
    _default_manager = manager


def _http(error: IncidentError) -> HTTPException:
    return HTTPException(error.status, detail={"code": error.code})


def build_incident_router(manager: Optional[IncidentManager] = None) -> APIRouter:
    """The manager is resolved per request when not given, so a test can swap it with set_default_manager."""
    router = APIRouter(prefix="/api/incident")

    def mgr() -> IncidentManager:
        return manager or default_manager()

    @router.get("", response_model=IncidentState)
    async def get_state() -> IncidentState:
        try:
            return mgr().state()
        except IncidentError as error:
            raise _http(error) from None

    @router.get("/door-plan")
    async def get_door_plan() -> Dict[str, Any]:
        """The full checked plan behind the current incident plan: after a jam, the fallback the doors now follow."""
        try:
            return mgr().door_plan_view()
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/hazards", response_model=IncidentState)
    async def post_hazards(request: HazardsRequest) -> IncidentState:
        try:
            return await mgr().set_hazards(request.venue_id, request.expected_plan_revision, request.hazards)
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/approve", response_model=ApprovalRecord)
    async def post_approve(request: ApproveRequest) -> ApprovalRecord:
        try:
            return await mgr().approve(request)
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/faults")
    async def post_fault(request: FaultRequest) -> Dict[str, Any]:
        try:
            return {"controller": mgr().inject_fault(request.gate_id, request.fault)}
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/faults/clear")
    async def post_clear(request: ClearFaultRequest) -> Dict[str, Any]:
        try:
            return {"controller": mgr().clear_faults(request.gate_id)}
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/reset", response_model=IncidentState)
    async def post_reset() -> IncidentState:
        try:
            return await mgr().reset()
        except IncidentError as error:
            raise _http(error) from None

    @router.post("/failsafe", response_model=FailSafeView)
    async def post_failsafe(request: FailSafeRequest) -> FailSafeView:
        """Arm or disarm. Local only, like every /api/incident route: a phone's scoped token never reaches it."""
        try:
            return await mgr().set_failsafe(request.armed, request.window_seconds)
        except IncidentError as error:
            raise _http(error) from None

    @router.get("/events")
    async def events(request: Request, last_event_id: Optional[int] = Query(default=None, ge=0)):
        header = request.headers.get("last-event-id")
        resume = last_event_id
        if resume is None and header and header.strip().isdigit():
            resume = int(header)
        m = mgr()
        m.state()  # bind the venue before the first snapshot
        return StreamingResponse(
            m.hub.stream(resume, m.snapshot), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})

    return router
