"""Map underlay: the source image of an accepted venue, laid under the 3D twin in venue metres.

GET /api/venues/{venue_id}/underlay      -> {available, venue_id, geometry_revision, image_url, corners_m, width_px,
                                             height_px, mime_type, provenance, provenance_label, reason}
GET /api/venues/{venue_id}/underlay.jpg  -> the stored source bytes (JPEG or PNG, sent with their own media type);
                                            404 ``underlay_unavailable`` whenever the JSON says it is not available

Why: a judge photographs a posted evacuation map, Argon reads it and the compiler turns the reading into a venue. Drawing
that photo under the model, exactly where the compiler put each room, is the most direct check a person can make that
the twin is the building they photographed. It is also the easiest thing to get subtly wrong, so it is held to three
rules:

* **Only the stored source, unaltered.** The bytes come from ``runtime/real2sim/<draft_id>/source.{jpg,png}`` (written
  by real2sim, already EXIF-upright) and are served only when their sha256 equals the venue record's
  ``source_sha256``. They are never copied, resized or re-encoded, and never appear in a log or an error.
* **Placed by the compiler's own map.** ``compiler.image_frame`` re-derives the pixel -> metre affine from the stored
  draft, the image size and the operator's width override; the corners returned are the image's TL, TR, BR, BL
  corners in venue metres (x east, y north).
* **Drawn only when it lines up.** Recompiling the stored draft at that size and width must put every stored room back
  where it is (each side within ``ALIGN_TOL_M``); otherwise the answer is ``underlay_misaligned`` and nothing is drawn.
  A photo that disagrees with the model would mislead more than no photo.

Unavailable is a normal answer (``available: false`` with a short ``reason``): the built-in building-v2 is authored
and has no photo, a PDF was read from a vector page (its overlay is a blank canvas), and a record may point at a
source that is gone or changed. The routes are local only: the app's NetworkGuard keeps them from phones and the LAN
(they are deliberately not in any phone allowlist), and nothing here calls a provider.
"""
from __future__ import annotations

import hashlib
import io
import re
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import ValidationError

from backend.app.ai.grounding.adapter import MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS
from backend.app.ai.real2sim.drafts import MAX_SOURCE_BYTES, runtime_root, valid_draft_id
from backend.app.ai.real2sim.schema import SourceImage, VenueDraftV1
from backend.app.venues.compiler import ImageFrame, compile_draft, image_frame
from backend.app.venues.model import BUILTIN_VENUE_ID, VENUE_ID_PATTERN, VenueV2
from backend.app.venues.registry import VenueRegistry, venue_registry

_VENUE_ID = re.compile(VENUE_ID_PATTERN)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
# Stored names real2sim writes for raster sources, and the formats their bytes must actually be.
_SOURCES: Tuple[Tuple[str, str, str], ...] = (("source.jpg", "JPEG", "image/jpeg"), ("source.png", "PNG", "image/png"))
# A recompile of the stored reading puts every room exactly where it is stored; this allows a compiler revision that
# nudges a wall by a few grid steps, and nothing like a scale error (0.6 % over a 50 m building already exceeds it).
ALIGN_TOL_M = 0.3


class UnderlayUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class _Source:
    __slots__ = ("data", "mime_type", "width_px", "height_px", "sha256")

    def __init__(self, data: bytes, mime_type: str, width_px: int, height_px: int, sha256: str):
        self.data, self.mime_type, self.width_px, self.height_px, self.sha256 = data, mime_type, width_px, height_px, sha256


def provenance_label(provenance: Optional[str], source_kind: Optional[str]) -> str:
    """The words drawn beside the underlay. Never claims a photograph or a live reading it was not."""
    noun = {"photo": "Source photo", "sketch": "Source sketch"}.get(source_kind or "", "Source image")
    if provenance == "live":
        return f"{noun} · read by Gemini 4 Argon"
    if provenance == "saved_run":
        return f"{noun} · saved run (a recorded Gemini 4 Argon reading, not live)"
    if provenance == "synthetic":
        return "Synthetic image · drawn by our own generator, not a photograph"
    return f"{noun} · provenance not recorded"


def _read_source(root: Path, draft_id: str, expected_sha: str) -> _Source:
    base = root.resolve()
    for name, fmt, mime in _SOURCES:
        path = root / draft_id / name
        try:
            if not path.is_file():
                continue
            if not path.resolve().is_relative_to(base):
                raise UnderlayUnavailable("source_missing")      # a link out of the runtime folder is not our file
            if path.stat().st_size > MAX_SOURCE_BYTES:
                raise UnderlayUnavailable("source_unreadable")
            data = path.read_bytes()
        except OSError:
            raise UnderlayUnavailable("source_missing") from None
        sha = hashlib.sha256(data).hexdigest()
        if sha != expected_sha:
            raise UnderlayUnavailable("source_changed")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(data)) as opened:
                    width, height = opened.size
                    orientation = opened.getexif().get(0x0112, 1)
                    actual = opened.format
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError,
                Image.DecompressionBombWarning):
            raise UnderlayUnavailable("source_unreadable") from None
        if actual != fmt or min(width, height) <= 0 or max(width, height) > MAX_IMAGE_DIMENSION \
                or width * height > MAX_IMAGE_PIXELS:
            raise UnderlayUnavailable("source_unreadable")
        if orientation not in (None, 1):
            # real2sim stores sources upright; a rotated one would be drawn turned against the model.
            raise UnderlayUnavailable("source_rotated")
        return _Source(data, mime, width, height, sha)
    raise UnderlayUnavailable("source_missing")


def _bbox(polygon: List[List[float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def misalignment_m(venue: VenueV2, draft: VenueDraftV1, image: SourceImage,
                   building_width_m: Optional[float]) -> float:
    """Worst distance (m) between a stored room and the same room recompiled from the stored draft at this image
    size and width; infinite when the rooms differ.

    The compiler is deterministic, so for the reading that built the venue every room comes back exactly where it
    is stored. Comparing room by room (each side of each bounding box) also catches a wrong scale, which a check of
    the whole outline would miss when the drawing's outer boxes were dropped or merged."""
    result = compile_draft(draft, image, venue_id="image-frame", building_width_m=building_width_m)
    if result.venue is None:
        return float("inf")
    stored = {zone.id: _bbox(zone.polygon) for zone in venue.zones}
    again = {zone.id: _bbox(zone.polygon) for zone in result.venue.zones}
    if set(stored) != set(again):
        return float("inf")
    return max(abs(a - b) for key in stored for a, b in zip(stored[key], again[key]))


def resolve_underlay(venue_id: str, *, registry: VenueRegistry, root: Path) -> Tuple[VenueV2, Dict[str, Any], _Source,
                                                                                         ImageFrame]:
    """The venue, its record, the verified source and its frame; raises UnderlayUnavailable or HTTPException 404."""
    if not _VENUE_ID.match(venue_id):
        raise HTTPException(404, detail={"code": "unknown_venue"})
    venue = registry.accepted_venue(venue_id)
    if venue is None:
        raise HTTPException(404, detail={"code": "unknown_venue"})
    if venue_id == BUILTIN_VENUE_ID:
        raise UnderlayUnavailable("no_source_image")
    record = registry.venue_record(venue_id) or {}
    if not record.get("draft") or not record.get("draft_id"):
        raise UnderlayUnavailable("no_source_image")
    if record.get("source_kind") == "pdf":
        raise UnderlayUnavailable("pdf_source")
    draft_id, sha = record.get("draft_id"), record.get("source_sha256")
    if not valid_draft_id(draft_id) or not isinstance(sha, str) or not _SHA256.match(sha):
        raise UnderlayUnavailable("invalid_record")
    try:
        draft = VenueDraftV1.model_validate(record["draft"])
    except ValidationError:
        raise UnderlayUnavailable("invalid_record") from None
    source = _read_source(root, draft_id, sha)
    width = record.get("building_width_m")
    width = float(width) if isinstance(width, (int, float)) and not isinstance(width, bool) and width > 0 else None
    image = SourceImage(source.width_px, source.height_px, sha, source.mime_type)
    frame = image_frame(draft, image, building_width_m=width)
    if frame is None or not misalignment_m(venue, draft, image, width) <= ALIGN_TOL_M:
        raise UnderlayUnavailable("underlay_misaligned")
    return venue, record, source, frame


def build_underlay_router(registry: Callable[[], VenueRegistry] = venue_registry,
                          runtime_dir: Optional[Path] = None) -> APIRouter:
    """Mounted by main.py beside the venues router. ``runtime_dir`` defaults to real2sim's runtime folder (read at
    request time, so tests that point SPATIALTWIN_REAL2SIM_DIR at a temporary folder are honoured)."""
    router = APIRouter(prefix="/api/venues")

    @router.get("/{venue_id}/underlay")
    def underlay(venue_id: str) -> Dict[str, Any]:
        reg = registry()
        try:
            venue, record, source, frame = resolve_underlay(venue_id, registry=reg, root=runtime_root(runtime_dir))
        except UnderlayUnavailable as missing:
            known = reg.accepted_venue(venue_id)
            return {"available": False, "venue_id": venue_id,
                    "geometry_revision": known.geometry_revision if known else None, "reason": missing.reason,
                    "image_url": None, "corners_m": None, "width_px": None, "height_px": None, "mime_type": None,
                    "provenance": None, "provenance_label": None}
        corners = [[round(x, 3), round(y, 3)] for x, y in frame.corners_m()]
        return {"available": True, "venue_id": venue.venue_id, "geometry_revision": venue.geometry_revision,
                "reason": None,
                # The sha prefix busts the browser cache when an accepted venue is replaced by a new reading.
                "image_url": f"/api/venues/{venue.venue_id}/underlay.jpg?v={source.sha256[:16]}",
                "corners_m": corners, "width_px": source.width_px, "height_px": source.height_px,
                "mime_type": source.mime_type, "provenance": record.get("provenance"),
                "provenance_label": provenance_label(record.get("provenance"), record.get("source_kind"))}

    @router.get("/{venue_id}/underlay.jpg")
    def underlay_image(venue_id: str) -> Response:
        try:
            _, _, source, _ = resolve_underlay(venue_id, registry=registry(), root=runtime_root(runtime_dir))
        except (UnderlayUnavailable, HTTPException):
            raise HTTPException(404, detail={"code": "underlay_unavailable"}) from None
        return Response(content=source.data, media_type=source.mime_type, headers={
            "Cache-Control": "private, max-age=300", "ETag": f'"{source.sha256}"',
            "X-Content-Type-Options": "nosniff"})

    return router
