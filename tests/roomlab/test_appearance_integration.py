import asyncio, json
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from backend.app.roomlab.contracts import AppearanceChoice, SurfaceAppearance, AppearanceProvenance, RoomSceneV1, CalibrateRequest, geometry_hash,render_hash
from test_v2_integration import app_scene,start,finish,response


def test_legacy_and_appearance_round_trip_with_isolated_geometric_provenance(tmp_path):
    app,scene=app_scene(tmp_path)
    before=scene.model_copy(deep=True);g=geometry_hash(scene);r=render_hash(scene)
    scene.floor_appearance=SurfaceAppearance(color='#bda581',material='wood',provenance=AppearanceProvenance(source='model_estimate',evidence_frame_ids=['frame-1'],note='Estimated under lighting.'))
    scene.objects[0].appearance=SurfaceAppearance(user_override=AppearanceChoice(color='#efefdf',material='marble'))
    scene.wall_appearance=SurfaceAppearance(color='#ddddcc',material='paint')
    scene.walls[0].appearance=SurfaceAppearance(color='#aaaabb',material='glass',provenance=AppearanceProvenance(source='model_estimate',evidence_frame_ids=['frame-1']))
    assert geometry_hash(scene)==g and render_hash(scene)!=r
    assert scene.objects[0].provenance==before.objects[0].provenance
    restored=RoomSceneV1.model_validate_json(scene.model_dump_json());assert restored==scene
    saved=app.state.store.save(scene.scene_id,restored,1)
    assert saved.scene_revision==2 and geometry_hash(saved)!=g
    assert saved.calibration==before.calibration and saved.floor==before.floor
    assert saved.objects[0].center==before.objects[0].center and saved.objects[0].width_m==before.objects[0].width_m
    assert saved.evidence_frames==before.evidence_frames
    assert app.state.store.get(scene.scene_id)==saved
    imported=app.state.store.import_scene(saved);assert imported.scene_id!=scene.scene_id and imported.objects[0].appearance==saved.objects[0].appearance
    legacy=before.model_dump();legacy.pop('floor_appearance',None);legacy.pop('wall_appearance',None)
    for o in legacy['objects']:o.pop('appearance',None)
    assert RoomSceneV1.model_validate(legacy).floor_appearance is None
    for value in ['red','#fff','#12345678','url(secret)']:
        with pytest.raises(ValidationError):AppearanceChoice(color=value)
    with pytest.raises(ValidationError):AppearanceChoice(material='unsupported')
    changed=before.model_copy(deep=True);changed.objects[0].center[0]+=.01;assert geometry_hash(changed)!=g


def test_calibration_does_not_measure_or_modify_appearance(tmp_path):
    app,scene=app_scene(tmp_path);scene.floor_appearance=SurfaceAppearance(material='terrazzo',provenance=AppearanceProvenance(source='model_estimate'))
    app.state.store.save(scene.scene_id,scene,1)
    scaled=app.state.store.calibrate(scene.scene_id,CalibrateRequest(expected_revision=2,anchor_id='wall-1',dimension='wall_length',measured_m=12.))
    assert scaled.floor_appearance==scene.floor_appearance
    assert scaled.floor_appearance.provenance.source=='model_estimate'


def test_review_rejects_changed_appearance_even_at_fixed_revision(tmp_path):
    app,scene=app_scene(tmp_path)
    async def provider(context,api_key=None):
        await asyncio.sleep(.1);return response(context)
    app.state.critic.provider=provider
    with TestClient(app) as client:
        started=start(client,scene);assert started.status_code==202
        # Simulate an external same-revision replacement, stricter than the normal saving flow.
        scene.floor_appearance=SurfaceAppearance(user_override=AppearanceChoice(color='#aaaabb',material='tile'))
        app.state.store._write(scene)
        job=finish(client,started.json()['job_id']);assert job['status']=='failed' and job['result'] is None
        old=client.post(f'/api/roomlab/scenes/{scene.scene_id}/critique',json={k:started.json()[k] for k in ['geometry_hash','evidence_hash','render_hash']}|{'expected_revision':1})
        assert old.status_code==409
