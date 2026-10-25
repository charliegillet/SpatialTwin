"""Frozen contract: what Gemini 4 Argon reads off a floor plan (VenueDraftV1) and what the compiler returns.

Coordinates in a draft are Gemini's spatial convention (as in grounding/hazard_read.py): integers 0–1000 over the
source image, a point is [y, x] and a box is [ymin, xmin, ymax, xmax]. Nothing in a draft is in metres except
the optional widths and the scale reference. ``backend/app/venues/compiler.py`` turns a draft plus the source
image size into a strict VenueV2; nothing a model returns reaches the planner without that compiler, the graph
checks and an operator's Accept.

Owner: lead. Teammates import from here and never edit it; request changes through the lead.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError, model_validator

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
    # May be empty: a drawing with no marked exit must not push the model into inventing one. The compiler then
    # reports no_exit_survived and Accept stays blocked.
    exits: Annotated[List[DraftExit], Field(max_length=MAX_EXITS)] = []
    # The paper sheet's corners in a photo of a posted map, TL, TR, BR, BL, for later perspective rectification.
    # Not used by the compiler yet; a tilted photo is compiled as if it were square-on.
    sheet_corners: Optional[Annotated[List[Point], Field(min_length=4, max_length=4)]] = None
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


def provider_response_schema() -> dict:
    """VenueDraftV1 as the response_format schema, using only keywords the live-proven card and grounding schemas use.

    ``pattern``, ``default`` and ``exclusiveMinimum`` have not been accepted live by the provider here, and constrained
    decoding cannot enforce cross-references, box ordering or the scale rule anyway; ``salvage_draft`` enforces all of
    those per element after decoding.
    """
    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(item) for item in node]
        if not isinstance(node, dict):
            return node
        out: Dict[str, Any] = {}
        for key, value in node.items():
            if key in ("pattern", "default", "title"):
                continue
            if key == "const":
                out["enum"] = [value]
            elif key == "exclusiveMinimum":
                out["minimum"] = value
            elif key == "exclusiveMaximum":
                out["maximum"] = value
            else:
                out[key] = clean(value)
        return out
    return clean(VenueDraftV1.model_json_schema())


@dataclass
class SalvageResult:
    """A draft rebuilt element by element: one bad door is dropped and reported, not fatal to the reading."""
    draft: Optional[VenueDraftV1]
    # "door KD3: joins unknown room OUTSIDE" — shown to the operator next to Accept
    dropped: List[str] = field(default_factory=list)
    # "room LIVING: name shortened to 40 characters" — repairs that kept the element
    repaired: List[str] = field(default_factory=list)
    error: Optional[str] = None


_OUTSIDE_WORDS = {"OUTSIDE", "EXTERIOR", "STREET", "OUT", "EXIT"}
_LIMITS = {"name": 40, "evidence": 160, "label": 40}


def _issue(error: ValidationError) -> str:
    first = error.errors()[0] if error.errors() else {}
    where = ".".join(str(part) for part in first.get("loc", ()))
    return f"{where}: {first.get('msg', 'invalid')}"[:120] if where else str(first.get("msg", "invalid"))[:120]


def _coordinates(value: Any, size: int) -> Any:
    """Integral floats become ints and out-of-range values clamp to 0–1000; anything else is left for validation."""
    if not isinstance(value, list) or len(value) != size:
        return value
    out = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            return value
        out.append(min(1000, max(0, int(round(item)))))
    return out


def _key(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    key = re.sub(r"[^A-Z0-9_]", "_", value.strip().upper())[:24]
    return key if key[:1].isalpha() else f"K{key}"[:24]


def salvage_draft(raw: Any) -> SalvageResult:
    """Validate a decoded model output element by element into a VenueDraftV1.

    Repairs that cannot change meaning are applied and listed (integral coordinates, clamping to the grid, key
    normalisation, over-long text). A door to the outside becomes an exit. Every element that still fails its own
    model, references an unknown room or repeats a key is dropped with a reason. Only a reading with no usable room
    fails as a whole.
    """
    result = SalvageResult(draft=None)
    if not isinstance(raw, dict):
        result.error = "draft_not_an_object"
        return result

    def text(item: Dict[str, Any], name: str, what: str) -> None:
        limit = _LIMITS[name]
        if isinstance(item.get(name), str) and len(item[name]) > limit:
            item[name] = item[name][:limit].rstrip()
            result.repaired.append(f"{what}: {name} shortened to {limit} characters")

    def prepare(item: Any, kind: str) -> Optional[Dict[str, Any]]:
        if not isinstance(item, dict):
            result.dropped.append(f"{kind}: not an object")
            return None
        item = dict(item)
        for name in ("key", "room"):
            if name in item:
                normalised = _key(item[name])
                if normalised != item[name]:
                    result.repaired.append(f"{kind} {item[name]}: key normalised to {normalised}")
                item[name] = normalised
        if isinstance(item.get("between"), list):
            item["between"] = [_key(value) for value in item["between"]]
        for name, size in (("point", 2), ("label_point", 2), ("box", 4)):
            if name in item:
                item[name] = _coordinates(item[name], size)
        if isinstance(item.get("extra_boxes"), list):
            item["extra_boxes"] = [_coordinates(box, 4) for box in item["extra_boxes"]]
        for name in ("name", "evidence", "label"):
            text(item, name, f"{kind} {item.get('key', '?')}")
        if kind == "room" and isinstance(item.get("name"), str) and not item["name"].strip():
            item["name"] = str(item.get("key") or "Room")
        return item

    seen: set = set()
    rooms: List[DraftRoom] = []
    for item in raw.get("rooms") or []:
        item = prepare(item, "room")
        if item is None:
            continue
        try:
            room = DraftRoom.model_validate(item)
        except ValidationError as error:
            result.dropped.append(f"room {item.get('key', '?')}: {_issue(error)}")
            continue
        if room.key in seen:
            result.dropped.append(f"room {room.key}: duplicate key")
        elif len(rooms) >= MAX_ROOMS:
            result.dropped.append(f"room {room.key}: more than {MAX_ROOMS} rooms")
        else:
            seen.add(room.key)
            rooms.append(room)
    room_keys = {room.key for room in rooms}

    doors: List[DraftDoor] = []
    exits: List[DraftExit] = []
    for item in raw.get("doors") or []:
        item = prepare(item, "door")
        if item is None:
            continue
        between = item.get("between") if isinstance(item.get("between"), list) else []
        known = [key for key in between if key in room_keys]
        unknown = [key for key in between if key not in room_keys]
        if len(between) == 2 and len(known) == 1 and unknown and unknown[0] in _OUTSIDE_WORDS:
            # A door from a room to the outside is an exit, not an internal door.
            item = {"key": item.get("key"), "room": known[0], "point": item.get("point"),
                    "width_m": item.get("width_m"), "kind": "door", "label": "door to outside",
                    "confidence": item.get("confidence", 0.5), "evidence": item.get("evidence", "")}
            result.repaired.append(f"door {item['key']}: leads outside, kept as an exit")
            raw_exits = list(raw.get("exits") or [])
            raw = {**raw, "exits": raw_exits + [item]}
            continue
        try:
            door = DraftDoor.model_validate(item)
        except ValidationError as error:
            result.dropped.append(f"door {item.get('key', '?')}: {_issue(error)}")
            continue
        a, b = door.between
        if door.key in seen:
            result.dropped.append(f"door {door.key}: duplicate key")
        elif a == b or a not in room_keys or b not in room_keys:
            missing = ", ".join(key for key in (a, b) if key not in room_keys) or a
            result.dropped.append(f"door {door.key}: joins unknown or identical room {missing}")
        elif len(doors) >= MAX_DOORS:
            result.dropped.append(f"door {door.key}: more than {MAX_DOORS} doors")
        else:
            seen.add(door.key)
            doors.append(door)

    for item in raw.get("exits") or []:
        item = prepare(item, "exit")
        if item is None:
            continue
        try:
            exit_ = DraftExit.model_validate(item)
        except ValidationError as error:
            result.dropped.append(f"exit {item.get('key', '?')}: {_issue(error)}")
            continue
        if exit_.key in seen:
            result.dropped.append(f"exit {exit_.key}: duplicate key")
        elif exit_.room not in room_keys:
            result.dropped.append(f"exit {exit_.key}: unknown room {exit_.room}")
        elif len(exits) >= MAX_EXITS:
            result.dropped.append(f"exit {exit_.key}: more than {MAX_EXITS} exits")
        else:
            seen.add(exit_.key)
            exits.append(exit_)

    scale_raw = raw.get("scale") if isinstance(raw.get("scale"), dict) else {}
    try:
        scale = DraftScale.model_validate({**scale_raw, **{name: _coordinates(scale_raw[name], 2)
                                                           for name in ("a", "b") if name in scale_raw}})
    except ValidationError as error:
        scale = DraftScale(basis="unknown")
        result.repaired.append(f"scale reference ignored: {_issue(error)}")

    corners = raw.get("sheet_corners")
    if corners is not None:
        corners = [_coordinates(point, 2) for point in corners] if isinstance(corners, list) else corners
    unreadable = [value[:160] for value in (raw.get("unreadable") or []) if isinstance(value, str)][:10]
    image_kind = raw.get("image_kind")
    if image_kind not in ImageKind.__args__:
        result.repaired.append(f"image_kind {str(image_kind)[:20]!r} read as other")
        image_kind = "other"
    if not rooms:
        result.error = "no_room_survived"
        return result
    try:
        result.draft = VenueDraftV1(
            schema_version="draft-1", title=str(raw.get("title") or "")[:60], image_kind=image_kind, scale=scale,
            rooms=rooms, doors=doors, exits=exits, sheet_corners=corners,
            you_are_here=_coordinates(raw.get("you_are_here"), 2) if raw.get("you_are_here") is not None else None,
            unreadable=unreadable, notes=str(raw.get("notes") or "")[:300])
    except ValidationError as error:
        # Only the optional extras can still fail here (sheet corners, the you-are-here marker); drop them.
        result.repaired.append(f"optional markers ignored: {_issue(error)}")
        result.draft = VenueDraftV1(
            schema_version="draft-1", title=str(raw.get("title") or "")[:60], image_kind=image_kind, scale=scale,
            rooms=rooms, doors=doors, exits=exits, unreadable=unreadable, notes=str(raw.get("notes") or "")[:300])
    return result


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
