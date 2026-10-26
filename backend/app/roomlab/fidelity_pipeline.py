"""High-fidelity extraction orchestration with isolated, cancellable geometry work."""
from __future__ import annotations
import asyncio,base64,json,os,shutil,sys,time,uuid
from pathlib import Path
from google import genai
from .contracts import MediaRecord,RoomDraftResult,RoomSceneV1
from .fidelity_sampling import prepare_evidence,detail_evidence
from .video_extractor import propose_room,_request_payload,_resolve_api_key,_safe_media_child,_close_sdk_client,SDK_TIMEOUT_MS
from .provider_schema import normalize_provider_payload
from .validation import validate_scene


def atomic_json(path:Path,data:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False));os.replace(tmp,path)


def tracking_summary(report: dict) -> dict:
    points=report['points'];stride=max(1,len(points)//1200)
    return dict(status='reconstructed',input_images=report['selected_frames'],registered_images=report['registered_frames'],
        registered_fraction=report['registered_frames']/max(1,report['selected_frames']),sparse_points=len(points),
        mean_reprojection_error_px=report['mean_reprojection_error_px'],component_count=report['component_count'],
        cameras=report['cameras'],points=[dict(xyz=p['xyz'],color=p['rgb'],error_px=p['error_px']) for p in points[::stride][:1200]],
        units='arbitrary_sfm',aligned_to_room=False,metric_scale_known=False,
        message='Sparse camera/point geometry only. No automatic metric or room-axis alignment; reprojection error is not dimensional accuracy.')


async def track_camera(media:MediaRecord,media_root:Path,work:Path)->dict:
    from .fidelity_media import source_digest
    # Reuse only source- and frame-catalog-matched evidence from a completed explicit reconstruction.
    signature=await asyncio.to_thread(source_digest,media,media_root)
    ids={f.frame_id for f in media.frames}
    job_root=media_root.parent/'geometry-jobs'
    for path in sorted(job_root.glob('geometry-*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        try:
            job=json.loads(path.read_text());report=job.get('report')
            if job['status']!='completed' or not report or report['media_id']!=media.media_id or report['source_sha256']!=signature:continue
            inputs=json.loads((path.parent/'input.json').read_text())
            if {f['frame_id'] for f in inputs['media']['frames']}!=ids:continue
            return tracking_summary(report)
        except (ValueError,KeyError,OSError):continue
    work.mkdir(parents=True,exist_ok=True)
    atomic_json(work/'input.json',{'media':media.model_dump(mode='json'),'media_root':str(media_root.resolve())})
    with (work/'worker.log').open('wb') as log:
        process=await asyncio.create_subprocess_exec(sys.executable,'-m','backend.app.roomlab.geometry_worker',str(work.resolve()),
            stdout=log,stderr=log,cwd=str(Path(__file__).resolve().parents[3]))
        try:
            await asyncio.wait_for(process.wait(),timeout=900)
        except (asyncio.CancelledError,asyncio.TimeoutError) as exc:
            if process.returncode is None:process.kill()
            await process.wait()
            if isinstance(exc,asyncio.CancelledError):raise
            return dict(status='timeout',message='Camera reconstruction reached its CPU budget. No geometry constraints were assumed.')
    if process.returncode or not (work/'result.json').is_file():
        return dict(status='failed',message='Camera alignment failed. No metric geometry was fabricated. Record more sharp overlapping viewpoints.')
    return tracking_summary(json.loads((work/'result.json').read_text()))


def geometry_overview(tracking:dict)->bytes|None:
    """An explicitly unscaled sparse-cloud view; never a floor plan."""
    if not tracking.get('points'):return None
    import io,numpy as np
    from PIL import Image,ImageDraw
    points=np.array([p['xyz'] for p in tracking['points']],dtype=float)
    centered=points-np.median(points,axis=0)
    _,_,axes=np.linalg.svd(centered,full_matrices=False)
    xy=centered@axes[:2].T;lo,hi=np.percentile(xy,[2,98],axis=0);span=np.maximum(hi-lo,.001)
    image=Image.new('RGB',(900,650),'#f7f8f5');draw=ImageDraw.Draw(image)
    draw.text((20,15),'UNSCALED sparse structure / PCA view. Axes are NOT RoomLab axes.',fill='#283b30')
    for value,point in zip(xy,tracking['points']):
        x,y=(value-lo)/span*[830,550]+[35,60]
        if 20<=x<=880 and 40<=y<=630:draw.ellipse((x-2,y-2,x+2,y+2),fill=tuple(point['color']))
    result=io.BytesIO();image.save(result,format='PNG');return result.getvalue()


async def high_fidelity_room(media:MediaRecord,media_root:Path,api_key:str|None=None,*,client=None,
                             tracker=track_camera,extractor=propose_room,progress=None)->tuple[RoomDraftResult,MediaRecord,dict]:
    def emit(stage:str,msg:str):
        if callable(progress):progress(stage,msg)
    started=time.monotonic()
    emit('scoring_frames',f'Scanning {media.duration_s:.1f}s walkthrough at 2fps for sharpness, exposure & viewpoint diversity…')
    selected,selection=await asyncio.to_thread(prepare_evidence,media,media_root)
    emit('tracking_cameras',f'Selected {len(selected.frames)}/{selection.get("candidate_count",len(selected.frames))} sharp keyframes ({selection.get("duplicate_skipped_count",0)} duplicates skipped). Running multi-view camera tracking…')
    work=media_root/media.media_id/('fidelity-'+uuid.uuid4().hex)
    tracking=await tracker(selected,media_root,work)
    emit('drafting_room',f'Camera tracking: {tracking.get("status","done")} ({tracking.get("registered_images",0)}/{tracking.get("input_images",len(selected.frames))} views). Running Gemini 4 Argon spatial draft…')
    initial=await extractor(selected,media_root,api_key=api_key,**({'client':client} if client is not None else {}))
    atomic_json(work/'initial-draft.json',initial.draft.model_dump(mode='json'))
    emit('extracting_detail_crops',f'Drafted "{initial.draft.name}" ({len(initial.draft.walls)} walls, {len(initial.draft.objects)} objects). Extracting 1600px 4fps detail crops around {len(initial.inspect_requests)} model-requested and uncertain elements…')
    details,targets=await asyncio.to_thread(detail_evidence,selected,media_root,initial.draft,initial.inspect_requests)
    augmented=selected.model_copy(update={'frames':sorted([*selected.frames,*details],key=lambda f:f.timestamp_s)})
    report=dict(version=1,selection=selection,tracking=tracking,
        refinement=dict(status='not_needed',additional_frames=len(details),targets=targets),
        limitations=['Camera structure is unscaled and not automatically aligned to the editable room.',
                     'Glass, reflections, textureless walls and moving people can defeat tracking.',
                     'Measurements are required to evaluate metric accuracy.'])
    result=initial
    if targets and not details:
        report['refinement']['status']='unavailable'
        report['refinement']['message']='Targeted views could not be decoded; the initial complete draft was retained.'
    if details:
        emit('refining_geometry',f'Extracted {len(details)} high-res (1600px) close-up views across {len(targets)} target elements. Running closed-loop BEV + detail refinement with Gemini 4 Argon…')
        before_scene=RoomSceneV1(**initial.draft.model_dump(),scene_id='before',evidence_frames=selected.frames)
        before=validate_scene(before_scene)
        diag_issues=[dict(code=i.code,severity=i.severity,element_ids=i.element_ids,message=i.message) for i in before.issues]
        inputs=[dict(type='text',text='Refine this ESTIMATED single-level room using additional source views and the rendered 2D BEV plan preview of the initial draft. '
            'Prioritize these targets: '+json.dumps(targets)+'. Retain distinct furniture, stair direction and glass walls. '
            'Only correct what source views support; do not guess hidden geometry. '
            'Do not infer metres from the unscaled camera reconstruction. '
            'Preserve original element IDs and valid citations; old views remain evidence through their citations. '
            'Keep geometry not contradicted by the additional views. '
            'If validation_diagnostics reports object_overlap or object_outside and the video shows those items are distinct and non-overlapping, adjust their estimated centers/dimensions slightly to match the video. '
            'Return the complete provider room schema, not a patch. '
            'Camera diagnostics: '+json.dumps({k:v for k,v in tracking.items() if k not in ('points','cameras')})+
            '\nValidation diagnostics on initial draft: '+json.dumps(diag_issues)+
            '\nExisting draft: '+initial.draft.model_dump_json()+
            '\nNOTE canonical draft uses floor [x,z], object center [x,z]; output must convert these '
            'back to provider floor_vertices {x_m,z_m}, objects x_m,z_m and wall-attached openings. '
            '\nAllowed evidence IDs: '+json.dumps([f.frame_id for f in augmented.frames]))]
        try:
            from .scene_preview import render_scene_preview
            bev_png=render_scene_preview(before_scene)
            inputs.extend([dict(type='text',text='Rendered 2D BEV Floor Plan of Initial Draft (compare against video frames):'),
                dict(type='image',mime_type='image/png',data=base64.b64encode(bev_png).decode('ascii'))])
        except Exception:
            pass
        overview_ids=sorted({round(i*(len(selected.frames)-1)/3) for i in range(4)}) if selected.frames else []
        review_frames=[*[selected.frames[i] for i in overview_ids],*details]
        for frame in review_frames:
            inputs.extend([dict(type='text',text=f'Frame ID: {frame.frame_id} | Timestamp: {frame.timestamp_s:.2f}s'),
                dict(type='image',mime_type='image/jpeg',data=base64.b64encode(_safe_media_child(media_root,frame.relative_path).read_bytes()).decode('ascii'))])
        overview=geometry_overview(tracking)
        if overview:inputs.append(dict(type='image',mime_type='image/png',data=base64.b64encode(overview).decode('ascii')))
        active=client or genai.Client(api_key=_resolve_api_key(api_key),http_options={'timeout':SDK_TIMEOUT_MS})
        try:
            payload=await _request_payload(active,inputs,initial_tokens=32768,synthesis=True)
            refined,warnings=normalize_provider_payload(payload,{f.frame_id for f in augmented.frames})
            atomic_json(work/'refinement-candidate.json',refined.model_dump(mode='json'))
            after=validate_scene(RoomSceneV1(**refined.model_dump(),scene_id='after',evidence_frames=augmented.frames))
            before_errors=sum(i.severity=='error' for i in before.issues)
            after_errors=sum(i.severity=='error' for i in after.issues)
            # Avoid presenting a model rewrite that drops previously observed scene content as a refinement.
            old_ids={(kind,o.id) for kind in ('objects','walls','openings','floor_voids') for o in getattr(initial.draft,kind)}
            new_ids={(kind,o.id) for kind in ('objects','walls','openings','floor_voids') for o in getattr(refined,kind)}
            if after_errors>before_errors or not old_ids.issubset(new_ids):
                report['refinement']['status']='rejected'
                report['refinement']['message']='Refinement introduced validation errors or dropped existing architecture/furniture; initial draft retained.'
                emit('refinement_reviewed','Refinement candidate dropped elements or increased errors; retained complete initial draft.')
            else:
                refined.topology_review_required = refined.topology_review_required or initial.draft.topology_review_required
                result=initial.model_copy(update={'draft':refined,'warnings':[*initial.warnings,*warnings]})
                report['refinement']['status']='applied'
                report['refinement']['message']='Source-informed model revision, not a measured accuracy improvement.'
                emit('refinement_reviewed',f'Applied closed-loop refinement ({len(refined.objects)} objects, {after_errors} errors).')
        except RuntimeError:
            report['refinement']['status']='failed'
            report['refinement']['message']='Optional source reinspection did not complete; initial complete draft retained.'
            emit('refinement_reviewed','Optional refinement call did not complete; retained complete initial draft.')
        finally:
            if client is None:await _close_sdk_client(active)
    else:
        emit('refinement_reviewed',f'Completed spatial extraction ({len(result.draft.objects)} objects).')
    result=result.model_copy(update={'latency_ms':round((time.monotonic()-started)*1000,2),
        'warnings':[*result.warnings,*selection['warnings'],
                    f"Camera tracking: {tracking['status']}. {tracking.get('message','')}",
                    'High-fidelity source reinspection is estimated; verify dimensions with independent measurements.']})
    atomic_json(work/'report.json',report)
    return result,augmented,report
