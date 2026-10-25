"""Adaptive planning, bounded retries, source coverage and all-or-nothing persistence."""
import asyncio
import json
import subprocess
from types import SimpleNamespace

import imageio_ffmpeg
import pytest

from backend.app.roomlab.contracts import EvidenceFrame, MediaRecord, RoomSceneV1
from backend.app.roomlab.media import MAX_DURATION_S, MAX_FRAMES, _select_timestamps, _probe_and_measure_duration
from backend.app.roomlab.video_extractor import MODEL_ID, propose_room, extraction_timeout_s


def payload():
    return dict(name="Offline test only", wall_height_m=2.7, wall_thickness_m=.12,
                floor_vertices=[dict(x_m=x,z_m=z) for x,z in [(0,0),(6,0),(6,5),(0,5)]],
                floor_voids=[],interior_walls=[],openings=[],objects=[],notes=[])


def media_fixture(tmp_path, duration):
    frames=[]
    for i,t in enumerate(_select_timestamps(duration)):
        path=tmp_path/f'frame-{i}.jpg'; path.write_bytes(b'offline-placeholder-not-sent-to-provider')
        frames.append(EvidenceFrame(frame_id=f'frame-{i}',media_id='media-test',timestamp_s=t,
                                    url=f'/media/{path.name}',relative_path=path.name))
    return MediaRecord(media_id='media-test',filename='test.mp4',mime_type='video/mp4',
                       duration_s=duration,video_url='',frames=frames)


@pytest.mark.parametrize('duration,expected_calls',[(5,1),(120,3),(600,11)])
@pytest.mark.asyncio
async def test_adaptive_calls_cover_all_frames_and_fit_scene(tmp_path,duration,expected_calls):
    media=media_fixture(tmp_path,duration);calls=[]
    class Interactions:
        async def create(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status='completed',model=MODEL_ID,output_text=json.dumps(payload()))
    result=await propose_room(media,tmp_path,api_key='offline-test',client=SimpleNamespace(aio=SimpleNamespace(interactions=Interactions())))
    assert len(calls)==expected_calls
    assert result.provenance=='live'  # Fake client explicitly injected; never a production fallback.
    segment_calls=calls[:-1] if expected_calls>1 else calls
    ids=set()
    for call in segment_calls:
        images=[x for x in call['input'] if x['type']=='image']
        assert len(images)<=48
        for item in call['input']:
            if item['type']=='text' and item['text'].startswith('Frame ID:'):
                ids.add(item['text'].split(' |')[0].removeprefix('Frame ID: '))
    assert ids=={f.frame_id for f in media.frames}
    if expected_calls>1:
        assert 'independent' in calls[-1]['input'][0]['text']
        assert '150' in calls[-1]['system_instruction']
        # Adjacent calls share boundary evidence, rather than independent unalignable snippets.
        assert any(f'Frame ID: {media.frames[len(media.frames)//2].frame_id}' in str(c['input']) for c in calls)
    scene=RoomSceneV1(scene_id='offline-scene',**result.draft.model_dump(),evidence_frames=media.frames)
    assert len(scene.evidence_frames)<=200


@pytest.mark.asyncio
async def test_incomplete_retries_with_larger_budget_and_discards_partial_json(tmp_path):
    calls=[]
    class Interactions:
        async def create(self,**kwargs):
            calls.append(kwargs['generation_config']['max_output_tokens'])
            if len(calls)==1:return SimpleNamespace(status='incomplete',output_text='{"name":"truncated')
            return SimpleNamespace(status='completed',model=MODEL_ID,output_text=json.dumps(payload()))
    result=await propose_room(media_fixture(tmp_path,5),tmp_path,api_key='offline-test',client=SimpleNamespace(aio=SimpleNamespace(interactions=Interactions())))
    assert calls==[16384,65536]
    assert result.draft.name=='Offline test only'


@pytest.mark.asyncio
async def test_middle_segment_failure_stops_before_synthesis(tmp_path):
    calls=[]
    class Interactions:
        async def create(self,**kwargs):
            calls.append(kwargs)
            if len(calls)>1:return SimpleNamespace(status='incomplete',output_text='bad')
            return SimpleNamespace(status='completed',model=MODEL_ID,output_text=json.dumps(payload()))
    with pytest.raises(RuntimeError,match='segment 2/10 failed.*No partial room'):
        await propose_room(media_fixture(tmp_path,600),tmp_path,api_key='offline-test',client=SimpleNamespace(aio=SimpleNamespace(interactions=Interactions())))
    assert len(calls)==3


@pytest.mark.asyncio
async def test_cancellation_never_starts_next_segment(tmp_path):
    class Interactions:
        async def create(self,**kwargs):raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await propose_room(media_fixture(tmp_path,600),tmp_path,api_key='offline-test',client=SimpleNamespace(aio=SimpleNamespace(interactions=Interactions())))


def test_ten_minute_sampling_and_timeout_bounds():
    assert MAX_DURATION_S==600 and MAX_FRAMES<=200
    timestamps=_select_timestamps(600)
    assert timestamps[0]==0 and timestamps[-1]>599
    assert len(timestamps)<=200
    assert max(b-a for a,b in zip(timestamps,timestamps[1:]))<3.1
    assert extraction_timeout_s(600)>extraction_timeout_s(120)>extraction_timeout_s(5)


def test_real_ten_minute_video_duration_and_over_limit(tmp_path):
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    for duration in (600,602):
        path=tmp_path/f'{duration}.mp4'
        subprocess.run([ffmpeg,'-y','-loglevel','error','-f','lavfi','-i',
                        f'color=c=gray:s=32x32:r=1:d={duration}','-c:v','libx264',str(path)],check=True,timeout=30)
        if duration==600:assert _probe_and_measure_duration(ffmpeg,path)==600
        else:
            with pytest.raises(ValueError,match='600s maximum'):_probe_and_measure_duration(ffmpeg,path)


def test_ten_minute_upload_extraction_and_saved_evidence(tmp_path):
    """Real ten-minute decoding and API/store path; provider is explicitly offline."""
    import time
    from fastapi.testclient import TestClient
    from backend.app.roomlab.main import create_app
    from backend.app.roomlab.contracts import RoomDraft, RoomDraftResult
    path=tmp_path/'ten-minutes.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-loglevel','error','-f','lavfi','-i',
                    'color=c=gray:s=32x32:r=1:d=600','-c:v','libx264',str(path)],check=True,timeout=30)
    app=create_app(tmp_path/'api')
    async def offline_provider(media,media_root,api_key=None):
        assert media.duration_s==600
        assert 190 <= len(media.frames) <= 200
        assert all((media_root/f.relative_path).is_file() for f in media.frames)
        return RoomDraftResult(draft=RoomDraft(name='Explicit offline 10-minute test',
            floor=[[0,0],[6,0],[6,5],[0,5]]),model='offline-test',latency_ms=1)
    app.state.extractor=offline_provider
    with TestClient(app) as client:
        config=client.get('/api/roomlab/config').json()
        assert config['max_video_seconds']==600
        assert config['max_upload_bytes']==1024**3
        with path.open('rb') as f:
            uploaded=client.post('/api/roomlab/media',files={'file':('ten-minutes.mp4',f,'video/mp4')})
        assert uploaded.status_code==200,uploaded.text
        media=uploaded.json()
        job=client.post('/api/roomlab/extractions',json={'media_id':media['media_id']}).json()
        for _ in range(100):
            job=client.get('/api/roomlab/jobs/'+job['job_id']).json()
            if job['status'] in ('completed','failed'):break
            time.sleep(.01)
        assert job['status']=='completed',job
        scene=client.get('/api/roomlab/scenes/'+job['scene_id']).json()
        assert len(scene['evidence_frames'])==len(media['frames'])
        assert client.get(scene['evidence_frames'][-1]['url']).status_code==200
        scene['name']='Edited ten-minute room'
        saved=client.patch('/api/roomlab/scenes/'+scene['scene_id'],
            json={'scene':scene,'expected_revision':scene['scene_revision']})
        assert saved.status_code==200,saved.text
