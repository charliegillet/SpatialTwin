"""Standalone RoomLab app: no imported SpatialTwin runtime or hardware."""
from __future__ import annotations
import asyncio,os,json,uuid,logging,ipaddress
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .contracts import RoomSceneV1,RoomDraft,MediaRecord,JobRecord,ExtractRequest,EditSceneRequest,CalibrateRequest,SolveRequest,CritiqueRequest,RepairRequest,SceneReceipt,CritiqueJobRecord,RoomLibrary
from .store import SceneStore,ConflictError
from .library import ExtractionJournal,list_rooms
from .validation import validate_scene
from .reachability import solve
from .optimizer import optimize
from .overlap_repair import repair_overlaps
from .critique_service import CritiqueService,receipt
from .accuracy import AccuracyRequest,report_for_scene,evaluate

ROOT=Path(__file__).resolve().parents[3]
from .media import MAX_MEDIA_BYTES,MAX_DURATION_S
MAX_BYTES=MAX_MEDIA_BYTES
log=logging.getLogger('roomlab')

def create_app(runtime:Path|None=None)->FastAPI:
    runtime=runtime or ROOT/'runtime/roomlab';runtime.mkdir(parents=True,exist_ok=True)
    media_root=runtime/'media';media_root.mkdir(exist_ok=True)
    journal=ExtractionJournal(runtime/'extraction-jobs')
    store=SceneStore(runtime/'scenes');jobs=journal.load();tasks={};limit=asyncio.Semaphore(1)
    critic=CritiqueService(store,media_root)
    from .fidelity_api import fidelity_router
    fidelity,close_fidelity=fidelity_router(runtime,store)
    @asynccontextmanager
    async def lifespan(_app):
        for previous in jobs.values():
            if previous.status in ('queued','running'):
                previous.status='failed';previous.error='Room building stopped when the server restarted. Retry this walkthrough.';journal.save(previous)
        yield
        await critic.close()
        await close_fidelity()
        pending=[task for task in tasks.values() if not task.done()]
        for task in pending:task.cancel()
        if pending:await asyncio.gather(*pending,return_exceptions=True)
    app=FastAPI(title='RoomLab',version='1.0.0',lifespan=lifespan)
    app.state.store=store;app.state.runtime=runtime;app.state.jobs=jobs
    # Test injection replaces only a provider function; default is always a real model call.
    app.state.extractor=None;app.state.media_processor=None
    app.state.critic=critic

    network_enabled=os.environ.get('ROOMLAB_HOST','127.0.0.1') in ('0.0.0.0','::')

    @app.middleware('http')
    async def check_access(request:Request,call_next):
        from fastapi.responses import JSONResponse
        if request.client and not network_enabled:
            try:allowed=ipaddress.ip_address(request.client.host).is_loopback
            except ValueError:allowed=request.client.host=='testclient'
            if not allowed:return JSONResponse({'detail':'RoomLab is a local-only application.'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            same_origin=f'{request.url.scheme}://{request.url.netloc}'
            if origin and origin not in (same_origin,'http://127.0.0.1:5174','http://localhost:5174'):
                return JSONResponse({'detail':'Unexpected request origin.'},status_code=403)
        return await call_next(request)

    @app.exception_handler(ConflictError)
    async def conflict(_request,exc):
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':str(exc)},status_code=409)

    def get_scene(id):
        try:return store.get(id)
        except KeyError:raise HTTPException(404,'Scene not found.')

    @app.get('/health')
    def health():return {'status':'healthy','application':'RoomLab','hardware':'none'}

    @app.get('/api/roomlab/config')
    def config():return {'gemini_configured':bool(os.environ.get('GEMINI_API_KEY')),'model':'gemini-4-argon',
        'max_video_seconds':MAX_DURATION_S,'max_upload_bytes':MAX_BYTES,
        'sample_video_url':'/api/roomlab/examples/room-walkthrough.mp4' if (runtime/'sample-room.mp4').exists() else None}

    @app.get('/api/roomlab/examples/room-walkthrough.mp4')
    def sample():
        path=runtime/'sample-room.mp4'
        if not path.exists():raise HTTPException(404,'Sample video has not been generated.')
        return FileResponse(path,media_type='video/mp4',filename='synthetic-room-walkthrough.mp4')

    @app.post('/api/roomlab/media',response_model=MediaRecord)
    async def upload(file:UploadFile=File(...)):
        from .media import process_media
        data=await file.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise HTTPException(413,'Video must be at most 1024 MiB.')
        processor=app.state.media_processor or process_media
        try:record=await asyncio.to_thread(processor,data,file.filename or 'video.mp4',file.content_type or '',media_root)
        except ValueError as exc:raise HTTPException(422,str(exc))
        (media_root/record.media_id/'record.json').write_text(record.model_dump_json(indent=2))
        return record

    @app.get('/api/roomlab/media/{id}',response_model=MediaRecord)
    def media_record(id:str):
        if not id.startswith('media-') or '/' in id or '..' in id:raise HTTPException(404,'Media not found.')
        try:return MediaRecord.model_validate_json((media_root/id/'record.json').read_text())
        except (ValueError,FileNotFoundError):raise HTTPException(404,'Media not found.')

    async def extract_job(job:JobRecord,media:MediaRecord,quality:str):
        try:
            async with limit:
                job.status='running';journal.save(job)
                from .video_extractor import propose_room,extraction_timeout_s
                extractor=app.state.extractor or propose_room
                fidelity_report=None
                if quality=='high' and app.state.extractor is None:
                    from .fidelity_pipeline import high_fidelity_room
                    result,media,fidelity_report=await asyncio.wait_for(
                        high_fidelity_room(media,media_root,api_key=os.environ.get('GEMINI_API_KEY')),
                        timeout=min(10800,extraction_timeout_s(media.duration_s)+2280))
                else:
                    result=await asyncio.wait_for(extractor(media,media_root,api_key=os.environ.get('GEMINI_API_KEY')),timeout=extraction_timeout_s(media.duration_s))
                from .contracts import Wall
                pending=RoomSceneV1(**result.draft.model_dump(),scene_id='pending',evidence_frames=media.frames)
                if not pending.walls:pending.walls=[Wall(id=f'wall-{i+1}',start=p,end=pending.floor[(i+1)%len(pending.floor)]) for i,p in enumerate(pending.floor)]
                draft_report=validate_scene(pending)
                errors=[i.model_dump() for i in draft_report.issues if i.severity=='error']
                if errors:
                    result.draft.topology_review_required=True
                    if fidelity_report is not None:fidelity_report['geometry_errors']=errors
                scene=store.create(result.draft,media.frames)
                if fidelity_report is not None:
                    from .fidelity_pipeline import atomic_json
                    fidelity_report['extraction_revision']=scene.scene_revision
                    atomic_json(runtime/'fidelity-scenes'/(scene.scene_id+'.json'),fidelity_report)
                job.scene_id=scene.scene_id;job.model=result.model;job.latency_ms=result.latency_ms;job.warnings=result.warnings
                report=validate_scene(scene)
                job.warnings += [x.message for x in report.issues]
                job.status='completed'
        except asyncio.CancelledError:job.status='cancelled';job.error='Room building was cancelled. You can retry.'
        except asyncio.TimeoutError:job.status='failed';job.error='Extraction exceeded its adaptive time budget. Your uploaded video is preserved; retry the extraction.'
        except Exception as exc:
            job.status='failed'
            # Provider modules supply user-safe RuntimeError/ValueError messages. Never emit key-bearing raw SDK errors.
            job.error=str(exc)[:600] if isinstance(exc,(RuntimeError,ValueError)) else 'Room extraction failed. Try a clearer translated walkthrough.'
            log.warning('Extraction job failed: %s',type(exc).__name__)
        finally:journal.save(job)

    @app.post('/api/roomlab/extractions',response_model=JobRecord,status_code=202)
    async def extract(request:ExtractRequest):
        if not app.state.extractor and not os.environ.get('GEMINI_API_KEY'):raise HTTPException(503,'Gemini is not configured. Set GEMINI_API_KEY on the backend; no scene will be substituted.')
        if not request.media_id.startswith('media-') or '/' in request.media_id or '..' in request.media_id:raise HTTPException(404,'Media not found.')
        try:media=MediaRecord.model_validate_json((media_root/request.media_id/'record.json').read_text())
        except (ValueError,FileNotFoundError):raise HTTPException(404,'Media not found.')
        active=next((j for j in jobs.values() if j.media_id==request.media_id and j.status in ('queued','running')),None)
        if active:return active
        if sum(j.status in ('queued','running') for j in jobs.values())>=3:raise HTTPException(429,'Extraction queue is full. Wait or cancel a pending job.')
        job=JobRecord(job_id='job-'+uuid.uuid4().hex,status='queued',media_id=request.media_id);jobs[job.job_id]=job;journal.save(job)
        tasks[job.job_id]=asyncio.create_task(extract_job(job,media,request.quality));return job

    @app.get('/api/roomlab/jobs/{id}',response_model=JobRecord)
    def job(id:str):
        if id not in jobs:raise HTTPException(404,'Job not found.')
        return jobs[id]

    @app.delete('/api/roomlab/jobs/{id}',response_model=JobRecord)
    async def cancel(id:str):
        value=job(id)
        if value.status in ('running','queued'):
            tasks[id].cancel();value.status='cancelled';value.error='Room building was cancelled. You can retry.';journal.save(value)
        return value

    @app.get('/api/roomlab/rooms',response_model=RoomLibrary)
    def room_library():return list_rooms(runtime,jobs)

    @app.get('/api/roomlab/scenes/{id}',response_model=RoomSceneV1)
    def scene(id:str):return get_scene(id)

    @app.post('/api/roomlab/scenes',response_model=RoomSceneV1)
    def import_scene(scene:RoomSceneV1):return store.import_scene(scene)

    @app.patch('/api/roomlab/scenes/{id}',response_model=RoomSceneV1)
    def edit(id:str,request:EditSceneRequest):
        get_scene(id)
        try:return store.save(id,request.scene,request.expected_revision)
        except ValueError as exc:
            if isinstance(exc,ConflictError):raise
            raise HTTPException(422,str(exc))

    @app.post('/api/roomlab/scenes/{id}/calibrate',response_model=RoomSceneV1)
    def calibrate(id:str,request:CalibrateRequest):
        get_scene(id)
        try:return store.calibrate(id,request)
        except ValueError as exc:
            if isinstance(exc,ConflictError):raise
            raise HTTPException(422,str(exc))

    @app.post('/api/roomlab/scenes/{id}/validate')
    def validate(id:str):return validate_scene(get_scene(id))

    @app.post('/api/roomlab/scenes/{id}/solve')
    async def check_path(id:str,request:SolveRequest):
        scene=get_scene(id)
        if request.expected_revision!=scene.scene_revision:raise ConflictError('Scene revision changed. Save/reload before solving.')
        return await asyncio.to_thread(solve,scene,request)

    @app.post('/api/roomlab/scenes/{id}/optimize')
    async def improve(id:str,request:SolveRequest):
        scene=get_scene(id)
        if request.expected_revision!=scene.scene_revision:raise ConflictError('Scene revision changed. Save/reload before optimizing.')
        return await asyncio.to_thread(optimize,scene,request)


    @app.get('/api/roomlab/scenes/{id}/receipt',response_model=SceneReceipt)
    async def scene_receipt(id:str):
        try:return await asyncio.to_thread(receipt,get_scene(id),media_root)
        except ValueError as exc:raise HTTPException(422,str(exc))

    @app.get('/api/roomlab/scenes/{id}/preview.png')
    async def scene_preview(id:str,revision:int|None=None):
        from .scene_preview import render_scene_preview
        from fastapi.responses import Response
        scene=get_scene(id)
        if revision is not None and revision!=scene.scene_revision:raise ConflictError('Scene revision changed.')
        data=await asyncio.to_thread(render_scene_preview,scene)
        return Response(data,media_type='image/png',headers={'Cache-Control':'no-store'})

    @app.post('/api/roomlab/scenes/{id}/critique',response_model=CritiqueJobRecord,status_code=202)
    async def request_critique(id:str,request:CritiqueRequest):
        scene=get_scene(id);key=os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if not key and critic.provider is None:raise HTTPException(503,'Gemini is not configured for visual review.')
        try:return await critic.start(scene,request,key or '')
        except ValueError as exc:
            if isinstance(exc,ConflictError):raise
            raise HTTPException(422,str(exc))

    @app.get('/api/roomlab/critique-jobs/{id}',response_model=CritiqueJobRecord)
    def get_critique_job(id:str):
        if id not in critic.jobs:raise HTTPException(404,'Visual review job not found.')
        return critic.jobs[id]

    @app.delete('/api/roomlab/critique-jobs/{id}',response_model=CritiqueJobRecord)
    async def cancel_critique_job(id:str):
        if id not in critic.jobs:raise HTTPException(404,'Visual review job not found.')
        return critic.cancel(id)

    @app.post('/api/roomlab/scenes/{id}/repair-overlaps')
    async def propose_overlap_repair(id:str,request:RepairRequest):
        scene=get_scene(id)
        if scene.scene_revision!=request.expected_revision:raise ConflictError('Scene revision changed. Reload before proposing repair.')
        return await asyncio.to_thread(repair_overlaps,scene,request)

    app.include_router(fidelity)
    from .fidelity_pipeline import atomic_json

    @app.get('/api/roomlab/scenes/{id}/accuracy')
    def accuracy_report(id:str):
        try:return report_for_scene(get_scene(id),runtime)
        except ValueError:raise HTTPException(422,'A saved measurement references an element removed from this room.')

    @app.post('/api/roomlab/scenes/{id}/accuracy')
    def check_accuracy(id:str,request:AccuracyRequest):
        with store.lock:
            scene=get_scene(id)
            if scene.scene_revision!=request.expected_revision:raise ConflictError('Scene changed. Reload before checking measurements.')
            try:result=evaluate(scene,request.references)
            except ValueError as exc:raise HTTPException(422,str(exc))
            atomic_json(runtime/'accuracy-checks'/(scene.scene_id+'.json'),dict(scene_revision=scene.scene_revision,geometry_hash=result['geometry_hash'],references=[r.model_dump() for r in request.references]))
            return report_for_scene(scene,runtime)

    app.mount('/media',StaticFiles(directory=media_root),name='media')
    dist=ROOT/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='roomlab-ui')
    return app

app=create_app()
