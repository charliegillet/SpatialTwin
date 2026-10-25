"""Discover local walkthroughs/rooms; persist extraction attempts across restarts.

One uploaded media record is one submission. Re-extractions/imported copies sharing
its evidence appear as saved outputs within it, not as duplicate upload cards.
Legacy creation times use existing record modification times (no invented events).
"""
from __future__ import annotations
import json, re, os, uuid
from pathlib import Path
from .contracts import JobRecord,MediaRecord,RoomSceneV1,SavedRoomSummary,RoomSubmission,RoomLibrary

class ExtractionJournal:
    def __init__(self,root:Path):self.root=root;root.mkdir(parents=True,exist_ok=True)
    def save(self,job:JobRecord):
        if not re.fullmatch(r'job-[A-Za-z0-9-]+',job.job_id):raise ValueError('Invalid job identity.')
        path=self.root/(job.job_id+'.json');tmp=path.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        tmp.write_text(job.model_dump_json());os.replace(tmp,path)
    def load(self):
        jobs={}
        for path in self.root.glob('*.json'):
            try:
                job=JobRecord.model_validate_json(path.read_text())
                if path.stem!=job.job_id:continue
                jobs[job.job_id]=job
            except (ValueError,OSError):continue
        return jobs


def list_rooms(runtime:Path,jobs:dict[str,JobRecord])->RoomLibrary:
    media_root=runtime/'media';scenes_root=runtime/'scenes';journal=runtime/'extraction-jobs'
    media={};rooms={};grouped={};times={}
    for path in media_root.glob('*/record.json'):
        try:
            record=MediaRecord.model_validate_json(path.read_text())
            if path.parent.name!=record.media_id:continue
            media[record.media_id]=record;times[record.media_id]=path.stat().st_mtime
        except (ValueError,OSError):continue
    for path in scenes_root.glob('scene-*.json'):
        try:
            scene=RoomSceneV1.model_validate_json(path.read_text())
            if scene.scene_id!=path.stem:continue
            timestamp=path.stat().st_mtime
            summary=SavedRoomSummary(scene_id=scene.scene_id,name=scene.name,scene_revision=scene.scene_revision,updated_at=timestamp)
            rooms[scene.scene_id]=(scene,summary)
            mid=scene.evidence_frames[0].media_id if scene.evidence_frames else None
            key=mid if mid in media else scene.scene_id
            grouped.setdefault(key,[]).append(summary)
        except (ValueError,OSError):continue
    latest={}
    for job in jobs.values():
        path=journal/(job.job_id+'.json')
        try:stamp=path.stat().st_mtime
        except OSError:continue
        old=latest.get(job.media_id)
        if old is None or stamp>old[0]:latest[job.media_id]=(stamp,job)
    items=[]
    for key in set(media)|set(grouped):
        record=media.get(key);versions=sorted(grouped.get(key,[]),key=lambda s:(s.updated_at,s.scene_id),reverse=True)
        last=versions[0] if versions else None
        stamp,job=latest.get(key,(0,None))
        if job and job.status in ('queued','running'):status='processing'
        elif job and job.status in ('failed','cancelled'):status='needs_attention'
        elif last:status='ready'
        else:status='uploaded'
        submitted=times.get(key,last.updated_at if last else stamp)
        updated=max(submitted,stamp,last.updated_at if last else 0)
        frames=record.frames if record else rooms[last.scene_id][0].evidence_frames if last else []
        thumbnail=None
        if frames:
            try:
                frame=frames[len(frames)//2];path=(media_root/frame.relative_path).resolve()
                if path.is_relative_to(media_root.resolve()) and path.is_file():thumbnail='/media/'+path.relative_to(media_root.resolve()).as_posix()
            except (ValueError,OSError):pass
        items.append(RoomSubmission(submission_id=key,media_id=record.media_id if record else None,scene_id=last.scene_id if last else None,
            title=last.name if last else Path(record.filename).stem if record else 'Untitled room',filename=record.filename if record else None,
            thumbnail_url=thumbnail,submitted_at=submitted,updated_at=updated,status=status,
            job_id=job.job_id if job else None,error=job.error if job and status=='needs_attention' else None,
            duration_s=record.duration_s if record else None,scenes=versions))
    items.sort(key=lambda item:(item.updated_at,item.submission_id),reverse=True)
    return RoomLibrary(items=items,total_count=len(items))
