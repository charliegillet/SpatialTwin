"""Shared WalkTwin data contracts (immutable pydantic v2 models)."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ZONE_ID = r"^Z\d{1,3}$"
_DOOR_ID = r"^D\d{1,3}$"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


def _round_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 3)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_round_floats(v) for v in obj]
    return obj


def _canonical_json(model: BaseModel) -> str:
    data = _round_floats(model.model_dump(mode="json"))
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _sha256(model: BaseModel) -> str:
    return hashlib.sha256(_canonical_json(model).encode("utf-8")).hexdigest()


class Evidence(_Model):
    start_s: float = Field(ge=0)
    end_s: float
    note: str = Field(max_length=200)

    @model_validator(mode="after")
    def _check_order(self) -> "Evidence":
        if self.end_s < self.start_s:
            raise ValueError("end_s must be >= start_s")
        return self


class Measure(_Model):
    low_m: float = Field(gt=0)
    high_m: float
    basis: Literal["anchor_measured", "estimated", "assumed"]

    @model_validator(mode="after")
    def _check_order(self) -> "Measure":
        if self.high_m < self.low_m:
            raise ValueError("high_m must be >= low_m")
        return self


class Zone(_Model):
    id: str = Field(pattern=_ZONE_ID)
    name: str = Field(max_length=60)
    rect: tuple[float, float, float, float]  # x, y, w, h in meters
    occupants: int = Field(ge=0)
    furniture_seen: bool = False
    evidence: list[Evidence]

    @model_validator(mode="after")
    def _check_rect(self) -> "Zone":
        if self.rect[2] <= 0 or self.rect[3] <= 0:
            raise ValueError("rect w and h must be > 0")
        return self


class Door(_Model):
    id: str = Field(pattern=_DOOR_ID)
    a: str
    b: str  # zone id or "OUTSIDE"
    kind: Literal["door", "opening", "exit", "stair"]
    state: Literal["open", "closed", "locked", "unknown"]
    clear_width: Measure
    position: tuple[float, float]
    evidence: list[Evidence]


class Keyframe(_Model):
    t_s: float = Field(ge=0)
    zone_id: str
    x: float
    y: float
    heading_deg: float = Field(ge=0, lt=360)


class Anchor(_Model):
    door_id: str
    measured_width_m: float = Field(gt=0)


class VenueGraph(_Model):
    schema_version: Literal["1"]
    video_sha256: str
    anchor: Anchor | None
    zones: list[Zone]
    doors: list[Door]
    keyframes: list[Keyframe]

    @property
    def revision(self) -> str:
        return "g-" + _sha256(self)[:16]


class Hazard(_Model):
    door_id: str
    kind: Literal["fire"]
    from_s: float = 0


class Scenario(_Model):
    hazards: list[Hazard] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)  # e.g. "OPEN:D3"

    @property
    def hash(self) -> str:
        return "s-" + _sha256(self)[:12]


class FlowParams(_Model):
    dt_s: int = 2
    horizon_s: int = 120
    specific_flow_p_per_m_s: float = 1.3
    boundary_layer_m: float = 0.15
    walk_speed_m_s: float = 1.2


def apply_anchor(graph: VenueGraph, anchor: Anchor, uncertainty: float = 0.20) -> VenueGraph:
    """Scale the graph so the anchor door matches its measured width.

    factor = measured / midpoint(anchor door estimate). Geometry (zone rects,
    door positions, keyframe coordinates) scales by factor; non-anchor widths
    become mid*factor*(1 +/- uncertainty), keeping the `assumed` basis.
    """
    anchor_door = next((d for d in graph.doors if d.id == anchor.door_id), None)
    if anchor_door is None:
        raise ValueError(f"anchor door {anchor.door_id!r} not in graph")
    w = anchor_door.clear_width
    f = anchor.measured_width_m / ((w.low_m + w.high_m) / 2)

    zones = [
        z.model_copy(update={"rect": tuple(v * f for v in z.rect)}) for z in graph.zones
    ]
    doors = []
    for d in graph.doors:
        if d.id == anchor.door_id:
            cw = Measure(
                low_m=anchor.measured_width_m,
                high_m=anchor.measured_width_m,
                basis="anchor_measured",
            )
        else:
            mid = (d.clear_width.low_m + d.clear_width.high_m) / 2 * f
            basis = "assumed" if d.clear_width.basis == "assumed" else "estimated"
            cw = Measure(low_m=mid * (1 - uncertainty), high_m=mid * (1 + uncertainty), basis=basis)
        doors.append(
            d.model_copy(
                update={
                    "clear_width": cw,
                    "position": (d.position[0] * f, d.position[1] * f),
                }
            )
        )
    keyframes = [k.model_copy(update={"x": k.x * f, "y": k.y * f}) for k in graph.keyframes]
    return graph.model_copy(
        update={"anchor": anchor, "zones": zones, "doors": doors, "keyframes": keyframes}
    )
