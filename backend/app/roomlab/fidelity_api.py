"""Read-only capture diagnostics, isolated reconstruction jobs and explicit imports."""
from pathlib import Path
import asyncio, hashlib, json, os, re, sys, uuid
from fastapi import APIRouter, HTTPException, Request
from .contracts import MediaRecord, GeometryJob, GeometryReport, GeometryFloorRequest, CalibrateRequest,GeometryObjectRequest,geometry_hash
from .fidelity_media import dense_candidates, source_digest
from .geometry_floor import fit_floor,fit_object
from .roomplan_import import import_roomplan


def fidelity_router(runtime: Path, store):
    router=APIRouter(prefix='/api/roomlab');root=runtime/'media';jobs_root=runtime/'geometry-jobs';jobs_root.mkdir(exist_ok=True)
    tasks={};lock=asyncio.Semaphore(1);quality_lock=asyncio.Lock()
    def media(id):
        if not re.fullmatch(r'media-[a-zA-Z0-9-]+',id):raise HTTPException(404,'Media not found.')
        try:return MediaRecord.model_validate_json((root/id/'record.json').read_text())
        except (ValueError,OSError):raise HTTPException(404,'Media not found.')
    def directory(id):
        if not re.fullmatch(r'geometry-[a-f0-9]{32}',id):raise HTTPException(404,'Geometry job not found.')
        return jobs_root/id
    def read(id):
        try:return GeometryJob.model_validate_json((directory(id)/'job.json').read_text())
        except (ValueError,OSError):raise HTTPException(404,'Geometry job not found.')
    def save(job):
        path=directory(job.job_id)/'job.json';tmp=path.with_suffix('.tmp');tmp.write_text(job.model_dump_json());os.replace(tmp,path)
    async def quality_record(id):
        from .frame_quality import select_quality_frames
        original=media(id)
        async with quality_lock:
            selected=await asyncio.to_thread(dense_candidates,original,root)
            report=await asyncio.to_thread(select_quality_frames,selected,root,max_frames=96)
            # Leaf module returns a serializable report; canonical catalog is original frame metadata.
            report=report.model_dump(mode='json') if hasattr(report,'model_dump') else report
            ids=set(report['selected_frame_ids'])
            chosen=[f for f in selected.frames if f.frame_id in ids]
            if len(chosen)<3:raise HTTPException(422,'Too few usable views. Record sharper overlapping footage.')
            evidence=selected.model_copy(update={'frames':chosen})
            artifact={'sha256':source_digest(original,root),'report':report,'media':evidence.model_dump(mode='json')}
            (root/id/'quality.json').write_text(json.dumps(artifact))
            return artifact
    @router.post('/media/{id}/quality')
    async def quality(id:str):
        try:return (await quality_record(id))['report']
        except (ValueError,RuntimeError) as exc:raise HTTPException(422,str(exc))
    @router.get('/media/{id}/quality')
    def saved_quality(id:str):
        media(id)
        try:return json.loads((root/id/'quality.json').read_text())['report']
        except OSError:raise HTTPException(404,'No capture-quality analysis yet.')
    async def run(job):
        process=None
        try:
            async with lock:
                job.status='running';save(job)
                artifact=await quality_record(job.media_id)
                workspace=directory(job.job_id)
                (workspace/'input.json').write_text(json.dumps({'media':artifact['media'],'media_root':str(root.resolve())}))
                with (workspace/'worker.log').open('wb') as log:
                    process=await asyncio.create_subprocess_exec(sys.executable,'-m','backend.app.roomlab.geometry_worker',str(workspace.resolve()),stdout=log,stderr=log)
                    await asyncio.wait_for(process.wait(),timeout=900)
                if process.returncode!=0:
                    try:message=json.loads((workspace/'failure.json').read_text())['error']
                    except (ValueError,OSError):message='Geometry worker failed; uploaded evidence remains available.'
                    raise ValueError(message)
                job.report=GeometryReport.model_validate_json((workspace/'result.json').read_text());job.status='completed'
        except asyncio.CancelledError:
            job.status='cancelled';job.error='Geometry reconstruction cancelled; evidence is preserved.'
            raise
        except Exception as exc:
            job.status='failed';job.error=str(exc)[:500] if isinstance(exc,(ValueError,HTTPException)) else 'Geometry reconstruction failed or timed out. Retry with clearer overlapping footage.'
        finally:
            if process and process.returncode is None:
                process.kill();await process.wait()
            save(job)
    @router.post('/media/{id}/geometry',response_model=GeometryJob,status_code=202)
    async def start(id:str):
        media(id)
        try:import pycolmap  # noqa: F401
        except ImportError:raise HTTPException(503,'Install pycolmap==4.2.1 on the server to enable COLMAP.')
        active=[read(i) for i in tasks if not tasks[i].done()]
        existing=next((j for j in active if j.media_id==id),None)
        if existing:return existing
        if len(active)>=2:raise HTTPException(429,'Geometry queue is full.')
        job=GeometryJob(job_id='geometry-'+uuid.uuid4().hex,media_id=id,status='queued')
        directory(job.job_id).mkdir();save(job);tasks[job.job_id]=asyncio.create_task(run(job));return job
    @router.get('/media/{id}/geometry',response_model=GeometryJob)
    def latest_geometry(id:str):
        original=media(id)
        # Surface real automatic SfM outputs through the same inspector/fitting workflow.
        for candidate_path in sorted((root/id).glob('fidelity-*/result.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                suffix=candidate_path.parent.name.removeprefix('fidelity-')
                if not re.fullmatch(r'[a-f0-9]{32}',suffix):continue
                indexed='geometry-'+suffix
                if (directory(indexed)/'job.json').exists():continue
                report=GeometryReport.model_validate_json(candidate_path.read_text())
                if report.media_id!=id or report.source_sha256!=source_digest(original,root):continue
                input_data=json.loads((candidate_path.parent/'input.json').read_text())
                observed=MediaRecord.model_validate(input_data['media'])
                if observed.media_id!=id or not {c.frame_id for c in report.cameras}<={f.frame_id for f in observed.frames}:continue
                directory(indexed).mkdir(exist_ok=True)
                (directory(indexed)/'input.json').write_text(json.dumps(input_data))
                save(GeometryJob(job_id=indexed,media_id=id,status='completed',report=report))
            except (ValueError,KeyError,OSError):continue
        paths=sorted(jobs_root.glob('geometry-*/job.json'),key=lambda p:p.stat().st_mtime,reverse=True)
        for path in paths:
            try:
                candidate=GeometryJob.model_validate_json(path.read_text())
                if candidate.media_id==id:return job(candidate.job_id)
            except (ValueError,OSError):continue
        raise HTTPException(404,'No geometry reconstruction yet.')
    @router.get('/geometry-jobs/{id}',response_model=GeometryJob)
    def job(id:str):
        result=read(id)
        if result.status in ('queued','running') and id not in tasks:
            result.status='failed';result.error='Server restarted; retry geometry reconstruction.';save(result)
        return result
    @router.delete('/geometry-jobs/{id}',response_model=GeometryJob)
    async def cancel(id:str):
        result=read(id)
        if id in tasks and not tasks[id].done():
            tasks[id].cancel()
            try:await tasks[id]
            except asyncio.CancelledError:pass
        result=read(id)
        if result.status in ('queued','running'):
            result.status='cancelled';result.error='Geometry reconstruction cancelled.';save(result)
        return result
    @router.post('/geometry-jobs/{id}/floor')
    def floor(id:str,body:GeometryFloorRequest):
        result=job(id)
        if result.status!='completed' or result.report is None:raise HTTPException(409,'Geometry is not ready.')
        original=media(result.media_id)
        if source_digest(original,root)!=result.report.source_sha256:raise HTTPException(409,'Source video changed. Reconstruct it again.')
        try:
            draft=fit_floor(result.report,body)
            evidence=MediaRecord.model_validate(json.loads((directory(id)/'input.json').read_text())['media'])
            scene=store.create(draft,evidence.frames,source='geometry_fit')
            scene=store.calibrate(scene.scene_id,CalibrateRequest(expected_revision=1,anchor_id='wall-1',dimension='wall_length',measured_m=body.first_edge_measured_m))
            references=runtime/'geometry-fits';references.mkdir(exist_ok=True)
            (references/(scene.scene_id+'.json')).write_text(json.dumps({'job_id':id,'floor_request':body.model_dump(),'geometry_hash':geometry_hash(scene)}))
            return scene
        except ValueError as exc:raise HTTPException(422,str(exc))
    @router.post('/geometry-jobs/{id}/object')
    def object_fit(id:str,body:GeometryObjectRequest):
        result=job(id)
        if result.status!='completed' or not result.report:raise HTTPException(409,'Geometry is not ready.')
        try:
            with store.lock:
                scene=store.get(body.scene_id)
                if scene.scene_revision!=body.expected_revision:raise HTTPException(409,'Room changed. Reload first.')
                saved_path=runtime/'geometry-fits'/(scene.scene_id+'.json')
                if not saved_path.exists():raise ValueError('First create a floor from this reconstruction and a measured edge.')
                saved=json.loads(saved_path.read_text())
                if saved['job_id']!=id or saved['geometry_hash']!=geometry_hash(scene):raise ValueError('Geometry reference changed. Recreate the floor proposal before fitting objects.')
                if source_digest(media(result.media_id),root)!=result.report.source_sha256:raise ValueError('Source video changed; reconstruct it again.')
                item=fit_object(result.report,GeometryFloorRequest.model_validate(saved['floor_request']),scene,body)
                proposal=scene.model_copy(deep=True);proposal.objects.append(item)
                from .validation import validate_scene
                issues=validate_scene(proposal).issues
                if any(i.severity=='error' and i.code!='topology_review_required' for i in issues):raise ValueError('Fitted object does not form a valid room proposal. Review walls and selected landmarks.')
                proposal=store.import_scene(proposal)
                saved['geometry_hash']=geometry_hash(proposal)
                (runtime/'geometry-fits'/(proposal.scene_id+'.json')).write_text(json.dumps(saved))
                return proposal
        except (KeyError,ValueError) as exc:raise HTTPException(422,str(exc))
    @router.post('/imports/roomplan')
    async def roomplan(request:Request):
        data=await request.body()
        if len(data)>4*1024*1024:raise HTTPException(413,'RoomPlan JSON must be at most 4 MiB.')
        try:
            draft=import_roomplan(json.loads(data));return store.create(draft,source='geometry_fit')
        except (ValueError,KeyError,TypeError,IndexError):raise HTTPException(422,'Unsupported or invalid single-room CapturedRoom JSON. Check closed walls, rigid column-major transforms, dimensions and one floor level.')
    async def close():
        for task in tasks.values():
            if not task.done():task.cancel()
        if tasks:await asyncio.gather(*tasks.values(),return_exceptions=True)
    return router,close
