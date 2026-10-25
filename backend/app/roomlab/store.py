"""Atomic worktree-local JSON store with optimistic revisions."""
from __future__ import annotations
import json,threading,uuid,re,math,os
from pathlib import Path
from .contracts import RoomSceneV1,RoomDraft,Wall,Calibration,CalibrateRequest

class ConflictError(ValueError):pass
class SceneStore:
    def __init__(self,root:Path):
        self.root=root;root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
    def _path(self,id:str):
        if not re.fullmatch(r'[a-zA-Z0-9-]{1,100}',id):raise KeyError(id)
        return self.root/(id+'.json')
    def _write(self,scene):
        path=self._path(scene.scene_id);tmp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        tmp.write_text(scene.model_dump_json(indent=2));os.replace(tmp,path)
    def get(self,id:str)->RoomSceneV1:
        with self.lock:
            try:return RoomSceneV1.model_validate_json(self._path(id).read_text())
            except FileNotFoundError:raise KeyError(id)
    def create(self,draft:RoomDraft,frames=None,source='model_estimate')->RoomSceneV1:
        data=draft.model_dump()
        if not data['walls']:
            data['walls']=[Wall(id=f'wall-{i+1}',start=p,end=draft.floor[(i+1)%len(draft.floor)]).model_dump() for i,p in enumerate(draft.floor)]
        scene=RoomSceneV1(**data,scene_id='scene-'+uuid.uuid4().hex,geometry_source=source,evidence_frames=frames or [])
        with self.lock:self._write(scene)
        return scene
    def import_scene(self,scene:RoomSceneV1):
        # Preserve calibration, provenance and observations; fork identity/revision.
        scene=scene.model_copy(deep=True);scene.scene_id='scene-'+uuid.uuid4().hex;scene.scene_revision=1
        with self.lock:self._write(scene)
        return scene
    def save(self,id,scene:RoomSceneV1,expected:int):
        with self.lock:
            old=self.get(id)
            if old.scene_revision!=expected:raise ConflictError('Scene changed on the server. Reload before saving; your local draft is preserved.')
            if scene.scene_id!=id or scene.scene_revision!=expected:raise ConflictError('Scene identity/revision does not match the saved draft.')
            updated=scene.model_copy(deep=True)
            # Clients cannot manufacture measurement evidence or replace original media metadata.
            if updated.calibration!=old.calibration:raise ValueError('Use the calibration endpoint for measurements.')
            if updated.evidence_frames!=old.evidence_frames:raise ValueError('Source evidence is immutable.')
            updated.geometry_source=old.geometry_source
            old_objects={o.id:o for o in old.objects}
            for obj in updated.objects:
                previous=old_objects.get(obj.id)
                if previous:
                    resized=any(abs(getattr(obj,k)-getattr(previous,k))>1e-7 for k in ('width_m','depth_m','height_m'))
                    if resized and not previous.resize_allowed:raise ValueError('This measured reference is locked against resizing. Use another reference or recalibrate.')
                    if resized or obj.center!=previous.center or obj.yaw_deg!=previous.yaw_deg:
                        obj.provenance.source='user_edit'
            if old.calibration:
                try:changed=abs(dimension(updated,old.calibration.anchor_id,old.calibration.dimension)-dimension(old,old.calibration.anchor_id,old.calibration.dimension))>1e-6
                except ValueError:changed=True
                if changed:
                    updated.calibration=None;updated.notes.append('Anchor geometry changed; remeasure before metre-based clearance checks.')
            updated.scene_revision=expected+1;self._write(updated);return updated
    def calibrate(self,id,request:CalibrateRequest):
        with self.lock:
            scene=self.get(id)
            if scene.scene_revision!=request.expected_revision:raise ConflictError('Scene changed. Reload before calibrating.')
            estimated=dimension(scene,request.anchor_id,request.dimension)
            factor=request.measured_m/estimated
            if not .001<=factor<=1000:raise ValueError('Scale change is out of supported range.')
            original_holdout=None
            if request.holdout_anchor_id:
                if request.holdout_anchor_id==request.anchor_id and request.holdout_dimension==request.dimension:raise ValueError('Held-out measurement must use a different dimension.')
                if not request.holdout_dimension or not request.holdout_measured_m:raise ValueError('Complete the held-out dimension and measurement.')
                original_holdout=dimension(scene,request.holdout_anchor_id,request.holdout_dimension)
            scaled=scene.model_copy(deep=True)
            scaled.floor=[[v*factor for v in p] for p in scaled.floor]
            for wall in scaled.walls:
                wall.start=[v*factor for v in wall.start];wall.end=[v*factor for v in wall.end];wall.height_m*=factor;wall.thickness_m*=factor
            for opening in scaled.openings:
                for attr in ('offset_m','width_m','height_m','sill_m'):setattr(opening,attr,getattr(opening,attr)*factor)
                if opening.width_interval_m:opening.width_interval_m=[v*factor for v in opening.width_interval_m]
            for obj in scaled.objects:
                obj.center=[v*factor for v in obj.center]
                for attr in ('width_m','depth_m','height_m','uncertainty_radius_m'):setattr(obj,attr,getattr(obj,attr)*factor)
                if obj.id==request.anchor_id:obj.resize_allowed=False
            predicted=original_holdout*factor if original_holdout is not None else None
            scaled.calibration=Calibration(anchor_id=request.anchor_id,dimension=request.dimension,measured_m=request.measured_m,
                tolerance_m=request.tolerance_m,original_estimate_m=estimated,scale_factor=factor,holdout_predicted_m=predicted,
                holdout_measured_m=request.holdout_measured_m,holdout_residual_m=(predicted-request.holdout_measured_m) if predicted is not None else None)
            scaled.scene_revision+=1
            # Revalidate scalar limits after scale multiplication.
            scaled=RoomSceneV1.model_validate(scaled.model_dump());self._write(scaled);return scaled

def dimension(scene,id,kind):
    if kind=='wall_length':
        wall=next((w for w in scene.walls if w.id==id),None)
        if wall:return math.dist(wall.start,wall.end)
    else:
        obj=next((o for o in scene.objects if o.id==id),None)
        if obj:return obj.width_m if kind=='object_width' else obj.depth_m
    raise ValueError('Choose an existing wall/object and a matching dimension.')
