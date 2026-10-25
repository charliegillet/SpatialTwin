"""Venue routes (local, no provider calls).

GET  /api/venues                      -> built-in and accepted venues, plus the active pointer
GET  /api/venues/active               -> {venue_id, revision}
PUT  /api/venues/active               -> body {venue_id, expected_revision}; 409 when stale
GET  /api/venues/{venue_id}           -> the venue
GET  /api/venues/{venue_id}/checks    -> graph checks for the venue
POST /api/venues/{venue_id}/door-plan -> checked door plan
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.hazard.door_planner import DoorPlanError, plan_doors
from backend.app.venues.camera import CAMERA_STORE
from backend.app.venues.graph_checks import check_venue, summary
from backend.app.venues.model import VENUE_ID_PATTERN, get_venue
from backend.app.venues.registry import RegistryConflict, venue_registry
from backend.app.venues.schemas import DoorPlanRequest, DoorPlanResponse

router = APIRouter(prefix="/api/venues")


class ActiveVenueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    venue_id: str = Field(pattern=VENUE_ID_PATTERN)
    expected_revision: Optional[int] = Field(default=None, ge=0)


def _venue_or_404(venue_id: str):
    venue = get_venue(venue_id)
    if venue is None:
        raise HTTPException(404, detail={"code": "unknown_venue"})
    return venue


# Registered before /{venue_id}: "active" is also a valid venue id shape.
@router.get("")
def list_venues() -> Dict[str, Any]:
    registry = venue_registry()
    return {"venues": registry.list_venues(), "active": registry.active()}


@router.get("/active")
def active_venue() -> Dict[str, Any]:
    return venue_registry().active()


@router.put("/active")
def set_active_venue(request: ActiveVenueRequest) -> Dict[str, Any]:
    try:
        return venue_registry().set_active(request.venue_id, request.expected_revision)
    except RegistryConflict as error:
        raise HTTPException(404 if error.code == "unknown_venue" else 409, detail={"code": error.code}) from None


@router.get("/{venue_id}")
def get_venue_route(venue_id: str) -> Dict[str, Any]:
    return _venue_or_404(venue_id).to_json()


@router.get("/{venue_id}/checks")
def venue_checks(venue_id: str) -> Dict[str, Any]:
    venue = _venue_or_404(venue_id)
    issues = check_venue(venue)
    return {"venue_id": venue.venue_id, "geometry_revision": venue.geometry_revision,
            "issues": [issue.to_json() for issue in issues], **summary(issues)}


@router.post("/{venue_id}/door-plan", response_model=DoorPlanResponse)
async def door_plan(venue_id: str, request: DoorPlanRequest) -> DoorPlanResponse:
    venue = _venue_or_404(venue_id)
    # A camera hazard must come from a card the operator confirmed; it cannot be typed in by a client.
    for hazard in request.hazards:
        if hazard.source == "camera":
            code = CAMERA_STORE.verify_camera_hazard(venue_id, hazard)
            if code is not None:
                raise HTTPException(422, detail={"code": code})
    try:
        plan = await asyncio.to_thread(plan_doors, venue, request)
    except DoorPlanError as error:
        raise HTTPException(422, detail={"code": error.code}) from None
    for echo in plan.hazards:
        if echo.source == "camera":
            echo.camera_provenance = CAMERA_STORE.camera_provenance(venue_id, echo.proposal_id)
    return plan
