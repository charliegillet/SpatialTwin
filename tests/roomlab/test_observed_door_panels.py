"""Static observed leaf boxes must affect clearance, not just look like doors."""
from backend.app.roomlab.contracts import RoomDraft,RoomObject,Wall,Opening,CalibrateRequest,SolveRequest,geometry_hash
from backend.app.roomlab.store import SceneStore
from backend.app.roomlab.validation import validate_scene
from backend.app.roomlab.reachability import solve


def test_observed_static_door_leaf_reduces_the_modeled_aperture(tmp_path):
    store=SceneStore(tmp_path)
    scene=store.create(RoomDraft(floor=[[0.,0.],[6.,0.],[6.,6.],[0.,6.]]))
    scene.walls.append(Wall(id='partition',role='partition',start=[3.,0.],end=[3.,6.]))
    scene.openings=[Opening(id='entry',wall_id='partition',kind='door',offset_m=2.,width_m=2.)]
    scene=store.save(scene.scene_id,scene,1)
    scene=store.calibrate(scene.scene_id,CalibrateRequest(expected_revision=2,anchor_id='wall-1',dimension='wall_length',measured_m=6.))
    request=SolveRequest(expected_revision=3,start=[1.,2.5],goal=[5.,2.5],agent_diameter_m=1.2,margin_m=.01)
    assert solve(scene,request).status=='ROBUST_PASS'
    old_hash=geometry_hash(scene)
    scene.objects=[RoomObject(id='closed-leaf',category='door_leaf',label='Observed closed south leaf',center=[3.,3.5],width_m=.96,depth_m=.035,height_m=2.1,yaw_deg=90.,movable=False),
                   RoomObject(id='open-leaf',category='door_leaf',label='Observed propped north leaf',center=[2.52,2.04],width_m=.96,depth_m=.035,height_m=2.1,yaw_deg=180.,movable=False)]
    assert validate_scene(scene).valid
    assert geometry_hash(scene)!=old_hash
    assert solve(scene,request).status=='ROBUST_BLOCKED'
    request.agent_diameter_m=.6
    assert solve(scene,request).status=='ROBUST_PASS'


def test_provider_static_leaf_keeps_thin_depth_and_requires_evidence():
    from backend.app.roomlab.provider_schema import ProviderRoomPayload,normalize_provider_payload
    payload={'floor_vertices':[{'x_m':0.,'z_m':0.},{'x_m':6.,'z_m':0.},{'x_m':6.,'z_m':6.},{'x_m':0.,'z_m':6.}],
             'objects':[{'id':'leaf','label':'Observed glass leaf','category':'door_leaf','x_m':3.,'z_m':3.,'width_m':.96,'depth_m':.035,'height_m':2.1,'yaw_deg':90.,'movable':True,'evidence_frame_ids':['frame-1']}]}
    draft,warnings=normalize_provider_payload(ProviderRoomPayload.model_validate(payload),{'frame-1'})
    assert draft.objects[0].depth_m==.035 and not draft.objects[0].movable
    assert draft.objects[0].provenance.evidence_frame_ids==['frame-1']
    payload['objects'][0]['evidence_frame_ids']=['invented']
    draft,warnings=normalize_provider_payload(ProviderRoomPayload.model_validate(payload),{'frame-1'})
    assert draft.objects==[] and draft.topology_review_required
    assert any('uncited static door leaf' in w for w in warnings)
