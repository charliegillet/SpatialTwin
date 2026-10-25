"""Unaligned preview of the walker's SfM path (D4).

Shown as soon as SfM completes, before Argon has produced a graph to align to.
It is a top-down view in SfM units, not metres: the camera centres are projected
onto their top two principal components, centred at the first frame, with the
walking direction as +v. When the frames carry camera rotations, the sign of +u
is chosen so the view is seen from above (not mirrored).
"""
from __future__ import annotations

from typing import Any

import numpy as np

NOTE = "unaligned, SfM units"
_MIN_FRAMES = 3
_MIN_SPREAD = 1e-9


def _get(obj: Any, key: str) -> Any:
    return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)


def sfm_preview(sfm: Any) -> dict | None:
    """``{"points": [{"t_s", "u", "v"}], "note": NOTE}``, or None when SfM failed,
    has fewer than 3 frames, or the camera never moved. ``sfm`` is an
    ``SfmResult`` or its JSON dict."""
    if sfm is None or _get(sfm, "status") != "completed":
        return None
    frames = sorted(_get(sfm, "frames") or [], key=lambda f: float(_get(f, "t_s")))
    if len(frames) < _MIN_FRAMES:
        return None
    c = np.array([_get(f, "center") for f in frames], float).reshape(-1, 3)
    _, sv, vt = np.linalg.svd(c - c.mean(axis=0), full_matrices=False)
    if sv[0] <= _MIN_SPREAD:
        return None
    v_ax, u_ax = vt[0], vt[1]
    rel = c - c[0]
    # +v along the walk: the net displacement, or the first real step if it loops back
    along = rel @ v_ax
    ref = along[-1] if abs(along[-1]) > _MIN_SPREAD else next(
        (a for a in along if abs(a) > _MIN_SPREAD), 1.0)
    if ref < 0:
        v_ax = -v_ax
    up = _up(frames)
    if up is not None:
        if float(np.cross(u_ax, v_ax) @ up) < 0:  # (u, v, up) right-handed: a top view
            u_ax = -u_ax
    elif u_ax[int(np.argmax(np.abs(u_ax)))] < 0:  # deterministic fallback
        u_ax = -u_ax
    u, v = rel @ u_ax, rel @ v_ax
    return {"points": [{"t_s": float(_get(f, "t_s")), "u": float(a), "v": float(b)}
                       for f, a, b in zip(frames, u, v)],
            "note": NOTE}


def _up(frames: list) -> np.ndarray | None:
    """Mean camera "up" (minus COLMAP image +y, the second column of camera-to-world R)."""
    downs = []
    for f in frames:
        r = _get(f, "R")
        if r is None:
            return None
        downs.append(np.asarray(r, float)[:, 1])
    up = -np.mean(downs, axis=0)
    n = float(np.linalg.norm(up))
    return up / n if n > _MIN_SPREAD else None
