"""Isolated CPU COLMAP worker. No model calls and no automatic metric claim."""
from pathlib import Path
import json, shutil, sys
import numpy as np
from .contracts import MediaRecord, GeometryReport, GeometryPoint, GeometryCamera
from .fidelity_media import source_digest


def reconstruct(media: MediaRecord, root: Path, workspace: Path) -> GeometryReport:
    import pycolmap
    workspace.mkdir(parents=True, exist_ok=True)
    images = workspace / 'images'; images.mkdir(exist_ok=True)
    from .video_extractor import _safe_media_child
    for f in media.frames:
        shutil.copyfile(_safe_media_child(root, f.relative_path), images / (f.frame_id + '.jpg'))
    db = workspace / 'database.db'
    extraction = pycolmap.FeatureExtractionOptions()
    extraction.max_image_size = 1200; extraction.num_threads = 4
    extraction.sift.max_num_features = 4096; extraction.use_gpu = False
    matching = pycolmap.FeatureMatchingOptions(); matching.num_threads=4; matching.use_gpu=False
    pycolmap.extract_features(str(db),str(images),camera_mode=pycolmap.CameraMode.SINGLE,
                             extraction_options=extraction,device=pycolmap.Device.cpu)
    pairing=pycolmap.SequentialPairingOptions(); pairing.overlap=8
    pycolmap.match_sequential(str(db),matching_options=matching,pairing_options=pairing,device=pycolmap.Device.cpu)
    # Exhaustive matching of bounded selected views closes loops without downloading a vocabulary tree.
    if len(media.frames)<=96:
        pycolmap.match_exhaustive(str(db),matching_options=matching,device=pycolmap.Device.cpu)
    options=pycolmap.IncrementalPipelineOptions()
    options.num_threads=4; options.random_seed=0; options.min_model_size=3
    options.max_num_models=4; options.max_runtime_seconds=600
    models=pycolmap.incremental_mapping(str(db),str(images),str(workspace/'sparse'),options=options)
    if not models: raise ValueError('Camera alignment failed. Capture sharper overlapping views while walking, rather than only panning.')
    model=max(models.values(),key=lambda m:m.num_reg_images())
    points=[GeometryPoint(id=int(i),xyz=[float(x) for x in p.xyz],rgb=[int(x) for x in p.color],error_px=float(p.error))
            for i,p in sorted(model.points3D.items()) if 0<=p.error<=4 and len(p.track.elements)>=3 and np.isfinite(p.xyz).all()][:12000]
    if len(points)<30 or model.num_reg_images()<3:
        raise ValueError('Too little stable 3D evidence. Add overlapping views of textured stationary surfaces.')
    cameras=[GeometryCamera(frame_id=Path(image.name).stem,
              center=[float(x) for x in image.cam_from_world().inverse().translation])
             for image in model.images.values() if image.has_pose]
    model.export_PLY(str(workspace/'points.ply'))
    return GeometryReport(media_id=media.media_id,source_sha256=source_digest(media,root),
        engine=f'COLMAP {pycolmap.__version__} / CPU SIFT',registered_frames=model.num_reg_images(),
        selected_frames=len(media.frames),component_count=len(models),
        mean_reprojection_error_px=float(model.compute_mean_reprojection_error()),points=points,cameras=cameras,
        warnings=['Sparse reconstruction is scale-free; reprojection error is not room-dimension accuracy.',
                  'Glass, reflections, textureless walls and moving people can leave gaps or false points.',
                  'Only the largest connected component is shown; disconnected components are not merged.'])

if __name__=='__main__':
    workspace=Path(sys.argv[1]); config=json.loads((workspace/'input.json').read_text())
    try:
        report=reconstruct(MediaRecord.model_validate(config['media']),Path(config['media_root']),workspace)
        (workspace/'result.json').write_text(report.model_dump_json())
    except Exception as exc:
        # Detailed local logs are separate from API errors; never a synthetic fallback.
        print(type(exc).__name__,str(exc),file=sys.stderr)
        (workspace/'failure.json').write_text(json.dumps({'error':str(exc) if isinstance(exc,ValueError) else 'COLMAP reconstruction failed. Check local geometry logs and capture coverage.'}))
        sys.exit(1)
