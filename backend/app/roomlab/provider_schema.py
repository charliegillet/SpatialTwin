"""Simplified provider JSON schema and normalization into canonical RoomDraft.

Gemini structured outputs support a strict subset of JSON Schema and reject overly
deep or constraint-heavy schemas. This module defines the compact provider schema
and converts raw model JSON into a validated RoomDraft while filtering evidence IDs
to actual frames from the uploaded MediaRecord without fabricating element-level
evidence links or silently disguising clamped/repaired geometry.
"""
from __future__ import annotations

import math
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from shapely.geometry import LineString, Polygon

from backend.app.roomlab.contracts import (
    FloorVoid,
    Opening,
    Provenance,
    RoomDraft,
    RoomObject,
    Wall,
)


class ProviderFloorVertex(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x_m: float
    z_m: float


class ProviderFloorVoidDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    vertices: list[ProviderFloorVertex] = Field(default_factory=list)
    visibility: Literal["observed", "partial", "unobserved"] = "observed"
    evidence_frame_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ProviderInteriorWallDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    role: Literal["partition", "railing"] = "partition"
    start_x_m: float
    start_z_m: float
    end_x_m: float
    end_z_m: float
    height_m: float = 2.7
    thickness_m: float = 0.12
    visibility: Literal["observed", "partial", "unobserved"] = "observed"
    evidence_frame_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ProviderOpeningDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    wall_id: str
    kind: Literal["door", "window", "passage"] = "door"
    offset_m: float
    width_m: float
    height_m: float = 2.1
    sill_m: float = 0.0
    min_width_m: float | None = None
    max_width_m: float | None = None
    visibility: Literal["observed", "partial", "unobserved"] = "observed"
    evidence_frame_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ProviderObjectDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    label: str
    category: str = "furniture"
    x_m: float
    z_m: float
    width_m: float
    depth_m: float
    height_m: float = 0.75
    yaw_deg: float = 0.0
    movable: bool = True
    uncertainty_radius_m: float = 0.1
    visibility: Literal["observed", "partial", "unobserved"] = "observed"
    evidence_frame_ids: list[str] = Field(default_factory=list)
    note: str = ""


class ProviderRoomPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Estimated room"
    floor_vertices: list[ProviderFloorVertex]
    floor_voids: list[ProviderFloorVoidDraft] = Field(default_factory=list)
    interior_walls: list[ProviderInteriorWallDraft] = Field(default_factory=list)
    wall_height_m: float = 2.7
    wall_thickness_m: float = 0.12
    openings: list[ProviderOpeningDraft] = Field(default_factory=list)
    objects: list[ProviderObjectDraft] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def provider_response_json_schema() -> dict:
    """Return a clean, Gemini-compatible JSON Schema for structured output."""
    return {
        "type": "object",
        "required": [
            "name",
            "floor_vertices",
            "floor_voids",
            "interior_walls",
            "openings",
            "objects",
            "notes",
        ],
        "properties": {
            "name": {"type": "string", "description": "Short descriptive room title."},
            "wall_height_m": {
                "type": "number",
                "description": "Estimated outer shell wall height in meters (typically 2.5 to 4.0).",
            },
            "wall_thickness_m": {
                "type": "number",
                "description": "Estimated outer shell wall thickness in meters (typically 0.12 to 0.25).",
            },
            "floor_vertices": {
                "type": "array",
                "description": "Ordered 2D outer floor polygon corners in meters [x_m, z_m] forming a simple non-self-intersecting loop. Minimum 3 vertices. Outer shell walls are derived in order: wall-1 connects vertex 0 to 1, wall-2 connects 1 to 2, ..., wall-N connects N-1 to 0.",
                "items": {
                    "type": "object",
                    "required": ["x_m", "z_m"],
                    "properties": {
                        "x_m": {"type": "number"},
                        "z_m": {"type": "number"},
                    },
                },
            },
            "floor_voids": {
                "type": "array",
                "description": "Non-walkable floor cutouts or open atrium drop-offs strictly inside floor_vertices. Empty array if the floor is completely solid.",
                "items": {
                    "type": "object",
                    "required": ["id", "vertices", "visibility", "evidence_frame_ids"],
                    "properties": {
                        "id": {"type": "string"},
                        "vertices": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["x_m", "z_m"],
                                "properties": {
                                    "x_m": {"type": "number"},
                                    "z_m": {"type": "number"},
                                },
                            },
                        },
                        "visibility": {
                            "type": "string",
                            "enum": ["observed", "partial", "unobserved"],
                        },
                        "evidence_frame_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "note": {"type": "string"},
                    },
                },
            },
            "interior_walls": {
                "type": "array",
                "description": "Interior dividing partitions (e.g. glass storefront walls dividing a corridor/landing from an interior lobby) or balustrades/railings bordering an atrium drop-off.",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "role",
                        "start_x_m",
                        "start_z_m",
                        "end_x_m",
                        "end_z_m",
                        "height_m",
                        "thickness_m",
                        "visibility",
                        "evidence_frame_ids",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "role": {"type": "string", "enum": ["partition", "railing"]},
                        "start_x_m": {"type": "number"},
                        "start_z_m": {"type": "number"},
                        "end_x_m": {"type": "number"},
                        "end_z_m": {"type": "number"},
                        "height_m": {"type": "number"},
                        "thickness_m": {"type": "number"},
                        "visibility": {
                            "type": "string",
                            "enum": ["observed", "partial", "unobserved"],
                        },
                        "evidence_frame_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "note": {"type": "string"},
                    },
                },
            },
            "openings": {
                "type": "array",
                "description": "Doors, windows, or open passages attached to either a shell wall (wall-1..wall-N) or an interior_walls ID.",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "wall_id",
                        "kind",
                        "offset_m",
                        "width_m",
                        "height_m",
                        "sill_m",
                        "visibility",
                        "evidence_frame_ids",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "wall_id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["door", "window", "passage"]},
                        "offset_m": {"type": "number"},
                        "width_m": {"type": "number"},
                        "height_m": {"type": "number"},
                        "sill_m": {"type": "number"},
                        "min_width_m": {"type": "number"},
                        "max_width_m": {"type": "number"},
                        "visibility": {
                            "type": "string",
                            "enum": ["observed", "partial", "unobserved"],
                        },
                        "evidence_frame_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "note": {"type": "string"},
                    },
                },
            },
            "objects": {
                "type": "array",
                "description": "Floor-supported furniture, counters, stools, plants, or fixed staircases inside the walkable room floor.",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "label",
                        "category",
                        "x_m",
                        "z_m",
                        "width_m",
                        "depth_m",
                        "height_m",
                        "yaw_deg",
                        "movable",
                        "uncertainty_radius_m",
                        "visibility",
                        "evidence_frame_ids",
                    ],
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "category": {"type": "string"},
                        "x_m": {"type": "number"},
                        "z_m": {"type": "number"},
                        "width_m": {"type": "number"},
                        "depth_m": {"type": "number"},
                        "height_m": {"type": "number"},
                        "yaw_deg": {"type": "number"},
                        "movable": {"type": "boolean"},
                        "uncertainty_radius_m": {"type": "number"},
                        "visibility": {
                            "type": "string",
                            "enum": ["observed", "partial", "unobserved"],
                        },
                        "evidence_frame_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "note": {"type": "string"},
                    },
                },
            },
            "notes": {
                "type": "array",
                "description": "Explicit assumptions, occluded areas, atrium drop-offs, glass partitions, and scale estimation notes.",
                "items": {"type": "string"},
            },
        },
    }


def _clamp_with_warning(
    val: float,
    low: float,
    high: float,
    default: float,
    label: str,
    warnings: list[str],
) -> tuple[float, bool]:
    if not isinstance(val, (int, float)) or isinstance(val, bool) or not math.isfinite(float(val)):
        warnings.append(f"Repaired non-finite {label} to default {default:.2f}m.")
        return default, True
    fval = float(val)
    if fval < low - 1e-6 or fval > high + 1e-6:
        clamped = float(min(max(fval, low), high))
        warnings.append(f"Clamped {label} from {fval:.2f} to {clamped:.2f} (bounds [{low:.2f}, {high:.2f}]).")
        return clamped, True
    return float(min(max(fval, low), high)), False


def _clean_polygon_vertices(
    raw_vertices: list[ProviderFloorVertex],
    label: str,
    warnings: list[str],
) -> list[list[float]]:
    pts: list[list[float]] = []
    for idx, v in enumerate(raw_vertices[:100]):
        if not (math.isfinite(v.x_m) and math.isfinite(v.z_m)):
            raise ValueError(f"Provider returned non-finite coordinates in {label}.")
        pt = [round(float(v.x_m), 3), round(float(v.z_m), 3)]
        if not pts or math.hypot(pt[0] - pts[-1][0], pt[1] - pts[-1][1]) > 0.05:
            pts.append(pt)
        else:
            warnings.append(f"Merged near-duplicate vertex #{idx + 1} in {label} at {pt}.")
    if len(pts) >= 3 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= 0.05:
        pts.pop()
        warnings.append(f"Removed closing duplicate vertex in {label}.")
    return pts


def normalize_provider_payload(
    payload: ProviderRoomPayload,
    valid_frame_ids: set[str],
    default_frame_ids: list[str] | None = None,
) -> tuple[RoomDraft, list[str]]:
    """Convert a ProviderRoomPayload into a canonical RoomDraft and collect warnings."""
    del default_frame_ids  # Never fabricate element-specific frame links from generic defaults
    warnings: list[str] = []
    topology_review_required = False
    topology_reasons: list[str] = []

    if len(payload.floor_vertices) < 3:
        raise ValueError("Provider room draft returned fewer than 3 floor vertices.")

    floor = _clean_polygon_vertices(payload.floor_vertices, "floor_vertices", warnings)
    if len(floor) < 3:
        raise ValueError("Provider floor vertices collapsed to fewer than 3 distinct corners.")

    outer_poly = Polygon(floor)
    if not outer_poly.is_valid or outer_poly.area < 0.1:
        raise ValueError("Provider floor vertices do not form a valid non-self-intersecting polygon.")

    wall_h, _ = _clamp_with_warning(payload.wall_height_m, 1.8, 6.0, 2.7, "wall_height_m", warnings)
    wall_t, _ = _clamp_with_warning(payload.wall_thickness_m, 0.05, 0.6, 0.12, "wall_thickness_m", warnings)

    def _clean_frame_ids(raw_ids: list[str], element_label: str) -> list[str]:
        matched: list[str] = []
        for fid in raw_ids:
            if fid in valid_frame_ids and fid not in matched:
                matched.append(fid)
        if len(matched) < len(raw_ids):
            warnings.append(f"Dropped unknown evidence frame IDs on {element_label}.")
        if not matched:
            warnings.append(f"No valid evidence frame IDs cited for {element_label}; keeping evidence_frame_ids=[].")
        return matched

    seen_ids: set[str] = set()

    # 1. Outer shell walls (wall-1 .. wall-N)
    walls: list[Wall] = []
    wall_map: dict[str, Wall] = {}
    wall_lengths: dict[str, float] = {}
    for idx in range(len(floor)):
        a = floor[idx]
        b = floor[(idx + 1) % len(floor)]
        wid = f"wall-{idx + 1}"
        seen_ids.add(wid)
        w_len = math.hypot(b[0] - a[0], b[1] - a[1])
        wall_lengths[wid] = w_len
        w_obj = Wall(
            role="shell",
            id=wid,
            start=a,
            end=b,
            height_m=round(wall_h, 3),
            thickness_m=round(wall_t, 3),
            provenance=Provenance(
                source="model_estimate",
                visibility="partial",
                evidence_frame_ids=[],
                note="Derived from estimated outer floor polygon; no per-wall frame citation returned.",
            ),
        )
        walls.append(w_obj)
        wall_map[wid] = w_obj

    # 2. Floor voids (atrium cutouts / non-walkable drop-offs strictly inside outer_poly)
    floor_voids: list[FloorVoid] = []
    accepted_void_polys: list[Polygon] = []
    for idx, v_draft in enumerate(payload.floor_voids[:30], start=1):
        vid = re.sub(r"[^A-Za-z0-9_-]+", "-", (v_draft.id or "").strip()) or f"void-{idx}"
        if vid in seen_ids:
            vid = f"{vid}-{idx}"
        try:
            v_pts = _clean_polygon_vertices(v_draft.vertices, f"floor_void '{vid}'", warnings)
        except ValueError as exc:
            msg = f"Skipped floor_void '{vid}': {exc}"
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue
        if len(v_pts) < 3:
            msg = f"Skipped floor_void '{vid}' with fewer than 3 distinct corners."
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue
        v_poly = Polygon(v_pts)
        if not v_poly.is_valid or v_poly.area < 0.05:
            msg = f"Skipped invalid or zero-area floor_void '{vid}'."
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue
        void_clipped = False
        if not outer_poly.contains(v_poly) or outer_poly.boundary.intersects(v_poly.boundary):
            shrunk_outer = outer_poly.buffer(-0.08)
            clipped = v_poly.intersection(shrunk_outer)
            if isinstance(clipped, Polygon) and clipped.is_valid and clipped.area >= 0.15:
                coords = list(clipped.exterior.coords)[:-1]
                v_pts = [[round(float(x), 3), round(float(z), 3)] for x, z in coords[:80]]
                v_poly = Polygon(v_pts)
                void_clipped = True
                msg = f"Clipped floor_void '{vid}' by 0.08m inset so it lies strictly inside the outer floor boundary."
                warnings.append(msg)
                topology_review_required = True
                topology_reasons.append(msg)
            else:
                msg = f"Skipped floor_void '{vid}' because it extends outside the outer floor boundary."
                warnings.append(msg)
                topology_review_required = True
                topology_reasons.append(msg)
                continue
        if any(v_poly.intersects(existing) for existing in accepted_void_polys):
            msg = f"Skipped floor_void '{vid}' because it overlaps another floor void."
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue

        seen_ids.add(vid)
        accepted_void_polys.append(v_poly)
        ev_ids = _clean_frame_ids(v_draft.evidence_frame_ids, f"floor_void '{vid}'")
        vis: Literal["observed", "partial", "unobserved"] = v_draft.visibility
        if (void_clipped or not ev_ids) and vis == "observed":
            vis = "partial"
        note_parts = [v_draft.note.strip()] if v_draft.note and v_draft.note.strip() else []
        if void_clipped:
            note_parts.append("Clipped by 0.08m inset to fit inside outer floor boundary; verify atrium cutout edges.")
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        floor_voids.append(
            FloorVoid(
                id=vid[:80],
                polygon=v_pts,
                provenance=Provenance(
                    source="geometry_fit" if void_clipped else "model_estimate",
                    visibility=vis,
                    evidence_frame_ids=ev_ids,
                    note=" ".join(note_parts)[:500],
                ),
            )
        )

    # 3. Interior walls (role="partition" | "railing")
    outer_buffered = outer_poly.buffer(1e-4)
    for idx, iw in enumerate(payload.interior_walls[:50], start=1):
        if not all(math.isfinite(v) for v in (iw.start_x_m, iw.start_z_m, iw.end_x_m, iw.end_z_m)):
            msg = f"Skipped interior {iw.role} '{iw.id}' with non-finite endpoints."
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue
        iwid = re.sub(r"[^A-Za-z0-9_-]+", "-", (iw.id or "").strip()) or f"wall-int-{idx}"
        if iwid in seen_ids:
            iwid = f"{iwid}-{idx}"

        p_start = [round(float(iw.start_x_m), 3), round(float(iw.start_z_m), 3)]
        p_end = [round(float(iw.end_x_m), 3), round(float(iw.end_z_m), 3)]
        seg = LineString([p_start, p_end])
        repaired_seg = False
        if not outer_buffered.covers(seg):
            clipped_seg = seg.intersection(outer_poly)
            if isinstance(clipped_seg, LineString) and clipped_seg.length >= 0.25:
                c_coords = list(clipped_seg.coords)
                p_start = [round(float(c_coords[0][0]), 3), round(float(c_coords[0][1]), 3)]
                p_end = [round(float(c_coords[-1][0]), 3), round(float(c_coords[-1][1]), 3)]
                repaired_seg = True
                msg = f"Clipped interior {iw.role} '{iwid}' endpoints to lie within outer shell."
                warnings.append(msg)
            else:
                msg = f"Skipped interior {iw.role} '{iwid}' outside the outer floor shell."
                warnings.append(msg)
                topology_review_required = True
                topology_reasons.append(msg)
                continue

        seg_len = math.hypot(p_end[0] - p_start[0], p_end[1] - p_start[1])
        if seg_len < 0.25:
            msg = f"Skipped interior {iw.role} '{iwid}' shorter than 0.25m."
            warnings.append(msg)
            topology_review_required = True
            topology_reasons.append(msg)
            continue

        default_h = 1.05 if iw.role == "railing" else wall_h
        max_h = 2.0 if iw.role == "railing" else 6.0
        low_h = 0.5 if iw.role == "railing" else 1.2
        ih_m, ch = _clamp_with_warning(
            iw.height_m, low_h, max_h, default_h, f"interior wall '{iwid}' height_m", warnings
        )
        it_m, ct = _clamp_with_warning(
            iw.thickness_m, 0.04, 0.5, 0.10 if iw.role == "railing" else 0.12, f"interior wall '{iwid}' thickness_m", warnings
        )
        ev_ids = _clean_frame_ids(iw.evidence_frame_ids, f"interior wall '{iwid}'")
        repaired = repaired_seg or ch or ct
        vis = iw.visibility
        if (repaired or not ev_ids) and vis == "observed":
            vis = "partial"

        note_parts = [iw.note.strip()] if iw.note and iw.note.strip() else []
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        if repaired:
            note_parts.append("Endpoints or dimensions clamped during normalization.")

        seen_ids.add(iwid)
        wall_lengths[iwid] = seg_len
        w_obj = Wall(
            role=iw.role,
            id=iwid[:80],
            start=p_start,
            end=p_end,
            height_m=round(ih_m, 3),
            thickness_m=round(it_m, 3),
            provenance=Provenance(
                source="geometry_fit" if repaired_seg else "model_estimate",
                visibility=vis,
                evidence_frame_ids=ev_ids,
                note=" ".join(note_parts)[:500],
            ),
        )
        walls.append(w_obj)
        wall_map[iwid] = w_obj

    # 4. Openings (doors, windows, passages on shell or interior walls; non-overlapping per wall)
    openings: list[Opening] = []
    openings_by_wall: dict[str, list[tuple[float, float]]] = {}
    for idx, op in enumerate(payload.openings[:60], start=1):
        wid = op.wall_id.strip()
        if wid not in wall_lengths:
            warnings.append(f"Skipped opening '{op.id}' attached to unknown wall '{wid}'.")
            continue
        w_len = wall_lengths[wid]
        parent_wall = wall_map[wid]
        if w_len < 0.35:
            warnings.append(f"Skipped opening '{op.id}' on short wall '{wid}' ({w_len:.2f}m).")
            continue

        oid = re.sub(r"[^A-Za-z0-9_-]+", "-", (op.id or "").strip()) or f"open-{idx}"
        if oid in seen_ids:
            oid = f"{oid}-{idx}"

        width_m, c_w = _clamp_with_warning(
            op.width_m, 0.4, max(0.4, w_len - 0.08), min(0.9, w_len * 0.6), f"opening '{oid}' width_m", warnings
        )
        max_offset = max(0.0, w_len - width_m - 0.02)
        offset_m, c_off = _clamp_with_warning(
            op.offset_m, 0.0, max_offset, max_offset * 0.5, f"opening '{oid}' offset_m", warnings
        )

        placed_spans = openings_by_wall.setdefault(wid, [])
        if any(min(offset_m + width_m, s_end) > max(offset_m, s_start) - 0.01 for s_start, s_end in placed_spans):
            warnings.append(
                f"Skipped opening '{oid}' on wall '{wid}' because it overlaps an existing opening on the same wall."
            )
            continue

        if op.kind in ("door", "passage"):
            if abs(op.sill_m) > 1e-4:
                warnings.append(f"Clamped {op.kind} '{oid}' sill_m from {op.sill_m:.2f} to 0.00.")
                c_sill = True
            else:
                c_sill = False
            sill_m = 0.0
        else:
            sill_m, c_sill = _clamp_with_warning(
                op.sill_m,
                0.15,
                max(0.2, parent_wall.height_m - 0.35),
                min(0.9, max(0.2, parent_wall.height_m * 0.3)),
                f"window '{oid}' sill_m",
                warnings,
            )
        height_m, c_h = _clamp_with_warning(
            op.height_m,
            0.3,
            max(0.3, parent_wall.height_m - sill_m - 0.04),
            min(2.1, max(0.3, parent_wall.height_m - sill_m - 0.05)),
            f"opening '{oid}' height_m",
            warnings,
        )

        interval: list[float] | None = None
        if op.min_width_m is not None and op.max_width_m is not None:
            lo, _ = _clamp_with_warning(
                op.min_width_m, 0.2, width_m, max(0.2, width_m - 0.12), f"opening '{oid}' min_width_m", warnings
            )
            hi, _ = _clamp_with_warning(
                op.max_width_m,
                width_m,
                max(width_m, w_len - offset_m),
                min(w_len - offset_m, width_m + 0.12),
                f"opening '{oid}' max_width_m",
                warnings,
            )
            if hi >= lo:
                interval = [round(lo, 3), round(hi, 3)]

        ev_ids = _clean_frame_ids(op.evidence_frame_ids, f"opening '{oid}'")
        repaired = c_w or c_off or c_sill or c_h
        vis = op.visibility
        if (repaired or not ev_ids) and vis == "observed":
            vis = "partial"

        note_parts = [op.note.strip()] if op.note and op.note.strip() else []
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        if repaired:
            note_parts.append("Dimensions clamped to wall bounds during normalization.")

        seen_ids.add(oid)
        placed_spans.append((round(offset_m, 3), round(offset_m + width_m, 3)))
        openings.append(
            Opening(
                id=oid[:80],
                wall_id=wid,
                kind=op.kind,
                offset_m=round(offset_m, 3),
                width_m=round(width_m, 3),
                height_m=round(height_m, 3),
                sill_m=round(sill_m, 3),
                width_interval_m=interval,
                provenance=Provenance(
                    source="model_estimate",
                    visibility=vis,
                    evidence_frame_ids=ev_ids,
                    note=" ".join(note_parts)[:500],
                ),
            )
        )

    walkable_poly = Polygon(floor, [v.polygon for v in floor_voids])
    wall_solid_polys: list[Polygon] = []
    for w in walls:
        wlen = wall_lengths[w.id]
        if wlen < 1e-6:
            continue
        gaps = sorted(
            (o.offset_m, o.offset_m + o.width_m)
            for o in openings
            if o.wall_id == w.id and o.kind in ("door", "passage") and o.sill_m <= 1e-6
        )
        cursor = 0.0
        for g_start, g_end in gaps + [(wlen, wlen)]:
            if g_start > cursor + 1e-6:
                pa = [w.start[i] + (w.end[i] - w.start[i]) * cursor / wlen for i in range(2)]
                pb = [w.start[i] + (w.end[i] - w.start[i]) * min(g_start, wlen) / wlen for i in range(2)]
                wall_solid_polys.append(LineString([pa, pb]).buffer(w.thickness_m / 2.0, cap_style="flat"))
            cursor = max(cursor, g_end)

    def _obj_footprint(cx: float, cz: float, w_m: float, d_m: float, yaw_deg: float) -> Polygon:
        ang = math.radians(yaw_deg)
        c, s = math.cos(ang), math.sin(ang)
        return Polygon(
            [
                (cx + c * dx + s * dz, cz - s * dx + c * dz)
                for dx, dz in [
                    (-w_m / 2.0, -d_m / 2.0),
                    (w_m / 2.0, -d_m / 2.0),
                    (w_m / 2.0, d_m / 2.0),
                    (-w_m / 2.0, d_m / 2.0),
                ]
            ]
        )

    # 5. Objects (furniture, counters, fixed staircases)
    objects: list[RoomObject] = []
    has_stairs = False
    for idx, obj in enumerate(payload.objects[:100], start=1):
        if not (math.isfinite(obj.x_m) and math.isfinite(obj.z_m)):
            warnings.append(f"Skipped object '{obj.id}' with non-finite center.")
            continue
        obj_id = re.sub(r"[^A-Za-z0-9_-]+", "-", (obj.id or "").strip()) or f"obj-{idx}"
        if obj_id in seen_ids:
            obj_id = f"{obj_id}-{idx}"

        category = (obj.category or "furniture").strip()[:80] or "furniture"
        cat_lower = category.lower()
        lbl_lower = (obj.label or "").strip().lower()
        is_stairs = cat_lower in ("stairs", "staircase", "stair") or lbl_lower.startswith(("stair", "stairs", "staircase", "interior stair"))
        if is_stairs:
            has_stairs = True
        is_fixed_arch = is_stairs or cat_lower in ("pillar", "column", "structural", "counter", "island", "fixed", "reception") or lbl_lower.startswith(("pillar", "column", "reception counter", "reception desk", "built-in"))
        movable = False if is_fixed_arch else bool(obj.movable)
        if is_stairs and obj.movable:
            warnings.append(f"Forced staircase object '{obj_id}' to movable=False (fixed placeholder).")

        w_m, cw = _clamp_with_warning(obj.width_m, 0.15, 20.0, 0.8, f"object '{obj_id}' width_m", warnings)
        d_m, cd = _clamp_with_warning(obj.depth_m, 0.15, 20.0, 0.8, f"object '{obj_id}' depth_m", warnings)
        h_m, ch = _clamp_with_warning(obj.height_m, 0.15, wall_h, 0.75, f"object '{obj_id}' height_m", warnings)
        yaw, cy = _clamp_with_warning(obj.yaw_deg, -360.0, 360.0, 0.0, f"object '{obj_id}' yaw_deg", warnings)
        unc, cu = _clamp_with_warning(
            obj.uncertainty_radius_m, 0.0, 2.5, 0.12, f"object '{obj_id}' uncertainty_radius_m", warnings
        )

        orig_cx, orig_cz = round(float(obj.x_m), 3), round(float(obj.z_m), 3)
        cx, cz = orig_cx, orig_cz
        fp = _obj_footprint(cx, cz, w_m, d_m, yaw)
        repaired_pos = False
        if not walkable_poly.buffer(1e-5).covers(fp) or any(
            fp.intersection(ws).area > 1e-5 for ws in wall_solid_polys
        ):
            best_pt: tuple[float, float] | None = None
            for radius_step in (0.08, 0.16, 0.25, 0.35, 0.5, 0.7):
                for ang_deg in range(0, 360, 30):
                    rad = math.radians(ang_deg)
                    nx = round(cx + radius_step * math.cos(rad), 3)
                    nz = round(cz + radius_step * math.sin(rad), 3)
                    cand_fp = _obj_footprint(nx, nz, w_m, d_m, yaw)
                    if walkable_poly.buffer(1e-5).covers(cand_fp) and not any(
                        cand_fp.intersection(ws).area > 1e-5 for ws in wall_solid_polys
                    ):
                        best_pt = (nx, nz)
                        break
                if best_pt is not None:
                    break
            if best_pt is not None:
                warnings.append(
                    f"Auto-translated object '{obj_id}' (geometry_fit) from [{orig_cx:.2f}, {orig_cz:.2f}] to [{best_pt[0]:.2f}, {best_pt[1]:.2f}] to clear modeled wall/void boundary; verify against video."
                )
                cx, cz = best_pt
                repaired_pos = True
            else:
                warnings.append(
                    f"Object '{obj_id}' at [{cx:.2f}, {cz:.2f}] touches or extends beyond modeled walkable floor/walls."
                )

        ev_ids = _clean_frame_ids(obj.evidence_frame_ids, f"object '{obj_id}'")
        repaired = cw or cd or ch or cy or cu or repaired_pos
        vis = obj.visibility
        if (repaired or not ev_ids) and vis == "observed":
            vis = "partial"

        note_parts = [obj.note.strip()] if obj.note and obj.note.strip() else []
        if is_stairs:
            note_parts.append(
                "Fixed single-level obstruction placeholder; staircase steps and upper/lower level travel are not modeled."
            )
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        if repaired_pos:
            note_parts.append(
                f"Auto-translated from [{orig_cx:.2f}, {orig_cz:.2f}] to [{cx:.2f}, {cz:.2f}] (geometry_fit) to avoid modeled wall/void overlap; verify position against video."
            )
        elif repaired:
            note_parts.append("Geometry clamped during normalization.")

        seen_ids.add(obj_id)
        objects.append(
            RoomObject(
                id=obj_id[:80],
                label=(obj.label or obj_id).strip()[:160],
                category=category,
                center=[cx, cz],
                width_m=round(w_m, 3),
                depth_m=round(d_m, 3),
                height_m=round(h_m, 3),
                yaw_deg=round(yaw, 2),
                movable=movable,
                resize_allowed=True,
                uncertainty_radius_m=round(unc, 3),
                provenance=Provenance(
                    source="geometry_fit" if repaired_pos else "model_estimate",
                    visibility=vis,
                    evidence_frame_ids=ev_ids,
                    note=" ".join(note_parts)[:500],
                ),
            )
        )

    notes = [str(n).strip()[:400] for n in payload.notes[:25] if str(n).strip()]
    if topology_review_required:
        notes.insert(
            0,
            "TOPOLOGY REVIEW REQUIRED: One or more floor voids or interior partitions/railings were clipped or skipped during normalization ("
            + "; ".join(topology_reasons[:3])
            + "). Review and confirm topology in the editor before running clearance checks.",
        )
    if has_stairs and not any("stair" in n.lower() for n in notes):
        notes.append(
            "Staircases are modeled as fixed single-level bounding boxes; multi-level floor transitions are not reconstructed."
        )
    if not notes:
        notes = [
            "Estimated 3D room draft inferred from video frames; metric scale requires a measured anchor.",
        ]

    draft = RoomDraft(
        topology_review_required=topology_review_required,
        name=(payload.name or "Estimated room").strip()[:160] or "Estimated room",
        floor=floor,
        floor_voids=floor_voids,
        walls=walls,
        openings=openings,
        objects=objects,
        notes=notes[:30],
    )
    return draft, warnings
