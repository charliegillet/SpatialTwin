"""Canonical RoomLab contracts. Revisions and receipts are application-owned."""
from __future__ import annotations
import hashlib
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Positive = Annotated[float, Field(strict=True, gt=0, le=1000, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(strict=True, ge=0, le=1000, allow_inf_nan=False)]
Point2 = Annotated[list[Finite], Field(min_length=2, max_length=2)]
Interval = Annotated[list[Nonnegative], Field(min_length=2, max_length=2)]
HexColor = Annotated[str, Field(pattern=r'^#[0-9a-f]{6}$')]
FloorMaterial = Literal['wood','tile','stone','terrazzo','carpet','concrete','unknown']

class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Provenance(Contract):
    source: Literal['model_estimate','geometry_fit','user_edit','user_measurement'] = 'model_estimate'
    visibility: Literal['observed','partial','unobserved'] = 'partial'
    evidence_frame_ids: list[str] = Field(default_factory=list, max_length=100)
    note: str = Field(default='', max_length=1000)

class EvidenceFrame(Contract):
    frame_id: str
    media_id: str
    timestamp_s: Nonnegative
    url: str
    relative_path: str

class MediaRecord(Contract):
    media_id: str
    filename: str
    mime_type: Literal['video/mp4','video/webm','video/quicktime']
    duration_s: Positive
    video_url: str
    frames: list[EvidenceFrame]

class FloorVoid(Contract):
    id: str = Field(min_length=1,max_length=80)
    polygon: Annotated[list[Point2],Field(min_length=3,max_length=100)]
    provenance: Provenance = Field(default_factory=Provenance)

class Wall(Contract):
    role: Literal['shell','partition','railing'] = 'shell'
    id: str = Field(min_length=1,max_length=80)
    start: Point2
    end: Point2
    height_m: Positive = 2.7
    thickness_m: Positive = .12
    provenance: Provenance = Field(default_factory=Provenance)

class Opening(Contract):
    id: str
    wall_id: str
    kind: Literal['door','window','passage']
    offset_m: Nonnegative
    width_m: Positive
    height_m: Positive = 2.1
    sill_m: Nonnegative = 0
    width_interval_m: Interval | None = None
    provenance: Provenance = Field(default_factory=Provenance)

class RoomObject(Contract):
    id: str = Field(min_length=1,max_length=80)
    label: str = Field(min_length=1,max_length=160)
    category: str = Field(default='furniture',max_length=80)
    center: Point2
    width_m: Positive
    depth_m: Positive
    height_m: Positive
    yaw_deg: Finite = 0
    movable: bool = True
    resize_allowed: bool = True
    uncertainty_radius_m: Nonnegative = 0
    color: HexColor | None = None
    provenance: Provenance = Field(default_factory=Provenance)

class RoomAppearance(Contract):
    wall_color: HexColor | None = None
    floor_color: HexColor | None = None
    floor_material: FloorMaterial = 'unknown'

class Calibration(Contract):
    anchor_id: str
    dimension: Literal['wall_length','object_width','object_depth']
    measured_m: Positive
    tolerance_m: Nonnegative = .01
    original_estimate_m: Positive
    scale_factor: Positive
    holdout_predicted_m: Positive | None = None
    holdout_measured_m: Positive | None = None
    holdout_residual_m: Finite | None = None

class RoomDraft(Contract):
    topology_review_required: bool = False
    name: str = Field(default='Estimated room',min_length=1,max_length=160)
    floor: Annotated[list[Point2],Field(min_length=3,max_length=100)]
    floor_voids: list[FloorVoid] = Field(default_factory=list,max_length=30)
    walls: list[Wall] = Field(default_factory=list,max_length=100)
    openings: list[Opening] = Field(default_factory=list,max_length=100)
    objects: list[RoomObject] = Field(default_factory=list,max_length=200)
    notes: list[str] = Field(default_factory=list,max_length=30)
    appearance: RoomAppearance | None = None

class RoomSceneV1(RoomDraft):
    schema_version: Literal['1.0'] = '1.0'
    scene_id: str
    scene_revision: int = Field(default=1,ge=1)
    units: Literal['m'] = 'm'
    up_axis: Literal['Y'] = 'Y'
    geometry_source: Literal['model_estimate','user_authored','geometry_fit'] = 'model_estimate'
    calibration: Calibration | None = None
    evidence_frames: list[EvidenceFrame] = Field(default_factory=list)

class RoomDraftResult(Contract):
    draft: RoomDraft
    model: str = 'gemini-4-argon'
    provenance: Literal['live'] = 'live'
    latency_ms: Annotated[float, Field(ge=0, le=600000, allow_inf_nan=False)]
    warnings: list[str] = Field(default_factory=list)

class ValidationIssue(Contract):
    code: str
    message: str
    element_ids: list[str] = Field(default_factory=list)
    severity: Literal['error','warning'] = 'error'

class ValidationReport(Contract):
    valid: bool
    issues: list[ValidationIssue]

class EditSceneRequest(Contract):
    expected_revision: int = Field(ge=1)
    scene: RoomSceneV1

class CalibrateRequest(Contract):
    expected_revision: int = Field(ge=1)
    anchor_id: str
    dimension: Literal['wall_length','object_width','object_depth']
    measured_m: Positive
    tolerance_m: Nonnegative = .01
    holdout_anchor_id: str | None = None
    holdout_dimension: Literal['wall_length','object_width','object_depth'] | None = None
    holdout_measured_m: Positive | None = None

class SolveRequest(Contract):
    expected_revision: int = Field(ge=1)
    start: Point2
    goal: Point2
    agent_diameter_m: Positive = .65
    margin_m: Nonnegative = .02

class SolveResult(Contract):
    status: Literal['ROBUST_PASS','ROBUST_BLOCKED','INCONCLUSIVE','INVALID_SCENE','UNSCALED']
    scene_revision: int
    geometry_hash: str
    path: list[Point2] = Field(default_factory=list)
    path_length_m: Nonnegative | None = None
    minimum_clearance_m: Nonnegative | None = None
    message: str
    assumptions: list[str]
    obstacles: list[list[Point2]] = Field(default_factory=list)
    evidence_requests: list[str] = Field(default_factory=list)

class OptimizeResult(Contract):
    status: Literal['FOUND','NO_CANDIDATE','ALREADY_PASSABLE','UNAVAILABLE']
    message: str
    candidates_checked: int = 0
    object_id: str | None = None
    translation: Point2 | None = None
    scene: RoomSceneV1 | None = None
    before: SolveResult
    after: SolveResult | None = None

class ExtractRequest(Contract):
    media_id: str

class JobRecord(Contract):
    job_id: str
    status: Literal['queued','running','completed','failed','cancelled']
    media_id: str
    scene_id: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    model: str | None = None
    latency_ms: float | None = None

def geometry_hash(scene: RoomSceneV1) -> str:
    # Colors are presentation only; recoloring must not invalidate solver receipts.
    payload = scene.model_dump(mode='json',exclude={'evidence_frames':True,'notes':True,'name':True,'appearance':True,'objects':{'__all__':{'color'}}})
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
