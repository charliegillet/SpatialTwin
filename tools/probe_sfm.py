#!/usr/bin/env python
"""Standalone pycolmap probe: python tools/probe_sfm.py CLIP.mp4 [--fps 2] [--keep DIR]

Samples frames at --fps with ffmpeg, runs SIFT extraction, sequential matching and
the global mapper, then prints registered_fraction and elapsed seconds.
Target: registered_fraction >= 0.80 on a real phone walkthrough.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

import pycolmap


def run(clip: Path, fps: float, work: Path) -> dict:
    images = work / "images"
    images.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-vf", f"fps={fps}",
                    "-qscale:v", "2", str(images / "f_%05d.jpg")], check=True)
    sampled = len(list(images.glob("*.jpg")))
    t_frames = time.monotonic()
    db = work / "db.db"
    sparse = work / "sparse"
    sparse.mkdir(exist_ok=True)
    pycolmap.extract_features(db, images)
    pycolmap.match_sequential(db)
    t_match = time.monotonic()
    if hasattr(pycolmap, "global_mapping"):
        recs = pycolmap.global_mapping(db, images, sparse)
    else:  # older builds: incremental mapper
        recs = pycolmap.incremental_mapping(db, images, sparse)
    elapsed = time.monotonic() - t0
    registered = max((r.num_reg_images() for r in recs.values()), default=0)
    return {"clip": str(clip), "fps": fps, "sampled_frames": sampled,
            "registered_images": registered,
            "registered_fraction": round(registered / sampled, 3) if sampled else 0.0,
            "models": len(recs), "elapsed_s": round(elapsed, 1),
            "frames_s": round(t_frames - t0, 1), "features_match_s": round(t_match - t_frames, 1),
            "pycolmap": pycolmap.__version__}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", type=Path)
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--keep", type=Path, help="work dir to keep (default: temp)")
    a = ap.parse_args()
    if a.keep:
        res = run(a.clip, a.fps, a.keep)
    else:
        with tempfile.TemporaryDirectory() as d:
            res = run(a.clip, a.fps, Path(d))
    print(json.dumps(res, indent=2))
    out = Path(__file__).resolve().parents[1] / "runtime" / "probes"
    out.mkdir(parents=True, exist_ok=True)
    (out / "sfm.json").write_text(json.dumps(res, indent=2))
