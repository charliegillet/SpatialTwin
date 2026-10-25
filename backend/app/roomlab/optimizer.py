from __future__ import annotations
import math,time
from .contracts import RoomSceneV1,SolveRequest,OptimizeResult
from .reachability import solve
from .validation import validate_scene
from .geometry import footprint

def optimize(scene:RoomSceneV1,request:SolveRequest)->OptimizeResult:
    before=solve(scene,request)
    if before.status=='ROBUST_PASS':return OptimizeResult(status='ALREADY_PASSABLE',message='A verified path already exists.',before=before)
    if before.status in ('UNSCALED','INVALID_SCENE'):return OptimizeResult(status='UNAVAILABLE',message=before.message,before=before)
    candidates=[]
    for i,obj in enumerate(scene.objects):
        if not obj.movable:continue
        for dx,dz in [(x*.2,z*.2) for x in range(-4,5) for z in range(-4,5) if (x or z) and math.hypot(x*.2,z*.2)<=.800001]:
            candidates.append((math.hypot(dx,dz),obj.id,i,dx,dz,0.))
        for yaw in (-90.,-45.,-15.,15.,45.,90.):
            candidates.append((.2+abs(yaw)/450,obj.id,i,0.,0.,yaw))
    checked=0;deadline=time.monotonic()+4
    for _,_,index,dx,dz,yaw in sorted(candidates)[:120]:
        if time.monotonic()>deadline:break
        candidate=scene.model_copy(deep=True);obj=candidate.objects[index]
        obj.center=[obj.center[0]+dx,obj.center[1]+dz];obj.yaw_deg=(obj.yaw_deg+yaw+180)%360-180
        checked+=1
        if not validate_scene(candidate).valid:continue
        if any(footprint(obj).intersection(footprint(other)).area>1e-6 for j,other in enumerate(candidate.objects) if j!=index):continue
        # Finalize every field included in the receipt hash before verifying.
        obj.provenance.source='user_edit';obj.provenance.note='Proposed final-layout translation/yaw; movement sweep is not modeled.'
        after=solve(candidate,request)
        if after.status=='ROBUST_PASS':
            return OptimizeResult(status='FOUND',message='First verified candidate in a bounded ordered one-object translation/yaw search. Final pose only; not a movement plan.',
                candidates_checked=checked,object_id=obj.id,translation=[dx,dz],rotation_delta_deg=yaw,scene=candidate,before=before,after=after)
    return OptimizeResult(status='NO_CANDIDATE',message='No verified candidate within the 120-candidate / 4-second, 0.8 m translation / selected ±15,45,90 degree yaw budget. Not a proof of infeasibility.',candidates_checked=checked,before=before)
