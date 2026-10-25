"""Denser evidence lives alongside, never replaces original frame files or scenes."""
from pathlib import Path
import json, subprocess, hashlib
import imageio_ffmpeg
from .contracts import MediaRecord, EvidenceFrame


def source_digest(media: MediaRecord, root: Path) -> str:
    from .video_extractor import _safe_media_child
    path = _safe_media_child(root, media.video_url.removeprefix('/media/'))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def dense_candidates(media: MediaRecord, root: Path) -> MediaRecord:
    import fcntl
    lock_path=root/media.media_id/'detail.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        try:return _dense_candidates_locked(media,root)
        finally:fcntl.flock(lock,fcntl.LOCK_UN)


def _dense_candidates_locked(media: MediaRecord, root: Path) -> MediaRecord:
    from .video_extractor import _safe_media_child
    source = _safe_media_child(root, media.video_url.removeprefix('/media/'))
    output = root / media.media_id / 'detail'
    output.mkdir(exist_ok=True)
    fps = min(2.0, 1200 / media.duration_s)
    manifest = output / 'candidates.json'
    signature = source_digest(media, root)
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if saved['sha256'] == signature:
            return MediaRecord.model_validate(saved['media'])
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-loglevel', 'error', '-i', str(source),
               '-vf', f'fps={fps},scale=960:960:force_original_aspect_ratio=decrease',
               '-frames:v', '1200', '-q:v', '3', '-y', str(output / 'detail-%04d.jpg')]
    subprocess.run(command, check=True, capture_output=True, timeout=360)
    frames = [EvidenceFrame(frame_id=f'{media.media_id}-detail-{i:04}', media_id=media.media_id,
               timestamp_s=min(media.duration_s, (i - .5) / fps),
               relative_path=f'{media.media_id}/detail/{p.name}', url=f'/media/{media.media_id}/detail/{p.name}')
              for i,p in enumerate(sorted(output.glob('detail-*.jpg')), 1)]
    if not frames: raise ValueError('No detailed frames could be decoded.')
    result = media.model_copy(update={'frames': frames})
    temporary=manifest.with_suffix('.tmp')
    temporary.write_text(json.dumps({'sha256': signature, 'media': result.model_dump(mode='json')}))
    temporary.replace(manifest)
    return result
