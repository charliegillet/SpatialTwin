"""Synthetic SfM scene: floor, walls and ceiling points plus a walking camera path.

No video and no pycolmap. The scene is built in graph metres (z up, floor at
z = 0, cameras at eye height), then mapped into an "SfM" frame with the inverse
of a known similarity, so a correct `fit_alignment` recovers exactly that
similarity: graph_xy = scale * Rz(yaw) * sfm_xy + (tx, ty).
"""
from __future__ import annotations

import math

import numpy as np

from walktwin.contracts import Keyframe, VenueGraph
from walktwin.sfm import SfmFrame, SfmResult

ROOM_W, ROOM_D, ROOM_H = 12.0, 8.0, 2.7
WAYPOINTS = [(1.5, 1.5), (10.5, 1.5), (10.5, 6.5), (3.0, 6.5), (3.0, 3.5)]
WALK_SPEED = 1.2
FPS = 2.0
KEYFRAME_EVERY_S = 2.0
K = [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]]


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def rot_axis(axis, a: float) -> np.ndarray:
    """Rodrigues rotation about an arbitrary axis."""
    k = np.asarray(axis, float)
    k = k / np.linalg.norm(k)
    kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(a) * kx + (1 - math.cos(a)) * kx @ kx


def _world_points(rng: np.random.Generator, noise_m: float, n_floor: int, n_ceiling: int,
                  n_wall: int) -> np.ndarray:
    floor = np.c_[rng.uniform(0, ROOM_W, n_floor), rng.uniform(0, ROOM_D, n_floor), np.zeros(n_floor)]
    ceiling = np.c_[rng.uniform(0, ROOM_W, n_ceiling), rng.uniform(0, ROOM_D, n_ceiling),
                    np.full(n_ceiling, ROOM_H)]
    n = n_wall
    z = lambda: rng.uniform(0, ROOM_H, n)  # noqa: E731
    walls = []
    walls.append(np.c_[rng.uniform(0, ROOM_W, n), np.zeros(n), z()])        # south
    walls.append(np.c_[rng.uniform(0, ROOM_W, n), np.full(n, ROOM_D), z()])  # north
    walls.append(np.c_[np.zeros(n), rng.uniform(0, ROOM_D, n), z()])        # west
    walls.append(np.c_[np.full(n, ROOM_W), rng.uniform(0, ROOM_D, n), z()])  # east
    pts = np.vstack([floor, ceiling, *walls])
    return pts + rng.normal(0, noise_m, pts.shape)


def _camera_path(eye_m: float, waypoints) -> list[tuple[float, np.ndarray, float]]:
    """(t_s, centre_xyz, heading_rad) sampled at FPS along the waypoints.
    heading_rad is the math angle from +x (counter-clockwise)."""
    out = []
    t = 0.0
    seg_start_t = 0.0
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        dur = length / WALK_SPEED
        heading = math.atan2(y1 - y0, x1 - x0)
        while t < seg_start_t + dur:
            f = (t - seg_start_t) / dur
            out.append((t, np.array([x0 + f * (x1 - x0), y0 + f * (y1 - y0), eye_m]), heading))
            t = round(t + 1.0 / FPS, 6)
        seg_start_t += dur
    return out


def _cam_to_world(heading: float) -> np.ndarray:
    """COLMAP camera axes (x right, y down, z forward) as world columns."""
    fwd = np.array([math.cos(heading), math.sin(heading), 0.0])
    down = np.array([0.0, 0.0, -1.0])
    right = np.cross(down, fwd)
    return np.c_[right, down, fwd]


def make_scene(
    scale: float = 0.37,
    yaw_deg: float = 30.0,
    shift: tuple[float, float] = (2.0, -1.0),
    z0: float = 0.8,
    eye_m: float = 1.5,
    tilt: np.ndarray | None = None,
    mirror: bool = False,
    graph_scale: float = 1.0,
    noise_m: float = 0.01,
    n_floor: int = 1500,
    n_ceiling: int = 300,
    n_wall: int = 400,
    waypoints=None,
    seed: int = 0,
) -> tuple[SfmResult, VenueGraph]:
    """Return (sfm, graph). `tilt` is an extra 3D rotation applied to the SfM frame,
    `mirror` negates graph y, `graph_scale` scales graph keyframes (a wrong anchor).
    Keyframe `heading_deg` is clockwise from +y: atan2(dx, dy) in degrees mod 360."""
    rng = np.random.default_rng(seed)
    yaw = math.radians(yaw_deg)
    Q = np.eye(3) if tilt is None else np.asarray(tilt, float)
    R_inv = Q @ rot_z(-yaw)
    t3 = np.array([shift[0], shift[1], 0.0])

    def to_sfm(p: np.ndarray) -> np.ndarray:
        local = (rot_z(-yaw) @ (p - t3).T).T / scale + np.array([0.0, 0.0, z0])
        return (Q @ local.T).T

    points = to_sfm(_world_points(rng, noise_m, n_floor, n_ceiling, n_wall))
    frames, keyframes = [], []
    for t_s, c, heading in _camera_path(eye_m, WAYPOINTS if waypoints is None else waypoints):
        frames.append(SfmFrame(
            t_s=t_s,
            center=tuple(float(v) for v in to_sfm(c[None])[0]),
            R=(R_inv @ _cam_to_world(heading)).tolist(),
            K=K,
        ))
        if abs(t_s / KEYFRAME_EVERY_S - round(t_s / KEYFRAME_EVERY_S)) < 1e-6:
            gx, gy = c[0] * graph_scale, c[1] * graph_scale
            dx, dy = math.cos(heading), math.sin(heading)
            if mirror:
                gy, dy = -gy, -dy
            hd = math.degrees(math.atan2(dx, dy)) % 360  # clockwise from +y
            keyframes.append(Keyframe(t_s=t_s, zone_id="Z1", x=gx, y=gy, heading_deg=hd))
    sfm = SfmResult(
        status="completed",
        frames=frames,
        points=[tuple(float(v) for v in p) for p in points],
        registered_fraction=1.0,
        elapsed_ms=0,
        error=None,
    )
    graph = VenueGraph(
        schema_version="1", video_sha256="synthetic", anchor=None,
        zones=[], doors=[], keyframes=keyframes,
    )
    return sfm, graph
