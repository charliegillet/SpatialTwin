"""Offline dependency injection exercises refinement and failure boundaries honestly."""
import asyncio
from types import SimpleNamespace
import pytest
from backend.app.roomlab.contracts import RoomDraft,RoomDraftResult,EvidenceFrame,MediaRecord,RoomSceneV1
from backend.app.roomlab import fidelity_pipeline as fp
from backend.app.roomlab.accuracy import ReferenceCheck,evaluate


@pytest.mark.asyncio
async def test_refinement_cannot_drop_architecture_or_clear_topology(tmp_path,monkeypatch):
    media=MediaRecord(media_id='media-offline',filename='offline.mp4',mime_type='video/mp4',duration_s=2,video_url='',frames=[])
    wall=dict(id='partition',start=[1.,0.],end=[1.,3.],role='partition')
    draft=RoomDraft(floor=[[0,0],[4,0],[4,3],[0,3]],walls=[wall],topology_review_required=True)
    async def tracker(*args):return {'status':'failed','message':'Explicit offline tracker fixture.'}
    async def extractor(*args,**kwargs):return RoomDraftResult(draft=draft,latency_ms=1)
    image=tmp_path/'detail.jpg';image.write_bytes(b'offline-not-sent-to-provider')
    detail=EvidenceFrame(frame_id='detail',media_id=media.media_id,timestamp_s=1,url='/media/detail.jpg',relative_path='detail.jpg')
    monkeypatch.setattr(fp,'prepare_evidence',lambda *args:(media,{'warnings':[]}))
    monkeypatch.setattr(fp,'detail_evidence',lambda *args:([detail],[{'element_id':'partition','timestamp_s':1}]))
    async def request(*args,**kwargs):return object()
    monkeypatch.setattr(fp,'_request_payload',request)
    monkeypatch.setattr(fp,'normalize_provider_payload',lambda *args:(RoomDraft(floor=draft.floor),[]))
    result,augmented,report=await fp.high_fidelity_room(media,tmp_path,api_key='offline-test',client=object(),tracker=tracker,extractor=extractor)
    assert report['refinement']['status']=='rejected'
    assert result.draft.walls[0].id=='partition' and result.draft.topology_review_required
    # An accepted source revision still cannot silently resolve topology uncertainty.
    monkeypatch.setattr(fp,'normalize_provider_payload',lambda *args:(draft.model_copy(update={'topology_review_required':False}),[]))
    result,_,report=await fp.high_fidelity_room(media,tmp_path,api_key='offline-test',client=object(),tracker=tracker,extractor=extractor)
    assert report['refinement']['status']=='applied' and result.draft.topology_review_required


def test_independent_measurements_wrap_angles_and_do_not_mutate_scene():
    scene=RoomSceneV1(scene_id='offline',floor=[[0,0],[4,0],[4,4]],objects=[dict(id='chair',label='chair',center=[1,1],width_m=1,depth_m=1,height_m=1,yaw_deg=179)])
    before=scene.model_dump_json()
    checks=[ReferenceCheck(element_id='chair',dimension='yaw_deg',measured_value=-179,tolerance=3),ReferenceCheck(element_id='chair',dimension='object_width',measured_value=.8)]
    result=evaluate(scene,checks)
    assert result['angular_mae_deg']==2 and result['mae_m']==pytest.approx(.2)
    assert scene.model_dump_json()==before
