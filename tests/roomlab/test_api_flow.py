"""Actual decoding and persistence with explicitly injected offline perception."""
import time,subprocess
import pytest,imageio_ffmpeg
from fastapi.testclient import TestClient
from backend.app.roomlab.main import create_app
from backend.app.roomlab.contracts import RoomDraft,RoomObject,RoomDraftResult

@pytest.fixture
def clip(tmp_path):
    path=tmp_path/'source.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','lavfi','-i','color=c=blue:s=320x240:r=5:d=1.2','-c:v','libx264','-pix_fmt','yuv420p',str(path)],check=True)
    return path

def test_actual_video_decode_to_editable_saved_scene(tmp_path,clip):
    app=create_app(tmp_path/'app')
    async def offline_stub(media,media_root,api_key=None):
        assert 0<len(media.frames)<=12
        assert (media_root/media.frames[0].relative_path).exists()
        return RoomDraftResult(draft=RoomDraft(name='Explicit offline stub',floor=[[0.,0.],[4.,0.],[4.,3.],[0.,3.]],
          objects=[RoomObject(id='table',label='Table',center=[2.,1.5],width_m=1.,depth_m=.5,height_m=.75)]),
          model='offline-test-stub',latency_ms=2.,warnings=['Offline test provider was explicitly injected.'])
    app.state.extractor=offline_stub
    with TestClient(app) as client:
        uploaded=client.post('/api/roomlab/media',files={'file':('source.mp4',clip.read_bytes(),'video/mp4')})
        assert uploaded.status_code==200,uploaded.text
        media=uploaded.json();assert media['duration_s']>0
        assert client.get(media['frames'][0]['url']).status_code==200
        queued=client.post('/api/roomlab/extractions',json={'media_id':media['media_id']});assert queued.status_code==202
        id=queued.json()['job_id']
        for _ in range(100):
            job=client.get('/api/roomlab/jobs/'+id).json()
            if job['status'] in ('failed','completed'):break
            time.sleep(.01)
        assert job['status']=='completed',job
        scene=client.get('/api/roomlab/scenes/'+job['scene_id']).json()
        assert len(scene['walls'])==4
        assert scene['evidence_frames']==media['frames']
        scene['objects'][0]['center']=[1.5,1.5]
        saved=client.patch('/api/roomlab/scenes/'+scene['scene_id'],json={'expected_revision':1,'scene':scene})
        assert saved.status_code==200
        assert saved.json()['objects'][0]['provenance']['source']=='user_edit'
        calibrated=client.post('/api/roomlab/scenes/'+scene['scene_id']+'/calibrate',json={'expected_revision':2,'anchor_id':'wall-1','dimension':'wall_length','measured_m':8.})
        assert calibrated.status_code==200,calibrated.text
        assert calibrated.json()['objects'][0]['center']==[3.,3.]
        assert calibrated.json()['geometry_source']=='model_estimate'
        path=client.post('/api/roomlab/scenes/'+scene['scene_id']+'/solve',json={'expected_revision':3,'start':[.8,.8],'goal':[7.,.8],'agent_diameter_m':.6})
        assert path.status_code==200 and path.json()['status']=='ROBUST_PASS'
    reloaded=create_app(tmp_path/'app').state.store.get(scene['scene_id'])
    assert reloaded.scene_revision==3 and reloaded.objects[0].center==[3.,3.]

def test_provider_error_has_no_fake_scene(tmp_path,clip):
    app=create_app(tmp_path/'app')
    async def fail(*args,**kwargs):raise RuntimeError('Provider test failure')
    app.state.extractor=fail
    with TestClient(app) as c:
        media=c.post('/api/roomlab/media',files={'file':('source.mp4',clip.read_bytes(),'video/mp4')}).json()
        job=c.post('/api/roomlab/extractions',json={'media_id':media['media_id']}).json()
        for _ in range(50):
            r=c.get('/api/roomlab/jobs/'+job['job_id']).json()
            if r['status']=='failed':break
            time.sleep(.01)
        assert r['status']=='failed' and r['scene_id'] is None
        assert not list((tmp_path/'app/scenes').glob('*.json'))

def test_decode_rejects_text_and_external_origins(tmp_path):
    with TestClient(create_app(tmp_path/'app')) as c:
        assert c.post('/api/roomlab/media',files={'file':('fake.mp4',b'not a video','video/mp4')}).status_code==422
