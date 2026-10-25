"""Independent measurement checks. Fitting an anchor never counts as validation."""
from __future__ import annotations
import math
from pathlib import Path
from typing import Literal
from pydantic import Field,model_validator
from .contracts import Contract,Finite,RoomSceneV1,geometry_hash
from .fidelity_pipeline import atomic_json

Dimension=Literal['wall_length','wall_height','object_width','object_depth','object_height','opening_width','opening_height','center_distance','yaw_deg']

class ReferenceCheck(Contract):
    element_id:str=Field(min_length=1,max_length=100)
    second_element_id:str|None=None
    dimension:Dimension
    measured_value:Finite
    tolerance:Finite=.02
    @model_validator(mode='after')
    def limits(self):
        if self.tolerance<0 or self.tolerance>100:raise ValueError('Tolerance must be between 0 and 100.')
        if self.dimension!='yaw_deg' and not 0<self.measured_value<=1000:raise ValueError('Length measurements must be positive and at most 1000m.')
        if self.dimension=='yaw_deg' and not -360<=self.measured_value<=360:raise ValueError('Yaw must be within -360 to 360 degrees.')
        if self.dimension=='center_distance' and (not self.second_element_id or self.second_element_id==self.element_id):
            raise ValueError('Choose two different object centers.')
        return self

class AccuracyRequest(Contract):
    expected_revision:int=Field(ge=1)
    references:list[ReferenceCheck]=Field(min_length=1,max_length=50)
    @model_validator(mode='after')
    def distinct(self):
        keys=[(r.element_id,r.dimension,r.second_element_id) for r in self.references]
        if len(keys)!=len(set(keys)):raise ValueError('Duplicate measurement checks are not independent samples.')
        return self


def prediction(scene:RoomSceneV1,check:ReferenceCheck)->float:
    walls={w.id:w for w in scene.walls};objects={o.id:o for o in scene.objects};openings={o.id:o for o in scene.openings}
    kind=check.dimension;key=check.element_id
    if kind in ('wall_length','wall_height') and key in walls:
        return math.dist(walls[key].start,walls[key].end) if kind=='wall_length' else walls[key].height_m
    if kind.startswith('object_') and key in objects:return getattr(objects[key],kind.removeprefix('object_')+'_m')
    if kind.startswith('opening_') and key in openings:return getattr(openings[key],kind.removeprefix('opening_')+'_m')
    if kind=='center_distance' and key in objects and check.second_element_id in objects:
        return math.dist(objects[key].center,objects[check.second_element_id].center)
    if kind=='yaw_deg' and key in objects:return objects[key].yaw_deg
    raise ValueError('Measurement references an unavailable element or incompatible dimension.')


def evaluate(scene:RoomSceneV1,references:list[ReferenceCheck])->dict:
    rows=[];length_errors=[];angle_errors=[]
    for reference in references:
        predicted=prediction(scene,reference)
        error=predicted-reference.measured_value
        angular=reference.dimension=='yaw_deg'
        if angular:error=(error+180)%360-180
        fitted=bool(scene.calibration and scene.calibration.anchor_id==reference.element_id and
                    scene.calibration.dimension==reference.dimension)
        row=dict(**reference.model_dump(),predicted=predicted,error=error,absolute_error=abs(error),
            units='degrees' if angular else 'm',fitted_anchor=fitted,within_tolerance=abs(error)<=reference.tolerance)
        rows.append(row)
        if not fitted:(angle_errors if angular else length_errors).append(error)
    return dict(scene_id=scene.scene_id,scene_revision=scene.scene_revision,geometry_hash=geometry_hash(scene),
        references=rows,independent_length_checks=len(length_errors),independent_angle_checks=len(angle_errors),
        mae_m=sum(abs(e) for e in length_errors)/len(length_errors) if length_errors else None,
        rmse_m=math.sqrt(sum(e*e for e in length_errors)/len(length_errors)) if length_errors else None,
        max_error_m=max(map(abs,length_errors)) if length_errors else None,
        angular_mae_deg=sum(abs(e) for e in angle_errors)/len(angle_errors) if angle_errors else None,
        limitation='Errors apply only to the supplied references. They do not certify the entire room, unseen surfaces, or accessibility. '
                   'A scale-fitting anchor is excluded from independent error metrics.')


def report_for_scene(scene:RoomSceneV1,runtime:Path)->dict:
    import json
    base=dict(scene_id=scene.scene_id,scene_revision=scene.scene_revision,geometry_hash=geometry_hash(scene),
              calibrated=scene.calibration is not None,capture=None,measurements=None)
    capture=runtime/'fidelity-scenes'/(scene.scene_id+'.json')
    if capture.exists():base['capture']=json.loads(capture.read_text())
    check_path=runtime/'accuracy-checks'/(scene.scene_id+'.json')
    if check_path.exists():
        saved=json.loads(check_path.read_text())
        result=evaluate(scene,[ReferenceCheck.model_validate({k:v for k,v in r.items() if k in ReferenceCheck.model_fields}) for r in saved['references']])
        result['saved_at_revision']=saved['scene_revision']
        result['geometry_changed_since_check']=saved['geometry_hash']!=geometry_hash(scene)
        base['measurements']=result
    return base
