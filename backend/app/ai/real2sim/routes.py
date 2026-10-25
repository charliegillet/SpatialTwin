"""Real2Sim routes (Contract 3). Exact request/response shapes: docs/plans/contracts/real2sim-api.md.

POST /api/real2sim/drafts                     -> start a draft (live Argon reading or a labelled saved run)
POST /api/real2sim/drafts/video               -> start a live draft from a video walkthrough (raw body, video/*)
PUT  /api/real2sim/drafts/{draft_id}/furniture -> store the operator's furniture edit (looks only) as a new revision
GET  /api/real2sim/drafts/{draft_id}          -> the draft view
GET  /api/real2sim/drafts/{draft_id}/events   -> SSE: status, thought, draft, checks, round, done, error (+ ": ping")
GET  /api/real2sim/drafts/{draft_id}/overlay.png | /topdown.png
POST /api/real2sim/drafts/{draft_id}/accept   -> compile with the operator's choices, check, store, activate
GET  /api/real2sim/saved                      -> saved runs (fixture mode only)

Errors are ``{"detail": {"code": ...}}`` with short snake_case codes. Every registry call runs in a worker thread:
the registry serializes writers on a threading lock and SQLite's busy timeout, which must never stall the loop.
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.real2sim.drafts import Real2SimError, Real2SimService, decode_source
from backend.app.ai.real2sim.fixtures import FixtureError, fixtures_dir, list_saved_runs, load_saved_run
from backend.app.ai.real2sim.video_source import MAX_VIDEO_BYTES, prepare_video
from backend.app.venues.model import VENUE_ID_PATTERN

SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
_FIXTURE_HTTP = {"invalid_fixture_id": 422, "unknown_fixture": 404, "invalid_fixture": 422}


class DraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["live", "fixture"] = "live"
    image_base64: Optional[str] = None
    mime_type: Optional[str] = Field(default=None, max_length=64)
    source_kind: Literal["photo", "sketch", "pdf"] = "photo"
    fixture_id: Optional[str] = Field(default=None, max_length=64)
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    thinking_level: Optional[Literal["low", "medium", "high"]] = None


class AcceptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    controllable_doors: List[str] = Field(default_factory=list, max_length=16)
    headcount: Optional[int] = Field(default=None, ge=0, le=5000)
    building_width_m: Optional[float] = Field(default=None, gt=0, le=500)
    venue_id: Optional[str] = Field(default=None, pattern=VENUE_ID_PATTERN)
    make_active: bool = True


class FurniturePiece(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: Optional[str] = Field(default=None, max_length=8)
    zone: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=40)
    category: str = Field(default="furniture", max_length=24)
    position: List[float] = Field(min_length=2, max_length=2)
    width: float = Field(gt=0, le=10)
    depth: float = Field(gt=0, le=10)
    height: float = Field(gt=0, le=4)
    yaw_deg: float = Field(default=0, ge=-180, le=180)
    color: str = Field(default="", pattern=r"^(#[0-9a-f]{6})?$")


class FurnitureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    furniture: List[FurniturePiece] = Field(default_factory=list, max_length=60)


def _http(error: Real2SimError) -> HTTPException:
    return HTTPException(error.http_status, detail={"code": error.code, **error.extra})


def _last_event_id(header: Optional[str], query: Optional[str]) -> int:
    for value in (header, query):
        if value is not None and value.strip().isdigit():
            return min(int(value.strip()), 10**9)
    return 0


def build_real2sim_router(adapter: GroundingAdapter, fixtures_enabled: Callable[[], bool], *,
                          service: Optional[Real2SimService] = None) -> APIRouter:
    """``service`` is injectable for tests; the default reuses ``adapter``'s client and reads its settings from env."""
    router = APIRouter(prefix="/api/real2sim")
    real2sim = service or Real2SimService(adapter)
    router.real2sim_service = real2sim  # type: ignore[attr-defined]  # lets the lead hook aclose() into lifespan

    @router.post("/drafts")
    async def create_draft(request: DraftCreateRequest) -> Dict[str, Any]:
        try:
            if request.mode == "fixture":
                if not fixtures_enabled():
                    raise Real2SimError("fixtures_disabled", 403)
                if request.image_base64 or request.mime_type:
                    raise Real2SimError("fixture_with_image", 422)
                if request.fixture_id is None:
                    raise Real2SimError("fixture_id_required", 422)
                try:
                    saved = await asyncio.to_thread(load_saved_run, request.fixture_id, fixtures_dir())
                except FixtureError as error:
                    raise Real2SimError(error.code, _FIXTURE_HTTP.get(error.code, 422)) from None
                return await real2sim.create_fixture(saved, name=request.name)
            if request.fixture_id is not None:
                raise Real2SimError("live_request_with_fixture_id", 422)
            if not real2sim.is_live_configured():
                raise Real2SimError("configuration_missing", 503)
            if real2sim.live_busy():
                raise Real2SimError("real2sim_busy", 429)
            source, notes = await asyncio.to_thread(decode_source, request.image_base64, request.mime_type,
                                                    request.source_kind)
            return await real2sim.create_live(source, name=request.name, thinking_level=request.thinking_level,
                                              notes=notes)
        except Real2SimError as error:
            raise _http(error) from None

    @router.post("/drafts/video")
    async def create_video_draft(request: Request,
                                 name: Optional[str] = Query(default=None, min_length=1, max_length=60),
                                 thinking_level: Optional[Literal["low", "medium", "high"]] = Query(default=None),
                                 ) -> Dict[str, Any]:
        """The body is the video file itself (MP4, WebM or MOV); it is streamed to a temporary file, never held whole."""
        try:
            if not real2sim.is_live_configured():
                raise Real2SimError("configuration_missing", 503)
            if real2sim.live_busy():
                raise Real2SimError("real2sim_busy", 429)
            declared = request.headers.get("content-length")
            if declared is not None and declared.isdigit() and int(declared) > MAX_VIDEO_BYTES:
                raise Real2SimError("source_too_large", 413)
            with tempfile.TemporaryDirectory(prefix="r2s-upload-") as tmp:
                path = Path(tmp) / "upload.bin"
                size = 0
                with path.open("wb") as handle:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > MAX_VIDEO_BYTES:
                            raise Real2SimError("source_too_large", 413)
                        handle.write(chunk)
                if size == 0:
                    raise Real2SimError("source_required", 422)
                source, notes = await asyncio.to_thread(prepare_video, path, original_bytes=size)
            return await real2sim.create_live(source, name=name, thinking_level=thinking_level, notes=notes)
        except Real2SimError as error:
            raise _http(error) from None

    @router.put("/drafts/{draft_id}/furniture")
    async def save_furniture(draft_id: str, request: FurnitureRequest) -> Dict[str, Any]:
        try:
            return await real2sim.save_furniture(
                draft_id, expected_revision=request.expected_revision,
                furniture=[piece.model_dump(exclude={"id"}) for piece in request.furniture])
        except Real2SimError as error:
            raise _http(error) from None

    @router.get("/saved")
    async def saved_runs() -> Dict[str, Any]:
        if not fixtures_enabled():
            return {"fixtures_enabled": False, "saved": [], "invalid": []}
        listed = await asyncio.to_thread(list_saved_runs, fixtures_dir())
        return {"fixtures_enabled": True, **listed}

    @router.get("/drafts/{draft_id}")
    async def get_draft(draft_id: str) -> Dict[str, Any]:
        try:
            return await asyncio.to_thread(real2sim.view, draft_id)
        except Real2SimError as error:
            raise _http(error) from None

    @router.get("/drafts/{draft_id}/events")
    async def draft_events(draft_id: str, last_event_id_header: Optional[str] = Header(default=None,
                                                                                        alias="Last-Event-ID"),
                           last_event_id: Optional[str] = Query(default=None, max_length=12)) -> StreamingResponse:
        try:
            log = await asyncio.to_thread(real2sim.event_log, draft_id)
        except Real2SimError as error:
            raise _http(error) from None
        cursor = _last_event_id(last_event_id_header, last_event_id)
        return StreamingResponse(log.stream(cursor, real2sim.ping_seconds), media_type="text/event-stream",
                                 headers=SSE_HEADERS)

    async def _png(draft_id: str, name: str) -> Response:
        try:
            data = await asyncio.to_thread(real2sim.image, draft_id, name)
        except Real2SimError as error:
            raise _http(error) from None
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @router.get("/drafts/{draft_id}/overlay.png")
    async def overlay_png(draft_id: str) -> Response:
        return await _png(draft_id, "overlay.png")

    @router.get("/drafts/{draft_id}/topdown.png")
    async def topdown_png(draft_id: str) -> Response:
        return await _png(draft_id, "topdown.png")

    @router.post("/drafts/{draft_id}/accept")
    async def accept_draft(draft_id: str, request: AcceptRequest) -> Dict[str, Any]:
        try:
            return await real2sim.accept(
                draft_id, expected_revision=request.expected_revision,
                controllable_doors=list(request.controllable_doors), headcount=request.headcount,
                building_width_m=request.building_width_m, venue_id=request.venue_id,
                make_active=request.make_active)
        except Real2SimError as error:
            raise _http(error) from None

    return router
