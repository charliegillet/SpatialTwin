"""Quality-aware temporal sampling. Scores are diagnostics, never accuracy probabilities."""
from __future__ import annotations
import subprocess
from pathlib import Path
import imageio_ffmpeg
from .contracts import EvidenceFrame, InspectionRequest, MediaRecord
from .media import _extract_frame_jpeg
from .video_extractor import _safe_media_child

def prepare_evidence(media: MediaRecord, media_root: Path) -> tuple[MediaRecord, dict]:
    from .fidelity_media import dense_candidates
    from .frame_quality import select_quality_frames
    candidates=dense_candidates(media,media_root)
    selection=select_quality_frames(candidates,media_root,max_frames=96)
    frames=selection.selected_frames
    if len(frames)<3:raise ValueError('Too few usable views. Capture sharper overlapping footage.')
    report=dict(candidate_count=len(candidates.frames),selected_count=len(frames),candidate_fps=2,
        blur_or_low_texture_count=selection.low_sharpness_count,poor_exposure_count=selection.exposure_flagged_count,
        duplicate_skipped_count=selection.duplicate_skipped_count,coverage_ratio=selection.coverage_ratio,
        selected=[m.model_dump() for m in selection.metrics if m.selected],warnings=selection.notes,
        method='temporal coverage + sharpness/exposure + perceptual duplicate rejection',
        limitation='Heuristic image quality, not recovered camera motion or dimensional accuracy.')
    return media.model_copy(update={'frames':frames}),report


def detail_evidence(
    media: MediaRecord,
    media_root: Path,
    draft,
    plan: list[InspectionRequest] | None = None,
) -> tuple[list[EvidenceFrame], list[dict]]:
    """Revisit evidence around model-requested and validation-flagged elements at 4fps, with a strict budget."""
    catalog = {f.frame_id: f for f in media.frames}
    targets: list[dict] = []
    seen_el: set[str] = set()
    known_ids = {
        *(w.id for w in draft.walls),
        *(o.id for o in draft.openings),
        *(o.id for o in draft.objects),
        *(v.id for v in draft.floor_voids),
    }

    # 1. Consume up to 6 validated model-directed InspectionRequests first
    for req in (plan or [])[:6]:
        eid = (req.element_id or "").strip()
        if not eid or eid not in known_ids:
            continue
        ts = float(req.timestamp_s)
        if not (0.0 <= ts <= float(media.duration_s) + 1e-6):
            continue
        ts_clamped = round(min(float(media.duration_s), max(0.0, ts)), 3)
        if any(t["element_id"] == eid and abs(t["timestamp_s"] - ts_clamped) < 0.05 for t in targets):
            continue
        seen_el.add(eid)
        targets.append(
            dict(
                element_id=eid,
                timestamp_s=ts_clamped,
                source="model_plan",
                reason=(req.reason or "").strip()[:240],
            )
        )
        if len(targets) >= 6:
            break

    # 2. Include any elements currently flagged by deterministic validation (e.g. object_wall_overlap, object_overlap, object_outside)
    try:
        from .contracts import RoomSceneV1
        from .validation import validate_scene
        val = validate_scene(RoomSceneV1(**draft.model_dump(), scene_id="detail-check", evidence_frames=media.frames))
        flagged_ids = {
            eid
            for issue in val.issues
            if issue.code in (
                "object_wall_overlap",
                "object_outside",
                "object_overlap",
                "overlapping_openings",
                "opening_outside_wall",
                "opening_above_wall",
                "partition_outside",
                "invalid_void",
            )
            for eid in issue.element_ids
        }
    except Exception:
        flagged_ids = set()

    elements = [*draft.walls, *draft.openings, *draft.objects, *draft.floor_voids]
    def priority(element):
        eid = getattr(element, "id", "")
        if eid in flagged_ids:
            return -1
        category = str(getattr(element, "category", "")).lower()
        if "stair" in category:
            return 0
        if getattr(element, "kind", "") in ("door", "window"):
            return 1
        appearance = getattr(element, "appearance", None)
        if appearance and appearance.material == "glass":
            return 2
        return 3 if getattr(element, "uncertainty_radius_m", 0) > 0.2 else 4

    for element in sorted(elements, key=priority):
        if len(targets) >= 8:
            break
        eid = getattr(element, "id", "")
        if eid in seen_el:
            continue
        tag = (getattr(element, "category", "") + " " + getattr(element, "label", "")).lower()
        appearance = getattr(element, "appearance", None)
        critical = (
            eid in flagged_ids
            or "stair" in tag
            or getattr(element, "kind", "") == "door"
            or (appearance is not None and appearance.material == "glass")
            or getattr(element, "uncertainty_radius_m", 0) > 0.2
            or element.provenance.visibility != "observed"
        )
        if critical:
            cited = [catalog[i] for i in element.provenance.evidence_frame_ids if i in catalog]
            if cited:
                seen_el.add(eid)
                targets.append(
                    dict(
                        element_id=eid,
                        timestamp_s=cited[len(cited) // 2].timestamp_s,
                        source="validation" if eid in flagged_ids else "heuristic",
                    )
                )
    targets = targets[:8]
    source=_safe_media_child(media_root,media.video_url.removeprefix('/media/'))
    known={round(f.timestamp_s,2) for f in media.frames};frames=[];seen=set()
    for target in targets:
        for offset in (-.75,-.5,-.25,.25,.5,.75):
            t=round(max(0,min(media.duration_s-.08,target['timestamp_s']+offset)),3)
            if t in seen or round(t,2) in known or len(frames)>=min(48,200-len(media.frames)):continue
            seen.add(t);ms=round(t*1000);name=f'detail-{ms:06d}.jpg';path=media_root/media.media_id/name
            if _extract_frame_jpeg(imageio_ffmpeg.get_ffmpeg_exe(),source,t,path):
                # Detail crops retain more source pixels than the regular 960px evidence.
                subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-v','error','-ss',str(t),'-i',str(source),
                    '-frames:v','1','-vf',"scale='min(1600,iw)':-2",'-q:v','2','-y',str(path)],
                    capture_output=True,timeout=20,check=True)
                frames.append(EvidenceFrame(frame_id=f'{media.media_id}-detail-{ms:06d}',media_id=media.media_id,
                    timestamp_s=t,url=f'/media/{media.media_id}/{name}',relative_path=f'{media.media_id}/{name}'))
    return frames,targets
