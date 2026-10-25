"""Structure-from-motion camera path and a frozen floor-plan alignment.

`run_sfm` is the only function that touches pycolmap. Everything else is pure
numpy: floor-plane RANSAC, 2D Umeyama, eye height, hashing and projection.

Conventions:
- `SfmFrame.R` is camera-to-world (columns are the COLMAP camera axes x right,
  y down, z forward, expressed in SfM world coordinates). `center` is the
  camera centre in SfM world coordinates. `K` is the 3x3 intrinsics matrix.
- `Alignment` maps SfM world points into graph floor coordinates (metres):
  project onto the floor plane with a basis derived only from `floor_normal`,
  then graph_xy = scale * R(yaw_rad) * plane_xy + (tx, ty). If the graph is a
  mirror image of the SfM frame, the second basis axis is flipped first; that
  flag is private (`_reflected`) and is part of `hash`.
- Fit it once on the iteration-0 graph and freeze it. Re-fitting each round
  would let the geometry score improve without a real fix.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

from walktwin.contracts import VenueGraph
from walktwin.media import PreparedVideo, prepare_video, sample_frames

log = logging.getLogger(__name__)

# Declared parameters (model assumptions, not measurements).
EYE_HEIGHT_M = 1.5
EYE_HEIGHT_TOL_M = 0.1
RESIDUAL_MAX_M = 0.5
KEYFRAME_MATCH_S = 0.5

# SfM settings: SIFT runs on CPU here, so keep images and features modest.
SEQUENTIAL_OVERLAP = 10
MAX_IMAGE_SIZE = 1024
MAX_NUM_FEATURES = 4096
MIN_REGISTERED = 3
SFM_RANDOM_SEED = 0  # fixed seed; multithreading still makes reruns differ slightly

# Floor RANSAC.
_RANSAC_MAX_ITERS = 40000
_RANSAC_CHUNK = 500          # candidates per batch; bounds the (points x candidates) matrix
_RANSAC_MAX_POINTS = 10000
_RANSAC_SEED = 0
_RANSAC_THRESH_FRAC = 0.01   # inlier band, fraction of the point-cloud diagonal
_CAM_SAME_SIDE_FRAC = 0.9    # cameras on the normal's side of the plane
_CAM_HEIGHT_MAX_CV = 0.25    # std/median of camera heights above the plane
_FINAL_BAND_FRAC_OF_EYE = 0.03  # final LS band, fraction of camera height
_DOWN_MAX_COS = -0.5         # camera "down" (image +y) must point at the floor


@dataclass(frozen=True)
class SfmFrame:
    t_s: float
    center: tuple[float, float, float]
    R: list[list[float]]
    K: list[list[float]]


@dataclass(frozen=True)
class SfmResult:
    status: Literal["completed", "failed"]
    frames: list[SfmFrame]
    points: list[tuple[float, float, float]]
    registered_fraction: float
    elapsed_ms: int
    error: str | None


@dataclass(frozen=True)
class Alignment:
    scale: float
    yaw_rad: float
    tx: float
    ty: float
    floor_normal: tuple[float, float, float]
    floor_offset: float
    residual_m: float
    eye_height_m: float
    hash: str
    _reflected: bool = field(default=False, repr=False)


# --------------------------------------------------------------------------- math


def _plane_basis(normal: Sequence[float], reflected: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Orthonormal in-plane axes (u, v) derived deterministically from the normal.

    (u, v, n) is right-handed; `reflected` flips v.
    """
    n = np.asarray(normal, float)
    n = n / np.linalg.norm(n)
    # reference axis e_x unless n is nearly parallel to it; continuous near any
    # other normal, so tiny floor-fit noise cannot swap the axes
    a = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = a - a.dot(n) * n
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    return u, (-v if reflected else v)


def _project_plane(points: np.ndarray, normal: Sequence[float], reflected: bool = False) -> np.ndarray:
    u, v = _plane_basis(normal, reflected)
    p = np.atleast_2d(np.asarray(points, float))
    return np.c_[p @ u, p @ v]


def _fit_plane_lsq(points: np.ndarray) -> tuple[np.ndarray, float]:
    c = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - c, full_matrices=False)
    n = vt[-1]
    return n, float(-n.dot(c))


def _floor_candidates(pts: np.ndarray, rng: np.random.Generator, k: int,
                      centers: np.ndarray, down: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """k random 3-point planes, oriented toward the cameras, kept only if the
    cameras sit on one side at a consistent height and image-down faces them."""
    idx = rng.integers(0, len(pts), size=(k, 3))
    a, b, c = pts[idx[:, 0]], pts[idx[:, 1]], pts[idx[:, 2]]
    normals = np.cross(b - a, c - a)
    norms = np.linalg.norm(normals, axis=1)
    ok = norms > 1e-12
    normals, a = normals[ok] / norms[ok, None], a[ok]
    offsets = -np.einsum("ij,ij->i", normals, a)
    cam_h = centers @ normals.T + offsets
    sign = np.where(np.median(cam_h, axis=0) < 0, -1.0, 1.0)
    normals, offsets, cam_h = normals * sign[:, None], offsets * sign, cam_h * sign
    med = np.median(cam_h, axis=0)
    same_side = (cam_h > 0).mean(axis=0)
    cv = cam_h.std(axis=0) / np.maximum(med, 1e-12)
    facing = normals @ down
    valid = ((med > 0) & (same_side >= _CAM_SAME_SIDE_FRAC) & (cv <= _CAM_HEIGHT_MAX_CV)
             & (facing <= _DOWN_MAX_COS))
    if not valid.any():
        return None
    return normals[valid], offsets[valid]


def _fit_floor_plane(points: np.ndarray, centers: np.ndarray, downs: np.ndarray) -> tuple[np.ndarray, float]:
    """RANSAC the floor: the plane that the cameras sit above at a consistent
    height, whose normal opposes the cameras' image-down direction, with the most
    inliers. Returns (unit normal oriented toward the cameras, offset d) with
    n.p + d = height above the floor in SfM units."""
    if len(points) < 3 or len(centers) < 2:
        raise ValueError("no_floor_plane")
    rng = np.random.default_rng(_RANSAC_SEED)
    pts = points
    if len(pts) > _RANSAC_MAX_POINTS:
        pts = pts[rng.choice(len(pts), _RANSAC_MAX_POINTS, replace=False)]
    lo, hi = np.percentile(pts, 5, axis=0), np.percentile(pts, 95, axis=0)
    thresh = _RANSAC_THRESH_FRAC * float(np.linalg.norm(hi - lo))
    if thresh <= 0:
        raise ValueError("no_floor_plane")
    down = downs.mean(axis=0)
    down /= max(np.linalg.norm(down), 1e-12)

    best_count, n, d = 0, None, 0.0
    done, needed = 0, _RANSAC_MAX_ITERS
    while done < min(needed, _RANSAC_MAX_ITERS):
        cand = _floor_candidates(pts, rng, _RANSAC_CHUNK, centers, down)
        done += _RANSAC_CHUNK
        if cand is None:
            continue
        normals, offsets = cand
        counts = (np.abs(pts @ normals.T + offsets) < thresh).sum(axis=0)
        i = int(np.argmax(counts))
        if counts[i] > best_count:
            best_count, n, d = int(counts[i]), normals[i], float(offsets[i])
            w = best_count / len(pts)  # adaptive stop: 99.9% chance of one clean sample
            needed = int(math.ceil(math.log(1e-3) / math.log(max(1 - w ** 3, 1e-12))))
    if n is None:
        raise ValueError("no_floor_plane")

    # refine by least squares on inliers, tightening the band; the last band is
    # a few percent of eye height so wall feet near the floor barely bias it
    cam_band = _FINAL_BAND_FRAC_OF_EYE * float(np.median(centers @ n + d))
    for band in (thresh, thresh / 2, min(thresh / 2, cam_band)):
        inl = pts[np.abs(pts @ n + d) < band]
        if len(inl) < 3:
            break
        n2, d2 = _fit_plane_lsq(inl)
        if n2.dot(n) < 0:
            n2, d2 = -n2, -d2
        n, d = n2, d2
    if np.median(centers @ n + d) < 0:
        n, d = -n, -d
    return n, float(d)


def _umeyama_2d(src: np.ndarray, dst: np.ndarray) -> tuple[float, float, np.ndarray]:
    """Similarity dst ~ s * R(yaw) * src + t (proper rotation). Returns (s, yaw, t)."""
    mu_s, mu_d = src.mean(axis=0), dst.mean(axis=0)
    xs, xd = src - mu_s, dst - mu_d
    var_s = float((xs ** 2).sum(axis=1).mean())
    if var_s <= 1e-12:
        raise ValueError("degenerate_path")
    cov = xd.T @ xs / len(src)
    U, D, Vt = np.linalg.svd(cov)
    S = np.diag([1.0, 1.0 if np.linalg.det(U) * np.linalg.det(Vt) >= 0 else -1.0])
    R = U @ S @ Vt
    s = float(np.trace(np.diag(D) @ S) / var_s)
    t = mu_d - s * R @ mu_s
    return s, math.atan2(R[1, 0], R[0, 0]), t


def _apply_2d(s: float, yaw: float, t: np.ndarray, xy: np.ndarray) -> np.ndarray:
    c, si = math.cos(yaw), math.sin(yaw)
    R = np.array([[c, -si], [si, c]])
    return s * xy @ R.T + t


def _alignment_hash(params: dict) -> str:
    def r(x):
        if isinstance(x, bool):
            return x
        if isinstance(x, (list, tuple)):
            return [r(v) for v in x]
        return round(float(x), 4) + 0.0  # + 0.0 folds -0.0 into 0.0
    data = {k: r(v) for k, v in params.items()}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _match_keyframes(sfm: SfmResult, graph: VenueGraph) -> list[tuple[int, tuple[float, float]]]:
    """(frame index, keyframe xy) for the nearest SfM frame within KEYFRAME_MATCH_S."""
    if not sfm.frames:
        return []
    ts = np.array([f.t_s for f in sfm.frames])
    pairs = []
    for kf in graph.keyframes:
        i = int(np.argmin(np.abs(ts - kf.t_s)))
        if abs(ts[i] - kf.t_s) <= KEYFRAME_MATCH_S:
            pairs.append((i, (kf.x, kf.y)))
    return pairs


def fit_alignment(sfm: SfmResult, graph: VenueGraph) -> Alignment:
    """Fit the SfM -> graph-floor alignment. Raises ValueError("too_few_matches")
    with fewer than 2 keyframe/frame pairs, ValueError("no_floor_plane") when no
    floor is found."""
    pairs = _match_keyframes(sfm, graph)
    if len(pairs) < 2:
        raise ValueError("too_few_matches")
    centers = np.array([f.center for f in sfm.frames], float)
    downs = np.array([np.asarray(f.R, float)[:, 1] for f in sfm.frames])
    n, d = _fit_floor_plane(np.asarray(sfm.points, float).reshape(-1, 3), centers, downs)

    dst = np.array([xy for _, xy in pairs], float)
    sel = centers[[i for i, _ in pairs]]
    src = _project_plane(sel, n)
    reflected = False
    if len(pairs) >= 3:
        cov = (dst - dst.mean(0)).T @ (src - src.mean(0))
        if np.linalg.det(cov) < -1e-12 * max(float(np.abs(cov).max()) ** 2, 1e-300):
            reflected = True
            src = _project_plane(sel, n, reflected=True)
    s, yaw, t = _umeyama_2d(src, dst)
    residual = float(np.sqrt(((_apply_2d(s, yaw, t, src) - dst) ** 2).sum(axis=1).mean()))
    eye = float(np.mean(centers @ n + d) * s)

    params = {
        "scale": s, "yaw_rad": yaw, "tx": float(t[0]), "ty": float(t[1]),
        "floor_normal": tuple(float(v) for v in n), "floor_offset": d,
        "residual_m": residual, "eye_height_m": eye,
    }
    return Alignment(**params, hash=_alignment_hash({**params, "reflected": reflected}),
                     _reflected=reflected)


def to_graph_xy(alignment: Alignment, p_xyz: Sequence[float]) -> tuple[float, float]:
    """Project an SfM world point onto the floor and map it into graph (x, y) metres."""
    q = _project_plane(np.asarray(p_xyz, float), alignment.floor_normal, alignment._reflected)
    xy = _apply_2d(alignment.scale, alignment.yaw_rad, np.array([alignment.tx, alignment.ty]), q)[0]
    return float(xy[0]), float(xy[1])


def height_above_floor_m(alignment: Alignment, p_xyz: Sequence[float]) -> float:
    n = np.asarray(alignment.floor_normal, float)
    return float((np.asarray(p_xyz, float) @ n + alignment.floor_offset) * alignment.scale)


def scale_badge(alignment: Alignment) -> Literal["agrees", "disagrees"]:
    """Cross-check of the anchor's scale. The tape-measured anchor stays the authority."""
    ok = (abs(alignment.eye_height_m - EYE_HEIGHT_M) <= EYE_HEIGHT_TOL_M
          and alignment.residual_m <= RESIDUAL_MAX_M)
    return "agrees" if ok else "disagrees"


# ------------------------------------------------------------------------ pycolmap


def _failed(t0: float, error: str) -> SfmResult:
    return SfmResult("failed", [], [], 0.0, int((time.monotonic() - t0) * 1000), error)


def _map(pycolmap, db: Path, images: Path, out: Path) -> dict:
    """GLOMAP global mapping, falling back to incremental mapping."""
    try:
        opts = pycolmap.GlobalPipelineOptions()
        opts.random_seed = SFM_RANDOM_SEED
        try:
            opts.mapper.global_positioning.use_gpu = False
            opts.mapper.bundle_adjustment.ceres.use_gpu = False
        except AttributeError:
            pass
        models = pycolmap.global_mapping(db, images, out / "global", opts)
        if models:
            log.info("sfm: global (GLOMAP) mapping produced %d model(s)", len(models))
            return models
        log.info("sfm: global mapping produced no model; trying incremental")
    except Exception as e:  # noqa: BLE001
        log.info("sfm: global mapping failed (%s); trying incremental", e)
    inc = pycolmap.IncrementalPipelineOptions()
    inc.random_seed = SFM_RANDOM_SEED
    models = pycolmap.incremental_mapping(db, images, out / "incremental", inc)
    log.info("sfm: incremental mapping produced %d model(s)", len(models or {}))
    return models or {}


def run_sfm(video: PreparedVideo, work_dir: Path, fps: float = 2.0) -> SfmResult:
    """Recover the camera path with pycolmap. Never raises; failures return
    status="failed" with an error string."""
    t0 = time.monotonic()
    try:
        import pycolmap

        work_dir = Path(work_dir)
        frames_dir = work_dir / "frames"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        sampled = sample_frames(video.path, fps, frames_dir)
        if len(sampled) < MIN_REGISTERED:
            return _failed(t0, f"too_few_frames: {len(sampled)}")
        t_by_name = {p.name: t for t, p in sampled}

        db = work_dir / "database.db"
        if db.exists():
            db.unlink()
        for sub in ("global", "incremental"):
            shutil.rmtree(work_dir / sub, ignore_errors=True)

        ex = pycolmap.FeatureExtractionOptions()
        ex.max_image_size = MAX_IMAGE_SIZE
        ex.sift.max_num_features = MAX_NUM_FEATURES
        pycolmap.extract_features(db, frames_dir, camera_mode=pycolmap.CameraMode.SINGLE,
                                  extraction_options=ex, device=pycolmap.Device.cpu)
        pycolmap.match_sequential(
            db, pairing_options=pycolmap.SequentialPairingOptions(overlap=SEQUENTIAL_OVERLAP),
            device=pycolmap.Device.cpu)

        models = _map(pycolmap, db, frames_dir, work_dir)
        if not models:
            return _failed(t0, "no_reconstruction: no model could be built "
                               "(too little texture or overlap)")
        rec = max(models.values(), key=lambda r: r.num_reg_images())
        if rec.num_reg_images() < MIN_REGISTERED:
            return _failed(t0, f"no_reconstruction: largest model has {rec.num_reg_images()} images")

        frames = []
        for img in rec.images.values():
            if not img.has_pose or img.name not in t_by_name:
                continue
            R_c2w = np.asarray(img.cam_from_world().rotation.matrix()).T
            frames.append(SfmFrame(
                t_s=float(t_by_name[img.name]),
                center=tuple(float(v) for v in np.asarray(img.projection_center()).ravel()),
                R=R_c2w.tolist(),
                K=np.asarray(img.camera.calibration_matrix()).tolist(),
            ))
        frames.sort(key=lambda f: f.t_s)
        points = [tuple(float(v) for v in p.xyz) for p in rec.points3D.values()]
        return SfmResult("completed", frames, points, len(frames) / len(sampled),
                         int((time.monotonic() - t0) * 1000), None)
    except Exception as e:  # noqa: BLE001 - run_sfm never raises
        return _failed(t0, f"{type(e).__name__}: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m walktwin.sfm",
                                 description="Run SfM on a video; print registered_fraction and elapsed_ms.")
    ap.add_argument("video", type=Path)
    ap.add_argument("--fps", type=float, default=2.0, help="frame sampling rate (default 2)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with tempfile.TemporaryDirectory(prefix="walktwin-sfm-") as tmp:
        try:
            prepared = prepare_video(args.video, Path(tmp) / "prep")
        except Exception as e:  # noqa: BLE001
            print("status=failed\nregistered_fraction=0.000\nelapsed_ms=0")
            print(f"error=prepare_video: {type(e).__name__}: {e}")
            return 1
        res = run_sfm(prepared, Path(tmp) / "sfm", fps=args.fps)
    print(f"status={res.status}")
    print(f"registered_fraction={res.registered_fraction:.3f}")
    print(f"elapsed_ms={res.elapsed_ms}")
    print(f"frames={len(res.frames)} points={len(res.points)}")
    if res.error:
        print(f"error={res.error}")
    return 0 if res.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())


def from_graph_xyz(alignment: Alignment, x: float, y: float, height_m: float) -> tuple[float, float, float]:
    """SfM world point at graph (x, y) metres and `height_m` above the floor.

    Exact inverse of `to_graph_xy` and `height_above_floor_m` (reflection included).
    """
    u, v = _plane_basis(alignment.floor_normal, alignment._reflected)
    n = np.asarray(alignment.floor_normal, float)
    norm = float(np.linalg.norm(n))
    c, si = math.cos(alignment.yaw_rad), math.sin(alignment.yaw_rad)
    dx, dy = (x - alignment.tx) / alignment.scale, (y - alignment.ty) / alignment.scale
    q0, q1 = c * dx + si * dy, -si * dx + c * dy  # R(yaw)^T applied
    h = (height_m / alignment.scale - alignment.floor_offset) / norm
    p = q0 * u + q1 * v + h * (n / norm)
    return float(p[0]), float(p[1]), float(p[2])
