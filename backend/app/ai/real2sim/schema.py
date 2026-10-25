"""Frozen contract: what Gemini 4 Argon reads off a floor plan (VenueDraftV1) and what the compiler returns.

Coordinates in a draft are Gemini's spatial convention (as in grounding/hazard_read.py): integers 0–1000 over the
source image, a point is [y, x] and a box is [ymin, xmin, ymax, xmax]. Nothing in a draft is in metres except
the optional widths and the scale reference. ``backend/app/venues/compiler.py`` turns a draft plus the source
image size into a strict VenueV2; nothing a model returns reaches the planner without that compiler, the graph
checks and an operator's Accept.

Owner: lead. Teammates import from here and never edit it; request changes through the lead.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from backend.app.venues.model import VenueV2

DRAFT_SCHEMA_VERSION = "draft-1"
MAX_ROOMS, MAX_DOORS, MAX_EXITS = 16, 32, 12
KEY_PATTERN = r"^[A-Z][A-Z0-9_]{0,23}$"

Coordinate = Annotated[StrictInt, Field(ge=0, le=1000)]
Point = Annotated[List[Coordinate], Field(min_length=2, max_length=2)]   # [y, x]
Box = Annotated[List[Coordinate], Field(min_length=4, max_length=4)]     # [ymin, xmin, ymax, xmax]
Key = Annotated[str, Field(pattern=KEY_PATTERN)]
ShortText = Annotated[str, Field(max_length=160)]

RoomKind = Literal["room", "corridor", "lobby", "hall", "stair", "kitchen", "bedroom", "bathroom", "office",
                   "storage", "other"]
DoorSymbol = Literal["swing", "double", "sliding", "opening", "fire_door", "unknown"]
ExitKind = Literal["door", "stair", "window", "unknown"]
ScaleBasis = Literal["dimension_label", "scale_bar", "door_width_prior", "operator_input", "unknown"]
ImageKind = Literal["evacuation_map", "architectural_plan", "sketch", "photo_of_plan", "other"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _check_box(box: List[int]) -> None:
    ymin, xmin, ymax, xmax = box
    if ymin >= ymax or xmin >= xmax:
        raise ValueError("unordered or empty box")


class DraftScale(_Strict):
    """How the drawing maps to metres. ``a``→``b`` is a measured reference on the image of length ``metres``."""
    basis: ScaleBasis
    a: Optional[Point] = None
    b: Optional[Point] = None
    metres: Optional[float] = Field(default=None, gt=0, le=500)
    evidence: ShortText = ""

    @model_validator(mode="after")
    def _reference_complete(self) -> "DraftScale":
        given = [self.a is not None, self.b is not None, self.metres is not None]
        if any(given) and not all(given):
            raise ValueError("a scale reference needs a, b and metres")
        if self.a is not None and self.a == self.b:
            raise ValueError("scale reference endpoints must differ")
        return self


class DraftRoom(_Strict):
    key: Key
    name: Annotated[str, Field(min_length=1, max_length=40)]
    kind: RoomKind
    box: Box
    # Up to two more boxes for L- or T-shaped rooms; the compiler unions them.
    extra_boxes: Annotated[List[Box], Field(max_length=2)] = []
    label_point: Point
    occupants_hint: Optional[Annotated[StrictInt, Field(ge=0, le=2000)]] = None

    @model_validator(mode="after")
    def _boxes(self) -> "DraftRoom":
        for box in [self.box, *self.extra_boxes]:
            _check_box(box)
        return self


class DraftDoor(_Strict):
    key: Key
    between: Annotated[List[Key], Field(min_length=2, max_length=2)]
    point: Point
    width_m: Optional[float] = Field(default=None, gt=0, le=10)
    symbol: DoorSymbol = "unknown"
    confidence: float = Field(ge=0, le=1)
    evidence: ShortText = ""


class DraftExit(_Strict):
    key: Key
    room: Key
    point: Point
    width_m: Optional[float] = Field(default=None, gt=0, le=10)
    kind: ExitKind = "door"
    label: Annotated[str, Field(max_length=40)] = ""
    confidence: float = Field(ge=0, le=1)
    evidence: ShortText = ""


class VenueDraftV1(_Strict):
    schema_version: Literal["draft-1"]
    title: Annotated[str, Field(max_length=60)] = ""
    image_kind: ImageKind
    scale: DraftScale
    rooms: Annotated[List[DraftRoom], Field(min_length=1, max_length=MAX_ROOMS)]
    doors: Annotated[List[DraftDoor], Field(max_length=MAX_DOORS)] = []
    exits: Annotated[List[DraftExit], Field(min_length=1, max_length=MAX_EXITS)]
    # A posted evacuation map's "you are here" marker, when one is drawn.
    you_are_here: Optional[Point] = None
    # What Argon saw but could not read with confidence; shown to the operator next to Accept.
    unreadable: Annotated[List[ShortText], Field(max_length=10)] = []
    notes: Annotated[str, Field(max_length=300)] = ""

    @model_validator(mode="after")
    def _references(self) -> "VenueDraftV1":
        keys = [r.key for r in self.rooms] + [d.key for d in self.doors] + [e.key for e in self.exits]
        if len(keys) != len(set(keys)):
            raise ValueError("room, door and exit keys must be unique across the draft")
        rooms = {r.key for r in self.rooms}
        for door in self.doors:
            a, b = door.between
            if a == b or a not in rooms or b not in rooms:
                raise ValueError(f"door {door.key} must join two different known rooms")
        for exit_ in self.exits:
            if exit_.room not in rooms:
                raise ValueError(f"exit {exit_.key} references an unknown room")
        return self


@dataclass(frozen=True)
class SourceImage:
    """The image a draft was read from. Width and height convert 0–1000 coordinates to pixels."""
    width_px: int
    height_px: int
    sha256: str
    mime_type: str = "image/png"


@dataclass
class CompileReport:
    """What the compiler did, for the overlay, the critique and the operator."""
    # draft key -> venue element id (zones keep the draft key; doors become D1.., exits E1..)
    element_ids: Dict[str, str] = field(default_factory=dict)
    # venue element id -> [y, x] on the 0–1000 source grid: the evidence point drawn on the overlay
    evidence_points: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    metres_per_px: float = 0.0
    scale_basis: str = "unknown"
    # declared defaults the compiler filled in, in plain words ("door D3 width 0.9 m (default)")
    defaults: List[str] = field(default_factory=list)
    # geometry edits ("snapped Kitchen west wall to x=7.0 m", "merged doors KD1 and KD2")
    edits: List[str] = field(default_factory=list)
    # draft elements the compiler could not place, with the reason
    dropped: List[str] = field(default_factory=list)


@dataclass
class CompileResult:
    venue: Optional[VenueV2]
    report: CompileReport
    # set when no VenueV2 could be built at all (e.g. no room survives); graph issues are separate
    error: Optional[str] = None
