import asyncio,hashlib,time
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.roomlab.main import create_app
from backend.app.roomlab.contracts import (RoomDraft,RoomObject,FloorVoid,RepairRequest,EvidenceFrame,
    CritiqueResult,CritiqueFinding,geometry_hash)
from backend.app.roomlab.overlap_repair import repair_overlaps
from backend.app.roomlab.critique_service import frame_bytes


def draft(fixed=False):
    return RoomDraft(floor=[[0.,0.],[6.,0.],[6.,5.],[0.,5.]],objects=[
        RoomObject(id='fixed',label='Counter',center=[2.,2.],width_m=1.,depth_m=1.,height_m=1.,movable=False),
        RoomObject(id='move',label='Chair',center=[2.7,2.],width_m=1.,depth_m=1.,height_m=.8,movable=not fixed)])


def app_scene(tmp_path):
    app=create_app(tmp_path);root=tmp_path/'media';folder=root/'media-test';folder.mkdir()
    Image.new('RGB',(160,100),'tan').save(folder/'frame.jpg')
    frame=EvidenceFrame(frame_id='frame-1',media_id='media-test',timestamp_s=0.,url='/media/media-test/frame.jpg',relative_path='media-test/frame.jpg')
    scene=app.state.store.create(draft(),[frame]);return app,scene


def response(context,**overrides):
    data=dict(scene_id=context.scene.scene_id,scene_revision=context.scene.scene_revision,
       geometry_hash=context.geometry_hash,evidence_hash=context.evidence_hash,
       reviewed_frame_ids=[f.record.frame_id for f in context.frames],summary='Compare with the source.',latency_ms=1.,
       findings=[CritiqueFinding(kind='needs_evidence',element_ids=['move'],frame_ids=['frame-1'],message='Measure this object.')])
    data.update(overrides);return CritiqueResult(**data)


def start(client,scene):
    r=client.get(f'/api/roomlab/scenes/{scene.scene_id}/receipt');r.raise_for_status();receipt=r.json()
    return client.post(f'/api/roomlab/scenes/{scene.scene_id}/critique',json={
      'expected_revision':scene.scene_revision,'geometry_hash':receipt['geometry_hash'],'evidence_hash':receipt['evidence_hash']})


def finish(client,id):
    for _ in range(100):
        r=client.get('/api/roomlab/critique-jobs/'+id).json()
        if r['status'] not in ('queued','running'):return r
        time.sleep(.01)
    raise AssertionError('Review job did not finish')


def test_overlap_preview_keeps_original_and_fixed_geometry(tmp_path):
    app,scene=app_scene(tmp_path);before=scene.model_dump_json()
    r=repair_overlaps(scene,RepairRequest(expected_revision=1,max_displacement_m=.5))
    assert r.status=='FOUND' and not r.after_overlap_pairs
    assert scene.model_dump_json()==before and r.geometry_hash==geometry_hash(scene)
    assert r.scene.objects[0]==scene.objects[0]
    change=r.changes[0];assert change.object_id=='move'
    assert r.scene.objects[1].provenance.source=='geometry_fit'
    assert r.scene.objects[1].provenance.visibility=='partial'
    assert sum((x-y)**2 for x,y in zip(change.from_center,change.to_center))<=.5**2
    with TestClient(app) as c:
        api=c.post(f'/api/roomlab/scenes/{scene.scene_id}/repair-overlaps',json={'expected_revision':1})
        assert api.status_code==200 and api.json()['scene']
        assert c.get(f'/api/roomlab/scenes/{scene.scene_id}').json()['scene_revision']==1
        assert c.post(f'/api/roomlab/scenes/{scene.scene_id}/repair-overlaps',json={'expected_revision':2}).status_code==409


def test_fixed_fixed_or_too_small_budget_remains_unresolved(tmp_path):
    app,scene=app_scene(tmp_path);scene.objects[1].movable=False
    r=repair_overlaps(scene,RepairRequest(expected_revision=1));assert r.status=='NO_CHANGE' and r.scene is None
    scene.objects[1].movable=True
    r=repair_overlaps(scene,RepairRequest(expected_revision=1,max_displacement_m=.05));assert r.status=='NO_CHANGE'
    scene.topology_review_required=True
    assert repair_overlaps(scene,RepairRequest(expected_revision=1)).status=='UNAVAILABLE'


def test_rotated_overlap_and_void_are_never_invalidated(tmp_path):
    from backend.app.roomlab.validation import validate_scene
    app,scene=app_scene(tmp_path);scene.objects[1].yaw_deg=30.
    scene.floor_voids=[FloorVoid(id='void',polygon=[[3.5,1.],[5.,1.],[5.,3.],[3.5,3.]])]
    r=repair_overlaps(scene,RepairRequest(expected_revision=1,max_displacement_m=1.))
    if r.scene:assert validate_scene(r.scene).valid and r.scene.floor_voids==scene.floor_voids


def test_critique_job_is_grounded_and_read_only(tmp_path):
    app,scene=app_scene(tmp_path);before=scene.model_dump_json()
    async def provider(context,api_key=None):
        assert context.bev_png.startswith(b'\x89PNG') and context.frames[0].jpeg_bytes.startswith(b'\xff\xd8')
        assert context.scene.floor==scene.floor and context.validation.valid
        return response(context)
    app.state.critic.provider=provider
    with TestClient(app) as c:
        preview=c.get(f'/api/roomlab/scenes/{scene.scene_id}/preview.png?revision=1');assert preview.status_code==200 and preview.content.startswith(b'\x89PNG')
        assert c.get(f'/api/roomlab/scenes/{scene.scene_id}/preview.png?revision=2').status_code==409
        r=start(c,scene);assert r.status_code==202
        result=finish(c,r.json()['job_id']);assert result['status']=='completed' and result['result']['reviewed_frame_ids']==['frame-1']
        assert app.state.store.get(scene.scene_id).model_dump_json()==before


@pytest.mark.parametrize('failure',['frame','element','receipt'])
def test_invalid_critic_references_or_receipt_never_publish(tmp_path,failure):
    app,scene=app_scene(tmp_path)
    async def provider(context,api_key=None):
        if failure=='receipt':return response(context,geometry_hash='wrong')
        finding=CritiqueFinding(kind='observation',element_ids=['wrong'] if failure=='element' else ['move'],frame_ids=['wrong'] if failure=='frame' else ['frame-1'],message='Untrusted claim')
        return response(context,findings=[finding])
    app.state.critic.provider=provider
    with TestClient(app) as c:
        r=start(c,scene);job=finish(c,r.json()['job_id']);assert job['status']=='failed' and job['result'] is None
        assert app.state.store.get(scene.scene_id).scene_revision==1


def test_stale_review_and_cancel_are_not_completed(tmp_path):
    app,scene=app_scene(tmp_path)
    async def provider(context,api_key=None):
        await asyncio.sleep(.15);return response(context)
    app.state.critic.provider=provider
    with TestClient(app) as c:
        r=start(c,scene);id=r.json()['job_id']
        scene.objects[1].center=[3.,2.]
        app.state.store.save(scene.scene_id,scene,1)
        job=finish(c,id);assert job['status']=='failed' and job['result'] is None
        # The old receipt cannot authorize another review.
        old=c.post(f'/api/roomlab/scenes/{scene.scene_id}/critique',json={'expected_revision':1,'geometry_hash':r.json()['geometry_hash'],'evidence_hash':r.json()['evidence_hash']})
        assert old.status_code==409
        current=app.state.store.get(scene.scene_id);r=start(c,current)
        cancelled=c.delete('/api/roomlab/critique-jobs/'+r.json()['job_id']).json();assert cancelled['status']=='cancelled'


def test_evidence_path_safety_and_missing_source(tmp_path):
    with pytest.raises(ValueError):frame_bytes(tmp_path,'../../secret.txt')
    app,scene=app_scene(tmp_path);(tmp_path/'media/media-test/frame.jpg').unlink()
    async def provider(context,api_key=None):raise AssertionError('No source must not call provider')
    app.state.critic.provider=provider
    with TestClient(app) as c:
        r=start(c,scene);job=finish(c,r.json()['job_id']);assert job['status']=='failed'
        assert 'Source evidence' in job['error']


def test_rotation_only_candidate_can_open_a_narrow_room(tmp_path):
    from backend.app.roomlab.store import SceneStore
    from backend.app.roomlab.contracts import CalibrateRequest,SolveRequest
    from backend.app.roomlab.optimizer import optimize
    from backend.app.roomlab.reachability import solve
    store=SceneStore(tmp_path)
    scene=store.create(RoomDraft(floor=[[0.,0.],[6.,0.],[6.,2.1],[0.,2.1]],objects=[
        RoomObject(id='blocker',label='Long table',center=[3.,1.05],width_m=.3,depth_m=1.8,height_m=.8)]))
    scene=store.calibrate(scene.scene_id,CalibrateRequest(expected_revision=1,anchor_id='wall-1',dimension='wall_length',measured_m=6.))
    request=SolveRequest(expected_revision=2,start=[.7,1.05],goal=[5.3,1.05],agent_diameter_m=.6)
    original=scene.model_dump()
    result=optimize(scene,request)
    assert result.status=='FOUND' and abs(result.rotation_delta_deg)==90.
    assert result.translation==[0.,0.] and scene.model_dump()==original
    assert result.after.geometry_hash==geometry_hash(result.scene)
    assert solve(result.scene,request).status=='ROBUST_PASS'


def test_bev_grid_is_bounded_for_extreme_imported_coordinates(tmp_path):
    from backend.app.roomlab.scene_preview import render_scene_preview
    from backend.app.roomlab.store import SceneStore
    scene=SceneStore(tmp_path).create(RoomDraft(floor=[[0.,0.],[1e9,0.],[1e9,1e9],[0.,1e9]]))
    started=time.monotonic()
    assert render_scene_preview(scene).startswith(b'\x89PNG')
    assert time.monotonic()-started<2.
