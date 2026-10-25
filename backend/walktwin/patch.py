"""Graph patch operations proposed by Argon and their deterministic application.

``apply_patch`` is pure: it never mutates its input and never calls a model. Ops
are applied in order; an op is rejected (and reverted) when it names an unknown
id, cites a time outside the video, fails contract validation, or introduces an
error-severity finding the graph did not have before it. Rejected ops do not
stop later ops.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .contracts import Door, Measure, VenueGraph, Zone
from .graph_checks import Finding, check_graph

DoorKind = Literal["door", "opening", "exit", "stair"]
DoorState = Literal["open", "closed", "locked", "unknown"]


class _Op(BaseModel):
    model_config = ConfigDict(frozen=True)

    cite_t_s: float = Field(ge=0)
    reason: str = Field(max_length=200)


class AddDoor(_Op):
    op: Literal["add_door"]
    door: Door


class RemoveDoor(_Op):
    op: Literal["remove_door"]
    id: str


class UpdateDoor(_Op):
    op: Literal["update_door"]
    id: str
    position: tuple[float, float] | None = None
    clear_width: Measure | None = None
    state: DoorState | None = None
    kind: DoorKind | None = None


class AddZone(_Op):
    op: Literal["add_zone"]
    zone: Zone


class UpdateZone(_Op):
    op: Literal["update_zone"]
    id: str
    rect: tuple[float, float, float, float] | None = None
    name: str | None = Field(default=None, max_length=60)
    furniture_seen: bool | None = None


class RemoveZone(_Op):
    op: Literal["remove_zone"]
    id: str


PatchOp = Annotated[
    Union[AddDoor, RemoveDoor, UpdateDoor, AddZone, UpdateZone, RemoveZone],
    Field(discriminator="op"),
]

OP_NAMES = ("add_door", "remove_door", "update_door", "add_zone", "update_zone", "remove_zone")


@dataclass(frozen=True)
class PatchOutcome:
    graph: VenueGraph
    applied: list[int] = field(default_factory=list)
    rejected: list[tuple[int, str]] = field(default_factory=list)


class _Reject(Exception):
    pass


def _updates(op: BaseModel, keys: tuple[str, ...]) -> dict[str, Any]:
    return {k: getattr(op, k) for k in keys if getattr(op, k) is not None}


def _replace(items: list, ident: str, kind: str, updates: dict, model: type[BaseModel]) -> list:
    out, found = [], False
    for el in items:
        if el.id == ident:
            found = True
            # rebuild through validation (model_copy would skip validators)
            data = el.model_dump()
            for k, v in updates.items():
                data[k] = v.model_dump() if isinstance(v, BaseModel) else v
            el = model.model_validate(data)
        out.append(el)
    if not found:
        raise _Reject(f"unknown id {ident} ({kind})")
    return out


def _apply_one(graph: VenueGraph, op: Any) -> VenueGraph:
    doors, zones = list(graph.doors), list(graph.zones)
    if isinstance(op, AddDoor):
        doors.append(op.door)
    elif isinstance(op, AddZone):
        zones.append(op.zone)
    elif isinstance(op, (RemoveDoor, RemoveZone)):
        items, kind = (doors, "door") if isinstance(op, RemoveDoor) else (zones, "zone")
        kept = [el for el in items if el.id != op.id]
        if len(kept) == len(items):
            raise _Reject(f"unknown id {op.id} ({kind})")
        if kind == "door":
            doors = kept
        else:
            zones = kept
    elif isinstance(op, UpdateDoor):
        doors = _replace(doors, op.id, "door",
                         _updates(op, ("position", "clear_width", "state", "kind")), Door)
    elif isinstance(op, UpdateZone):
        zones = _replace(zones, op.id, "zone",
                         _updates(op, ("rect", "name", "furniture_seen")), Zone)
    else:
        raise _Reject(f"unsupported op {type(op).__name__}")
    return VenueGraph.model_validate(
        {**graph.model_dump(), "zones": [z.model_dump() for z in zones],
         "doors": [d.model_dump() for d in doors]})


def _error_keys(findings: list[Finding]) -> Counter:
    return Counter((f.code, f.element_id) for f in findings if f.severity == "error")


def apply_patch(graph: VenueGraph, ops: list, video_duration_s: float) -> PatchOutcome:
    current = graph
    errors = _error_keys(check_graph(current, video_duration_s))
    applied: list[int] = []
    rejected: list[tuple[int, str]] = []
    for i, op in enumerate(ops):
        try:
            if op.cite_t_s > video_duration_s:
                raise _Reject(f"cite_t_s {op.cite_t_s}s is outside the {video_duration_s}s video")
            candidate = _apply_one(current, op)
        except _Reject as e:
            rejected.append((i, str(e)))
            continue
        except ValidationError as e:
            first = e.errors()[0]
            rejected.append((i, f"invalid: {'.'.join(map(str, first['loc']))}: {first['msg']}"[:300]))
            continue
        findings = check_graph(candidate, video_duration_s)
        new_errors = _error_keys(findings)
        added = new_errors - errors
        if added:
            msgs = [f"{f.code}: {f.message}" for f in findings
                    if f.severity == "error" and (f.code, f.element_id) in added]
            rejected.append((i, "new error " + "; ".join(msgs)))
            continue
        current, errors = candidate, new_errors
        applied.append(i)
    return PatchOutcome(graph=current, applied=applied, rejected=rejected)
