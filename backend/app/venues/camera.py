"""Camera twin routes: calibrate the printed sheet, read hazard cards, confirm them.

A read is a proposal: candidates stay pending until the operator confirms them, and only confirmed
camera hazards are accepted by the door planner. Card positions are mapped onto the reviewed floor
plan through a homography; the 3D model is authored, not reconstructed. State is kept in memory,
bounded, for the running demo only. Every route touching the store is async, so the store is only
ever used from the event-loop thread.
"""
from __future__ import annotations

import asyncio
import math
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.grounding.calibration import (
    CORNER_ORDER,
    Calibration,
    CalibrationError,
    calibrate,
    map_card,
    normalized_to_px,
)
from backend.app.ai.grounding.hazard_read import HazardCardReader, HazardReadResult
from backend.app.venues.model import VenueV2, get_venue

MAPPING_NOTE = "Card positions mapped onto the reviewed floor plan; the 3D model is authored, not reconstructed."
MAX_READS = 64
MAX_CALIBRATIONS = 16
READ_TTL_SECONDS = 2 * 60 * 60
POSITION_TOLERANCE_M = 1e-6


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CalibrationRequest(_Strict):
    corners_px: Dict[Literal["TL", "TR", "BR", "BL"], Tuple[float, float]]
    image_size: Tuple[int, int]


class FixtureCard(_Strict):
    type: Literal["FIRE", "SMOKE", "GAS", "CHEMICAL", "WATER"]
    point: Tuple[int, int]
    box_2d: Tuple[int, int, int, int]
    label_text: Optional[str] = None


class HazardReadRequest(_Strict):
    capture_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    timestamp_iso: str = Field(min_length=1, max_length=64)
    image_base64: Optional[str] = Field(default=None, max_length=7_000_000)
    image_sha256: Optional[str] = Field(default=None, max_length=64)
    dimensions: Tuple[int, int]
    calibration_id: Optional[str] = Field(default=None, max_length=64)
    auto_corners: bool = False
    mode: Literal["live", "fixture"] = "live"
    fixture_cards: Optional[List[FixtureCard]] = Field(default=None, max_length=8)
    thinking_level: Literal["low", "medium", "high"] = "low"
    deadline_seconds: float = Field(default=25.0, gt=0, le=60, allow_inf_nan=False)


class ConfirmRequest(_Strict):
    candidate_ids: List[str] = Field(min_length=1, max_length=8)


@dataclass
class Candidate:
    candidate_id: str
    type: str
    point: List[int]
    box_2d: List[int]
    label_text: str
    evidence: str
    confidence: str
    low_confidence_reason: Optional[str]
    floor: Optional[Tuple[float, float]]
    zone_id: Optional[str]
    rejected_reason: Optional[str]
    confirmed: bool = False

    @property
    def hazard_id(self) -> str:
        return f"cam-{self.candidate_id}"

    def to_json(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "type": self.type,
            "point": self.point,
            "box_2d": self.box_2d,
            "label_text": self.label_text,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "low_confidence_reason": self.low_confidence_reason,
            "floor": None if self.floor is None else {"x": round(self.floor[0], 3), "y": round(self.floor[1], 3)},
            "zone_id": self.zone_id,
            "usable": self.rejected_reason is None,
            "rejected_reason": self.rejected_reason,
            "confirmed": self.confirmed,
        }


@dataclass
class ReadRecord:
    read_id: str
    venue_id: str
    provenance: str
    created: float
    candidates: Dict[str, Candidate] = field(default_factory=dict)


class CameraStore:
    """Bounded in-memory state for calibrations and reads (one demo laptop, one running server)."""

    def __init__(self) -> None:
        self.calibrations: "OrderedDict[str, Tuple[str, str, Calibration]]" = OrderedDict()
        self.reads: "OrderedDict[str, ReadRecord]" = OrderedDict()

    def clear(self) -> None:
        self.calibrations.clear()
        self.reads.clear()

    def add_calibration(self, venue_id: str, source: str, calibration: Calibration) -> str:
        calibration_id = f"cal-{uuid4().hex[:12]}"
        self.calibrations[calibration_id] = (venue_id, source, calibration)
        while len(self.calibrations) > MAX_CALIBRATIONS:
            self.calibrations.popitem(last=False)
        return calibration_id

    def calibration(self, venue_id: str, calibration_id: str) -> Optional[Tuple[str, Calibration]]:
        entry = self.calibrations.get(calibration_id)
        if entry is None or entry[0] != venue_id:
            return None
        return entry[1], entry[2]

    def add_read(self, record: ReadRecord) -> None:
        self._expire()
        self.reads[record.read_id] = record
        while len(self.reads) > MAX_READS:
            self.reads.popitem(last=False)

    def read(self, venue_id: str, read_id: str) -> Optional[ReadRecord]:
        self._expire()
        record = self.reads.get(read_id)
        return record if record is not None and record.venue_id == venue_id else None

    def _expire(self) -> None:
        cutoff = time.monotonic() - READ_TTL_SECONDS
        for read_id in [rid for rid, rec in self.reads.items() if rec.created < cutoff]:
            del self.reads[read_id]

    def verify_camera_hazard(self, venue_id: str, hazard) -> Optional[str]:
        """None when the camera hazard matches a confirmed candidate; otherwise an error code."""
        if not hazard.proposal_id:
            return "unconfirmed_camera_hazard"
        record = self.read(venue_id, hazard.proposal_id)
        if record is None:
            return "unconfirmed_camera_hazard"
        candidate = next((c for c in record.candidates.values() if c.hazard_id == hazard.id), None)
        if candidate is None or not candidate.confirmed or candidate.floor is None:
            return "unconfirmed_camera_hazard"
        if (candidate.type != hazard.type
                or abs(candidate.floor[0] - hazard.position.x) > POSITION_TOLERANCE_M + 5e-4
                or abs(candidate.floor[1] - hazard.position.y) > POSITION_TOLERANCE_M + 5e-4
                or hazard.untenable_s is not None):
            return "camera_hazard_mismatch"
        return None

    def camera_provenance(self, venue_id: str, read_id: Optional[str]) -> Optional[str]:
        record = self.read(venue_id, read_id) if read_id else None
        return record.provenance if record is not None and record.provenance in ("live", "fixture") else None


CAMERA_STORE = CameraStore()


def _venue_or_404(venue_id: str) -> VenueV2:
    venue = get_venue(venue_id)
    if venue is None:
        raise HTTPException(404, detail={"code": "unknown_venue"})
    return venue


def _candidates(venue: VenueV2, result: HazardReadResult, calibration: Optional[Calibration]) -> Dict[str, Candidate]:
    out: Dict[str, Candidate] = {}
    for index, card in enumerate(result.cards, start=1):
        candidate_id = f"{uuid4().hex[:8]}-{index}"
        floor = zone = rejected = None
        if calibration is None:
            rejected = "no_calibration"
        else:
            try:
                placement = map_card(calibration, card.point, card.box_2d, venue.extent)
            except CalibrationError:
                placement = None
            if placement is None or not all(math.isfinite(v) for v in placement.floor_xy):
                rejected = "outside_building"
            else:
                floor = placement.floor_xy
                zone = venue.locate_zone(*floor)
                if zone is None or not placement.inside_building:
                    rejected, zone = "outside_building", None
                elif placement.crosses_building_edge:
                    rejected = "crosses_building_edge"
        out[candidate_id] = Candidate(
            candidate_id=candidate_id, type=card.type, point=list(card.point), box_2d=list(card.box_2d),
            label_text=card.label_text, evidence=card.evidence, confidence=card.confidence,
            low_confidence_reason=card.low_confidence_reason, floor=floor, zone_id=zone, rejected_reason=rejected,
        )
    return out


def build_camera_router(adapter: GroundingAdapter, fixtures_enabled: Callable[[], bool],
                        store: CameraStore = CAMERA_STORE) -> APIRouter:
    router = APIRouter(prefix="/api/venues")
    reader = HazardCardReader(adapter)
    live_slot = asyncio.Semaphore(1)

    @router.post("/{venue_id}/camera/calibration")
    async def post_calibration(venue_id: str, request: CalibrationRequest) -> dict:
        _venue_or_404(venue_id)
        try:
            calibration = calibrate(dict(request.corners_px), request.image_size)
        except CalibrationError as error:
            raise HTTPException(422, detail={"code": error.code}) from None
        calibration_id = store.add_calibration(venue_id, "clicked", calibration)
        return {"calibration_id": calibration_id, "source": "clicked",
                "reprojection_error_m": calibration.reprojection_error_m,
                "corners_px": {k: list(v) for k, v in calibration.corners_px.items()},
                "image_size": list(calibration.image_size)}

    @router.post("/{venue_id}/camera/hazard-read")
    async def post_hazard_read(venue_id: str, request: HazardReadRequest) -> dict:
        venue = _venue_or_404(venue_id)
        if request.mode == "fixture":
            if not fixtures_enabled():
                raise HTTPException(403, detail={"code": "fixtures_disabled"})
            if request.image_base64 or not request.fixture_cards:
                raise HTTPException(422, detail={"code": "fixture_cards_without_image_required"})
        elif request.fixture_cards:
            raise HTTPException(422, detail={"code": "live_request_with_fixture_cards"})
        calibration: Optional[Calibration] = None
        calibration_info: Optional[dict] = None
        if request.calibration_id:
            found = store.calibration(venue_id, request.calibration_id)
            if found is None:
                raise HTTPException(422, detail={"code": "unknown_calibration"})
            source, calibration = found
            if tuple(calibration.image_size) != tuple(request.dimensions):
                raise HTTPException(422, detail={"code": "calibration_image_size_mismatch"})
            calibration_info = {"calibration_id": request.calibration_id, "source": source,
                                "reprojection_error_m": calibration.reprojection_error_m}
        wants_corners = request.auto_corners and calibration is None and request.mode == "live"
        if request.mode == "live" and live_slot.locked():
            raise HTTPException(429, detail={"code": "camera_read_busy"})
        async with live_slot:
            result = await reader.read(
                capture_id=request.capture_id, timestamp_iso=request.timestamp_iso,
                image_base64=request.image_base64, dimensions=request.dimensions,
                image_sha256=request.image_sha256, mode=request.mode,
                fixture_cards=[card.model_dump() for card in request.fixture_cards or []],
                include_corners=wants_corners, thinking_level=request.thinking_level,
                deadline_seconds=request.deadline_seconds,
            )
        errors = list(result.errors)
        if wants_corners and result.status == "completed":
            corners = {c.id: normalized_to_px(c.point, request.dimensions) for c in result.corners}
            if set(corners) == set(CORNER_ORDER):
                try:
                    calibration = calibrate(corners, request.dimensions)
                    calibration_id = store.add_calibration(venue_id, "gemini_corners", calibration)
                    calibration_info = {"calibration_id": calibration_id, "source": "gemini_corners",
                                        "reprojection_error_m": calibration.reprojection_error_m}
                except CalibrationError as error:
                    errors.append(f"calibration:{error.code}")
            else:
                errors.append("calibration:missing_corner")
        candidates = _candidates(venue, result, calibration) if result.status == "completed" else {}
        read_id = f"read-{uuid4().hex}"
        if result.status == "completed":
            store.add_read(ReadRecord(read_id=read_id, venue_id=venue_id, provenance=result.provenance,
                                      created=time.monotonic(), candidates=candidates))
        return {
            "read_id": read_id if result.status == "completed" else None,
            "status": result.status,
            "provenance": result.provenance,
            "errors": errors,
            "calibration": calibration_info,
            "candidates": [c.to_json() for c in candidates.values()],
            "provider_interaction_id": result.provider_interaction_id,
            "provider_model": result.provider_model,
            "token_usage": result.token_usage,
            "latency_ms": round(result.latency_ms, 1),
            "mapping_note": MAPPING_NOTE,
        }

    @router.post("/{venue_id}/camera/reads/{read_id}/confirm")
    async def post_confirm(venue_id: str, read_id: str, request: ConfirmRequest) -> dict:
        _venue_or_404(venue_id)
        record = store.read(venue_id, read_id)
        if record is None:
            raise HTTPException(404, detail={"code": "unknown_read"})
        chosen: List[Candidate] = []
        for candidate_id in request.candidate_ids:
            candidate = record.candidates.get(candidate_id)
            if candidate is None:
                raise HTTPException(422, detail={"code": "unknown_candidate"})
            if candidate.rejected_reason is not None:
                raise HTTPException(422, detail={"code": f"candidate_not_usable:{candidate.rejected_reason}"})
            chosen.append(candidate)
        hazards = []
        for candidate in chosen:
            candidate.confirmed = True
            hazards.append({
                "id": candidate.hazard_id, "type": candidate.type,
                "position": {"x": candidate.floor[0], "y": candidate.floor[1]},
                "zone_id": candidate.zone_id, "source": "camera", "untenable_s": None, "proposal_id": read_id,
            })
        return {"read_id": read_id, "provenance": record.provenance, "hazards": hazards}

    return router
