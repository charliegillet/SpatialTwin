"""Geometry fitting and sensor imports fail closed on ambiguous topology/scale."""
import copy
import numpy as np
import pytest
from fastapi.testclient import TestClient
from backend.app.roomlab.geometry_floor import fit_floor
from backend.app.roomlab.roomplan_import import import_roomplan
from backend.app.roomlab.contracts import GeometryReport,GeometryPoint,GeometryFloorRequest
from backend.app.roomlab.main import create_app


def report():
    return GeometryReport(media_id='media-test',source_sha256='a'*64,engine='offline-fixture',registered_frames=3,
        selected_frames=4,component_count=1,mean_reprojection_error_px=.5,cameras=[],warnings=[],
        points=[GeometryPoint(id=i,xyz=p,rgb=[1,2,3],error_px=.5) for i,p in enumerate([[0,0,0],[2,0,0],[2,0,3],[0,0,3],[0,1,0]])])


def test_geometry_floor_uses_actual_measurement_and_checks_plane():
    req=GeometryFloorRequest(point_ids=[0,1,2,3],first_edge_measured_m=4,measurement_confirmed=True,topology_confirmed=True)
    draft=fit_floor(report(),req)
    assert np.linalg.norm(np.array(draft.floor[1])-draft.floor[0])==pytest.approx(4)
    assert draft.topology_review_required and all(w.provenance.source=='geometry_fit' for w in draft.walls)
    with pytest.raises(ValueError,match='Confirm'):fit_floor(report(),req.model_copy(update={'measurement_confirmed':False}))
    with pytest.raises(ValueError,match='coplanar'):fit_floor(report(),req.model_copy(update={'point_ids':[0,1,2,4]}))
    with pytest.raises(ValueError,match='crosses'):fit_floor(report(),req.model_copy(update={'point_ids':[0,2,1,3]}))
    with pytest.raises(ValueError,match='not in'):fit_floor(report(),req.model_copy(update={'point_ids':[0,1,999]}))


def surface(width,x,z,yaw=0,height=2.7):
    c,s=np.cos(yaw),np.sin(yaw)
    matrix=np.array([[c,0,s,x],[0,1,0,height/2],[-s,0,c,z],[0,0,0,1.]])
    return {'dimensions':[width,height,0.0],'transform':matrix.T.tolist()}


def room():
    return {'name':'Explicit offline RoomPlan fixture','walls':[
        surface(4,2,0),surface(3,4,1.5,-np.pi/2),surface(4,2,3),surface(3,0,1.5,-np.pi/2)],'objects':[]}


def test_roomplan_single_level_geometry_and_bad_transforms():
    draft=import_roomplan(room())
    assert len(draft.floor)==4 and len(draft.walls)==4 and draft.topology_review_required
    from backend.app.roomlab.validation import validate_scene
    from backend.app.roomlab.contracts import RoomSceneV1
    errors=[i.code for i in validate_scene(RoomSceneV1(scene_id='offline',**draft.model_dump())).issues if i.severity=='error']
    assert errors==['topology_review_required']
    bad=room();bad['walls'][0]['transform'][0][0]=2
    with pytest.raises(ValueError,match='rigid'):import_roomplan(bad)
    bad=room();bad['walls'][0]['transform'][3][1]+=1
    with pytest.raises(ValueError,match='levels'):import_roomplan(bad)
    bad=room();bad['walls'].pop()
    with pytest.raises(ValueError,match='closed'):import_roomplan(bad)
    bad=room();bad['walls'][0]['curve']={'radius':2}
    with pytest.raises(ValueError,match='Curved'):import_roomplan(bad)


def test_roomplan_import_api_creates_separate_estimated_scene(tmp_path):
    with TestClient(create_app(tmp_path/'runtime')) as client:
        response=client.post('/api/roomlab/imports/roomplan',json=room())
        assert response.status_code==200,response.text
        scene=response.json()
        assert scene['geometry_source']=='geometry_fit' and scene['calibration'] is None
        assert scene['topology_review_required'] and scene['evidence_frames']==[]
        assert client.post('/api/roomlab/imports/roomplan',json={'walls':[]}).status_code==422
        assert client.get('/api/roomlab/geometry-jobs/../../etc').status_code==404


def test_measurement_accuracy_excludes_anchor_and_survives_reload(tmp_path):
    from backend.app.roomlab.contracts import CalibrateRequest,RoomDraft
    app=create_app(tmp_path/'runtime')
    scene=app.state.store.create(RoomDraft(floor=[[0,0],[4,0],[4,3],[0,3]]))
    calibrated=app.state.store.calibrate(scene.scene_id,CalibrateRequest(expected_revision=1,anchor_id='wall-1',dimension='wall_length',measured_m=4))
    with TestClient(app) as client:
        result=client.post(f'/api/roomlab/scenes/{scene.scene_id}/accuracy',json={'expected_revision':calibrated.scene_revision,
            'references':[{'element_id':'wall-1','dimension':'wall_length','measured_value':4},
                          {'element_id':'wall-2','dimension':'wall_length','measured_value':2.8,'tolerance':.02}]})
        assert result.status_code==200,result.text
        metrics=result.json()['measurements']
        assert metrics['independent_length_checks']==1 and metrics['mae_m']==pytest.approx(.2)
        restored=client.get(f'/api/roomlab/scenes/{scene.scene_id}/accuracy')
        assert restored.status_code==200,restored.text
        assert restored.json()['measurements']['max_error_m']==pytest.approx(.2)


def test_geometry_floor_api_checks_source_and_persists_measured_proposal(tmp_path):
    import json,hashlib
    from backend.app.roomlab.contracts import MediaRecord,GeometryJob
    runtime=tmp_path/'runtime';app=create_app(runtime)
    root=runtime/'media'/'media-test';root.mkdir()
    source=root/'source.mp4';source.write_bytes(b'explicit isolated fixture; no provider call')
    media=MediaRecord(media_id='media-test',filename='offline.mp4',mime_type='video/mp4',duration_s=1,video_url='/media/media-test/source.mp4',frames=[])
    (root/'record.json').write_text(media.model_dump_json())
    reconstructed=report().model_copy(update={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()})
    from backend.app.roomlab.contracts import GeometryCamera
    reconstructed.cameras=[GeometryCamera(frame_id='offline',center=[1,2,1])]
    reconstructed.points += [GeometryPoint(id=i,xyz=p,rgb=[0,0,0],error_px=.5) for i,p in enumerate([[.5,0,.5],[1.,0,.5],[1.,.6,1.],[.5,.6,1.]],5)]
    job=GeometryJob(job_id='geometry-'+'a'*32,media_id=media.media_id,status='completed',report=reconstructed)
    folder=runtime/'geometry-jobs'/job.job_id;folder.mkdir()
    (folder/'job.json').write_text(job.model_dump_json());(folder/'input.json').write_text(json.dumps({'media':media.model_dump(mode='json')}))
    with TestClient(app) as client:
        body={'point_ids':[0,1,2,3],'first_edge_measured_m':4,'wall_height_m':2.7,'measurement_confirmed':True,'topology_confirmed':True}
        url=f'/api/roomlab/geometry-jobs/{job.job_id}/floor'
        response=client.post(url,json=body)
        assert response.status_code==200,response.text
        scene=response.json()
        assert scene['calibration']['measured_m']==4 and scene['topology_review_required']
        assert scene['geometry_source']=='geometry_fit'
        assert client.get('/api/roomlab/media/media-test/geometry').json()['job_id']==job.job_id
        object_result=client.post(f'/api/roomlab/geometry-jobs/{job.job_id}/object',json={
            'scene_id':scene['scene_id'],'expected_revision':scene['scene_revision'],'point_ids':[5,6,7,8],
            'label':'Explicit offline fitted box','floor_supported_confirmed':True})
        assert object_result.status_code==200,object_result.text
        assert object_result.json()['scene_id']!=scene['scene_id']
        assert object_result.json()['objects'][0]['height_m']==pytest.approx(1.2)
        source.write_bytes(b'different source')
        assert client.post(url,json=body).status_code==409


def test_geometry_object_obb_uses_same_measured_floor_frame():
    from backend.app.roomlab.geometry_floor import fit_object
    from backend.app.roomlab.contracts import GeometryObjectRequest,RoomSceneV1,GeometryCamera
    r=report()
    r.cameras=[GeometryCamera(frame_id='offline',center=[1,2,1])]
    r.points += [GeometryPoint(id=i,xyz=p,rgb=[0,0,0],error_px=.5) for i,p in enumerate([[.5,0,.5],[1.,0,.5],[1.,.6,1.],[.5,.6,1.]],5)]
    floor_request=GeometryFloorRequest(point_ids=[0,1,2,3],first_edge_measured_m=4,measurement_confirmed=True,topology_confirmed=True)
    scene=RoomSceneV1(scene_id='offline',**fit_floor(r,floor_request).model_dump())
    request=GeometryObjectRequest(scene_id=scene.scene_id,expected_revision=1,point_ids=[5,6,7,8],label='Offline box',floor_supported_confirmed=True)
    item=fit_object(r,floor_request,scene,request)
    assert item.width_m==pytest.approx(1) and item.depth_m==pytest.approx(1)
    assert item.height_m==pytest.approx(1.2) and item.provenance.source=='geometry_fit'
    with pytest.raises(ValueError,match='Confirm'):fit_object(r,floor_request,scene,request.model_copy(update={'floor_supported_confirmed':False}))


def test_roomplan_spanning_partition_preserves_outer_shell_and_opening_parent():
    raw=room()
    partition=surface(3,2,1.5,-np.pi/2);partition['identifier']='partition-original'
    raw['walls'].append(partition)
    door=surface(.8,2,1.5,-np.pi/2,height=2.1)
    door['parentIdentifier']='partition-original';raw['doors']=[door]
    draft=import_roomplan(raw)
    from backend.app.roomlab.contracts import RoomSceneV1
    from backend.app.roomlab.validation import validate_scene
    partitions=[w for w in draft.walls if w.role=='partition']
    assert len(draft.floor)==4 and len(partitions)==1 and len(draft.walls)==5
    assert draft.openings[0].wall_id==partitions[0].id
    assert [i.code for i in validate_scene(RoomSceneV1(scene_id='offline',**draft.model_dump())).issues if i.severity=='error']==['topology_review_required']


def test_roomplan_rejects_outside_objects_and_overlapping_openings_before_saving(tmp_path):
    outside=room();box=surface(1,20,20,height=1);box['dimensions'][2]=1;box['category']={'table':{}}
    outside['objects']=[box]
    with pytest.raises(ValueError,match='object_outside'):import_roomplan(outside)
    overlapping=room();door=surface(1,2,0,height=2.1);overlapping['doors']=[door,copy.deepcopy(door)]
    with pytest.raises(ValueError,match='overlapping_openings'):import_roomplan(overlapping)
    app=create_app(tmp_path/'runtime')
    with TestClient(app) as client:
        assert client.post('/api/roomlab/imports/roomplan',json=outside).status_code==422
        assert client.post('/api/roomlab/imports/roomplan',json=overlapping).status_code==422
    assert not list((tmp_path/'runtime/scenes').glob('scene-*.json'))
