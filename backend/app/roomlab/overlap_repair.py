"""Bounded optional box-separation proposals, never automatic scene normalization."""
from __future__ import annotations
import math,time
from .contracts import RoomSceneV1,RepairRequest,RepairResult,LayoutChange,geometry_hash
from .geometry import footprint
from .validation import validate_scene


def overlap_pairs(scene):
    shapes=[footprint(o) for o in scene.objects]
    return {(a.id,b.id):shapes[i].intersection(shapes[j]).area
            for i,a in enumerate(scene.objects) for j,b in enumerate(scene.objects) if j>i
            and shapes[i].intersection(shapes[j]).area>1e-5}


def separating_moves(a,b,gap=.01):
    """Generate separating translations along both boxes' SAT axes, including containment."""
    pa=list(footprint(a).exterior.coords)[:-1];pb=list(footprint(b).exterior.coords)[:-1]
    moves=[]
    for polygon in (pa,pb):
        for i in range(2):
            dx=polygon[i+1][0]-polygon[i][0];dz=polygon[i+1][1]-polygon[i][1]
            length=math.hypot(dx,dz)
            nx,nz=-dz/length,dx/length
            aa=[x*nx+z*nz for x,z in pa];bb=[x*nx+z*nz for x,z in pb]
            for delta in (max(bb)-min(aa)+gap,min(bb)-max(aa)-gap):
                moves.append((nx*delta,nz*delta))
    return sorted(moves,key=lambda v:math.hypot(*v))


def repair_overlaps(scene:RoomSceneV1,request:RepairRequest)->RepairResult:
    before=overlap_pairs(scene)
    base=dict(scene_revision=scene.scene_revision,geometry_hash=geometry_hash(scene),
              before_overlap_pairs=[list(p) for p in before])
    if not validate_scene(scene).valid:
        return RepairResult(**base,status='UNAVAILABLE',message='Correct architectural issues before proposing box separation.',after_overlap_pairs=[list(p) for p in before])
    if not before:return RepairResult(**base,status='NO_CHANGE',message='No overlapping object boxes were found.',after_overlap_pairs=[])
    candidate=scene.model_copy(deep=True);original={o.id:o for o in scene.objects};deadline=time.monotonic()+2
    for _ in range(20):
        current=overlap_pairs(candidate)
        if not current or time.monotonic()>deadline:break
        accepted=False;lookup={o.id:o for o in candidate.objects}
        for pair in sorted(current):
            for aid,bid in (pair,tuple(reversed(pair))):
                a,b=lookup[aid],lookup[bid]
                if not a.movable:continue
                for dx,dz in separating_moves(a,b):
                    if time.monotonic()>deadline:break
                    center=[a.center[0]+dx,a.center[1]+dz]
                    if math.dist(center,original[aid].center)>request.max_displacement_m+1e-7:continue
                    trial=candidate.model_copy(deep=True);moved=next(o for o in trial.objects if o.id==aid);moved.center=center
                    if not validate_scene(trial).valid:continue
                    after=overlap_pairs(trial)
                    # Never create another conflict while resolving this one.
                    if not set(after)<=set(current) or sum(after.values())>=sum(current.values())-1e-6:continue
                    candidate=trial;accepted=True;break
                if accepted:break
            if accepted:break
        if not accepted:break
    changes=[]
    for obj in candidate.objects:
        old=original[obj.id]
        if math.dist(obj.center,old.center)>1e-7:
            changes.append(LayoutChange(object_id=obj.id,from_center=old.center,to_center=obj.center,from_yaw_deg=old.yaw_deg,to_yaw_deg=obj.yaw_deg))
            obj.provenance.source='geometry_fit';obj.provenance.visibility='partial'
            obj.provenance.note=(f'Proposed box separation from {old.center} to {[round(v,4) for v in obj.center]}; verify against video. Bounds may overlap legitimately. '+old.provenance.note)[:1000]
    remaining=overlap_pairs(candidate)
    if not changes:
        return RepairResult(**base,status='NO_CHANGE',message='No bounded separation found. Fixed objects and source geometry were preserved; some overlaps may be intentional.',after_overlap_pairs=[list(p) for p in remaining])
    return RepairResult(**base,status='PARTIAL' if remaining else 'FOUND',
        message='Optional geometry-fit preview. Compare with evidence before applying; this is not a verified reconstruction or movement plan.',
        changes=changes,scene=candidate,after_overlap_pairs=[list(p) for p in remaining])
