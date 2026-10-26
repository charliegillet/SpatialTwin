"""Regressions from the agentic review: planning boundaries and terminal-state truth."""
import asyncio
import time
import math
from fastapi.testclient import TestClient
from backend.app.roomlab.contracts import MediaRecord,RoomDraft,RoomDraftResult,JobRecord
from backend.app.roomlab.main import create_app
from backend.app.roomlab.provider_schema import ProviderRoomPayload,extract_valid_inspect_requests


def test_provider_inspection_plan_is_bounded_to_known_elements_and_clip():
    draft=RoomDraft(floor=[[0,0],[4,0],[4,3],[0,3]],objects=[dict(id='desk',label='Desk',center=[2,1],width_m=1,depth_m=.5,height_m=.75)])
    payload=ProviderRoomPayload(floor_vertices=[{'x_m':p[0],'z_m':p[1]} for p in draft.floor],inspect_requests=[
        {'element_id':'unknown','timestamp_s':1},
        {'element_id':'desk','timestamp_s':-1},
        {'element_id':'desk','timestamp_s':11},
        {'element_id':'desk','timestamp_s':float('nan')},
        {'element_id':'desk','timestamp_s':float('inf')},
        *[{'element_id':'desk','timestamp_s':t,'reason':'Look at the back side'} for t in [1,1,2,3,4,5,6,7,8]]])
    plan=extract_valid_inspect_requests(payload,draft,10)
    assert [p.timestamp_s for p in plan]==[1,2,3,4,5,6]
    assert all(p.element_id=='desk' and math.isfinite(p.timestamp_s) for p in plan)


def test_save_failure_cancel_and_restart_never_report_completed_stage(tmp_path):
    runtime=tmp_path/'runtime';app=create_app(runtime)
    media=MediaRecord(media_id='media-review',filename='offline.mp4',mime_type='video/mp4',duration_s=1,video_url='',frames=[])
    folder=runtime/'media'/media.media_id;folder.mkdir();(folder/'record.json').write_text(media.model_dump_json())
    async def offline_extract(*args,**kwargs):return RoomDraftResult(draft=RoomDraft(floor=[[0,0],[4,0],[4,3],[0,3]]),latency_ms=1)
    app.state.extractor=offline_extract
    def fail_save(*args,**kwargs):raise OSError('Explicit isolated storage-failure regression')
    app.state.store.create=fail_save
    with TestClient(app) as client:
        job=client.post('/api/roomlab/extractions',json={'media_id':media.media_id}).json()
        for _ in range(100):
            failed=client.get('/api/roomlab/jobs/'+job['job_id']).json()
            if failed['status']=='failed':break
            time.sleep(.01)
        assert failed['status']==failed['stage']=='failed'
        assert not any('Saved editable room' in line for line in failed['agent_steps'])
    resumed=create_app(runtime)
    async def slow_extract(*args,**kwargs):await asyncio.sleep(30)
    resumed.state.extractor=slow_extract
    with TestClient(resumed) as client:
        assert client.get('/api/roomlab/jobs/'+job['job_id']).json()['stage']=='failed'
        pending=client.post('/api/roomlab/extractions',json={'media_id':media.media_id}).json()
        cancelled=client.delete('/api/roomlab/jobs/'+pending['job_id']).json()
        assert cancelled['status']==cancelled['stage']=='cancelled'
    interrupted=JobRecord(job_id='job-interrupted-review',media_id=media.media_id,status='running',stage='drafting_room')
    (runtime/'extraction-jobs'/f'{interrupted.job_id}.json').write_text(interrupted.model_dump_json())
    with TestClient(create_app(runtime)) as client:
        recovered=client.get('/api/roomlab/jobs/'+interrupted.job_id).json()
        assert recovered['status']==recovered['stage']=='failed'
