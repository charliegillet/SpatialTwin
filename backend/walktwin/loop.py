"""Render -> watch -> critique -> patch loop, graded by measured geometry.

Each round renders the current twin at the graph's keyframes, pairs each render
with the real video frame at the same time, and asks Argon (chained onto the
extraction, then onto its own previous critique) for discrepancies and patch
ops. ``apply_patch`` applies them deterministically; ``check_graph`` re-checks.
When an SfM path and its frozen alignment are available, the patched graph is
scored on held-out SfM frames (more than 1 s from any keyframe); a measured
regression reverts the whole round's patch and stops the loop.

Nothing here changes an accepted graph: the result is a proposal for a human to
accept with ``expected_revision``.

Labels: ``discrepancy_count`` is model-reported; ``geometry`` is measured.

CLI (live: pending key)::

    python -m walktwin.loop runtime/probe_clip.mp4 --base-url http://127.0.0.1:4173 [--sfm]
"""
from __future__ import annotations

import asyncio
import importlib
import math
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import critique as critique_mod
from .contracts import VenueGraph
from .critique import CritiqueResult, critique
from .extract import ExtractionResult
from .genai_client import Receipt
from .graph_checks import Finding, check_graph
from .media import PreparedVideo, extract_frame
from .patch import apply_patch
from .render import RenderedView, render_views
from .sfm import Alignment, SfmResult

# ``walktwin.geometry_score`` (another lane) is imported lazily on first use;
# tests replace this placeholder with a fake module.
geometry_score: Any = None

LABELS = {"discrepancy_count": "model-reported", "geometry": "measured"}
STOP_REASONS = ("no_discrepancies", "no_ops_applied", "repeated_revision",
                "measured_regression", "max_iterations", "provider_failed")
HELDOUT_MIN_GAP_S = 1.0
ZOOM_PAD_S = 2.0
MAX_ZOOM = 4

_DOOR_ID = re.compile(r"^D\d{1,3}$")


@dataclass(frozen=True)
class Iteration:
    index: int
    graph_revision: str            # graph after this round (unchanged if nothing was kept)
    discrepancy_count: int         # model-reported
    applied: list[int]
    rejected: list[tuple[int, str]]
    findings: list[Finding]        # check_graph of graph_revision
    geometry: Any | None           # measured GeometryScore of graph_revision; None without SfM
    renders: list[RenderedView]
    receipt: Receipt | None
    stop_reason: str | None
    # measured score of a candidate reverted for measured_regression
    rejected_geometry: Any | None = None
    critique: CritiqueResult | None = field(default=None, repr=False)


def _geometry_module():
    global geometry_score
    if geometry_score is None:
        geometry_score = importlib.import_module("walktwin.geometry_score")
    return geometry_score


def heldout_times(sfm: SfmResult, keyframe_t_s: list[float]) -> list[float]:
    """SfM frame times more than 1 s from every keyframe."""
    return [f.t_s for f in sfm.frames
            if all(abs(f.t_s - k) > HELDOUT_MIN_GAP_S for k in keyframe_t_s)]


def _pick(views: list[RenderedView], n: int) -> list[RenderedView]:
    if len(views) <= n:
        return views
    step = (len(views) - 1) / (n - 1)
    return [views[round(i * step)] for i in range(n)]


def _zoom_targets(graph: VenueGraph, result: CritiqueResult,
                  duration_s: float) -> list[tuple[str, float, float]]:
    """Doors named in this round's discrepancies, +-2 s around their evidence."""
    doors = {d.id: d for d in graph.doors}
    out: list[tuple[str, float, float]] = []
    seen: set[str] = set()
    for disc in result.discrepancies:
        ident = disc.element_id
        if not ident or not _DOOR_ID.match(ident) or ident in seen or ident not in doors:
            continue
        seen.add(ident)
        for ev in doors[ident].evidence:
            start = max(ev.start_s - ZOOM_PAD_S, 0.0)
            end = min(ev.end_s + ZOOM_PAD_S, duration_s)
            if end > start:
                out.append((ident, start, end))
    return out[:MAX_ZOOM]


async def refine_graph(client, graph: VenueGraph, video: PreparedVideo,
                       extraction: ExtractionResult, *, sfm: SfmResult | None,
                       alignment: Alignment | None, base_url: str, max_iterations: int = 4,
                       deadline_s: float, zoom_enabled: bool = False,
                       work_dir: Path | None = None) -> tuple[VenueGraph, list[Iteration]]:
    """Run the loop; returns (graph after the last kept patch, iterations)."""
    if extraction.receipt is None or not extraction.receipt.interaction_id:
        raise ValueError("refine needs the extraction's interaction_id to chain onto")
    if not extraction.video_uri:
        raise ValueError("refine needs the extraction's uploaded video_uri")
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    started = time.monotonic()
    work = Path(work_dir) if work_dir is not None else Path(tempfile.mkdtemp(prefix="walktwin-refine-"))
    duration = video.duration_s

    use_geometry = (sfm is not None and alignment is not None and sfm.status == "completed")
    gs = _geometry_module() if use_geometry else None
    heldout = heldout_times(sfm, [k.t_s for k in graph.keyframes]) if use_geometry else []

    def score(g: VenueGraph):
        return gs.score_geometry(g, sfm, alignment, video=video, heldout_t_s=heldout)

    current = graph
    current_findings = check_graph(current, duration)
    current_geom = score(current) if use_geometry else None
    seen = {current.revision}
    previous_id = extraction.receipt.interaction_id
    zoom: list[tuple[str, float, float]] = []
    iterations: list[Iteration] = []

    for index in range(max_iterations):
        rdir = work / f"iter_{index:02d}"
        renders = await render_views(current, rdir / "render", base_url)
        persp = _pick([v for v in renders if v.kind == "perspective" and v.t_s is not None],
                      critique_mod.MAX_PAIRS)
        top = next(v for v in renders if v.kind == "top")
        pairs = [(await asyncio.to_thread(extract_frame, video.path, v.t_s,
                                          rdir / f"frame_{i:02d}.jpg"), v.path, v.t_s)
                 for i, v in enumerate(persp)]

        remaining = max(deadline_s - (time.monotonic() - started), 0.001)
        res = await critique(client, current, pairs, previous_interaction_id=previous_id,
                             video_uri=extraction.video_uri, topdown=top.path,
                             zoom=zoom if zoom_enabled else [], deadline_s=remaining,
                             zoom_enabled=zoom_enabled)

        def record(*, applied=(), rejected=(), stop=None, rejected_geometry=None,
                   discrepancies=len(res.discrepancies)):
            iterations.append(Iteration(
                index=index, graph_revision=current.revision, discrepancy_count=discrepancies,
                applied=list(applied), rejected=list(rejected), findings=current_findings,
                geometry=current_geom, renders=renders, receipt=res.receipt, stop_reason=stop,
                rejected_geometry=rejected_geometry, critique=res))

        if res.status != "completed":
            record(stop="provider_failed", discrepancies=0)
            break
        previous_id = res.interaction_id or previous_id
        if not res.discrepancies:
            record(stop="no_discrepancies")
            break

        outcome = apply_patch(current, res.ops, duration)
        if not outcome.applied:
            record(rejected=outcome.rejected, stop="no_ops_applied")
            break

        candidate = outcome.graph
        cand_geom = score(candidate) if use_geometry else None
        if use_geometry and gs.is_regression(current_geom, cand_geom):
            rejected = sorted([*outcome.rejected,
                               *((i, "measured_regression") for i in outcome.applied)])
            record(rejected=rejected, stop="measured_regression", rejected_geometry=cand_geom)
            break

        current, current_geom = candidate, cand_geom
        current_findings = check_graph(current, duration)
        if current.revision in seen:
            record(applied=outcome.applied, rejected=outcome.rejected, stop="repeated_revision")
            break
        seen.add(current.revision)
        zoom = _zoom_targets(current, res, duration)
        last = index == max_iterations - 1
        record(applied=outcome.applied, rejected=outcome.rejected,
               stop="max_iterations" if last else None)

    return current, iterations


async def refine(client, graph: VenueGraph, video: PreparedVideo, extraction: ExtractionResult,
                 *, sfm: SfmResult | None, alignment: Alignment | None, base_url: str,
                 max_iterations: int = 4, deadline_s: float, zoom_enabled: bool = False,
                 work_dir: Path | None = None) -> list[Iteration]:
    _, iterations = await refine_graph(
        client, graph, video, extraction, sfm=sfm, alignment=alignment, base_url=base_url,
        max_iterations=max_iterations, deadline_s=deadline_s, zoom_enabled=zoom_enabled,
        work_dir=work_dir)
    return iterations


# --- CLI (live: pending key) ------------------------------------------------------


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _jsonable(getattr(obj, k)) for k in obj.__dataclass_fields__
                if not k.startswith("_")}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


async def _main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    from .extract import extract_venue
    from .genai_client import make_client
    from .media import prepare_video
    from .sfm import fit_alignment, run_sfm

    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(prog="python -m walktwin.loop",
                                 description="Extract, then run the critique loop (live).")
    ap.add_argument("video", type=Path)
    ap.add_argument("--base-url", required=True,
                    help="origin serving the built frontend/dist (render.html)")
    ap.add_argument("--mode", choices=["static", "static_hifps", "agentic"],
                    default="static_hifps")
    ap.add_argument("--deadline", type=float, default=1800.0)
    ap.add_argument("--max-iterations", type=int, default=4)
    ap.add_argument("--sfm", action="store_true", help="grade rounds with measured geometry")
    ap.add_argument("--zoom", action="store_true", help="send clipped zoom parts (probe-gated)")
    ap.add_argument("--out", type=Path, default=root / "runtime" / "receipts")
    a = ap.parse_args(argv)

    client = make_client()  # fail fast without a key
    stamp = time.strftime("%Y%m%dT%H%M%S")
    work = root / "runtime" / "refine" / f"{a.video.stem}-{stamp}"
    prepared = prepare_video(a.video, work / "prepared")
    ext = await extract_venue(client, prepared, mode=a.mode, deadline_s=a.deadline)
    print(f"extract status={ext.status} error={ext.error}")
    if ext.graph is None:
        return 1
    sfm = alignment = None
    if a.sfm:
        sfm = run_sfm(prepared, work / "sfm")
        print(f"sfm status={sfm.status} registered={sfm.registered_fraction:.2f} error={sfm.error}")
        if sfm.status == "completed":
            try:
                alignment = fit_alignment(sfm, ext.graph)  # frozen on the iteration-0 graph
            except ValueError as e:
                print(f"alignment failed: {e}")
                sfm = None
        else:
            sfm = None
    graph, its = await refine_graph(client, ext.graph, prepared, ext, sfm=sfm,
                                    alignment=alignment, base_url=a.base_url,
                                    max_iterations=a.max_iterations, deadline_s=a.deadline,
                                    zoom_enabled=a.zoom, work_dir=work)
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / f"refine-{stamp}.json"
    payload = {"labels": LABELS, "extraction": ext.model_dump(mode="json"),
               "alignment_hash": alignment.hash if alignment else None,
               "initial_revision": ext.graph.revision, "final_revision": graph.revision,
               "final_graph": graph.model_dump(mode="json"),
               "iterations": [_jsonable(it) for it in its]}
    path.write_text(json.dumps(payload, indent=2))
    for it in its:
        print(f"round {it.index}: rev={it.graph_revision} discrepancies(model-reported)="
              f"{it.discrepancy_count} applied={it.applied} rejected={len(it.rejected)} "
              f"geometry={'measured' if it.geometry is not None else 'unavailable'} "
              f"stop={it.stop_reason}")
    print(f"receipts -> {path}")
    return 0 if its and its[-1].stop_reason != "provider_failed" else 1


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(_main()))
