import math,json
from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.roomlab.contracts import RoomDraft,RoomObject,RoomSceneV1,Wall,Opening,SolveRequest,CalibrateRequest,Calibration
from backend.app.roomlab.geometry import footprint,free_space
from backend.app.roomlab.validation import validate_scene
from backend.app.roomlab.reachability import solve,find_path
from backend.app.roomlab.store import SceneStore,ConflictError
from backend.app.roomlab.main import create_app

def draft():
    floor=[[0.,0.],[6.,0.],[6.,5.],[0.,5.]]
    return RoomDraft(name='Test room',floor=floor,walls=[Wall(id=f'w{i}',start=p,end=floor[(i+1)%4]) for i,p in enumerate(floor)],
        objects=[RoomObject(id='table',label='Table',center=[3.,2.5],width_m=1.2,depth_m=.8,height_m=.75)])

def scene(tmp_path):return SceneStore(tmp_path).create(draft())
def calibrated(tmp_path):
    store=SceneStore(tmp_path);s=store.create(draft())
    return store.calibrate(s.scene_id,CalibrateRequest(expected_revision=1,anchor_id='w0',dimension='wall_length',measured_m=6.))

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),True,-1.,0.])
def test_invalid_dimension(bad):
    with pytest.raises(ValidationError):RoomObject(id='x',label='x',center=[0.,0.],width_m=bad,depth_m=1.,height_m=1.)

def test_axes_and_rotation():
    o=RoomObject(id='x',label='x',center=[2.,3.],width_m=4.,depth_m=2.,height_m=1.,yaw_deg=90.)
    assert footprint(o).bounds==pytest.approx((1.,1.,3.,5.))
    o.yaw_deg=0.;assert footprint(o).bounds==pytest.approx((0.,2.,4.,4.))

def test_validation_shell_openings_and_evidence(tmp_path):
    s=scene(tmp_path);assert validate_scene(s).valid
    s.openings=[Opening(id='door',wall_id='w0',kind='door',offset_m=5.8,width_m=1.)]
    assert not validate_scene(s).valid
    s.openings=[];s.walls[0].start=[1.,0.];assert not validate_scene(s).valid

def test_selfcrossing_floor(tmp_path):
    s=scene(tmp_path);s.floor=[[0.,0.],[6.,5.],[6.,0.],[0.,5.]]
    assert not validate_scene(s).valid

def test_store_revisions_and_persistence(tmp_path):
    store=SceneStore(tmp_path);s=store.create(draft());s.objects[0].center=[2.,2.]
    saved=store.save(s.scene_id,s,1);assert saved.scene_revision==2
    assert SceneStore(tmp_path).get(s.scene_id).objects[0].center==[2.,2.]
    with pytest.raises(ConflictError):store.save(s.scene_id,s,1)

def test_scale_and_heldout(tmp_path):
    store=SceneStore(tmp_path);s=store.create(draft())
    scaled=store.calibrate(s.scene_id,CalibrateRequest(expected_revision=1,anchor_id='w0',dimension='wall_length',measured_m=12.,holdout_anchor_id='w1',holdout_dimension='wall_length',holdout_measured_m=10.1))
    assert scaled.floor[2]==[12.,10.]
    assert scaled.objects[0].width_m==2.4
    assert scaled.calibration.holdout_residual_m==pytest.approx(-.1)
    assert scaled.geometry_source=='model_estimate'
    assert scaled.objects[0].provenance.source=='model_estimate'

def test_scale_is_not_fabricated_by_patch(tmp_path):
    store=SceneStore(tmp_path);s=store.create(draft())
    s.calibration=Calibration(anchor_id='w0',dimension='wall_length',measured_m=6.,original_estimate_m=6.,scale_factor=1.)
    with pytest.raises(ValueError):store.save(s.scene_id,s,1)

def test_unscaled_and_witness(tmp_path):
    s=scene(tmp_path);req=SolveRequest(expected_revision=1,start=[1.,1.],goal=[5.,1.],agent_diameter_m=.65)
    assert solve(s,req).status=='UNSCALED'
    s=calibrated(tmp_path/'scaled');req.expected_revision=s.scene_revision
    r=solve(s,req);assert r.status=='ROBUST_PASS';assert r.path_length_m==pytest.approx(4.)
    from shapely.geometry import LineString
    assert free_space(s,.345,True).contains(LineString(r.path))

def test_blocked_proof_and_uncertain_topology(tmp_path):
    s=calibrated(tmp_path);s.objects[0].center=[3.,2.5];s.objects[0].width_m=1.;s.objects[0].depth_m=4.86
    req=SolveRequest(expected_revision=2,start=[1.,2.5],goal=[5.,2.5])
    assert solve(s,req).status=='ROBUST_BLOCKED'
    s.openings=[Opening(id='d',wall_id='w0',kind='door',offset_m=1.,width_m=1.,width_interval_m=[.8,1.2])]
    assert solve(s,req).status=='ROBUST_BLOCKED'

def test_window_width_uncertainty_does_not_block_an_independent_route(tmp_path):
    s=calibrated(tmp_path)
    s.openings=[Opening(id='window',wall_id='w0',kind='window',offset_m=1.,width_m=1.,sill_m=1.,height_m=1.,width_interval_m=[.8,1.2])]
    req=SolveRequest(expected_revision=2,start=[1.,1.],goal=[5.,1.])
    assert solve(s,req).status=='ROBUST_PASS'

def test_path_around_furniture(tmp_path):
    s=calibrated(tmp_path);req=SolveRequest(expected_revision=2,start=[1.,2.5],goal=[5.,2.5])
    r=solve(s,req);assert r.status=='ROBUST_PASS';assert len(r.path)>2

def test_clean_app_and_stale_api(tmp_path):
    app=create_app(tmp_path);client=TestClient(app)
    assert client.get('/health').json()['hardware']=='none'
    assert client.get('/api/scenarios/facility-demo').status_code==404
    s=app.state.store.create(draft())
    r=client.patch('/api/roomlab/scenes/'+s.scene_id,json={'expected_revision':1,'scene':s.model_dump(mode='json')})
    assert r.status_code==200 and r.json()['scene_revision']==2
    assert client.patch('/api/roomlab/scenes/'+s.scene_id,json={'expected_revision':1,'scene':s.model_dump(mode='json')}).status_code==409
    assert client.get('/api/roomlab/scenes/'+s.scene_id).json()['scene_revision']==2
    fork=client.post('/api/roomlab/scenes',json=r.json());assert fork.status_code==200
    assert fork.json()['scene_id']!=s.scene_id

def test_missing_key_never_substitutes_scene(tmp_path,monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    client=TestClient(create_app(tmp_path))
    r=client.post('/api/roomlab/extractions',json={'media_id':'media-missing'})
    assert r.status_code==503
    assert list((tmp_path/'scenes').glob('*.json'))==[]

def test_cross_origin_write_refused(tmp_path):
    c=TestClient(create_app(tmp_path))
    assert c.post('/api/roomlab/extractions',json={'media_id':'x'},headers={'origin':'https://unrelated.example'}).status_code==403


def test_network_binding_accepts_same_origin_requests(tmp_path,monkeypatch):
    monkeypatch.setenv('ROOMLAB_HOST','0.0.0.0')
    c=TestClient(create_app(tmp_path),base_url='http://100.75.54.79:8001',client=('100.100.100.1',40000))
    assert c.get('/health').status_code==200
    s=c.app.state.store.create(draft())
    assert c.post('/api/roomlab/scenes',json=s.model_dump(mode='json'),headers={'origin':'http://100.75.54.79:8001'}).status_code==200
    assert c.post('/api/roomlab/scenes',json=s.model_dump(mode='json'),headers={'origin':'https://unrelated.example'}).status_code==403


def test_loopback_default_rejects_remote_client(tmp_path,monkeypatch):
    monkeypatch.delenv('ROOMLAB_HOST',raising=False)
    c=TestClient(create_app(tmp_path),client=('100.100.100.1',40000))
    assert c.get('/health').status_code==403


def test_atrium_void_excluded_from_paths_and_calibration(tmp_path):
    from backend.app.roomlab.contracts import FloorVoid
    from shapely.geometry import Polygon,LineString
    s=calibrated(tmp_path);s.objects=[]
    s.floor_voids=[FloorVoid(id='atrium',polygon=[[2.,1.],[4.,1.],[4.,4.],[2.,4.]])]
    req=SolveRequest(expected_revision=2,start=[1.,2.5],goal=[5.,2.5],agent_diameter_m=.4)
    r=solve(s,req)
    assert r.status=='ROBUST_PASS'
    assert not Polygon(s.floor_voids[0].polygon).intersects(LineString(r.path))
    req.goal=[3.,2.];assert solve(s,req).status=='INVALID_SCENE'
    store=SceneStore(tmp_path);s=store.save(s.scene_id,s,2)
    scaled=store.calibrate(s.scene_id,CalibrateRequest(expected_revision=3,anchor_id='w0',dimension='wall_length',measured_m=12.))
    assert scaled.floor_voids[0].polygon[0]==[4.,2.]


def test_interior_partition_door_controls_reachability(tmp_path):
    s=calibrated(tmp_path);s.objects=[]
    s.walls.append(Wall(id='glass-partition',role='partition',start=[3.,0.],end=[3.,5.]))
    req=SolveRequest(expected_revision=2,start=[1.,2.5],goal=[5.,2.5],agent_diameter_m=.4)
    assert validate_scene(s).valid
    assert solve(s,req).status=='ROBUST_BLOCKED'
    s.openings=[Opening(id='partition-door',wall_id='glass-partition',kind='door',offset_m=2.,width_m=1.)]
    assert solve(s,req).status=='ROBUST_PASS'
    s.openings[0].wall_id='missing'
    assert not validate_scene(s).valid


def test_void_objects_and_stair_warnings(tmp_path):
    from backend.app.roomlab.contracts import FloorVoid
    s=scene(tmp_path)
    s.floor_voids=[FloorVoid(id='atrium',polygon=[[2.,1.],[4.,1.],[4.,4.],[2.,4.]])]
    assert any(i.code=='object_outside' for i in validate_scene(s).issues)
    s.objects[0].center=[1.,1.];s.objects[0].category='stairs';s.objects[0].movable=False
    report=validate_scene(s)
    assert report.valid and any(i.code=='unsupported_stairs' for i in report.issues)
    s.objects[0].label='Potted Plant (Near Stairs)';s.objects[0].category='plant';s.objects[0].movable=True
    assert not any(i.code=='unsupported_stairs' for i in validate_scene(s).issues)
    s.floor_voids[0].polygon=[[7.,1.],[8.,1.],[8.,2.],[7.,2.]]
    assert any(i.code=='invalid_void' for i in validate_scene(s).issues)


def test_unresolved_topology_cannot_claim_reachability(tmp_path):
    s=calibrated(tmp_path);s.topology_review_required=True
    req=SolveRequest(expected_revision=2,start=[1.,1.],goal=[5.,1.])
    assert solve(s,req).status=='INVALID_SCENE'
    assert any(i.code=='topology_review_required' for i in validate_scene(s).issues)
