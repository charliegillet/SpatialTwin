"""GET /api/venues/{venue_id} and POST /api/venues/{venue_id}/door-plan (local, no provider calls)."""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.app.hazard.door_planner import DoorPlanError, plan_doors
from backend.app.venues.camera import CAMERA_STORE
from backend.app.venues.model import get_venue
from backend.app.venues.schemas import DoorPlanRequest, DoorPlanResponse

router = APIRouter(prefix="/api/venues")


def _venue_or_404(venue_id: str):
    venue = get_venue(venue_id)
    if venue is None:
        raise HTTPException(404, detail={"code": "unknown_venue"})
    return venue


@router.get("/{venue_id}")
def get_venue_route(venue_id: str) -> Dict[str, Any]:
    return _venue_or_404(venue_id).to_json()


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
