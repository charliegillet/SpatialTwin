"""Local room discovery and durable extraction states; fake provider is explicit."""
import asyncio,time,json
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient
from backend.app.roomlab.main import create_app
from backend.app.roomlab.contracts import MediaRecord,EvidenceFrame,RoomDraft,RoomDraftResult,JobRecord
from backend.app.roomlab.library import ExtractionJournal


def media_record(runtime):
    folder=runtime/'media/media-test';folder.mkdir(parents=True)
    Image.new('RGB',(64,64),'tan').save(folder/'frame.jpg')
    frame=EvidenceFrame(frame_id='f1',media_id='media-test',timestamp_s=0.,url='/media/media-test/frame.jpg',relative_path='media-test/frame.jpg')
    media=MediaRecord(media_id='media-test',filename='Walkthrough.mp4',mime_type='video/mp4',duration_s=2.,video_url='/media/media-test/video.mp4',frames=[frame])
    (folder/'record.json').write_text(media.model_dump_json());return media


def finish(client,id):
    for _ in range(100):
        job=client.get('/api/roomlab/jobs/'+id).json()
        if job['status'] not in ('queued','running'):return job
        time.sleep(.01)
    raise AssertionError('Offline test extraction did not finish')


def test_legacy_discovery_groups_outputs_and_revisions_without_fabricated_history(tmp_path):
    app=create_app(tmp_path);media=media_record(tmp_path)
    a=app.state.store.create(RoomDraft(name='Living room',floor=[[0.,0.],[4.,0.],[4.,4.],[0.,4.]]),media.frames)
    b=app.state.store.import_scene(a);b.name='Second saved output';app.state.store.save(b.scene_id,b,1)
    standalone=app.state.store.create(RoomDraft(name='Imported plan',floor=[[0.,0.],[3.,0.],[3.,3.],[0.,3.]]))
    (tmp_path/'scenes/scene-corrupt.json').write_text('{broken')
    with TestClient(app) as c:
        result=c.get('/api/roomlab/rooms');assert result.status_code==200
        data=result.json();assert data['total_count']==2
        row=next(r for r in data['items'] if r['media_id'])
        assert row['status']=='ready' and len(row['scenes'])==2
        assert row['scene_id']==b.scene_id and row['title']=='Second saved output'
        assert row['thumbnail_url']=='/media/media-test/frame.jpg'
        assert row['error'] is None and row['job_id'] is None
        assert row['submitted_at']>0 and row['updated_at']>=row['submitted_at']
        assert c.get(row['thumbnail_url']).status_code==200
    with TestClient(create_app(tmp_path)) as c:assert c.get('/api/roomlab/rooms').json()['total_count']==2


def test_uploaded_failure_retry_and_ready_survive_restart(tmp_path):
    app=create_app(tmp_path);media=media_record(tmp_path)
    async def fail(*args,**kwargs):raise RuntimeError('Explicit offline provider failure')
    app.state.extractor=fail
    with TestClient(app) as c:
        assert c.get('/api/roomlab/rooms').json()['items'][0]['status']=='uploaded'
        job=c.post('/api/roomlab/extractions',json={'media_id':media.media_id}).json()
        assert finish(c,job['job_id'])['status']=='failed'
        row=c.get('/api/roomlab/rooms').json()['items'][0]
        assert row['status']=='needs_attention' and row['error']=='Explicit offline provider failure'
    app=create_app(tmp_path)
    async def offline(*args,**kwargs):return RoomDraftResult(draft=RoomDraft(name='Offline test room',floor=[[0.,0.],[4.,0.],[4.,4.],[0.,4.]]),model='offline-test-stub',latency_ms=1.)
    app.state.extractor=offline
    with TestClient(app) as c:
        assert c.get('/api/roomlab/jobs/'+job['job_id']).json()['status']=='failed'
        assert c.get('/api/roomlab/rooms').json()['items'][0]['status']=='needs_attention'
        retried=c.post('/api/roomlab/extractions',json={'media_id':media.media_id}).json()
        done=finish(c,retried['job_id']);assert done['status']=='completed'
        row=c.get('/api/roomlab/rooms').json()['items'][0]
        assert row['status']=='ready' and row['scene_id']==done['scene_id'] and not row['error']
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/roomlab/rooms').json()['items'][0]['status']=='ready'
        assert c.get('/api/roomlab/jobs/'+retried['job_id']).json()['status']=='completed'


def test_interrupted_processing_is_attention_not_fake_running(tmp_path):
    media_record(tmp_path);journal=ExtractionJournal(tmp_path/'extraction-jobs')
    journal.save(JobRecord(job_id='job-interrupted',status='running',media_id='media-test'))
    (tmp_path/'extraction-jobs/broken.json').write_text('broken')
    with TestClient(create_app(tmp_path)) as c:
        row=c.get('/api/roomlab/rooms').json()['items'][0]
        assert row['status']=='needs_attention' and 'restarted' in row['error']
        assert c.get('/api/roomlab/jobs/job-interrupted').json()['status']=='failed'


def test_processing_state_and_duplicate_request_reuse_one_provider_call(tmp_path):
    app=create_app(tmp_path);media_record(tmp_path);calls=[]
    async def slow(*args,**kwargs):
        calls.append(1);await asyncio.sleep(.2)
        return RoomDraftResult(draft=RoomDraft(floor=[[0.,0.],[3.,0.],[3.,3.],[0.,3.]]),model='offline-test-stub',latency_ms=1.)
    app.state.extractor=slow
    with TestClient(app) as c:
        first=c.post('/api/roomlab/extractions',json={'media_id':'media-test'}).json()
        row=c.get('/api/roomlab/rooms').json()['items'][0];assert row['status']=='processing'
        second=c.post('/api/roomlab/extractions',json={'media_id':'media-test'}).json();assert second['job_id']==first['job_id']
        assert finish(c,first['job_id'])['status']=='completed' and len(calls)==1
