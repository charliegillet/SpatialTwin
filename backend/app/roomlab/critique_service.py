"""Revision-bound, read-only visual review jobs. Source file paths are constrained to media_root."""
from __future__ import annotations
import asyncio,hashlib,io,uuid
from pathlib import Path
from PIL import Image
from pydantic import ValidationError
from .contracts import (RoomSceneV1,SceneReceipt,CritiqueFrame,CritiqueContext,CritiqueRequest,
                        CritiqueResult,CritiqueJobRecord,geometry_hash,render_hash)
from .store import ConflictError
from .validation import validate_scene
from .reachability import solve


def frame_bytes(root:Path,relative:str)->bytes:
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Source evidence is unavailable. Re-upload the original walkthrough.')
    if path.stat().st_size>3*1024*1024:raise ValueError('Source evidence frame exceeds the review size limit.')
    return path.read_bytes()


def evidence_hash(scene:RoomSceneV1,root:Path)->str:
    h=hashlib.sha256();total=0
    for frame in scene.evidence_frames:
        h.update(frame.model_dump_json().encode())
        try:data=frame_bytes(root,frame.relative_path)
        except ValueError:data=b'[unavailable]'
        total+=len(data)
        if total>32*1024*1024:raise ValueError('Source evidence exceeds the review size budget.')
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def receipt(scene:RoomSceneV1,root:Path)->SceneReceipt:
    return SceneReceipt(scene_id=scene.scene_id,scene_revision=scene.scene_revision,
                        geometry_hash=geometry_hash(scene),evidence_hash=evidence_hash(scene,root),render_hash=render_hash(scene))


def make_context(scene:RoomSceneV1,root:Path,request:CritiqueRequest)->CritiqueContext:
    from .scene_preview import render_scene_preview
    elements=scene.objects+scene.walls+scene.openings+scene.floor_voids
    known={e.id for e in elements}
    if not set(request.focus_element_ids)<=known:raise ValueError('Review focus references an unknown scene element.')
    frames=scene.evidence_frames
    if not frames:raise ValueError('This scene has no source frames. Upload a walkthrough first.')
    focus={fid for e in elements if e.id in request.focus_element_ids for fid in e.provenance.evidence_frame_ids}
    chosen=[f for f in frames if f.frame_id in focus][:3]
    # Include spread views as well as selected-element evidence, never just the first frames.
    for i in [round(j*(len(frames)-1)/5) for j in range(6)]+list(range(len(frames))):
        if len(chosen)>=6:break
        if frames[i].frame_id not in {f.frame_id for f in chosen}:chosen.append(frames[i])
    selected=[]
    for f in sorted(chosen,key=lambda f:f.timestamp_s):
        data=frame_bytes(root,f.relative_path)
        try:
            with Image.open(io.BytesIO(data)) as original:
                if original.width*original.height>20_000_000:raise ValueError('Source frame dimensions exceed the review limit.')
                image=original.convert('RGB');image.thumbnail((1200,1200));out=io.BytesIO();image.save(out,format='JPEG',quality=85)
        except (OSError,Image.DecompressionBombError):raise ValueError('Source evidence image cannot be decoded.')
        selected.append(CritiqueFrame(record=f,jpeg_bytes=out.getvalue()))
    if request.solve_request and request.solve_request.expected_revision!=scene.scene_revision:
        raise ConflictError('Solver request revision does not match the reviewed scene.')
    result=solve(scene,request.solve_request) if request.solve_request else None
    return CritiqueContext(scene=scene,validation=validate_scene(scene),solve=result,
                           geometry_hash=geometry_hash(scene),evidence_hash=evidence_hash(scene,root),render_hash=render_hash(scene),
                           bev_png=render_scene_preview(scene,result),frames=selected)


class CritiqueService:
    def __init__(self,store,media_root:Path):
        self.store=store;self.media_root=media_root;self.jobs={};self.tasks={};self.limit=asyncio.Semaphore(1)
        self.provider=None

    def fresh(self,scene:RoomSceneV1,request:CritiqueRequest):
        r=receipt(scene,self.media_root)
        if (request.expected_revision,request.geometry_hash,request.evidence_hash,request.render_hash)!=(r.scene_revision,r.geometry_hash,r.evidence_hash,r.render_hash):
            raise ConflictError('Scene or evidence changed. Reload before requesting a review.')
        return r

    async def start(self,scene:RoomSceneV1,request:CritiqueRequest,api_key:str):
        r=await asyncio.to_thread(self.fresh,scene,request)
        if sum(j.status in ('queued','running') for j in self.jobs.values())>=3:raise ValueError('Review queue is full. Wait for an active review to finish.')
        # Register before awaiting provider/context work so concurrent callers cannot overfill the queue.
        job=CritiqueJobRecord(**r.model_dump(),job_id='critique-'+uuid.uuid4().hex,status='queued')
        self.jobs[job.job_id]=job
        self.tasks[job.job_id]=asyncio.create_task(self.run(job,scene,request,api_key))
        while len(self.jobs)>100:
            old=next((key for key,j in self.jobs.items() if j.status not in ('queued','running')),None)
            if old is None:break
            self.jobs.pop(old);self.tasks.pop(old,None)
        return job

    async def run(self,job,scene,request,api_key):
        try:
            async with self.limit:
                await asyncio.to_thread(self.fresh,self.store.get(scene.scene_id),request)
                job.status='running'
                async def review():
                    from .agent_critic import critique_scene
                    context=await asyncio.to_thread(make_context,scene,self.media_root,request)
                    result=CritiqueResult.model_validate(await (self.provider or critique_scene)(context,api_key=api_key))
                    expected=(scene.scene_id,scene.scene_revision,context.geometry_hash,context.evidence_hash,context.render_hash)
                    if (result.scene_id,result.scene_revision,result.geometry_hash,result.evidence_hash,result.render_hash)!=expected:
                        raise ValueError('Critic receipt does not match the reviewed scene.')
                    ids=[f.record.frame_id for f in context.frames]
                    if result.reviewed_frame_ids!=ids:raise ValueError('Critic reviewed-frame catalog does not match source evidence.')
                    elements={e.id for e in scene.objects+scene.walls+scene.openings+scene.floor_voids}
                    for finding in result.findings:
                        if not finding.frame_ids or not set(finding.frame_ids)<=set(ids) or not set(finding.element_ids)<=elements:
                            raise ValueError('Critic returned an unknown or missing evidence citation.')
                    return result
                result=await asyncio.wait_for(review(),timeout=180)
                await asyncio.to_thread(self.fresh,self.store.get(scene.scene_id),request)
                job.result=result;job.status='completed'
        except asyncio.CancelledError:job.status='cancelled'
        except asyncio.TimeoutError:job.status='failed';job.error='Visual review timed out. Your room is unchanged.'
        except ValidationError:job.status='failed';job.error='Critic returned invalid structured findings. Your room is unchanged.'
        except ConflictError:job.status='failed';job.error='Scene or evidence changed during review. Request a fresh review.'
        except (ValueError,RuntimeError) as exc:job.status='failed';job.error=str(exc)[:600]
        except Exception:job.status='failed';job.error='Visual review failed. Your room is unchanged.'

    def cancel(self,id):
        job=self.jobs[id]
        if job.status in ('queued','running'):
            job.status='cancelled';self.tasks[id].cancel()
        return job

    async def close(self):
        active=[t for t in self.tasks.values() if not t.done()]
        for task in active:task.cancel()
        if active:await asyncio.gather(*active,return_exceptions=True)
