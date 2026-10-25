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

from backend.app.roomlab.contracts import (
    Opening,
    Provenance,
    RoomDraft,
    RoomObject,
    Wall,
)


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


class ProviderFloorVertex(BaseModel):
    model_config = ConfigDict(extra="ignore")

    x_m: float
    z_m: float


class ProviderRoomPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = "Estimated room"
    floor_vertices: list[ProviderFloorVertex]
    wall_height_m: float = 2.7
    wall_thickness_m: float = 0.12
    openings: list[ProviderOpeningDraft] = Field(default_factory=list)
    objects: list[ProviderObjectDraft] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def provider_response_json_schema() -> dict:
    """Return a clean, Gemini-compatible JSON Schema for structured output."""
    return {
        "type": "object",
        "required": ["name", "floor_vertices", "openings", "objects", "notes"],
        "properties": {
            "name": {"type": "string", "description": "Short descriptive room title."},
            "wall_height_m": {"type": "number", "description": "Estimated wall height in meters (typically 2.5 to 3.2)."},
            "wall_thickness_m": {"type": "number", "description": "Estimated wall thickness in meters (typically 0.12 to 0.20)."},
            "floor_vertices": {
                "type": "array",
                "description": "Ordered 2D floor polygon corners in meters [x_m, z_m] forming a simple non-self-intersecting loop. Minimum 3 vertices. Walls are derived in order: wall-1 connects vertex 0 to 1, wall-2 connects 1 to 2, ..., wall-N connects N-1 to 0.",
                "items": {
                    "type": "object",
                    "required": ["x_m", "z_m"],
                    "properties": {
                        "x_m": {"type": "number"},
                        "z_m": {"type": "number"},
                    },
                },
            },
            "openings": {
                "type": "array",
                "description": "Doors, windows, or open passages along walls (wall_id in wall-1..wall-N).",
                "items": {
                    "type": "object",
                    "required": ["id", "wall_id", "kind", "offset_m", "width_m", "height_m", "sill_m", "visibility", "evidence_frame_ids"],
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
                        "visibility": {"type": "string", "enum": ["observed", "partial", "unobserved"]},
                        "evidence_frame_ids": {"type": "array", "items": {"type": "string"}},
                        "note": {"type": "string"},
                    },
                },
            },
            "objects": {
                "type": "array",
                "description": "Floor-supported furniture or fixed obstacles inside the room.",
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
                        "visibility": {"type": "string", "enum": ["observed", "partial", "unobserved"]},
                        "evidence_frame_ids": {"type": "array", "items": {"type": "string"}},
                        "note": {"type": "string"},
                    },
                },
            },
            "notes": {
                "type": "array",
                "description": "Explicit assumptions, occluded areas, and scale estimation notes.",
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


def normalize_provider_payload(
    payload: ProviderRoomPayload,
    valid_frame_ids: set[str],
    default_frame_ids: list[str] | None = None,
) -> tuple[RoomDraft, list[str]]:
    """Convert a ProviderRoomPayload into a canonical RoomDraft and collect warnings."""
    del default_frame_ids  # Never fabricate element-specific frame links from generic defaults
    warnings: list[str] = []

    if len(payload.floor_vertices) < 3:
        raise ValueError("Provider room draft returned fewer than 3 floor vertices.")

    floor: list[list[float]] = []
    for idx, v in enumerate(payload.floor_vertices[:100]):
        if not (math.isfinite(v.x_m) and math.isfinite(v.z_m)):
            raise ValueError("Provider returned non-finite floor coordinates.")
        pt = [round(float(v.x_m), 3), round(float(v.z_m), 3)]
        if not floor or math.hypot(pt[0] - floor[-1][0], pt[1] - floor[-1][1]) > 0.05:
            floor.append(pt)
        else:
            warnings.append(f"Merged near-duplicate floor vertex #{idx + 1} at {pt}.")

    if len(floor) >= 3 and math.hypot(floor[0][0] - floor[-1][0], floor[0][1] - floor[-1][1]) <= 0.05:
        floor.pop()
        warnings.append("Removed closing duplicate floor vertex.")

    if len(floor) < 3:
        raise ValueError("Provider floor vertices collapsed to fewer than 3 distinct corners.")

    wall_h, _ = _clamp_with_warning(payload.wall_height_m, 1.8, 6.0, 2.7, "wall_height_m", warnings)
    wall_t, _ = _clamp_with_warning(payload.wall_thickness_m, 0.05, 0.6, 0.12, "wall_thickness_m", warnings)

    walls: list[Wall] = []
    wall_lengths: dict[str, float] = {}
    for idx in range(len(floor)):
        a = floor[idx]
        b = floor[(idx + 1) % len(floor)]
        wid = f"wall-{idx + 1}"
        w_len = math.hypot(b[0] - a[0], b[1] - a[1])
        wall_lengths[wid] = w_len
        walls.append(
            Wall(
                id=wid,
                start=a,
                end=b,
                height_m=round(wall_h, 3),
                thickness_m=round(wall_t, 3),
                provenance=Provenance(
                    source="model_estimate",
                    visibility="partial",
                    evidence_frame_ids=[],
                    note="Derived from estimated floor polygon; no per-wall frame citation returned.",
                ),
            )
        )

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

    openings: list[Opening] = []
    seen_openings: set[str] = set()
    for idx, op in enumerate(payload.openings[:50], start=1):
        wid = op.wall_id.strip()
        if wid not in wall_lengths:
            warnings.append(f"Skipped opening '{op.id}' attached to unknown wall '{wid}'.")
            continue
        w_len = wall_lengths[wid]
        if w_len < 0.35:
            warnings.append(f"Skipped opening '{op.id}' on short wall '{wid}' ({w_len:.2f}m).")
            continue

        oid = re.sub(r"[^A-Za-z0-9_-]+", "-", op.id.strip()) or f"open-{idx}"
        if oid in seen_openings:
            oid = f"{oid}-{idx}"
        seen_openings.add(oid)

        width_m, c_w = _clamp_with_warning(
            op.width_m, 0.4, max(0.4, w_len - 0.1), min(0.9, w_len * 0.6), f"opening '{oid}' width_m", warnings
        )
        max_offset = max(0.0, w_len - width_m - 0.02)
        offset_m, c_off = _clamp_with_warning(
            op.offset_m, 0.0, max_offset, max_offset * 0.5, f"opening '{oid}' offset_m", warnings
        )
        if op.kind in ("door", "passage"):
            if abs(op.sill_m) > 1e-4:
                warnings.append(f"Clamped {op.kind} '{oid}' sill_m from {op.sill_m:.2f} to 0.00.")
                c_sill = True
            else:
                c_sill = False
            sill_m = 0.0
        else:
            sill_m, c_sill = _clamp_with_warning(
                op.sill_m, 0.2, wall_h - 0.4, 0.9, f"window '{oid}' sill_m", warnings
            )
        height_m, c_h = _clamp_with_warning(
            op.height_m,
            0.4,
            max(0.4, wall_h - sill_m - 0.05),
            min(2.1, wall_h - sill_m - 0.05),
            f"opening '{oid}' height_m",
            warnings,
        )

        interval: list[float] | None = None
        if op.min_width_m is not None and op.max_width_m is not None:
            lo, _ = _clamp_with_warning(
                op.min_width_m, 0.2, width_m, max(0.2, width_m - 0.12), f"opening '{oid}' min_width_m", warnings
            )
            hi, _ = _clamp_with_warning(
                op.max_width_m, width_m, max(width_m, w_len), min(w_len, width_m + 0.12), f"opening '{oid}' max_width_m", warnings
            )
            if hi >= lo:
                interval = [round(lo, 3), round(hi, 3)]

        ev_ids = _clean_frame_ids(op.evidence_frame_ids, f"opening '{oid}'")
        repaired = c_w or c_off or c_sill or c_h
        vis: Literal["observed", "partial", "unobserved"] = op.visibility
        if (repaired or not ev_ids) and vis == "observed":
            vis = "partial"

        note_parts = [op.note.strip()] if op.note and op.note.strip() else []
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        if repaired:
            note_parts.append("Dimensions clamped to wall bounds during normalization.")

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

    objects: list[RoomObject] = []
    seen_objects: set[str] = set()
    for idx, obj in enumerate(payload.objects[:100], start=1):
        if not (math.isfinite(obj.x_m) and math.isfinite(obj.z_m)):
            warnings.append(f"Skipped object '{obj.id}' with non-finite center.")
            continue
        obj_id = re.sub(r"[^A-Za-z0-9_-]+", "-", obj.id.strip()) or f"obj-{idx}"
        if obj_id in seen_objects:
            obj_id = f"{obj_id}-{idx}"
        seen_objects.add(obj_id)

        category = (obj.category or "furniture").strip()[:80] or "furniture"
        is_fixed_arch = any(
            k in category.lower() or k in obj.label.lower()
            for k in ("pillar", "column", "structural", "counter", "island", "fixed")
        )
        movable = False if is_fixed_arch else bool(obj.movable)

        w_m, cw = _clamp_with_warning(obj.width_m, 0.15, 20.0, 0.8, f"object '{obj_id}' width_m", warnings)
        d_m, cd = _clamp_with_warning(obj.depth_m, 0.15, 20.0, 0.8, f"object '{obj_id}' depth_m", warnings)
        h_m, ch = _clamp_with_warning(obj.height_m, 0.15, wall_h, 0.75, f"object '{obj_id}' height_m", warnings)
        yaw, cy = _clamp_with_warning(obj.yaw_deg, -360.0, 360.0, 0.0, f"object '{obj_id}' yaw_deg", warnings)
        unc, cu = _clamp_with_warning(
            obj.uncertainty_radius_m, 0.0, 2.5, 0.12, f"object '{obj_id}' uncertainty_radius_m", warnings
        )

        ev_ids = _clean_frame_ids(obj.evidence_frame_ids, f"object '{obj_id}'")
        repaired = cw or cd or ch or cy or cu
        vis = obj.visibility
        if (repaired or not ev_ids) and vis == "observed":
            vis = "partial"

        note_parts = [obj.note.strip()] if obj.note and obj.note.strip() else []
        if not ev_ids:
            note_parts.append("No element-specific frame evidence cited.")
        if repaired:
            note_parts.append("Geometry clamped during normalization.")

        objects.append(
            RoomObject(
                id=obj_id[:80],
                label=(obj.label or obj_id).strip()[:160],
                category=category,
                center=[round(float(obj.x_m), 3), round(float(obj.z_m), 3)],
                width_m=round(w_m, 3),
                depth_m=round(d_m, 3),
                height_m=round(h_m, 3),
                yaw_deg=round(yaw, 2),
                movable=movable,
                resize_allowed=True,
                uncertainty_radius_m=round(unc, 3),
                provenance=Provenance(
                    source="model_estimate",
                    visibility=vis,
                    evidence_frame_ids=ev_ids,
                    note=" ".join(note_parts)[:500],
                ),
            )
        )

    notes = [str(n).strip()[:400] for n in payload.notes[:25] if str(n).strip()]
    if not notes:
        notes = [
            "Estimated 3D room draft inferred from video frames; metric scale requires a measured anchor.",
        ]

    draft = RoomDraft(
        name=(payload.name or "Estimated room").strip()[:160] or "Estimated room",
        floor=floor,
        walls=walls,
        openings=openings,
        objects=objects,
        notes=notes,
    )
    return draft, warnings
