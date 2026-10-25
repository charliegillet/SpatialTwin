from __future__ import annotations
import math
from shapely.geometry import Polygon,LineString
from .contracts import RoomSceneV1,ValidationReport,ValidationIssue
from .geometry import footprint,wall_length,wall_solids,floor_polygon,EPS

def validate_scene(scene:RoomSceneV1)->ValidationReport:
    issues=[]
    def add(code,message,ids=None,severity='error'):
        issues.append(ValidationIssue(code=code,message=message,element_ids=ids or [],severity=severity))
    outer=Polygon(scene.floor)
    floor=floor_polygon(scene)
    if scene.topology_review_required:add('topology_review_required','Extraction repaired or omitted architectural topology. Inspect and correct voids and boundaries before clearing the review flag.')
    if not floor.is_valid or floor.area<EPS:add('invalid_floor','Floor must be a simple, nonzero-area polygon.')
    ids=[x.id for x in scene.walls+scene.openings+scene.objects+scene.floor_voids]
    if len(ids)!=len(set(ids)):add('duplicate_id','Every scene element needs a unique ID.')
    walls={w.id:w for w in scene.walls}
    shell=[w for w in scene.walls if w.role=='shell']
    if len(shell)!=len(scene.floor):add('shell_edges','Every floor edge needs one matching wall.')
    for i,wall in enumerate(shell):
        if wall_length(wall)<EPS:add('zero_wall','Wall length must be positive.',[wall.id]);continue
        if i<len(scene.floor) and (math.dist(wall.start,scene.floor[i])>1e-4 or math.dist(wall.end,scene.floor[(i+1)%len(scene.floor)])>1e-4):
            add('wall_floor_mismatch','Wall sequence must match the floor boundary.',[wall.id])
    for void in scene.floor_voids:
        poly=Polygon(void.polygon)
        if not poly.is_valid or poly.area<EPS or not outer.contains(poly):
            add('invalid_void','Floor void must be a simple polygon strictly inside the outer boundary.',[void.id])
    for wall in scene.walls:
        if wall.role!='shell':
            if wall_length(wall)<EPS:add('zero_wall','Wall length must be positive.',[wall.id])
            elif not outer.buffer(EPS).covers(LineString([wall.start,wall.end])):
                add('partition_outside','Interior boundary extends beyond the outer shell.',[wall.id])
    for obj in scene.objects:
        if 'stair' in obj.category.lower() or obj.label.lower().startswith(('stair','interior stair','exterior stair')):
            add('unsupported_stairs','Staircase is a fixed obstruction placeholder. Steps, upper floors and stair travel are not reconstructed.',[obj.id],'warning')
            if obj.movable:add('movable_stairs','Staircase must be fixed.',[obj.id])
    add('visual_unverified','Geometry checks test model consistency, not agreement with video; verify floor voids, partitions and dimensions against evidence.',severity='warning')
    for opening in scene.openings:
        wall=walls.get(opening.wall_id)
        if wall is None:add('unknown_wall','Opening references a missing wall.',[opening.id]);continue
        if opening.offset_m+opening.width_m>wall_length(wall)+EPS:add('opening_outside_wall','Opening extends past its wall.',[opening.id])
        if opening.sill_m+opening.height_m>wall.height_m+EPS:add('opening_above_wall','Opening extends above the wall.',[opening.id])
        if opening.width_interval_m and not (opening.width_interval_m[0]<=opening.width_m<=opening.width_interval_m[1]):
            add('invalid_interval','Opening width must lie inside its ordered interval.',[opening.id])
    for i,a in enumerate(scene.openings):
        for b in scene.openings[i+1:]:
            if a.wall_id==b.wall_id and min(a.offset_m+a.width_m,b.offset_m+b.width_m)>max(a.offset_m,b.offset_m)+EPS and min(a.sill_m+a.height_m,b.sill_m+b.height_m)>max(a.sill_m,b.sill_m)+EPS:
                add('overlapping_openings','Openings overlap on the same wall.',[a.id,b.id])
    if floor.is_valid:
        solids=wall_solids(scene)
        for obj in scene.objects:
            if not floor.buffer(EPS).covers(footprint(obj)):add('object_outside','Object footprint extends outside the modeled floor.',[obj.id])
            if any(footprint(obj).intersection(p).area>1e-5 for p in solids):add('object_wall_overlap','Object footprint intersects a modeled solid wall.',[obj.id])
        for i,a in enumerate(scene.objects):
            for b in scene.objects[i+1:]:
                if footprint(a).intersection(footprint(b)).area>1e-5:
                    add('object_overlap','Approximate object boxes overlap; verify support or placement.',[a.id,b.id],'warning')
    known={f.frame_id for f in scene.evidence_frames}
    for element in scene.walls+scene.openings+scene.objects+scene.floor_voids:
        if any(x not in known for x in element.provenance.evidence_frame_ids):add('missing_evidence','Element references an unknown evidence frame.',[element.id])
    if scene.calibration is None:add('unscaled','Dimensions are model estimates until a measured reference is supplied.',severity='warning')
    return ValidationReport(valid=not any(x.severity=='error' for x in issues),issues=issues)
