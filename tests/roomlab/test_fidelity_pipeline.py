"""Offline dependency injection exercises refinement and failure boundaries honestly."""
import asyncio
from types import SimpleNamespace
import pytest
from backend.app.roomlab.contracts import RoomDraft,RoomDraftResult,EvidenceFrame,InspectionRequest,MediaRecord,Provenance,RoomObject,RoomSceneV1,Wall
from backend.app.roomlab import fidelity_pipeline as fp
from backend.app.roomlab.fidelity_sampling import detail_evidence
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


@pytest.mark.asyncio
async def test_high_fidelity_room_emits_agent_progress_steps_and_bev_refinement(tmp_path, monkeypatch):
    media = MediaRecord(media_id='media-agent', filename='walk.mp4', mime_type='video/mp4', duration_s=5.0, video_url='', frames=[])
    draft = RoomDraft(
        name='Compact Bedroom',
        floor=[[0, 0], [4, 0], [4, 3], [0, 3]],
        objects=[RoomObject(id='bed-1', label='Queen Bed', category='bed', center=[2.0, 1.5], width_m=1.5, depth_m=2.0, height_m=0.9)],
    )
    async def tracker(*args): return {'status': 'reconstructed', 'registered_images': 10, 'input_images': 10, 'points': [], 'cameras': []}
    async def extractor(*args, **kwargs): return RoomDraftResult(draft=draft, latency_ms=5)
    detail_img = tmp_path / 'detail.jpg'
    detail_img.write_bytes(b'offline-detail')
    detail = EvidenceFrame(frame_id='detail-1', media_id=media.media_id, timestamp_s=2.0, url='/media/detail.jpg', relative_path='detail.jpg')
    monkeypatch.setattr(fp, 'prepare_evidence', lambda *args: (media, {'warnings': [], 'candidate_count': 12, 'duplicate_skipped_count': 2}))
    monkeypatch.setattr(fp, 'detail_evidence', lambda *args: ([detail], [{'element_id': 'bed-1', 'timestamp_s': 2.0}]))
    captured_inputs = []
    async def request(_client, inputs, **kwargs):
        captured_inputs.extend(inputs)
        return object()
    monkeypatch.setattr(fp, '_request_payload', request)
    monkeypatch.setattr(fp, 'normalize_provider_payload', lambda *args: (draft, []))

    steps = []
    result, _, report = await fp.high_fidelity_room(
        media, tmp_path, api_key='offline-test', client=object(),
        tracker=tracker, extractor=extractor,
        progress=lambda stage, msg: steps.append((stage, msg)),
    )
    stages = [s[0] for s in steps]
    assert 'scoring_frames' in stages
    assert 'tracking_cameras' in stages
    assert 'drafting_room' in stages
    assert 'extracting_detail_crops' in stages
    assert 'refining_geometry' in stages
    assert 'refinement_reviewed' in stages
    assert any(item.get('mime_type') == 'image/png' for item in captured_inputs)
    assert report['refinement']['status'] == 'applied'


def test_detail_evidence_consumes_model_inspect_requests_and_wall_overlap_diagnostics(tmp_path, monkeypatch):
    from backend.app.roomlab import fidelity_sampling as fs

    video_file = tmp_path / 'media-plan' / 'source.mp4'
    video_file.parent.mkdir(parents=True)
    video_file.write_bytes(b'fake-mp4')

    frames = [
        EvidenceFrame(frame_id='f-1', media_id='media-plan', timestamp_s=1.0, url='/media/media-plan/f1.jpg', relative_path='media-plan/f1.jpg'),
        EvidenceFrame(frame_id='f-2', media_id='media-plan', timestamp_s=5.0, url='/media/media-plan/f2.jpg', relative_path='media-plan/f2.jpg'),
    ]
    media = MediaRecord(
        media_id='media-plan',
        filename='plan.mp4',
        mime_type='video/mp4',
        duration_s=10.0,
        video_url='/media/media-plan/source.mp4',
        frames=frames,
    )
    # Place an observed low-uncertainty table overlapping wall-1 (z=0) so object_wall_overlap triggers
    draft = RoomDraft(
        name='Test Room',
        floor=[[0.0, 0.0], [5.0, 0.0], [5.0, 4.0], [0.0, 4.0]],
        walls=[
            Wall(id='wall-1', start=[0.0, 0.0], end=[5.0, 0.0]),
            Wall(id='wall-2', start=[5.0, 0.0], end=[5.0, 4.0]),
            Wall(id='wall-3', start=[5.0, 4.0], end=[0.0, 4.0]),
            Wall(id='wall-4', start=[0.0, 4.0], end=[0.0, 0.0]),
        ],
        objects=[
            RoomObject(
                id='obj-table-1',
                label='Dining Table',
                category='table',
                center=[2.5, 2.0],
                width_m=1.2,
                depth_m=0.8,
                height_m=0.75,
                uncertainty_radius_m=0.05,
                provenance=Provenance(source='model_estimate', visibility='observed', evidence_frame_ids=['f-1', 'f-2']),
            ),
            RoomObject(
                id='obj-wall-hit',
                label='Side Table',
                category='table',
                center=[2.5, 0.02],
                width_m=0.8,
                depth_m=0.8,
                height_m=0.75,
                uncertainty_radius_m=0.05,
                provenance=Provenance(source='model_estimate', visibility='observed', evidence_frame_ids=['f-2']),
            ),
        ],
    )

    extracted_timestamps: list[float] = []
    def fake_extract(_exe, _src, ts, out_path):
        extracted_timestamps.append(round(float(ts), 3))
        out_path.write_bytes(b'jpeg')
        return True

    monkeypatch.setattr(fs, '_extract_frame_jpeg', fake_extract)
    monkeypatch.setattr(fs.subprocess, 'run', lambda *args, **kwargs: None)

    # Plan A requests timestamp 2.0s on obj-table-1; Plan B requests timestamp 7.5s on obj-table-1
    plan_a = [InspectionRequest(element_id='obj-table-1', timestamp_s=2.0, reason='Check table leg clearance')]
    plan_b = [InspectionRequest(element_id='obj-table-1', timestamp_s=7.5, reason='Check table from second angle')]

    frames_a, targets_a = detail_evidence(media, tmp_path, draft, plan_a)
    ts_a = [f.timestamp_s for f in frames_a]
    frames_b, targets_b = detail_evidence(media, tmp_path, draft, plan_b)
    ts_b = [f.timestamp_s for f in frames_b]

    assert ts_a != ts_b
    assert targets_a[0]['element_id'] == 'obj-table-1' and targets_a[0]['timestamp_s'] == 2.0
    assert targets_b[0]['element_id'] == 'obj-table-1' and targets_b[0]['timestamp_s'] == 7.5
    # Verify that obj-wall-hit (observed, uncertainty=0.05, but triggers object_wall_overlap) is also targeted!
    assert any(t['element_id'] == 'obj-wall-hit' and t.get('source') == 'validation' for t in targets_a)
