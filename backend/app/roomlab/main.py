"""Standalone RoomLab app: no imported SpatialTwin runtime or hardware."""
from __future__ import annotations
import asyncio,os,json,uuid,logging,ipaddress
from pathlib import Path
from fastapi import FastAPI,UploadFile,File,HTTPException,Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .contracts import RoomSceneV1,RoomDraft,MediaRecord,JobRecord,ExtractRequest,EditSceneRequest,CalibrateRequest,SolveRequest
from .store import SceneStore,ConflictError
from .validation import validate_scene
from .reachability import solve
from .optimizer import optimize

ROOT=Path(__file__).resolve().parents[3]
MAX_BYTES=40*1024*1024
log=logging.getLogger('roomlab')

def create_app(runtime:Path|None=None)->FastAPI:
    runtime=runtime or ROOT/'runtime/roomlab';runtime.mkdir(parents=True,exist_ok=True)
    media_root=runtime/'media';media_root.mkdir(exist_ok=True)
    store=SceneStore(runtime/'scenes');jobs={};tasks={};limit=asyncio.Semaphore(1)
    app=FastAPI(title='RoomLab',version='1.0.0')
    app.state.store=store;app.state.runtime=runtime;app.state.jobs=jobs
    # Test injection replaces only a provider function; default is always a real model call.
    app.state.extractor=None;app.state.media_processor=None

    @app.middleware('http')
    async def local_only(request:Request,call_next):
        from fastapi.responses import JSONResponse
        if request.client:
            try:allowed=ipaddress.ip_address(request.client.host).is_loopback
            except ValueError:allowed=request.client.host=='testclient'
            if not allowed:return JSONResponse({'detail':'RoomLab is a local-only application.'},status_code=403)
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and origin not in ('http://127.0.0.1:8001','http://localhost:8001','http://127.0.0.1:5174','http://localhost:5174'):
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
        'max_video_seconds':15,'max_upload_bytes':MAX_BYTES,
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
        if len(data)>MAX_BYTES:raise HTTPException(413,'Video must be at most 40 MiB.')
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

    async def extract_job(job:JobRecord,media:MediaRecord):
        try:
            async with limit:
                job.status='running'
                from .video_extractor import propose_room
                extractor=app.state.extractor or propose_room
                result=await asyncio.wait_for(extractor(media,media_root,api_key=os.environ.get('GEMINI_API_KEY')),timeout=180)
                scene=store.create(result.draft,media.frames)
                job.scene_id=scene.scene_id;job.model=result.model;job.latency_ms=result.latency_ms;job.warnings=result.warnings
                report=validate_scene(scene)
                job.warnings += [x.message for x in report.issues]
                job.status='completed'
        except asyncio.CancelledError:job.status='cancelled'
        except asyncio.TimeoutError:job.status='failed';job.error='Extraction timed out. Your uploaded video is preserved; try a shorter clip.'
        except Exception as exc:
            job.status='failed'
            # Provider modules supply user-safe RuntimeError/ValueError messages. Never emit key-bearing raw SDK errors.
            job.error=str(exc)[:600] if isinstance(exc,(RuntimeError,ValueError)) else 'Room extraction failed. Try a clearer translated walkthrough.'
            log.warning('Extraction job failed: %s',type(exc).__name__)

    @app.post('/api/roomlab/extractions',response_model=JobRecord,status_code=202)
    async def extract(request:ExtractRequest):
        if not app.state.extractor and not os.environ.get('GEMINI_API_KEY'):raise HTTPException(503,'Gemini is not configured. Set GEMINI_API_KEY on the backend; no scene will be substituted.')
        if not request.media_id.startswith('media-') or '/' in request.media_id or '..' in request.media_id:raise HTTPException(404,'Media not found.')
        try:media=MediaRecord.model_validate_json((media_root/request.media_id/'record.json').read_text())
        except (ValueError,FileNotFoundError):raise HTTPException(404,'Media not found.')
        if sum(j.status in ('queued','running') for j in jobs.values())>=3:raise HTTPException(429,'Extraction queue is full. Wait or cancel a pending job.')
        job=JobRecord(job_id='job-'+uuid.uuid4().hex,status='queued',media_id=request.media_id);jobs[job.job_id]=job
        tasks[job.job_id]=asyncio.create_task(extract_job(job,media));return job

    @app.get('/api/roomlab/jobs/{id}',response_model=JobRecord)
    def job(id:str):
        if id not in jobs:raise HTTPException(404,'Job not found.')
        return jobs[id]

    @app.delete('/api/roomlab/jobs/{id}',response_model=JobRecord)
    async def cancel(id:str):
        value=job(id)
        if value.status in ('running','queued'):
            tasks[id].cancel();value.status='cancelled'
        return value

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

    app.mount('/media',StaticFiles(directory=media_root),name='media')
    dist=ROOT/'frontend/dist'
    if dist.exists():app.mount('/',StaticFiles(directory=dist,html=True),name='roomlab-ui')
    return app

app=create_app()
